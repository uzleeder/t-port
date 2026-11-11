"""Transfer feasibility rules (pure functions, no I/O).

A connection between two scheduled legs is accepted only when:
* both legs have fixed times (on-demand services can't be chronologically checked),
* the first leg ends in the same city where the second starts,
* the second leg departs after the first arrives plus a minimum connection time
  (larger when changing stations, larger again before a flight),
* the wait does not exceed a maximum.

Border crossings are never assumed: a connection whose legs enter another
country is rejected because no crossing-time data exists. Self-made
connections are never marked as guaranteed — tickets are separate and a
delay on the first leg is not protected.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Departure, ScheduleType, TransportMode
from app.services.catalog import LocationCatalog


@dataclass(frozen=True, slots=True)
class TransferPolicy:
    same_station_minutes: int = 20
    station_change_minutes: int = 60
    before_flight_minutes: int = 120
    max_wait_minutes: int = 360


@dataclass(frozen=True, slots=True)
class TransferCheck:
    at_location_id: str
    from_station_id: str
    to_station_id: str
    connection_minutes: int
    minimum_minutes: int
    station_change: bool
    guaranteed: bool = False  # only true for through-ticketed connections (none in Phase 1)


class InfeasibleTransfer(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def minimum_connection(policy: TransferPolicy, station_change: bool, next_mode: TransportMode) -> int:
    base = policy.station_change_minutes if station_change else policy.same_station_minutes
    if next_mode == TransportMode.FLIGHT:
        base = max(base, policy.before_flight_minutes)
    return base


def check_connection(
    first: Departure, second: Departure, catalog: LocationCatalog, policy: TransferPolicy
) -> TransferCheck:
    if ScheduleType.ON_DEMAND in (first.schedule_type, second.schedule_type):
        raise InfeasibleTransfer("on_demand_leg")
    if first.arrival_utc is None or second.departure_utc is None:
        raise InfeasibleTransfer("missing_times")
    arrive = catalog.station(first.destination_station_id)
    depart = catalog.station(second.origin_station_id)
    if arrive is None or depart is None:
        raise InfeasibleTransfer("unknown_station")
    if arrive.location_id != depart.location_id:
        raise InfeasibleTransfer("different_city")
    end = catalog.station(second.destination_station_id)
    start = catalog.station(first.origin_station_id)
    countries = {
        (catalog.get(s.location_id).country_code if s and catalog.get(s.location_id) else None)
        for s in (start, arrive, end)
    }
    if len(countries) != 1 or None in countries:
        raise InfeasibleTransfer("border_crossing_unknown")

    station_change = arrive.id != depart.id
    wait = int((second.departure_utc - first.arrival_utc).total_seconds() // 60)
    minimum = minimum_connection(policy, station_change, second.mode)
    if wait < minimum:
        raise InfeasibleTransfer("too_short" if wait >= 0 else "departs_before_arrival")
    if wait > policy.max_wait_minutes:
        raise InfeasibleTransfer("wait_too_long")
    return TransferCheck(
        at_location_id=arrive.location_id,
        from_station_id=arrive.id,
        to_station_id=depart.id,
        connection_minutes=wait,
        minimum_minutes=minimum,
        station_change=station_change,
    )
