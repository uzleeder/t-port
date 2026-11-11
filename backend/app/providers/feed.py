"""Timetable-feed adapter: serves a provider-supplied JSON timetable through the adapter interface.

This is the intended path for authorized sources that deliver files (published timetables,
tariffs) rather than a query API. The feed is schema-validated on load; malformed feeds are
rejected as a whole. Format (all times local to ``timezone``)::

    {
      "feed_version": "operator-2026.11",
      "generated_at": "2026-11-01T00:00:00Z",
      "timezone": "Asia/Tashkent",
      "currency": "UZS",
      "booking_url_template": "https://tickets.operator.example/book?service={service}&date={date}",
      "services": [
        {"code": "R100", "mode": "train", "operator": "Operator name",
         "from": "tashkent-rail", "to": "samarkand-rail", "depart": "07:15", "minutes": 125,
         "days": [0, 1, 2, 3, 4], "fares": [{"name": "Economy", "price": "250000.00"}]}
      ]
    }

Station IDs must already be mapped to T-Port's catalog (see the contract's data_mapping).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.clock import Clock, SystemClock
from app.domain.models import Departure, Offer, ProviderInfo, ScheduleType, TransportMode
from app.providers.base import ProviderAdapter, ProviderError, RateLimitPolicy
from app.services.catalog import LocationCatalog

_ID = re.compile(r"^(?P<code>[A-Za-z0-9_-]{1,32})\.(?P<date>\d{8})$")


class FeedFare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class FeedService(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    mode: Literal["train", "bus", "flight"]
    operator: str = Field(min_length=1, max_length=120)
    from_station: str = Field(alias="from", min_length=1)
    to_station: str = Field(alias="to", min_length=1)
    depart: time
    minutes: int = Field(gt=0, le=72 * 60)
    days: list[int] = Field(min_length=1)
    fares: list[FeedFare] = Field(min_length=1)

    @field_validator("days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if any(d not in range(7) for d in v) or len(set(v)) != len(v):
            raise ValueError("days must be distinct values 0 (Monday) to 6 (Sunday)")
        return v


class Feed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feed_version: str = Field(min_length=1, max_length=100)
    generated_at: AwareDatetime
    timezone: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    booking_url_template: str | None = None
    services: list[FeedService] = Field(min_length=1)

    @field_validator("services")
    @classmethod
    def _unique_codes(cls, v: list[FeedService]) -> list[FeedService]:
        codes = [s.code for s in v]
        if len(codes) != len(set(codes)):
            raise ValueError("service codes must be unique")
        return v


class FeedError(ValueError):
    pass


class FeedAdapter(ProviderAdapter):
    rate_limit = RateLimitPolicy(timeout_seconds=2.0)

    def __init__(
        self,
        info: ProviderInfo,
        raw_feed: dict,
        catalog: LocationCatalog,
        clock: Clock | None = None,
        *,
        retrieved_at: datetime | None = None,
    ) -> None:
        try:
            self.feed = Feed.model_validate(raw_feed)
        except ValidationError as exc:
            raise FeedError(f"invalid feed for {info.id}: {exc.error_count()} error(s)") from exc
        try:
            self._tz = ZoneInfo(self.feed.timezone)
        except Exception as exc:  # noqa: BLE001
            raise FeedError(f"unknown time zone {self.feed.timezone!r}") from exc
        self.info = info
        self._catalog = catalog
        self._clock = clock or SystemClock()
        # When T-Port obtained this feed; freshness is measured from here.
        self.retrieved_at = retrieved_at or self._clock.now()
        self._services = {s.code: s for s in self.feed.services}
        routes, locs = set(), set()
        for s in self.feed.services:
            o, d = catalog.station(s.from_station), catalog.station(s.to_station)
            if o is None or d is None:
                raise FeedError(f"service {s.code}: station not mapped to the T-Port catalog")
            routes.add((o.location_id, d.location_id))
            locs |= {o.location_id, d.location_id}
        self._routes, self._locations = frozenset(routes), frozenset(locs)

    def supported_location_ids(self) -> frozenset[str]:
        return self._locations

    def served_routes(self) -> frozenset[tuple[str, str]]:
        return self._routes

    def _departure(self, s: FeedService, day: date) -> Departure:
        dep_utc = datetime.combine(day, s.depart, self._tz).astimezone(UTC)
        return Departure(
            id=f"{s.code}.{day:%Y%m%d}",
            provider_id=self.id,
            service_code=s.code,
            operator_name=s.operator,
            mode=TransportMode(s.mode),
            origin_station_id=s.from_station,
            destination_station_id=s.to_station,
            schedule_type=ScheduleType.SCHEDULED,
            duration_minutes=s.minutes,
            departure_utc=dep_utc,
            arrival_utc=dep_utc + timedelta(minutes=s.minutes),
            retrieved_at=self.retrieved_at,
            source_updated_at=self.feed.generated_at,
        )

    async def get_departures(
        self,
        origin_location_id: str,
        destination_location_id: str,
        travel_date: date,
        modes: frozenset[TransportMode],
    ) -> Sequence[Departure]:
        out = []
        for s in self.feed.services:
            o, d = self._catalog.station(s.from_station), self._catalog.station(s.to_station)
            if (o.location_id, d.location_id) != (origin_location_id, destination_location_id):
                continue
            if travel_date.weekday() not in s.days or (modes and TransportMode(s.mode) not in modes):
                continue
            out.append(self._departure(s, travel_date))
        return out

    def _parse(self, departure_id: str) -> tuple[FeedService, date] | None:
        m = _ID.match(departure_id)
        s = self._services.get(m["code"]) if m else None
        if m is None or s is None:
            return None
        try:
            day = datetime.strptime(m["date"], "%Y%m%d").date()
        except ValueError:
            return None
        return (s, day) if day.weekday() in s.days else None

    async def get_departure(self, departure_id: str) -> Departure | None:
        parsed = self._parse(departure_id)
        return self._departure(*parsed) if parsed else None

    async def get_offers(self, departure_ids: Sequence[str]) -> Sequence[Offer]:
        offers = []
        for dep_id in departure_ids:
            parsed = self._parse(dep_id)
            if parsed is None:
                continue
            s, day = parsed
            url = None
            if self.feed.booking_url_template:
                try:
                    url = self.feed.booking_url_template.format(service=s.code, date=day.isoformat())
                except (KeyError, IndexError) as exc:
                    raise ProviderError(self.id, "booking_url_template has unknown placeholders") from exc
            for i, fare in enumerate(s.fares):
                offers.append(
                    Offer(
                        id=f"{dep_id}.f{i}",
                        provider_id=self.id,
                        departure_id=dep_id,
                        fare_name=fare.name,
                        price=fare.price,
                        currency=self.feed.currency,
                        retrieved_at=self.retrieved_at,
                        source_updated_at=self.feed.generated_at,
                        booking_url=url,
                    )
                )
        return offers
