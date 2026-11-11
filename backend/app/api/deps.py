"""Shared FastAPI dependencies: DB session, current user, CSRF enforcement."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.db import models as m
from app.services.auth import AuthService, Unauthorized


def get_db(request: Request) -> Iterator[DbSession]:
    """One transaction per request; committed on success, rolled back on error."""
    factory = request.app.state.session_factory
    with factory() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def get_auth(request: Request) -> AuthService:
    return request.app.state.auth


@dataclass(frozen=True, slots=True)
class Principal:
    user: m.User
    session: m.Session


def current_principal(request: Request, db: DbSession = Depends(get_db)) -> Principal | None:
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    session = request.app.state.auth.resolve(db, token, request.app.state.clock.now())
    return Principal(session.user, session) if session else None


def require_principal(principal: Principal | None = Depends(current_principal)) -> Principal:
    if principal is None:
        raise Unauthorized("Sign in to continue.")
    return principal


def require_csrf(request: Request, principal: Principal = Depends(require_principal)) -> Principal:
    AuthService.check_csrf(principal.session, request.headers.get("x-csrf-token"))
    return principal


def optional_principal(request: Request) -> Principal | None:
    """Best-effort user lookup for public endpoints: never fails the request."""
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    try:
        with request.app.state.session_factory() as db:
            session = request.app.state.auth.resolve(db, token, request.app.state.clock.now())
            if session is None:
                return None
            db.commit()
            return Principal(session.user, session)
    except Exception:
        logging.getLogger("tport.auth").warning("session lookup failed", exc_info=False)
        return None
