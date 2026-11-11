"""/api/v1 auth, account and saved-journey routes."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.api.deps import Principal, get_db, require_csrf, require_principal
from app.api.v1.routes import get_search
from app.api.v1.schemas import JourneyOut, Page
from app.core.errors import NotFound, ValidationFailed
from app.db import models as m
from app.db.repositories import (
    ActivityRepository,
    SavedJourneyRepository,
    SessionRepository,
    UserRepository,
)
from app.db.session import transaction
from app.services.auth import AuthService, Conflict, IssuedSession
from app.services.search import SearchService

router = APIRouter(prefix="/api/v1")


# --- schemas -------------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str = Field(max_length=254, examples=["traveller@example.com"])
    password: str = Field(max_length=128, json_schema_extra={"format": "password"})
    display_name: str | None = Field(default=None, max_length=80)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256, json_schema_extra={"format": "password"})


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    created_at: datetime

    @classmethod
    def of(cls, u: m.User) -> UserOut:
        return cls(id=u.id, email=u.email, display_name=u.display_name, created_at=u.created_at)


class RecentSearchOut(BaseModel):
    origin_id: str
    destination_id: str
    travel_date: date
    modes: list[str]
    created_at: datetime


class MeResponse(BaseModel):
    user: UserOut
    saved_count: int
    recent_searches: list[RecentSearchOut]
    session_expires_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    session_expires_at: datetime


class SaveRequest(BaseModel):
    journey_id: str = Field(min_length=3, max_length=128)
    note: str | None = Field(default=None, max_length=280)


class SavedJourneyOut(BaseModel):
    id: uuid.UUID
    journey_id: str
    origin_id: str
    destination_id: str
    travel_date: date | None
    note: str | None
    snapshot: dict[str, Any] = Field(description="Journey as seen when saved. Not live data.")
    snapshot_taken_at: datetime
    created_at: datetime

    @classmethod
    def of(cls, r: m.SavedJourney) -> SavedJourneyOut:
        return cls(
            id=r.id,
            journey_id=r.journey_id,
            origin_id=r.origin_location_id,
            destination_id=r.destination_location_id,
            travel_date=r.travel_date,
            note=r.note,
            snapshot=r.snapshot,
            snapshot_taken_at=r.snapshot_taken_at,
            created_at=r.created_at,
        )


# --- cookies -------------------------------------------------------------------------------
def _set_session_cookies(request: Request, response: Response, issued: IssuedSession) -> None:
    s = request.app.state.settings
    max_age = int((issued.expires_at - request.app.state.clock.now()).total_seconds())
    common = dict(max_age=max_age, path="/", secure=s.secure_cookies, samesite="lax")
    response.set_cookie(s.session_cookie_name, issued.token, httponly=True, **common)
    # Readable by the page's JS so it can echo it in X-CSRF-Token (double submit).
    response.set_cookie(s.csrf_cookie_name, issued.csrf_token, httponly=False, **common)


def _clear_session_cookies(request: Request, response: Response) -> None:
    s = request.app.state.settings
    for name in (s.session_cookie_name, s.csrf_cookie_name):
        response.delete_cookie(name, path="/", secure=s.secure_cookies, samesite="lax")


# --- auth ------------------------------------------------------------------------------------
@router.post("/auth/register", response_model=AuthResponse, status_code=201, tags=["auth"])
def register(
    body: RegisterRequest, request: Request, response: Response, db: Annotated[DbSession, Depends(get_db)]
) -> AuthResponse:
    auth: AuthService = request.app.state.auth
    now = request.app.state.clock.now()
    user = auth.register(db, body.email, body.password, body.display_name)
    issued = auth.issue_session(db, user, now)
    db.commit()
    _set_session_cookies(request, response, issued)
    return AuthResponse(user=UserOut.of(user), session_expires_at=issued.expires_at)


@router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
def login(
    body: LoginRequest, request: Request, response: Response, db: Annotated[DbSession, Depends(get_db)]
) -> AuthResponse:
    auth: AuthService = request.app.state.auth
    now = request.app.state.clock.now()
    user = auth.authenticate(db, body.email.strip().lower(), body.password, now)
    # Rotate: any session cookie presented before login is not reused.
    old = request.cookies.get(request.app.state.settings.session_cookie_name)
    if old and (prev := auth.resolve(db, old, now)):
        SessionRepository(db).revoke(prev.id, now)
    issued = auth.issue_session(db, user, now)
    db.commit()
    _set_session_cookies(request, response, issued)
    return AuthResponse(user=UserOut.of(user), session_expires_at=issued.expires_at)


@router.post("/auth/logout", status_code=204, tags=["auth"])
def logout(
    request: Request,
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> Response:
    SessionRepository(db).revoke(principal.session.id, request.app.state.clock.now())
    db.commit()
    response = Response(status_code=204)
    _clear_session_cookies(request, response)
    return response


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=256, json_schema_extra={"format": "password"})


@router.delete("/me", status_code=204, tags=["account"])
def delete_account(
    body: DeleteAccountRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> Response:
    """Permanently delete the account, its sessions and saved journeys (password re-check required)."""
    auth: AuthService = request.app.state.auth
    user = auth.authenticate(db, principal.user.email, body.password, request.app.state.clock.now())
    UserRepository(db).delete(user)
    db.commit()
    response = Response(status_code=204)
    _clear_session_cookies(request, response)
    return response


@router.get("/me", response_model=MeResponse, tags=["account"])
def me(
    principal: Annotated[Principal, Depends(require_principal)], db: Annotated[DbSession, Depends(get_db)]
) -> MeResponse:
    recent = ActivityRepository(db).recent_searches(principal.user.id)
    return MeResponse(
        user=UserOut.of(principal.user),
        saved_count=SavedJourneyRepository(db).count_for_user(principal.user.id),
        recent_searches=[
            RecentSearchOut(
                origin_id=r.origin_location_id,
                destination_id=r.destination_location_id,
                travel_date=r.travel_date,
                modes=r.modes or [],
                created_at=r.created_at,
            )
            for r in recent
        ],
        session_expires_at=principal.session.expires_at,
    )


# --- saved journeys --------------------------------------------------------------------------
@router.get("/saved", response_model=Page[SavedJourneyOut], tags=["saved"])
def list_saved(
    principal: Annotated[Principal, Depends(require_principal)],
    db: Annotated[DbSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SavedJourneyOut]:
    rows, total = SavedJourneyRepository(db).list_for_user(principal.user.id, limit, offset)
    return Page(items=[SavedJourneyOut.of(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/saved", response_model=SavedJourneyOut, status_code=201, tags=["saved"])
async def save_journey(
    body: SaveRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_csrf)],
    search: Annotated[SearchService, Depends(get_search)],
) -> SavedJourneyOut:
    # Only journeys that currently resolve to real configured data can be saved.
    journey, origin, destination = await search.get_journey(body.journey_id)
    snapshot = JourneyOut.of(journey, origin.timezone).model_dump(mode="json")
    snapshot["origin_name"], snapshot["destination_name"] = origin.name, destination.name
    first = journey.legs[0].departure
    travel_date = (
        first.departure_utc.astimezone(ZoneInfo(origin.timezone)).date() if first.departure_utc else None
    )
    settings = request.app.state.settings
    user_id = principal.user.id
    note = body.note.strip() if body.note and body.note.strip() else None

    def write() -> m.SavedJourney:
        with transaction(request.app.state.session_factory) as db:
            repo = SavedJourneyRepository(db)
            if repo.find(user_id, journey.id):
                raise Conflict("You have already saved this journey.")
            if repo.count_for_user(user_id) >= settings.max_saved_journeys_per_user:
                raise ValidationFailed("Saved journey limit reached. Remove some first.")
            return repo.create(
                user_id=user_id,
                journey_id=journey.id,
                origin_location_id=origin.id,
                destination_location_id=destination.id,
                travel_date=travel_date,
                note=note,
                snapshot=snapshot,
                snapshot_taken_at=request.app.state.clock.now(),
                created_at=request.app.state.clock.now(),
            )

    try:
        row = await run_in_threadpool(write)
    except IntegrityError:
        raise Conflict("You have already saved this journey.") from None
    return SavedJourneyOut.of(row)


@router.delete("/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["saved"])
def delete_saved(
    saved_id: Annotated[uuid.UUID, Path()],
    principal: Annotated[Principal, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> Response:
    repo = SavedJourneyRepository(db)
    row = repo.get_for_user(principal.user.id, saved_id)
    if row is None:  # also returned for other users' items: no existence leak
        raise NotFound("Saved journey not found.")
    repo.delete(row)
    db.commit()
    return Response(status_code=204)
