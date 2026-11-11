"""Public API response schemas (documented in OpenAPI)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.domain.models import Journey, Leg, Location, Offer, Station
from app.services.search import SearchResult, SourceStatus

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class StationOut(BaseModel):
    id: str
    name: str
    kind: str
    code: str | None = None

    @classmethod
    def of(cls, s: Station) -> StationOut:
        return cls(id=s.id, name=s.name, kind=s.kind.value, code=s.code)


class LocationOut(BaseModel):
    id: str
    name: str
    country_code: str
    region: str
    timezone: str
    latitude: float
    longitude: float
    aliases: list[str]

    @classmethod
    def of(cls, loc: Location) -> LocationOut:
        return cls(
            id=loc.id,
            name=loc.name,
            country_code=loc.country_code,
            region=loc.region,
            timezone=loc.timezone,
            latitude=loc.latitude,
            longitude=loc.longitude,
            aliases=list(loc.aliases),
        )


class LocationDetailOut(LocationOut):
    stations: list[StationOut]


class ProviderOut(BaseModel):
    id: str
    name: str
    is_demo: bool
    attribution: str


class SourceOut(BaseModel):
    provider: ProviderOut
    ok: bool
    retrieved_at: datetime | None
    freshness: str | None
    error: str | None = None

    @classmethod
    def of(cls, s: SourceStatus) -> SourceOut:
        p = s.provider
        return cls(
            provider=ProviderOut(id=p.id, name=p.name, is_demo=p.is_demo, attribution=p.attribution),
            ok=s.ok,
            retrieved_at=s.retrieved_at,
            freshness=s.freshness.value if s.freshness else None,
            error=s.error,
        )


class FareOut(BaseModel):
    name: str
    price: Decimal = Field(description="Fixed-precision amount in `currency`.")
    price_max: Decimal | None = None
    currency: str
    is_estimate: bool

    @classmethod
    def of(cls, o: Offer) -> FareOut:
        return cls(
            name=o.fare_name,
            price=o.price,
            price_max=o.price_max,
            currency=o.currency,
            is_estimate=o.is_estimate,
        )


def _local(dt: datetime | None, tz: str) -> str | None:
    return dt.astimezone(ZoneInfo(tz)).isoformat() if dt else None


class LegOut(BaseModel):
    mode: str
    operator: str
    service_code: str
    schedule_type: str
    origin: StationOut
    destination: StationOut
    departure_utc: datetime | None
    arrival_utc: datetime | None
    departure_local: str | None = Field(description="ISO 8601 in the origin's time zone.")
    arrival_local: str | None
    duration_minutes: int
    fares: list[FareOut]
    freshness: str
    retrieved_at: datetime
    source_updated_at: datetime | None

    @classmethod
    def of(cls, leg: Leg, tz: str) -> LegOut:
        d = leg.departure
        return cls(
            mode=d.mode.value,
            operator=d.operator_name,
            service_code=d.service_code,
            schedule_type=d.schedule_type.value,
            origin=StationOut.of(leg.origin),
            destination=StationOut.of(leg.destination),
            departure_utc=d.departure_utc,
            arrival_utc=d.arrival_utc,
            departure_local=_local(d.departure_utc, tz),
            arrival_local=_local(d.arrival_utc, tz),
            duration_minutes=d.duration_minutes,
            fares=[FareOut.of(o) for o in leg.offers],
            freshness=leg.freshness.value,
            retrieved_at=d.retrieved_at,
            source_updated_at=d.source_updated_at,
        )


class TransferCheckOut(BaseModel):
    at_location_id: str
    from_station: str
    to_station: str
    station_change: bool
    connection_minutes: int = Field(description="Scheduled time between arrival and next departure.")
    minimum_minutes: int = Field(description="Configured minimum connection time that was applied.")
    guaranteed: bool = Field(description="False for self-made connections on separate tickets.")


class JourneyOut(BaseModel):
    id: str
    modes: list[str]
    transfers: int
    price: Decimal
    price_max: Decimal | None
    currency: str
    is_price_estimate: bool
    travel_minutes: int = Field(description="In-vehicle time.")
    total_minutes: int = Field(description="First departure to final arrival.")
    departure_utc: datetime | None
    arrival_utc: datetime | None
    freshness: str
    is_demo: bool
    booking_url: str | None = Field(
        description="Only set when the provider permits booking redirects and the URL is verified."
    )
    notes: list[str]
    legs: list[LegOut]
    transfer_checks: list[TransferCheckOut] = Field(default_factory=list)

    @classmethod
    def of(cls, j: Journey, tz: str) -> JourneyOut:
        return cls(
            id=j.id,
            modes=[m.value for m in j.modes],
            transfers=j.transfers,
            price=j.price,
            price_max=j.price_max,
            currency=j.currency,
            is_price_estimate=j.is_price_estimate,
            travel_minutes=j.travel_minutes,
            total_minutes=j.total_minutes,
            departure_utc=j.departure_utc,
            arrival_utc=j.arrival_utc,
            freshness=j.freshness.value,
            is_demo=j.is_demo,
            booking_url=j.booking_url,
            notes=list(j.notes),
            legs=[LegOut.of(leg, tz) for leg in j.legs],
            transfer_checks=[
                TransferCheckOut(
                    at_location_id=c.at_location_id,
                    from_station=j.legs[i].destination.name,
                    to_station=j.legs[i + 1].origin.name,
                    station_change=c.station_change,
                    connection_minutes=c.connection_minutes,
                    minimum_minutes=c.minimum_minutes,
                    guaranteed=c.guaranteed,
                )
                for i, c in enumerate(j.transfer_checks)
            ],
        )


class SummaryOut(BaseModel):
    cheapest_id: str | None
    fastest_id: str | None
    earliest_id: str | None
    min_price: Decimal | None
    max_price: Decimal | None
    count_by_mode: dict[str, int]


class ExcludedOut(BaseModel):
    missing_offers: int
    expired_data: int
    already_departed: int
    over_budget: int
    outside_time_window: int


class QueryOut(BaseModel):
    origin: LocationOut
    destination: LocationOut
    date: date
    modes: list[str]
    sort: str
    max_price: Decimal | None
    depart_after: str | None = None
    depart_before: str | None = None


class SearchResponse(BaseModel):
    query: QueryOut
    items: list[JourneyOut]
    total: int
    page: int
    page_size: int
    summary: SummaryOut
    sources: list[SourceOut]
    excluded: ExcludedOut
    warnings: list[str]
    contains_demo_data: bool

    @classmethod
    def of(cls, r: SearchResult) -> SearchResponse:
        tz = r.origin.timezone
        s = r.summary
        return cls(
            query=QueryOut(
                origin=LocationOut.of(r.origin),
                destination=LocationOut.of(r.destination),
                date=r.query.travel_date,
                modes=sorted(m.value for m in r.query.modes),
                sort=r.query.sort.value,
                max_price=r.query.max_price,
                depart_after=r.query.depart_after.strftime("%H:%M") if r.query.depart_after else None,
                depart_before=r.query.depart_before.strftime("%H:%M") if r.query.depart_before else None,
            ),
            items=[JourneyOut.of(j, tz) for j in r.journeys],
            total=r.total,
            page=r.query.page,
            page_size=r.query.page_size,
            summary=SummaryOut(
                cheapest_id=s.cheapest_id,
                fastest_id=s.fastest_id,
                earliest_id=s.earliest_id,
                min_price=s.min_price,
                max_price=s.max_price,
                count_by_mode=s.count_by_mode,
            ),
            sources=[SourceOut.of(x) for x in r.sources],
            excluded=ExcludedOut(**asdict(r.excluded)),
            warnings=r.warnings,
            contains_demo_data=any(x.provider.is_demo for x in r.sources),
        )


class JourneyDetailResponse(BaseModel):
    journey: JourneyOut
    origin: LocationOut
    destination: LocationOut


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    ai_engine: str
    providers: list[ProviderOut]
