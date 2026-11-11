"""Deterministic journey search.

Pipeline: validate query -> fetch departures from every enabled provider
(failures isolated per provider) -> attach offers -> drop unusable records
(no fare, expired data, already departed) -> filter -> rank -> paginate.

No AI is involved here: every price and time comes from a provider record.
Milestone 7 extends this with multi-leg (transfer) composition.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from time import perf_counter
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.core.errors import NotFound, ProvidersUnavailable, ValidationFailed
from app.domain.models import (
    Departure,
    Freshness,
    Journey,
    Leg,
    Location,
    Offer,
    PriceType,
    ProviderInfo,
    ScheduleType,
    TransportMode,
)
from app.providers.base import ProviderAdapter, ProviderError
from app.services.catalog import LocationCatalog
from app.services.freshness import FreshnessPolicy, SourcePolicy, worst
from app.services.provider_health import ProviderCallStats
from app.services.transfers import InfeasibleTransfer, TransferPolicy, check_connection

log = logging.getLogger("tport.search")

_JOURNEY_ID = re.compile(r"^(?P<provider>[a-z0-9-]{1,32})~(?P<departure>[A-Za-z0-9._-]{1,64})$")
_LEG_REF = r"[a-z0-9-]{1,32}:[A-Za-z0-9._-]{1,48}"
_MULTI_ID = re.compile(rf"^x~(?P<legs>{_LEG_REF}(?:\+{_LEG_REF}){{1,2}})$")
_MAX_TRANSFER_JOURNEYS = 12
_PRICE_ORDER = [PriceType.CONFIRMED, PriceType.INDICATIVE, PriceType.ESTIMATED, PriceType.DEMO]


class SortKey(StrEnum):
    RECOMMENDED = "recommended"
    PRICE = "price"
    DURATION = "duration"
    DEPARTURE = "departure"


@dataclass(frozen=True, slots=True)
class SearchQuery:
    origin_id: str
    destination_id: str
    travel_date: date
    modes: frozenset[TransportMode] = frozenset()  # empty => all modes
    sort: SortKey = SortKey.RECOMMENDED
    max_price: Decimal | None = None
    # Local departure-time window at the origin, [after, before). On-demand services always match.
    depart_after: time | None = None
    depart_before: time | None = None
    max_transfers: int = 1  # 0 = direct only
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class SourceStatus:
    provider: ProviderInfo
    ok: bool
    retrieved_at: datetime | None
    freshness: Freshness | None
    error: str | None = None


@dataclass(slots=True)
class ExclusionCounts:
    missing_offers: int = 0
    expired_data: int = 0
    already_departed: int = 0
    over_budget: int = 0
    outside_time_window: int = 0


@dataclass(frozen=True, slots=True)
class SearchSummary:
    cheapest_id: str | None
    fastest_id: str | None
    earliest_id: str | None
    min_price: Decimal | None
    max_price: Decimal | None
    count_by_mode: dict[str, int]


@dataclass(slots=True)
class SearchResult:
    query: SearchQuery
    origin: Location
    destination: Location
    journeys: list[Journey]  # current page
    total: int
    summary: SearchSummary
    sources: list[SourceStatus]
    excluded: ExclusionCounts
    warnings: list[str] = field(default_factory=list)


class SearchService:
    def __init__(
        self,
        catalog: LocationCatalog,
        providers: Sequence[ProviderAdapter],
        clock: Clock,
        freshness: FreshnessPolicy,
        *,
        market_timezone: str = "Asia/Tashkent",
        max_days_ahead: int = 90,
        max_page_size: int = 50,
        transfer_policy: TransferPolicy | None = None,
        freshness_by_provider: dict[str, FreshnessPolicy | SourcePolicy] | None = None,
    ) -> None:
        # Provider-specific policies (from contracts) fall back to the global freshness policy.
        self._sources: dict[str, SourcePolicy] = {
            pid: p if isinstance(p, SourcePolicy) else SourcePolicy(p, p)
            for pid, p in (freshness_by_provider or {}).items()
        }
        self.stats: dict[str, ProviderCallStats] = {p.id: ProviderCallStats() for p in providers}
        self._transfer_policy = transfer_policy or TransferPolicy()
        self._catalog = catalog
        self._providers = {p.id: p for p in providers}
        self._clock = clock
        self._freshness = freshness
        self._tz = ZoneInfo(market_timezone)
        self._max_days_ahead = max_days_ahead
        self._max_page_size = max_page_size

    def source_policy(self, provider_id: str) -> SourcePolicy:
        return self._sources.get(provider_id) or SourcePolicy(self._freshness, self._freshness)

    def policy_for(self, provider_id: str) -> FreshnessPolicy:
        """Timetable freshness policy for a provider."""
        return self.source_policy(provider_id).timetable

    def _assess(self, record: Departure | Offer, now: datetime) -> Freshness:
        """Timetable policy for departures, price policy for offers, on the contract's timestamp."""
        sp = self.source_policy(record.provider_id)
        policy = sp.price if isinstance(record, Offer) else sp.timetable
        ts = record.source_updated_at if sp.basis == "source_updated_at" else record.retrieved_at
        return policy.assess(ts, now)

    def _make_leg(
        self, provider: ProviderAdapter, dep: Departure, offers: list[Offer], now: datetime
    ) -> Leg | None:
        o_st = self._catalog.station(dep.origin_station_id)
        d_st = self._catalog.station(dep.destination_station_id)
        if o_st is None or d_st is None:
            log.warning("departure %s references unknown station", dep.id)
            return None
        offers = sorted(offers, key=lambda o: (o.price, o.fare_name))
        timetable = self._assess(dep, now)
        price = worst(*(self._assess(o, now) for o in offers))
        cheapest = offers[0]
        if provider.info.is_demo:
            ptype = PriceType.DEMO
        elif cheapest.is_estimate:
            ptype = PriceType.ESTIMATED
        elif self.source_policy(provider.id).live_prices and price == Freshness.FRESH:
            ptype = PriceType.CONFIRMED
        else:
            ptype = PriceType.INDICATIVE
        return Leg(
            dep, o_st, d_st, tuple(offers), worst(timetable, price), provider.info, timetable, price, ptype
        )

    def _booking(self, provider: ProviderAdapter, leg: Leg) -> tuple[str | None, str | None]:
        """(booking_url, note). Never for demo data; withheld when the price can't be trusted."""
        if provider.info.is_demo:
            return None, "Demo journeys cannot be booked."
        url = provider.validate_booking_url(leg.offers[0].booking_url)
        if url is None:
            return None, "This provider has not authorised booking links for this journey."
        if (
            self.source_policy(provider.id).booking_requires_fresh_price
            and leg.price_freshness != Freshness.FRESH
        ):
            return None, "Booking link hidden: the price data is out of date. Check the operator directly."
        return url, None

    # -- validation -------------------------------------------------------------
    def today(self) -> date:
        return self._clock.now().astimezone(self._tz).date()

    def _validate(self, q: SearchQuery) -> tuple[Location, Location]:
        errors: list[dict[str, str]] = []
        origin = self._catalog.get(q.origin_id)
        destination = self._catalog.get(q.destination_id)
        if q.origin_id == q.destination_id:
            raise ValidationFailed(
                "Origin and destination must be different.",
                details=[{"field": "destination", "message": "Same as origin."}],
            )
        missing = [
            {"field": name, "message": f"Unknown location '{value}'."}
            for name, value, loc in (
                ("origin", q.origin_id, origin),
                ("destination", q.destination_id, destination),
            )
            if loc is None
        ]
        if missing:
            raise NotFound("Location not found.", details=missing)

        today = self.today()
        if q.travel_date < today:
            errors.append({"field": "date", "message": "Travel date is in the past."})
        elif q.travel_date > today + timedelta(days=self._max_days_ahead):
            errors.append(
                {
                    "field": "date",
                    "message": f"Travel date must be within {self._max_days_ahead} days.",
                }
            )
        if not 1 <= q.page_size <= self._max_page_size:
            errors.append({"field": "page_size", "message": f"Must be 1-{self._max_page_size}."})
        if q.max_transfers not in (0, 1):
            errors.append({"field": "max_transfers", "message": "Must be 0 or 1."})
        if q.page < 1:
            errors.append({"field": "page", "message": "Must be >= 1."})
        if q.depart_after and q.depart_before and q.depart_after >= q.depart_before:
            errors.append({"field": "depart_before", "message": "Must be later than depart_after."})
        if q.max_price is not None and q.max_price <= 0:
            errors.append({"field": "max_price", "message": "Must be positive."})
        if errors:
            raise ValidationFailed("Invalid search request.", details=errors)
        assert origin is not None and destination is not None
        return origin, destination

    # -- search -------------------------------------------------------------------
    async def search(self, q: SearchQuery) -> SearchResult:
        origin, destination = self._validate(q)
        now = self._clock.now()
        excluded = ExclusionCounts()
        warnings: list[str] = []
        sources: list[SourceStatus] = []

        eligible = [
            p for p in self._providers.values() if {origin.id, destination.id} <= p.supported_location_ids()
        ]
        results = await asyncio.gather(*(self._fetch(p, q) for p in eligible), return_exceptions=True)

        journeys: list[Journey] = []
        failures = 0
        for provider, outcome in zip(eligible, results, strict=True):
            if isinstance(outcome, BaseException):
                failures += 1
                log.warning("provider %s failed: %s", provider.id, type(outcome).__name__)
                sources.append(SourceStatus(provider.info, False, None, None, "Provider unavailable."))
                warnings.append(f"{provider.info.name} is temporarily unavailable.")
                continue
            departures, offers = outcome
            newest = max((d.retrieved_at for d in departures), default=None)
            sources.append(
                SourceStatus(
                    provider.info,
                    True,
                    newest,
                    self.policy_for(provider.id).assess(newest, now) if newest else None,
                )
            )
            journeys.extend(self._compose_direct(provider, departures, offers, now, excluded))

        if eligible and failures == len(eligible):
            raise ProvidersUnavailable("No transport data source could be reached. Try again.")

        if q.max_transfers >= 1:
            connecting, used = await self._compose_transfers(q, origin, destination, now)
            journeys.extend(_drop_dominated(connecting, journeys))
            known = {src.provider.id for src in sources}
            for provider, newest in used.items():
                if provider.id not in known:
                    sources.append(
                        SourceStatus(
                            provider.info, True, newest, self.policy_for(provider.id).assess(newest, now)
                        )
                    )

        if q.max_price is not None:
            within = [j for j in journeys if j.price <= q.max_price]
            excluded.over_budget += len(journeys) - len(within)
            journeys = within
        if q.depart_after is not None or q.depart_before is not None:
            tz = ZoneInfo(origin.timezone)
            within = [j for j in journeys if _in_window(j, tz, q.depart_after, q.depart_before)]
            excluded.outside_time_window += len(journeys) - len(within)
            journeys = within

        if excluded.expired_data:
            warnings.append(f"{excluded.expired_data} option(s) hidden because their data is out of date.")
        if any(j.freshness == Freshness.STALE for j in journeys):
            warnings.append("Some options use data that may be out of date. Verify before travel.")

        ranked = rank(journeys, q.sort)
        start = (q.page - 1) * q.page_size
        return SearchResult(
            query=q,
            origin=origin,
            destination=destination,
            journeys=ranked[start : start + q.page_size],
            total=len(ranked),
            summary=summarize(ranked),
            sources=sources,
            excluded=excluded,
            warnings=warnings,
        )

    async def _fetch(
        self, provider: ProviderAdapter, q: SearchQuery
    ) -> tuple[Sequence[Departure], Sequence[Offer]]:
        timeout = provider.rate_limit.timeout_seconds
        stats = self.stats.setdefault(provider.id, ProviderCallStats())
        started = perf_counter()
        try:
            departures = await asyncio.wait_for(
                provider.get_departures(q.origin_id, q.destination_id, q.travel_date, q.modes), timeout
            )
            offers = await asyncio.wait_for(provider.get_offers([d.id for d in departures]), timeout)
        except Exception as exc:
            stats.failure(exc, self._clock.now())
            raise
        stats.success((perf_counter() - started) * 1000, self._clock.now())
        return departures, offers

    def _compose_direct(
        self,
        provider: ProviderAdapter,
        departures: Sequence[Departure],
        offers: Sequence[Offer],
        now: datetime,
        excluded: ExclusionCounts,
    ) -> list[Journey]:
        by_departure: dict[str, list[Offer]] = {}
        for offer in offers:
            if offer.provider_id != provider.id or offer.price <= 0:
                continue
            by_departure.setdefault(offer.departure_id, []).append(offer)

        out: list[Journey] = []
        for dep in departures:
            usable = self._usable_offers(dep, by_departure.get(dep.id, []), now, excluded)
            if usable is None:
                continue
            journey = self._build_journey(provider, dep, usable, now)
            if journey is not None:
                out.append(journey)
        return out

    def _usable_offers(
        self, dep: Departure, offers: list[Offer], now: datetime, excluded: ExclusionCounts
    ) -> list[Offer] | None:
        """Current, priced offers for a departure that hasn't left, or None (reason counted)."""
        if dep.departure_utc is not None and dep.departure_utc <= now:
            excluded.already_departed += 1
            return None
        usable = [o for o in offers if self._assess(o, now) != Freshness.EXPIRED]
        if self._assess(dep, now) == Freshness.EXPIRED or (offers and not usable):
            excluded.expired_data += 1
            return None
        if not usable:
            excluded.missing_offers += 1
            return None
        return usable

    # -- transfers ------------------------------------------------------------------
    async def _legs(
        self,
        cache: dict,
        origin_id: str,
        destination_id: str,
        day: date,
        modes: frozenset[TransportMode],
        now: datetime,
    ) -> list[tuple[ProviderAdapter, Departure, list[Offer]]]:
        key = (origin_id, destination_id, day)
        if key in cache:
            return cache[key]
        out: list[tuple[ProviderAdapter, Departure, list[Offer]]] = []
        for provider in self._providers.values():
            if not {origin_id, destination_id} <= provider.supported_location_ids():
                continue
            try:
                deps, offers = await self._fetch(
                    provider, SearchQuery(origin_id, destination_id, day, modes=modes)
                )
            except Exception as exc:  # noqa: BLE001 - a failing provider just contributes no legs
                log.info("transfer leg fetch failed for %s: %s", provider.id, type(exc).__name__)
                continue
            by_dep: dict[str, list[Offer]] = {}
            for o in offers:
                if o.provider_id == provider.id and o.price > 0:
                    by_dep.setdefault(o.departure_id, []).append(o)
            for d in deps:
                if d.schedule_type != ScheduleType.SCHEDULED:
                    continue
                usable = self._usable_offers(d, by_dep.get(d.id, []), now, ExclusionCounts())
                if usable:
                    out.append((provider, d, usable))
        cache[key] = out
        return out

    async def _compose_transfers(
        self, q: SearchQuery, origin: Location, destination: Location, now: datetime
    ) -> tuple[list[Journey], dict[ProviderAdapter, datetime]]:
        providers = list(self._providers.values())
        hubs = [
            loc
            for loc in self._catalog.search(None)
            if loc.id not in (origin.id, destination.id)
            and any({origin.id, loc.id} <= p.supported_location_ids() for p in providers)
            and any({loc.id, destination.id} <= p.supported_location_ids() for p in providers)
        ]
        cache: dict = {}
        candidates: list[Journey] = []
        used: dict[ProviderAdapter, datetime] = {}
        for hub in hubs:
            firsts = await self._legs(cache, origin.id, hub.id, q.travel_date, q.modes, now)
            if not firsts:
                continue
            seconds = []
            for day in (q.travel_date, q.travel_date + timedelta(days=1)):
                seconds += await self._legs(cache, hub.id, destination.id, day, q.modes, now)
            for p1, d1, o1 in firsts:
                for p2, d2, o2 in seconds:
                    try:
                        check = check_connection(d1, d2, self._catalog, self._transfer_policy)
                    except InfeasibleTransfer:
                        continue
                    journey = self._build_multi([(p1, d1, o1), (p2, d2, o2)], [check], now)
                    if journey is None:
                        continue
                    candidates.append(journey)
                    for p, d in ((p1, d1), (p2, d2)):
                        used[p] = max(used.get(p, d.retrieved_at), d.retrieved_at)
        # Keep the best few connections, deterministically.
        candidates.sort(key=lambda j: (j.total_minutes, j.price, j.id))
        return candidates[:_MAX_TRANSFER_JOURNEYS], used

    def _build_multi(
        self, parts: list[tuple[ProviderAdapter, Departure, list[Offer]]], checks: list, now: datetime
    ) -> Journey | None:
        legs: list[Leg] = []
        total = Decimal(0)
        total_max = Decimal(0)
        any_estimate = False
        currencies: set[str] = set()
        if len({p.info.is_demo for p, _, _ in parts}) > 1:
            return None  # never present a demo leg and a real leg as one journey
        for provider, dep, offers in parts:
            leg = self._make_leg(provider, dep, offers, now)
            if leg is None:
                return None
            cheapest = leg.offers[0]
            currencies |= {o.currency for o in offers}
            total += cheapest.price
            total_max += cheapest.price_max or cheapest.price
            any_estimate |= cheapest.is_estimate
            legs.append(leg)
        if len(currencies) != 1:
            return None
        first, last = legs[0].departure, legs[-1].departure
        if first.departure_utc is None or last.arrival_utc is None:
            return None
        notes = [
            "Connection is not guaranteed: legs are separate tickets and a delay on the first leg "
            "is not protected. Allow extra time.",
        ]
        if any(c.station_change for c in checks):
            notes.append(
                "Includes a change of station. Travel time between stations is not in the data; "
                "the minimum connection time is meant to allow for it."
            )
        return Journey(
            id="x~" + "+".join(f"{p.id}:{d.id}" for p, d, _ in parts),
            legs=tuple(legs),
            price=total,
            price_max=total_max if any_estimate else None,
            currency=currencies.pop(),
            is_price_estimate=any_estimate,
            travel_minutes=sum(leg.departure.duration_minutes for leg in legs),
            total_minutes=int((last.arrival_utc - first.departure_utc).total_seconds() // 60),
            freshness=worst(*(leg.freshness for leg in legs)),
            is_demo=any(p.info.is_demo for p, _, _ in parts),
            booking_url=None,  # each leg is booked separately
            notes=tuple(notes),
            transfer_checks=tuple(checks),
            price_type=max((leg.price_type for leg in legs), key=_PRICE_ORDER.index),
            booking_note="Each leg is booked separately with its own operator.",
        )

    def _build_journey(
        self, provider: ProviderAdapter, dep: Departure, offers: list[Offer], now: datetime
    ) -> Journey | None:
        if len({o.currency for o in offers}) != 1:
            log.warning("departure %s has mixed currencies; skipped", dep.id)
            return None
        leg = self._make_leg(provider, dep, offers, now)
        if leg is None:
            return None
        cheapest = leg.offers[0]
        notes: list[str] = []
        if cheapest.is_estimate:
            notes.append("Price is an estimate range; confirm the fare with the driver/operator.")
        if dep.departure_utc is None:
            notes.append("On-demand service: departure time is arranged directly.")
        if leg.freshness == Freshness.UNKNOWN:
            notes.append("The source did not say when this data was last updated. Verify before travel.")
        booking_url, booking_note = self._booking(provider, leg)
        return Journey(
            id=f"{provider.id}~{dep.id}",
            legs=(leg,),
            price=cheapest.price,
            price_max=cheapest.price_max,
            currency=cheapest.currency,
            is_price_estimate=cheapest.is_estimate,
            travel_minutes=dep.duration_minutes,
            total_minutes=dep.duration_minutes,
            freshness=leg.freshness,
            is_demo=provider.info.is_demo,
            booking_url=booking_url,
            notes=tuple(notes),
            price_type=leg.price_type,
            booking_note=booking_note,
        )

    # -- detail ---------------------------------------------------------------------
    async def get_journey(self, journey_id: str) -> tuple[Journey, Location, Location]:
        if journey_id.startswith("x~"):
            journey = await self._get_multi(journey_id)
            origin = self._catalog.get(journey.legs[0].origin.location_id)
            destination = self._catalog.get(journey.legs[-1].destination.location_id)
            assert origin is not None and destination is not None
            return journey, origin, destination
        match = _JOURNEY_ID.match(journey_id)
        provider = self._providers.get(match["provider"]) if match else None
        if match is None or provider is None:
            raise NotFound("Journey not found.")
        try:
            dep = await provider.get_departure(match["departure"])
            offers = await provider.get_offers([dep.id]) if dep else []
        except (ProviderError, TimeoutError) as exc:
            raise ProvidersUnavailable("The data source for this journey is unavailable.") from exc
        if dep is None:
            raise NotFound("Journey not found.")
        now = self._clock.now()
        excluded = ExclusionCounts()
        journeys = self._compose_direct(provider, [dep], offers, now, excluded)
        if not journeys:
            reason = (
                "This departure has already left."
                if excluded.already_departed
                else "No current fare data is available for this journey."
            )
            raise NotFound(reason)
        journey = journeys[0]
        origin = self._catalog.get(journey.legs[0].origin.location_id)
        destination = self._catalog.get(journey.legs[-1].destination.location_id)
        assert origin is not None and destination is not None
        return journey, origin, destination

    async def _get_multi(self, journey_id: str) -> Journey:
        match = _MULTI_ID.match(journey_id)
        if match is None:
            raise NotFound("Journey not found.")
        now = self._clock.now()
        parts = []
        for ref in match["legs"].split("+"):
            provider_id, dep_id = ref.split(":", 1)
            provider = self._providers.get(provider_id)
            if provider is None:
                raise NotFound("Journey not found.")
            try:
                dep = await provider.get_departure(dep_id)
                offers = list(await provider.get_offers([dep.id])) if dep else []
            except (ProviderError, TimeoutError) as exc:
                raise ProvidersUnavailable("A data source for this journey is unavailable.") from exc
            if dep is None:
                raise NotFound("Journey not found.")
            excluded = ExclusionCounts()
            usable = self._usable_offers(dep, [o for o in offers if o.price > 0], now, excluded)
            if usable is None:
                raise NotFound(
                    "This departure has already left."
                    if excluded.already_departed
                    else "No current fare data is available for this journey."
                )
            parts.append((provider, dep, usable))
        checks = []
        for (_, a, _), (_, b, _) in zip(parts, parts[1:], strict=False):
            try:
                checks.append(check_connection(a, b, self._catalog, self._transfer_policy))
            except InfeasibleTransfer:
                raise NotFound("This connection is no longer feasible with current schedules.") from None
        journey = self._build_multi(parts, checks, now)
        if journey is None:
            raise NotFound("Journey not found.")
        return journey


def _drop_dominated(connecting: list[Journey], direct: list[Journey]) -> list[Journey]:
    """Hide a connection when a direct option is both no more expensive and no slower."""
    return [
        c
        for c in connecting
        if not any(d.price <= c.price and d.total_minutes <= c.total_minutes for d in direct)
    ]


def _in_window(j: Journey, tz: ZoneInfo, after: time | None, before: time | None) -> bool:
    if j.departure_utc is None:
        return True
    local = j.departure_utc.astimezone(tz).time()
    return (after is None or local >= after) and (before is None or local < before)


# -- ranking ---------------------------------------------------------------------------
_FAR_FUTURE = datetime.max.replace(tzinfo=ZoneInfo("UTC"))


def _departure_key(j: Journey) -> datetime:
    # On-demand journeys (no fixed time) sort after scheduled ones.
    return j.departure_utc or _FAR_FUTURE


def rank(journeys: list[Journey], sort: SortKey) -> list[Journey]:
    """Stable, fully deterministic ordering. Final tiebreaker is the journey ID."""
    if sort == SortKey.PRICE:
        key = lambda j: (j.price, j.total_minutes, _departure_key(j), j.id)  # noqa: E731
    elif sort == SortKey.DURATION:
        key = lambda j: (j.total_minutes, j.price, _departure_key(j), j.id)  # noqa: E731
    elif sort == SortKey.DEPARTURE:
        key = lambda j: (_departure_key(j), j.price, j.id)  # noqa: E731
    else:
        if not journeys:
            return []
        min_price = min(j.price for j in journeys)
        min_minutes = min(j.total_minutes for j in journeys)

        def score(j: Journey) -> tuple:
            # Equal weight on relative price and relative duration; each transfer adds 15%.
            # Estimated (non-fixed) prices get a small penalty for uncertainty.
            s = (j.price / min_price) + Decimal(j.total_minutes) / Decimal(min_minutes)
            s += Decimal("0.15") * j.transfers
            if j.is_price_estimate:
                s += Decimal("0.10")
            return (s.quantize(Decimal("0.0001")), _departure_key(j), j.id)

        key = score
    return sorted(journeys, key=key)


def summarize(journeys: list[Journey]) -> SearchSummary:
    if not journeys:
        return SearchSummary(None, None, None, None, None, {})
    return SearchSummary(
        cheapest_id=rank(journeys, SortKey.PRICE)[0].id,
        fastest_id=rank(journeys, SortKey.DURATION)[0].id,
        earliest_id=rank(journeys, SortKey.DEPARTURE)[0].id,
        min_price=min(j.price for j in journeys),
        max_price=max(j.price_max or j.price for j in journeys),
        count_by_mode=dict(Counter(m.value for j in journeys for m in j.modes)),
    )
