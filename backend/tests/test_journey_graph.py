"""Journey graph: bounded multi-transfer routing, chronology, overnight legs, time zones."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.journey_graph import GraphLimits, JourneyGraph
from app.services.search import SearchQuery, SearchService
from app.services.transfers import check_connection
from tests.conftest import POLICY, TOMORROW

TZ = ZoneInfo("Asia/Tashkent")


def _svc(catalog, clock, demo, **kw):
    return SearchService(catalog, [demo], clock, POLICY, **kw)


def _search(svc, origin, destination, day=TOMORROW, **q):
    return asyncio.run(svc.search(SearchQuery(origin, destination, day, page_size=50, **q)))


def test_location_paths_are_simple_bounded_and_sorted():
    g = JourneyGraph([("a", "b"), ("b", "c"), ("c", "d"), ("a", "c"), ("b", "a"), ("c", "b"), ("b", "d")])
    paths = g.location_paths("a", "d", GraphLimits(max_legs=3))
    assert paths == [("a", "b", "d"), ("a", "c", "d"), ("a", "b", "c", "d"), ("a", "c", "b", "d")]
    assert all(len(set(p)) == len(p) for p in paths)  # no revisited locations
    assert g.location_paths("a", "d", GraphLimits(max_legs=2)) == [("a", "b", "d"), ("a", "c", "d")]
    assert len(g.location_paths("a", "d", GraphLimits(max_legs=3, max_paths=1))) == 1


def test_graph_uses_only_served_routes(demo):
    g = JourneyGraph.from_providers([demo])
    assert ("tashkent", "samarkand") in {(a, b) for a in g.adj for b in g.adj[a]}
    assert "termez" not in g.adj.get("khiva", set())  # no direct Khiva->Termez service in the data


def _assert_chronology(journey, catalog):
    legs = [leg.departure for leg in journey.legs]
    for a, b in zip(legs, legs[1:], strict=False):
        assert a.arrival_utc < b.departure_utc
        check = check_connection(a, b, catalog, POLICY_TRANSFER)  # re-validates every connection
        assert check.connection_minutes >= check.minimum_minutes
    assert journey.total_minutes == int((legs[-1].arrival_utc - legs[0].departure_utc).total_seconds() // 60)
    assert journey.travel_minutes == sum(d.duration_minutes for d in legs)


from app.services.transfers import TransferPolicy  # noqa: E402

POLICY_TRANSFER = TransferPolicy()


def test_two_transfer_journeys_are_feasible(catalog, clock, demo):
    one = _search(_svc(catalog, clock, demo), "samarkand", "khiva", max_transfers=1)
    two = _search(_svc(catalog, clock, demo), "samarkand", "khiva", max_transfers=2)
    assert max(j.transfers for j in two.journeys) == 2
    assert max(j.transfers for j in one.journeys) <= 1
    for j in two.journeys:
        if j.transfers:
            _assert_chronology(j, catalog)
            stops = [leg.origin.location_id for leg in j.legs] + [j.legs[-1].destination.location_id]
            assert len(set(stops)) == len(stops)


def test_overnight_leg_connects_next_morning(catalog, clock, demo):
    # Regional night train Tashkent 20:30 -> Bukhara 06:30 (+1), then Bukhara -> Khiva on the next day.
    r = _search(_svc(catalog, clock, demo), "tashkent", "khiva", max_transfers=1)
    overnight = [
        j
        for j in r.journeys
        if j.transfers == 1
        and j.legs[0].departure.departure_utc.astimezone(TZ).date() == TOMORROW
        and j.legs[1].departure.departure_utc.astimezone(TZ).date() == TOMORROW + timedelta(days=1)
    ]
    assert overnight, "expected a connection continuing the morning after an overnight leg"
    for j in overnight:
        _assert_chronology(j, catalog)


def test_local_dates_drive_the_search_not_utc(catalog, clock, demo):
    # 06:10 local on the travel date is 01:10 UTC: still the requested local date.
    r = _search(_svc(catalog, clock, demo), "tashkent", "samarkand", max_transfers=0, sort="departure")
    first = r.journeys[0].legs[0].departure
    assert first.departure_utc.astimezone(TZ).date() == TOMORROW
    assert first.departure_utc.astimezone(TZ).strftime("%H:%M") == "06:10"


def test_results_are_reproducible(catalog, clock, demo):
    a = [j.id for j in _search(_svc(catalog, clock, demo), "samarkand", "termez", max_transfers=2).journeys]
    b = [j.id for j in _search(_svc(catalog, clock, demo), "samarkand", "termez", max_transfers=2).journeys]
    assert a == b and a


def test_search_expansion_is_bounded(catalog, clock, demo):
    tiny = GraphLimits(max_legs=3, max_paths=1, per_step=1, max_candidates=1)
    r = _search(_svc(catalog, clock, demo, graph_limits=tiny), "samarkand", "khiva", max_transfers=2)
    assert sum(1 for j in r.journeys if j.transfers) <= 1


def test_invalid_max_transfers_rejected(catalog, clock, demo):
    from app.core.errors import ValidationFailed

    with pytest.raises(ValidationFailed):
        _search(_svc(catalog, clock, demo), "tashkent", "khiva", max_transfers=3)


def test_api_accepts_two_transfers(client):
    r = client.get(
        "/api/v1/journeys/search",
        params={
            "origin": "samarkand",
            "destination": "khiva",
            "date": TOMORROW.isoformat(),
            "max_transfers": 2,
        },
    )
    assert r.status_code == 200 and max(j["transfers"] for j in r.json()["items"]) <= 2
    multi = next(j for j in r.json()["items"] if j["transfers"] >= 1)
    assert client.get(f"/api/v1/journeys/{multi['id']}").status_code == 200
    assert (
        client.get(
            "/api/v1/journeys/search",
            params={
                "origin": "samarkand",
                "destination": "khiva",
                "date": TOMORROW.isoformat(),
                "max_transfers": 3,
            },
        ).status_code
        == 422
    )
