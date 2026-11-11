"""Freshness engine: per-type policies, UNKNOWN, price types, booking eligibility, attribution."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.clock import FixedClock
from app.domain.models import Freshness, PriceType
from app.providers.registry import DEMO_CONTRACT
from app.services.freshness import FreshnessPolicy, SourcePolicy, worst
from app.services.search import SearchQuery, SearchService
from tests.conftest import NOW, SYNTH_CONTRACT, TOMORROW, FakeAdapter, dep, offer

GLOBAL = FreshnessPolicy(timedelta(minutes=15), timedelta(hours=6))
HOUR = timedelta(hours=1)


def _search(adapters, clock, policies, **q):
    svc = SearchService(_catalog(), adapters, clock, GLOBAL, freshness_by_provider=policies)
    return asyncio.run(svc.search(SearchQuery("tashkent", "samarkand", TOMORROW, **q)))


def _catalog():
    from app.data.reference import LOCATIONS, STATIONS
    from app.services.catalog import LocationCatalog

    return LocationCatalog(LOCATIONS, STATIONS)


def _real(departures, offers):
    """FakeAdapter serving the given records as the (non-demo) synthrail provider."""
    departures = [replace(d, provider_id="synthrail") for d in departures]
    offers = [replace(o, provider_id="synthrail") for o in offers]
    a = FakeAdapter(
        departures, offers, provider_id="synthrail", booking_hosts=frozenset({"tickets.synthrail.test"})
    )
    a.info = SYNTH_CONTRACT.info
    return a


def test_unknown_freshness():
    assert FreshnessPolicy(HOUR, 2 * HOUR).assess(None, NOW) == Freshness.UNKNOWN
    assert worst(Freshness.STALE, Freshness.UNKNOWN) == Freshness.UNKNOWN
    assert worst(Freshness.UNKNOWN, Freshness.EXPIRED) == Freshness.EXPIRED


def test_price_ages_faster_than_timetable():
    policy = SourcePolicy(
        FreshnessPolicy(timedelta(days=1), timedelta(days=7)),
        FreshnessPolicy(timedelta(minutes=10), timedelta(hours=2)),
        live_prices=True,
    )
    old = NOW - timedelta(minutes=30)
    r = _search(
        [_real([dep("A", retrieved_at=old)], [offer("A", 100, retrieved_at=old)])],
        FixedClock(NOW),
        {"synthrail": policy},
        max_transfers=0,
    )
    leg = r.journeys[0].legs[0]
    assert leg.timetable_freshness == Freshness.FRESH and leg.price_freshness == Freshness.STALE
    assert r.journeys[0].freshness == Freshness.STALE
    assert leg.price_type == PriceType.INDICATIVE  # live price no longer fresh => not "confirmed"

    expired = _search(
        [_real([dep("A", retrieved_at=NOW - 3 * HOUR)], [offer("A", 100, retrieved_at=NOW - 3 * HOUR)])],
        FixedClock(NOW),
        {"synthrail": policy},
        max_transfers=0,
    )
    assert expired.total == 0 and expired.excluded.expired_data == 1  # an expired price is never shown


def test_confirmed_only_for_fresh_live_prices():
    live = SourcePolicy(GLOBAL, GLOBAL, live_prices=True)
    published = SourcePolicy(GLOBAL, GLOBAL, live_prices=False)
    data = ([dep("A")], [offer("A", 100, booking_url="https://tickets.synthrail.test/a")])
    assert (
        _search([_real(*data)], FixedClock(NOW), {"synthrail": live}, max_transfers=0).journeys[0].price_type
        == PriceType.CONFIRMED
    )
    assert (
        _search([_real(*data)], FixedClock(NOW), {"synthrail": published}, max_transfers=0)
        .journeys[0]
        .price_type
        == PriceType.INDICATIVE
    )


def test_unknown_source_timestamp_is_labelled_not_hidden():
    by_source = SourcePolicy(GLOBAL, GLOBAL, basis="source_updated_at")
    r = _search(
        [_real([dep("A")], [offer("A", 100, booking_url="https://tickets.synthrail.test/a")])],
        FixedClock(NOW),
        {"synthrail": by_source},
        max_transfers=0,
    )
    j = r.journeys[0]
    assert j.freshness == Freshness.UNKNOWN and any("did not say" in n for n in j.notes)
    assert j.booking_url is None and "out of date" in j.booking_note  # unknown price age: no booking link


def test_booking_link_requires_fresh_price():
    policy = SourcePolicy(GLOBAL, GLOBAL)

    def data(ts):
        return (
            [dep("A", retrieved_at=ts)],
            [
                offer(
                    "A",
                    100,
                    retrieved_at=ts,
                    booking_url="https://tickets.synthrail.test/a",
                )
            ],
        )

    fresh = _search([_real(*data(NOW))], FixedClock(NOW), {"synthrail": policy}, max_transfers=0).journeys[0]
    stale = _search(
        [_real(*data(NOW - HOUR))], FixedClock(NOW), {"synthrail": policy}, max_transfers=0
    ).journeys[0]
    assert fresh.booking_url and fresh.booking_note is None
    assert stale.booking_url is None and "out of date" in stale.booking_note
    lenient = replace(policy, booking_requires_fresh_price=False)
    assert (
        _search([_real(*data(NOW - HOUR))], FixedClock(NOW), {"synthrail": lenient}, max_transfers=0)
        .journeys[0]
        .booking_url
    )


def test_demo_journeys_never_get_booking_and_say_why(demo, clock):
    r = _search([demo], clock, {"demo": SourcePolicy.from_contract(DEMO_CONTRACT)})
    assert r.journeys and all(j.booking_url is None and j.booking_note for j in r.journeys)
    assert {j.price_type for j in r.journeys} == {PriceType.DEMO}


def test_demo_and_real_legs_are_never_combined(demo, clock, synth):
    svc = SearchService(
        _catalog(),
        [demo, synth],
        clock,
        GLOBAL,
        freshness_by_provider={
            "demo": SourcePolicy.from_contract(DEMO_CONTRACT),
            "synthrail": SourcePolicy.from_contract(SYNTH_CONTRACT),
        },
    )
    r = asyncio.run(
        svc.search(SearchQuery("tashkent", "bukhara", TOMORROW + timedelta(days=1), page_size=50))
    )
    for j in r.journeys:
        assert len({leg.provider.is_demo for leg in j.legs}) == 1
        assert j.is_demo == any(leg.provider.is_demo for leg in j.legs)


def test_mixed_status_connection_takes_weakest():
    a = _real(
        [
            dep("A"),
            replace(
                dep("B", depart=NOW + timedelta(days=1, hours=1), retrieved_at=NOW - HOUR),
                origin_station_id="samarkand-rail",
                destination_station_id="bukhara-rail",
                id="B",
            ),
        ],
        [offer("A", 100), offer("B", 50, retrieved_at=NOW - HOUR)],
    )
    a.supported_location_ids = lambda: frozenset({"tashkent", "samarkand", "bukhara"})
    svc = SearchService(
        _catalog(),
        [a],
        FixedClock(NOW),
        GLOBAL,
        freshness_by_provider={"synthrail": SourcePolicy(GLOBAL, GLOBAL, live_prices=True)},
    )
    j = asyncio.run(svc.get_journey("x~synthrail:A+synthrail:B"))[0]
    assert [leg.price_type for leg in j.legs] == [PriceType.CONFIRMED, PriceType.INDICATIVE]
    assert j.price_type == PriceType.INDICATIVE and j.freshness == Freshness.STALE and j.booking_url is None


def test_api_exposes_status_attribution_and_booking_reason(client):
    body = client.get(
        "/api/v1/journeys/search",
        params={
            "origin": "tashkent",
            "destination": "samarkand",
            "date": TOMORROW.isoformat(),
            "max_transfers": 0,
        },
    ).json()
    j = body["items"][0]
    leg = j["legs"][0]
    assert j["price_type"] == "demo" and j["booking_url"] is None and "Demo" in j["booking_note"]
    assert (
        leg["provider"]["id"] == "demo"
        and leg["provider"]["is_demo"] is True
        and leg["provider"]["attribution"]
    )
    assert {leg["timetable_freshness"], leg["price_freshness"]} <= {"fresh", "stale", "unknown"}
    assert j["freshness"] in ("fresh", "stale", "unknown")  # field kept for backward compatibility


def test_contract_policies_are_used_by_the_app(app_factory, demo, synth):
    with TestClient(app_factory(providers=[demo, synth], contracts=[DEMO_CONTRACT, SYNTH_CONTRACT])) as c:
        svc = c.app.state.search
    sp = svc.source_policy("synthrail")
    assert sp.timetable.stale_after == SYNTH_CONTRACT.stale_after and sp.live_prices is False
    assert svc.source_policy("unknown-provider").timetable.stale_after == timedelta(minutes=15)


# -- fault simulation (dev/test only) ----------------------------------------------------------
def _sim_search(c, simulate):
    return c.get(
        "/api/v1/journeys/search",
        params={
            "origin": "tashkent",
            "destination": "samarkand",
            "date": TOMORROW.isoformat(),
            "simulate": simulate,
        },
    ).json()


def test_simulation_is_ignored_unless_enabled(client):
    body = _sim_search(client, "stale,outage")
    assert all(s["ok"] for s in body["sources"]) and {j["freshness"] for j in body["items"]} == {"fresh"}


def test_simulated_stale_and_outage(app_factory, settings):
    sim = settings.model_copy(update={"enable_fault_simulation": True})
    with TestClient(app_factory(settings=sim)) as c:
        stale = _sim_search(c, "stale")
        outage = _sim_search(c, "outage")
        normal = _sim_search(c, "")
        real_stats = c.app.state.search.stats
    assert {j["freshness"] for j in stale["items"]} == {"stale"}
    assert any("out of date" in w for w in stale["warnings"])
    failed = [s for s in outage["sources"] if not s["ok"]]
    assert failed and failed[0]["provider"]["is_demo"] and outage["total"] > 0
    assert any("temporarily unavailable" in w for w in outage["warnings"])
    assert all(s["ok"] for s in normal["sources"]) and "demo-outage" not in real_stats


def test_fault_simulation_forbidden_in_production():
    import pytest

    from app.core.config import Settings

    with pytest.raises(ValueError, match="FAULT_SIMULATION"):
        Settings(
            environment="production",
            cors_origins=["https://tport.example"],
            database_url="postgresql+psycopg://a:b@db/x",
            enable_fault_simulation=True,
        )
