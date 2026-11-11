"""Core domain types. Pure data — no I/O, no framework dependencies.

Conventions:
* All datetimes are timezone-aware UTC. Local times are derived using the
  station/location IANA time zone at presentation time.
* Money is ``decimal.Decimal`` with an explicit ISO 4217 currency code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class TransportMode(StrEnum):
    TRAIN = "train"
    BUS = "bus"
    FLIGHT = "flight"
    TAXI = "taxi"


class StationKind(StrEnum):
    RAIL_STATION = "rail_station"
    BUS_TERMINAL = "bus_terminal"
    AIRPORT = "airport"
    CITY_POINT = "city_point"  # door-to-door services (taxi) start/end in the city


class ScheduleType(StrEnum):
    SCHEDULED = "scheduled"  # fixed timetable departure
    ON_DEMAND = "on_demand"  # e.g. taxi: no fixed departure time


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class Location:
    id: str
    name: str
    country_code: str
    region: str
    timezone: str
    latitude: float
    longitude: float
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Station:
    id: str
    name: str
    location_id: str
    kind: StationKind
    code: str | None = None  # e.g. IATA code for airports


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    id: str
    name: str
    is_demo: bool
    attribution: str
    # Hosts that booking redirects may point to. Empty => booking redirects disabled.
    booking_hosts: frozenset[str] = frozenset()
    website: str | None = None


@dataclass(frozen=True, slots=True)
class Departure:
    """A single provider-reported service instance between two stations."""

    id: str  # provider-scoped, URL-safe
    provider_id: str
    service_code: str
    operator_name: str
    mode: TransportMode
    origin_station_id: str
    destination_station_id: str
    schedule_type: ScheduleType
    duration_minutes: int
    departure_utc: datetime | None  # None for on-demand services
    arrival_utc: datetime | None
    retrieved_at: datetime  # when T-Port obtained this record from the provider
    source_updated_at: datetime | None  # when the provider says the data was last updated


@dataclass(frozen=True, slots=True)
class Offer:
    id: str
    provider_id: str
    departure_id: str
    fare_name: str
    price: Decimal
    currency: str
    retrieved_at: datetime
    source_updated_at: datetime | None = None
    is_estimate: bool = False
    price_max: Decimal | None = None  # upper bound when the price is an estimate range
    booking_url: str | None = None


@dataclass(frozen=True, slots=True)
class Leg:
    departure: Departure
    origin: Station
    destination: Station
    offers: tuple[Offer, ...]
    freshness: Freshness


@dataclass(frozen=True, slots=True)
class Journey:
    id: str
    legs: tuple[Leg, ...]
    price: Decimal  # lowest available total fare
    price_max: Decimal | None
    currency: str
    is_price_estimate: bool
    travel_minutes: int  # sum of in-vehicle time
    total_minutes: int  # first departure to last arrival, including transfers
    freshness: Freshness
    is_demo: bool
    booking_url: str | None
    notes: tuple[str, ...] = field(default_factory=tuple)
    # One entry per connection (len == len(legs) - 1); see app.services.transfers.TransferCheck.
    transfer_checks: tuple = field(default_factory=tuple)

    @property
    def modes(self) -> tuple[TransportMode, ...]:
        return tuple(dict.fromkeys(leg.departure.mode for leg in self.legs))

    @property
    def transfers(self) -> int:
        return max(len(self.legs) - 1, 0)

    @property
    def departure_utc(self) -> datetime | None:
        return self.legs[0].departure.departure_utc

    @property
    def arrival_utc(self) -> datetime | None:
        return self.legs[-1].departure.arrival_utc
