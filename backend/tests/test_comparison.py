"""Journey comparison: best-per-criterion, ties, caveats, availability, validation, filters."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import time
from decimal import Decimal

from app.domain.models import Freshness, PriceType
from app.services.comparison import compare
from app.services.search import SearchQuery, SearchService
from tests.conftest import POLICY, TOMORROW

SEARCH = "/api/v1/journeys/search"
COMPARE = "/api/v1/journeys/compare"


def _journeys(catalog, clock, demo, n=3):
    svc = SearchService(catalog, [demo], clock, POLICY)
    q = SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0, page_size=50)
    return asyncio.run(svc.search(q)).journeys[:n]


def test_best_per_criterion_with_ties(catalog, clock, demo):
    a, b, c = _journeys(catalog, clock, demo)
    a = replace(a, id="a", price=Decimal(100), total_minutes=300)
    b = replace(b, id="b", price=Decimal(100), total_minutes=200)
    c = replace(c, id="c", price=Decimal(300), total_minutes=200)
    result = compare([a, b, c])
    assert result.cheapest == ["a", "b"]  # tie: both reported
    assert result.fastest == ["b", "c"]
    assert result.fewest_transfers == ["a", "b", "c"]
    assert len(result.earliest_departure) >= 1


def test_caveats(catalog, clock, demo):
    a, b = _journeys(catalog, clock, demo, 2)
    estimated = replace(a, price_type=PriceType.ESTIMATED)
    mixed = compare([estimated, replace(b, price_type=PriceType.INDICATIVE)])
    assert any("lower end" in c for c in mixed.caveats)
    assert any("Demonstration" in c for c in compare([a, b]).caveats)
    stale = compare([replace(a, freshness=Freshness.STALE), b])
    assert any("refreshed" in c for c in stale.caveats)
    other_currency = compare([a, replace(b, currency="USD")])
    assert other_currency.cheapest == [] and any("currencies" in c for c in other_currency.caveats)
    assert compare([a]).cheapest == []  # a single journey has nothing to be compared with


def _search_ids(client, **params):
    base = {"origin": "tashkent", "destination": "samarkand", "date": TOMORROW.isoformat()}
    return client.get(SEARCH, params={**base, **params}).json()["items"]


def test_compare_endpoint_matches_journey_data(client):
    items = _search_ids(client, max_transfers=0)[:3]
    r = client.get(COMPARE, params={"ids": ",".join(j["id"] for j in items)})
    body = r.json()
    assert r.status_code == 200 and [i["id"] for i in body["items"]] == [j["id"] for j in items]
    assert all(i["available"] and i["journey"]["id"] == i["id"] for i in body["items"])
    prices = {i["id"]: Decimal(i["journey"]["price"]) for i in body["items"]}
    assert set(body["best"]["cheapest"]) == {k for k, v in prices.items() if v == min(prices.values())}
    minutes = {i["id"]: i["journey"]["total_minutes"] for i in body["items"]}
    assert set(body["best"]["fastest"]) == {k for k, v in minutes.items() if v == min(minutes.values())}
    assert any("Demonstration" in c for c in body["caveats"])


def test_compare_multi_leg_and_unavailable(client):
    items = client.get(
        SEARCH,
        params={
            "origin": "samarkand",
            "destination": "khiva",
            "date": TOMORROW.isoformat(),
            "max_transfers": 2,
        },
    ).json()["items"]
    multi = next(j for j in items if j["transfers"] >= 1)
    direct_or_other = next(j for j in items if j["id"] != multi["id"])
    ids = [multi["id"], direct_or_other["id"], "demo:does-not-exist"]
    body = client.get(COMPARE, params={"ids": ",".join(ids)}).json()
    by_id = {i["id"]: i for i in body["items"]}
    assert by_id[multi["id"]]["available"] and by_id[multi["id"]]["journey"]["transfers"] >= 1
    missing = by_id["demo:does-not-exist"]
    assert not missing["available"] and missing["reason"] and missing["journey"] is None
    assert "demo:does-not-exist" not in sum(body["best"].values(), [])


def test_compare_validation(client):
    one = _search_ids(client)[0]["id"]
    assert client.get(COMPARE, params={"ids": one}).status_code == 422
    assert client.get(COMPARE, params={"ids": f"{one},{one}"}).status_code == 422  # duplicates collapse
    assert client.get(COMPARE, params={"ids": ",".join(f"demo:x{i}" for i in range(5))}).status_code == 422
    assert client.get(COMPARE, params={"ids": f"{one},{'x' * 200}"}).status_code == 422
    assert client.get(COMPARE).status_code == 422
    # The literal path segment is not mistaken for a journey ID.
    assert client.get("/api/v1/journeys/compare", params={"ids": ""}).status_code == 422


def test_search_filters_for_comparison(client):
    direct = _search_ids(client, max_transfers=0, page_size=50)
    assert direct and all(j["transfers"] == 0 for j in direct)
    cap = sorted(Decimal(j["price"]) for j in direct)[len(direct) // 2]
    cheap = _search_ids(client, max_price=str(cap), page_size=50)
    assert cheap and all(Decimal(j["price"]) <= cap for j in cheap)
    early = _search_ids(client, arrive_before="12:00", page_size=50)
    for j in early:
        assert j["arrival_utc"] is not None
        assert time.fromisoformat(j["legs"][-1]["arrival_local"][11:16]) <= time(12, 0)
