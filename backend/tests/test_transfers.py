"""Transfer feasibility and multimodal journey composition."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import NotFound
from app.domain.models import Departure, ScheduleType, TransportMode
from app.services.search import SearchQuery
from app.services.transfers import InfeasibleTransfer, TransferPolicy, check_connection
from tests.conftest import NOW, TOMORROW

POLICY = TransferPolicy(
    same_station_minutes=20, station_change_minutes=60, before_flight_minutes=120, max_wait_minutes=360
)
T0 = datetime(2026, 11, 12, 4, 0, tzinfo=UTC)


def leg(origin, dest, depart: datetime | None, minutes=60, mode=TransportMode.TRAIN) -> Departure:
    return Departure(
        id=f"{origin}-{dest}",
        provider_id="demo",
        service_code="X",
        operator_name="Op",
        mode=mode,
        origin_station_id=origin,
        destination_station_id=dest,
        schedule_type=ScheduleType.SCHEDULED if depart else ScheduleType.ON_DEMAND,
        duration_minutes=minutes,
        departure_utc=depart,
        arrival_utc=depart + timedelta(minutes=minutes) if depart else None,
        retrieved_at=NOW,
        source_updated_at=None,
    )


def test_same_station_connection(catalog):
    a = leg("tashkent-rail", "samarkand-rail", T0, 120)
    b = leg("samarkand-rail", "bukhara-rail", T0 + timedelta(minutes=145))
    check = check_connection(a, b, catalog, POLICY)
    assert check.connection_minutes == 25 and check.minimum_minutes == 20
    assert not check.station_change and not check.guaranteed


@pytest.mark.parametrize(
    ("second", "reason"),
    [
        (leg("samarkand-rail", "bukhara-rail", T0 + timedelta(minutes=130)), "too_short"),
        (leg("samarkand-rail", "bukhara-rail", T0 + timedelta(minutes=60)), "departs_before_arrival"),
        (
            leg("samarkand-bus", "bukhara-bus", T0 + timedelta(minutes=150), mode=TransportMode.BUS),
            "too_short",
        ),
        (
            leg("samarkand-air", "bukhara-air", T0 + timedelta(minutes=200), mode=TransportMode.FLIGHT),
            "too_short",
        ),
        (leg("samarkand-rail", "bukhara-rail", T0 + timedelta(hours=9)), "wait_too_long"),
        (leg("bukhara-rail", "khiva-rail", T0 + timedelta(hours=3)), "different_city"),
        (leg("samarkand-city", "bukhara-city", None, mode=TransportMode.TAXI), "on_demand_leg"),
        (leg("samarkand-rail", "nowhere", T0 + timedelta(hours=3)), "border_crossing_unknown"),
    ],
)
def test_invalid_connections(catalog, second, reason):
    first = leg("tashkent-rail", "samarkand-rail", T0, 120)
    with pytest.raises(InfeasibleTransfer) as exc:
        check_connection(first, second, catalog, POLICY)
    assert exc.value.reason == reason


def test_station_change_and_flight_minimums(catalog):
    a = leg("tashkent-rail", "samarkand-rail", T0, 120)
    bus = leg("samarkand-bus", "bukhara-bus", T0 + timedelta(minutes=180), mode=TransportMode.BUS)
    assert check_connection(a, bus, catalog, POLICY).station_change
    flight = leg("samarkand-air", "bukhara-air", T0 + timedelta(minutes=240), mode=TransportMode.FLIGHT)
    assert check_connection(a, flight, catalog, POLICY).minimum_minutes == 120


def _search(service, **kw):
    base = dict(origin_id="samarkand", destination_id="termez", travel_date=TOMORROW + timedelta(days=1))
    base.update(kw)
    return asyncio.run(service.search(SearchQuery(**base)))


def test_search_composes_feasible_transfer_journeys(service):
    result = _search(service)
    assert result.total > 0
    for j in result.journeys:
        assert j.transfers == 1 and len(j.transfer_checks) == 1 and j.booking_url is None
        a, b = j.legs[0].departure, j.legs[1].departure
        assert a.arrival_utc <= b.departure_utc - timedelta(minutes=j.transfer_checks[0].minimum_minutes)
        assert j.legs[0].destination.location_id == j.legs[1].origin.location_id
        assert j.travel_minutes == a.duration_minutes + b.duration_minutes
        assert j.total_minutes == int((b.arrival_utc - a.departure_utc).total_seconds() // 60)
        assert j.total_minutes >= j.travel_minutes
        assert j.price > 0
        assert any("not guaranteed" in n for n in j.notes)


def test_transfer_price_is_sum_of_leg_fares(service):
    j = _search(service).journeys[0]
    assert j.price == sum(min(o.price for o in leg.offers) for leg in j.legs)


def test_direct_only_flag(service):
    assert _search(service, max_transfers=0).total == 0
    assert _search(service, origin_id="tashkent", destination_id="samarkand").journeys[0].transfers == 0


def test_dominated_connections_are_hidden(service):
    # Tashkent->Bukhara has fast direct options; no connection should be both slower and pricier than one.
    r = _search(service, origin_id="tashkent", destination_id="bukhara", travel_date=TOMORROW, page_size=50)
    direct = [j for j in r.journeys if j.transfers == 0]
    for c in (j for j in r.journeys if j.transfers):
        assert not any(d.price <= c.price and d.total_minutes <= c.total_minutes for d in direct)


def test_multi_leg_journey_detail_roundtrip(service):
    j = _search(service).journeys[0]
    again, origin, destination = asyncio.run(service.get_journey(j.id))
    assert (
        again.id == j.id and again.price == j.price and (origin.id, destination.id) == ("samarkand", "termez")
    )


@pytest.mark.parametrize(
    "bad",
    [
        "x~demo:TR101.20261112",
        "x~demo:ZZ999.20261112+demo:TR101.20261112",
        "x~demo:TR101.20261112+demo:BU131.20261112",  # not a connection (different cities)
        "x~nope:TR101.20261112+demo:TR101.20261112",
        "x~" + "a" * 200,
    ],
)
def test_invalid_multi_leg_ids(service, bad):
    with pytest.raises(NotFound):
        asyncio.run(service.get_journey(bad))


def test_transfer_journeys_via_api(client):
    r = client.get(
        "/api/v1/journeys/search",
        params={"origin": "samarkand", "destination": "termez", "date": "2026-11-13"},
    )
    item = r.json()["items"][0]
    check = item["transfer_checks"][0]
    assert check["guaranteed"] is False and check["connection_minutes"] >= check["minimum_minutes"]
    assert client.get(f"/api/v1/journeys/{item['id']}").status_code == 200
    assert (
        client.get(
            "/api/v1/journeys/search",
            params={"origin": "samarkand", "destination": "termez", "date": "2026-11-13", "max_transfers": 3},
        ).status_code
        == 422
    )
