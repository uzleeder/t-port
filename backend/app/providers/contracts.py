"""Provider contracts: what a source is allowed to do, and checks that its data obeys.

A ``ProviderContract`` records the *documented* basis for using a source (permissions,
capabilities, freshness, ingestion limits). ``contract_problems`` decides whether a provider
may be enabled at all. ``validate_records`` and ``check_conformance`` verify that the data an
adapter returns honours the contract and T-Port's invariants, and are used both in tests and
by the importer before any data is written.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.domain.models import Departure, Offer, ProviderInfo, ScheduleType, TransportMode
from app.providers.base import ProviderAdapter, validate_booking_url
from app.services.catalog import LocationCatalog
from app.services.freshness import FreshnessPolicy

AuthorizationBasis = Literal["internal_synthetic", "licence", "written_agreement", "open_data_terms"]
_RECORD_ID = re.compile(r"^[A-Za-z0-9._-]{1,48}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Authorization:
    """Who allowed T-Port to use this data, and for what."""

    basis: AuthorizationBasis
    reference: str  # agreement number, licence URL, or "internal" for synthetic data
    attribution: str  # wording the source requires next to its data
    permits_price_display: bool
    permits_booking_redirects: bool
    verified_by: str | None = None  # person who checked the paperwork
    verified_on: date | None = None
    expires_on: date | None = None


@dataclass(frozen=True, slots=True)
class Capabilities:
    modes: frozenset[TransportMode]
    live_prices: bool  # prices reflect current availability (not a published tariff)
    seat_availability: bool
    on_demand: bool = False  # may return on-demand services (e.g. taxi) without fixed times


@dataclass(frozen=True, slots=True)
class IngestionPolicy:
    mode: Literal["live", "stored"]
    max_concurrency: int = 4  # simultaneous requests to the source during an import
    max_attempts: int = 3  # per request, for retryable errors only
    backoff_seconds: float = 1.0  # first retry delay; doubles each attempt
    offer_batch_size: int = 200
    lock_ttl_seconds: int = 15 * 60  # an import holding the lock longer is presumed dead
    update_interval_minutes: int | None = None  # expected schedule of stored imports


@dataclass(frozen=True, slots=True)
class ProviderContract:
    info: ProviderInfo
    authorization: Authorization
    capabilities: Capabilities
    ingestion: IngestionPolicy
    stale_after: timedelta
    expire_after: timedelta
    currency: str = "UZS"
    timezone: str = "Asia/Tashkent"
    data_mapping: str = ""  # how source stations/times/currency map to T-Port
    reliability_notes: str = ""
    update_frequency: str | None = None

    @property
    def freshness(self) -> FreshnessPolicy:
        return FreshnessPolicy(self.stale_after, self.expire_after)

    @property
    def access_basis(self) -> str:
        a = self.authorization
        parts = [f"{a.basis}: {a.reference}"]
        if a.verified_by and a.verified_on:
            parts.append(f"verified by {a.verified_by} on {a.verified_on.isoformat()}")
        if a.expires_on:
            parts.append(f"expires {a.expires_on.isoformat()}")
        return "; ".join(parts)


def contract_problems(c: ProviderContract, today: date) -> list[str]:
    """Reasons this provider must NOT be enabled. Empty list = may be enabled."""
    a, problems = c.authorization, []
    if c.info.is_demo:
        if a.basis != "internal_synthetic":
            problems.append("demo providers must use basis 'internal_synthetic'")
        if c.info.booking_hosts or a.permits_booking_redirects:
            problems.append("demo data must never be bookable")
    else:
        if a.basis == "internal_synthetic":
            problems.append("real providers need a licence, agreement or open-data terms")
        if not a.reference.strip():
            problems.append("authorization reference is missing")
        if not (a.verified_by and a.verified_on):
            problems.append("authorization has not been verified by a named person")
        if a.expires_on and a.expires_on < today:
            problems.append(f"authorization expired on {a.expires_on.isoformat()}")
        if not a.permits_price_display:
            problems.append("source does not permit showing prices; T-Port cannot list its fares")
        if not c.data_mapping.strip():
            problems.append("data mapping is undocumented")
    if c.info.booking_hosts and not a.permits_booking_redirects:
        problems.append("booking hosts configured but redirects are not permitted")
    if a.permits_booking_redirects and not c.info.booking_hosts:
        problems.append("booking redirects permitted but no allowed hosts listed")
    if not c.capabilities.modes:
        problems.append("no transport modes declared")
    if c.expire_after < c.stale_after:
        problems.append("expire_after must be >= stale_after")
    if not _CURRENCY.match(c.currency):
        problems.append("currency must be an ISO 4217 code")
    try:
        ZoneInfo(c.timezone)
    except Exception:  # noqa: BLE001
        problems.append(f"unknown time zone {c.timezone!r}")
    ing = c.ingestion
    if not 1 <= ing.max_concurrency <= 32:
        problems.append("max_concurrency must be 1-32")
    if not 1 <= ing.max_attempts <= 10:
        problems.append("max_attempts must be 1-10")
    if ing.mode == "stored" and not ing.update_interval_minutes:
        problems.append("stored providers must declare update_interval_minutes")
    return problems


@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    subject: str  # record id the problem refers to
    message: str


@dataclass(slots=True)
class ConformanceReport:
    provider_id: str
    queries: int = 0
    departures: int = 0
    offers: int = 0
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def validate_records(
    contract: ProviderContract,
    catalog: LocationCatalog,
    departures: Sequence[Departure],
    offers: Sequence[Offer],
    now: datetime,
    *,
    travel_dates: dict[str, date] | None = None,
) -> list[Violation]:
    """Invariants every record must satisfy before T-Port stores or shows it."""
    v: list[Violation] = []
    pid = contract.info.id
    tz = ZoneInfo(contract.timezone)
    future_limit = now + timedelta(minutes=5)
    seen: set[str] = set()

    def bad(code: str, subject: str, message: str) -> None:
        v.append(Violation(code, subject, message))

    for d in departures:
        if d.id in seen:
            bad("duplicate_departure", d.id, "departure id returned more than once")
        seen.add(d.id)
        if not _RECORD_ID.match(d.id):
            bad("bad_id", d.id, "ids must be 1-48 chars of A-Z a-z 0-9 . _ -")
        if d.provider_id != pid:
            bad("wrong_provider", d.id, f"provider_id {d.provider_id!r} != {pid!r}")
        if d.mode not in contract.capabilities.modes:
            bad("undeclared_mode", d.id, f"mode {d.mode.value} not in the contract")
        o, t = catalog.station(d.origin_station_id), catalog.station(d.destination_station_id)
        if o is None or t is None:
            bad("unknown_station", d.id, "station not in the T-Port catalog (add a data mapping)")
        elif o.location_id == t.location_id:
            bad("same_location", d.id, "origin and destination are in the same city")
        if d.duration_minutes <= 0:
            bad("bad_duration", d.id, "duration must be positive")
        if d.schedule_type == ScheduleType.SCHEDULED:
            if d.departure_utc is None or d.arrival_utc is None:
                bad("missing_times", d.id, "scheduled services need departure and arrival times")
            else:
                if d.arrival_utc <= d.departure_utc:
                    bad("chronology", d.id, "arrival is not after departure")
                span = (d.arrival_utc - d.departure_utc).total_seconds() / 60
                if abs(span - d.duration_minutes) > 1:
                    bad("duration_mismatch", d.id, f"duration {d.duration_minutes} != times ({span:.0f})")
                if travel_dates and d.id in travel_dates:
                    local = d.departure_utc.astimezone(tz).date()
                    if local != travel_dates[d.id]:
                        bad("wrong_date", d.id, f"departs {local}, requested {travel_dates[d.id]}")
        else:
            if not contract.capabilities.on_demand:
                bad("undeclared_on_demand", d.id, "on-demand services not declared in the contract")
            if d.departure_utc is not None:
                bad("on_demand_with_time", d.id, "on-demand services must not claim a fixed time")
        for label, ts in (("retrieved_at", d.retrieved_at), ("source_updated_at", d.source_updated_at)):
            if ts is not None and ts.tzinfo is None:
                bad("naive_timestamp", d.id, f"{label} must be timezone-aware")
            elif ts is not None and ts > future_limit:
                bad("future_timestamp", d.id, f"{label} is in the future")

    fares: set[tuple[str, str]] = set()
    for o in offers:
        if o.departure_id not in seen:
            bad("orphan_offer", o.id, "offer refers to a departure that was not returned")
        if o.provider_id != pid:
            bad("wrong_provider", o.id, f"provider_id {o.provider_id!r} != {pid!r}")
        if (o.departure_id, o.fare_name) in fares:
            bad("duplicate_fare", o.id, "same fare name twice for one departure")
        fares.add((o.departure_id, o.fare_name))
        if o.price <= 0:
            bad("bad_price", o.id, "price must be positive")
        if o.currency != contract.currency:
            bad("currency", o.id, f"currency {o.currency} != contract {contract.currency}")
        if o.price_max is not None and o.price_max < o.price:
            bad("bad_price_range", o.id, "price_max is below price")
        if o.price_max is not None and not o.is_estimate:
            bad("range_not_estimate", o.id, "a price range must be flagged as an estimate")
        if o.booking_url is not None:
            if not contract.authorization.permits_booking_redirects:
                bad("booking_not_permitted", o.id, "booking URL supplied but redirects are not permitted")
            elif validate_booking_url(o.booking_url, contract.info.booking_hosts) is None:
                bad("booking_host", o.id, "booking URL is not HTTPS on an allowed host")
        if o.retrieved_at.tzinfo is None:
            bad("naive_timestamp", o.id, "retrieved_at must be timezone-aware")
        elif o.retrieved_at > future_limit:
            bad("future_timestamp", o.id, "retrieved_at is in the future")
    return v


async def check_conformance(
    adapter: ProviderAdapter,
    contract: ProviderContract,
    catalog: LocationCatalog,
    queries: Iterable[tuple[str, str, date]],
    now: datetime,
) -> ConformanceReport:
    """Exercise an adapter through the real interface and report every contract violation."""
    report = ConformanceReport(adapter.id)
    if adapter.info != contract.info:
        report.violations.append(Violation("info_mismatch", adapter.id, "adapter info differs from contract"))
    supported = adapter.supported_location_ids()
    for origin, destination, day in queries:
        report.queries += 1
        deps = list(await adapter.get_departures(origin, destination, day, frozenset()))
        offers = list(await adapter.get_offers([d.id for d in deps]))
        report.departures += len(deps)
        report.offers += len(offers)
        report.violations += validate_records(
            contract, catalog, deps, offers, now, travel_dates={d.id: day for d in deps}
        )
        for d in deps:
            o, t = catalog.station(d.origin_station_id), catalog.station(d.destination_station_id)
            if o and t and (o.location_id, t.location_id) != (origin, destination):
                report.violations.append(
                    Violation("wrong_route", d.id, f"returned for {origin}->{destination}")
                )
            if o and o.location_id not in supported:
                report.violations.append(Violation("unsupported_location", d.id, "location not declared"))
            again = await adapter.get_departure(d.id)
            if again is None or (again.departure_utc, again.service_code) != (
                d.departure_utc,
                d.service_code,
            ):
                report.violations.append(Violation("lookup_mismatch", d.id, "get_departure() disagrees"))
    return report
