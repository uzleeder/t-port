"""Route optimisation: Pareto filtering, sorts, preferences, arrival deadlines."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import time
from decimal import Decimal

from app.domain.models import TransportMode
from app.services.route_optimizer import dominates, pareto_front, preference_bonus
from app.services.search import SearchQuery, SearchService, SortKey, rank
from tests.conftest import POLICY, TOMORROW


def _j(base, jid, price, minutes, legs=1):
    return replace(base, id=jid, price=Decimal(price), total_minutes=minutes, legs=base.legs * legs)


def _base(catalog, clock, demo):
    svc = SearchService(catalog, [demo], clock, POLICY)
    return asyncio.run(svc.search(SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0))).journeys[
        0
    ]


def test_dominance_and_pareto(catalog, clock, demo):
    b = _base(catalog, clock, demo)
    cheap_slow, fast_dear, worse, twin = (
        _j(b, "a", 100, 300),
        _j(b, "b", 300, 100),
        _j(b, "c", 300, 300),
        _j(b, "d", 100, 300),
    )
    two_legs = _j(b, "e", 100, 300, legs=2)  # same price/time as a but one more transfer
    assert dominates(cheap_slow, worse) and not dominates(cheap_slow, fast_dear)
    assert dominates(cheap_slow, two_legs)
    front = pareto_front([cheap_slow, fast_dear, worse, twin, two_legs])
    assert [j.id for j in front] == ["a", "b", "d"]  # ties kept, dominated removed, order preserved
    assert pareto_front([worse], against=[cheap_slow]) == []


def test_fewest_transfers_sort(catalog, clock, demo):
    b = _base(catalog, clock, demo)
    direct_slow, change_fast = _j(b, "a", 200, 500), _j(b, "b", 100, 200, legs=2)
    assert [j.id for j in rank([change_fast, direct_slow], SortKey.TRANSFERS)] == ["a", "b"]


def test_preferred_modes_shift_recommendations(catalog, clock, demo):
    svc = SearchService(catalog, [demo], clock, POLICY)
    q = SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0, page_size=50)
    plain = asyncio.run(svc.search(q)).journeys
    bus_first = asyncio.run(svc.search(replace(q, prefer_modes=frozenset({TransportMode.BUS})))).journeys
    assert sorted(j.id for j in plain) == sorted(j.id for j in bus_first)  # same results, different order
    assert bus_first[0].modes == (TransportMode.BUS,)
    assert preference_bonus(bus_first[0], frozenset({TransportMode.BUS})) == Decimal("0.25")
    assert preference_bonus(bus_first[0], frozenset()) == 0


def test_arrival_deadline(catalog, clock, demo):
    svc = SearchService(catalog, [demo], clock, POLICY)
    r = asyncio.run(
        svc.search(SearchQuery("tashkent", "bukhara", TOMORROW, arrive_before=time(12, 0), page_size=50))
    )
    assert r.total > 0 and r.excluded.outside_time_window > 0
    for j in r.journeys:
        local = j.arrival_utc.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Tashkent"))
        assert local.date() == TOMORROW and local.time() <= time(12, 0)
    # Taxis (no fixed arrival time) can't promise a deadline and are excluded.
    assert all(j.arrival_utc is not None for j in r.journeys)


def test_api_sort_and_filters(client):
    params = {"origin": "tashkent", "destination": "bukhara", "date": TOMORROW.isoformat()}
    r = client.get("/api/v1/journeys/search", params={**params, "sort": "transfers", "max_transfers": 2})
    transfers = [j["transfers"] for j in r.json()["items"]]
    assert transfers == sorted(transfers)
    r = client.get(
        "/api/v1/journeys/search", params={**params, "arrive_before": "12:00", "prefer_modes": "bus"}
    )
    body = r.json()
    assert (
        r.status_code == 200
        and body["query"]["arrive_before"] == "12:00"
        and body["query"]["prefer_modes"] == ["bus"]
    )
    assert (
        client.get("/api/v1/journeys/search", params={**params, "prefer_modes": "rocket"}).status_code == 422
    )
