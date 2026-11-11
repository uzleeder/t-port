"""/api/v1 routes for locations and journeys."""

from __future__ import annotations

import logging
from datetime import date, time
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from app.api.deps import Principal, optional_principal
from app.api.v1.schemas import (
    BookingInfoOut,
    CompareBestOut,
    CompareItemOut,
    CompareResponse,
    JourneyDetailResponse,
    JourneyOut,
    LocationDetailOut,
    LocationOut,
    Page,
    ProviderOut,
    SearchResponse,
    StationOut,
)
from app.core.errors import AppError, NotFound, ProvidersUnavailable, ValidationFailed
from app.db.repositories import ActivityRepository, BookingRedirectRepository
from app.db.session import transaction
from app.domain.models import TransportMode
from app.providers.base import validate_booking_url
from app.services.catalog import LocationCatalog
from app.services.comparison import MAX_COMPARE, compare
from app.services.search import SearchQuery, SearchService, SortKey
from app.services.simulation import parse_simulations, simulated

router = APIRouter(prefix="/api/v1")
log = logging.getLogger("tport.api")


def get_catalog(request: Request) -> LocationCatalog:
    return request.app.state.catalog


def get_search(request: Request) -> SearchService:
    return request.app.state.search


@router.get("/locations", response_model=Page[LocationOut], tags=["locations"])
def list_locations(
    catalog: Annotated[LocationCatalog, Depends(get_catalog)],
    q: Annotated[str | None, Query(max_length=64, description="Name or alias")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[LocationOut]:
    matches = catalog.search(q)
    return Page(
        items=[LocationOut.of(x) for x in matches[offset : offset + limit]],
        total=len(matches),
        limit=limit,
        offset=offset,
    )


@router.get("/locations/{location_id}", response_model=LocationDetailOut, tags=["locations"])
def get_location(
    catalog: Annotated[LocationCatalog, Depends(get_catalog)],
    location_id: Annotated[str, Path(max_length=64)],
) -> LocationDetailOut:
    loc = catalog.get(location_id)
    if loc is None:
        raise NotFound("Location not found.")
    return LocationDetailOut(
        **LocationOut.of(loc).model_dump(),
        stations=[StationOut.of(s) for s in catalog.stations_for(loc.id)],
    )


def _parse_modes(raw: str | None) -> frozenset[TransportMode]:
    if not raw:
        return frozenset()
    out = set()
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        try:
            out.add(TransportMode(part))
        except ValueError:
            raise ValidationFailed(
                "Invalid transport mode.",
                details=[{"field": "modes", "message": f"Unknown mode '{part[:20]}'."}],
            ) from None
    return frozenset(out)


@router.get("/journeys/search", response_model=SearchResponse, tags=["journeys"])
async def search_journeys(
    request: Request,
    search: Annotated[SearchService, Depends(get_search)],
    principal: Annotated[Principal | None, Depends(optional_principal)],
    origin: Annotated[str, Query(min_length=1, max_length=64)],
    destination: Annotated[str, Query(min_length=1, max_length=64)],
    date_: Annotated[date, Query(alias="date", description="Local travel date, YYYY-MM-DD")],
    modes: Annotated[
        str | None, Query(max_length=64, description="Comma list: train,bus,flight,taxi")
    ] = None,
    sort: SortKey = SortKey.RECOMMENDED,
    max_price: Annotated[Decimal | None, Query(gt=0, max_digits=14, decimal_places=2)] = None,
    depart_after: Annotated[time | None, Query(description="Local time HH:MM, inclusive")] = None,
    depart_before: Annotated[time | None, Query(description="Local time HH:MM, exclusive")] = None,
    max_transfers: Annotated[int, Query(ge=0, le=2, description="0 = direct only; up to 2 changes")] = 1,
    prefer_modes: Annotated[
        str | None, Query(max_length=64, description="Comma list; favoured by the recommended ranking")
    ] = None,
    arrive_before: Annotated[
        time | None, Query(description="Arrive by this local time at the destination (HH:MM)")
    ] = None,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
    channel: Annotated[str, Query(pattern="^(form|ai)$", include_in_schema=False)] = "form",
    simulate: Annotated[str | None, Query(max_length=32, include_in_schema=False)] = None,
) -> SearchResponse:
    if simulate and request.app.state.settings.enable_fault_simulation:  # dev/test only
        search = simulated(search, parse_simulations(simulate))
    result = await search.search(
        SearchQuery(
            origin_id=origin.strip().lower(),
            destination_id=destination.strip().lower(),
            travel_date=date_,
            modes=_parse_modes(modes),
            sort=sort,
            max_price=max_price,
            depart_after=depart_after,
            depart_before=depart_before,
            max_transfers=max_transfers,
            prefer_modes=_parse_modes(prefer_modes),
            arrive_before=arrive_before,
            page=page,
            page_size=page_size,
        )
    )
    await _log_search(request, principal, result, channel)
    _record_search_metrics(request, result)
    return SearchResponse.of(result)


def _record_search_metrics(request: Request, result) -> None:
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is None:
        return
    metrics.inc("tport_searches_total", outcome="results" if result.total else "empty")
    for j in result.journeys:
        metrics.inc("tport_journeys_shown_total", freshness=j.freshness.value, price_type=j.price_type.value)
    if result.excluded.expired_data:
        metrics.inc("tport_journeys_hidden_expired_total", result.excluded.expired_data)
    for s in result.sources:
        if not s.ok:
            metrics.inc("tport_search_provider_failures_total", provider=s.provider.id)


async def _log_search(request: Request, principal: Principal | None, result, channel: str) -> None:
    """Analytics only; a logging failure must never fail the search."""
    if result.query.page != 1:
        return

    def write() -> None:
        with transaction(request.app.state.session_factory) as db:
            ActivityRepository(db).record_search(
                user_id=principal.user.id if principal else None,
                origin_location_id=result.origin.id,
                destination_location_id=result.destination.id,
                travel_date=result.query.travel_date,
                modes=sorted(x.value for x in result.query.modes),
                sort=result.query.sort.value,
                result_count=result.total,
                channel=channel,
                created_at=request.app.state.clock.now(),
            )

    try:
        await run_in_threadpool(write)
    except Exception as exc:
        log.warning("search log failed: %s", type(exc).__name__)


@router.get("/journeys/compare", response_model=CompareResponse, tags=["journeys"])
async def compare_journeys(
    search: Annotated[SearchService, Depends(get_search)],
    ids: Annotated[str, Query(max_length=600, description="2-4 comma-separated journey IDs")],
) -> CompareResponse:
    """Re-resolves each journey from current provider data; unavailable ones are reported, not hidden."""
    wanted = list(dict.fromkeys(i.strip() for i in ids.split(",") if i.strip()))
    if not 2 <= len(wanted) <= MAX_COMPARE or any(len(i) > 128 for i in wanted):
        raise ValidationFailed(
            f"Choose between 2 and {MAX_COMPARE} journeys to compare.",
            details=[{"field": "ids", "message": f"2-{MAX_COMPARE} distinct journey IDs."}],
        )
    items: list[CompareItemOut] = []
    resolved = []
    for jid in wanted:
        try:
            journey, origin, destination = await search.get_journey(jid)
        except (NotFound, ProvidersUnavailable) as exc:
            items.append(CompareItemOut(id=jid, available=False, reason=exc.message))
            continue
        resolved.append(journey)
        items.append(
            CompareItemOut(
                id=jid,
                available=True,
                journey=JourneyOut.of(journey, origin.timezone),
                origin=LocationOut.of(origin),
                destination=LocationOut.of(destination),
            )
        )
    result = compare(resolved)
    return CompareResponse(
        items=items,
        best=CompareBestOut(
            cheapest=result.cheapest,
            fastest=result.fastest,
            fewest_transfers=result.fewest_transfers,
            earliest_departure=result.earliest_departure,
            earliest_arrival=result.earliest_arrival,
        ),
        caveats=result.caveats,
    )


class BookingUnavailable(AppError):
    status_code = 409
    code = "booking_unavailable"


def _booking_target(journey) -> tuple[str | None, str | None]:
    """(url, reason). Re-checks the link on every hand-off; never trusts an earlier answer."""
    if len(journey.legs) > 1:
        return None, "Each leg is booked separately with its own operator."
    if journey.booking_url is None:
        return None, journey.booking_note or "This journey can't be booked through T-Port."
    leg = journey.legs[0]
    provider = leg.provider
    if provider is None or provider.is_demo:
        return None, "Demo journeys cannot be booked."
    url = validate_booking_url(journey.booking_url, provider.booking_hosts)
    if url is None:
        return None, "This provider has not authorised booking links for this journey."
    return url, None


def _leg_journey_id(leg) -> str:
    return f"{leg.departure.provider_id}~{leg.departure.id}"


@router.get("/journeys/{journey_id}/booking", response_model=BookingInfoOut, tags=["booking"])
async def booking_info(
    search: Annotated[SearchService, Depends(get_search)],
    journey_id: Annotated[str, Path(max_length=600)],
) -> BookingInfoOut:
    """Explains the external booking before the traveller leaves T-Port (no redirect, no counting)."""
    journey, _, _ = await search.get_journey(journey_id)
    url, reason = _booking_target(journey)
    provider = journey.legs[0].provider
    priced_at = [o.retrieved_at for leg in journey.legs for o in leg.offers[:1]]
    return BookingInfoOut(
        journey_id=journey.id,
        bookable=url is not None,
        reason=reason,
        provider=ProviderOut(
            id=provider.id, name=provider.name, is_demo=provider.is_demo, attribution=provider.attribution
        )
        if provider and len(journey.legs) == 1
        else None,
        booking_host=urlsplit(url).hostname if url else None,
        price=journey.price,
        price_max=journey.price_max,
        currency=journey.currency,
        price_type=journey.price_type.value,
        price_retrieved_at=min(priced_at) if priced_at else None,
        leg_journey_ids=[_leg_journey_id(leg) for leg in journey.legs] if len(journey.legs) > 1 else [],
    )


@router.get("/journeys/{journey_id}/book", tags=["booking"], status_code=303)
async def book_redirect(
    request: Request,
    search: Annotated[SearchService, Depends(get_search)],
    journey_id: Annotated[str, Path(max_length=600)],
) -> RedirectResponse:
    """Hands the traveller to the operator's booking page.

    The journey is re-resolved from current data and the link re-validated (HTTPS, allow-listed host,
    fresh permitted price). T-Port adds nothing to the operator URL (no user data, no tracking) and
    only counts redirects per provider and day.
    """
    journey, _, _ = await search.get_journey(journey_id)
    url, reason = _booking_target(journey)
    if url is None:
        raise BookingUnavailable(reason or "This journey can't be booked through T-Port.")
    provider_id = journey.legs[0].departure.provider_id
    await _count_redirect(request, provider_id)
    return RedirectResponse(
        url,
        status_code=303,
        headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
    )


async def _count_redirect(request: Request, provider_id: str) -> None:
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is not None:
        metrics.inc("tport_booking_redirects_total", provider=provider_id)
    day = request.app.state.clock.now().date()

    def write() -> None:
        with transaction(request.app.state.session_factory) as db:
            BookingRedirectRepository(db).increment(provider_id, day)

    try:
        await run_in_threadpool(write)
    except Exception:  # noqa: BLE001 - counting must never block the hand-off
        log.warning("could not record booking redirect count")


@router.get("/journeys/{journey_id}", response_model=JourneyDetailResponse, tags=["journeys"])
async def get_journey(
    search: Annotated[SearchService, Depends(get_search)],
    journey_id: Annotated[str, Path(max_length=128)],
) -> JourneyDetailResponse:
    journey, origin, destination = await search.get_journey(journey_id)
    return JourneyDetailResponse(
        journey=JourneyOut.of(journey, origin.timezone),
        origin=LocationOut.of(origin),
        destination=LocationOut.of(destination),
    )
