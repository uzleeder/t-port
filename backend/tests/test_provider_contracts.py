"""Provider contracts: enablement rules, conformance checks, feed adapter, mixed sources."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.domain.models import Departure, Offer, ScheduleType, TransportMode
from app.providers.contracts import check_conformance, contract_problems, validate_records
from app.providers.feed import FeedAdapter, FeedError
from app.providers.registry import DEMO_CONTRACT, enabled_contracts
from app.services.freshness import FreshnessPolicy
from app.services.search import SearchQuery, SearchService
from tests.conftest import (
    NOW,
    SYNTH_CONTRACT,
    SYNTH_INFO,
    TODAY,
    TOMORROW,
    FakeAdapter,
    dep,
    synth_feed,
)

run = asyncio.run


def _auth(**kw):
    return replace(SYNTH_CONTRACT, authorization=replace(SYNTH_CONTRACT.authorization, **kw))


# -- enablement ---------------------------------------------------------------------------
def test_registered_contracts_are_valid():
    assert contract_problems(DEMO_CONTRACT, TODAY) == []
    assert [c.info.id for c in enabled_contracts(TODAY)] == ["demo"]
    assert contract_problems(SYNTH_CONTRACT, TODAY) == []


@pytest.mark.parametrize(
    ("contract", "expected"),
    [
        (_auth(verified_by=None), "not been verified"),
        (_auth(expires_on=date(2026, 1, 1)), "expired"),
        (_auth(permits_price_display=False), "does not permit showing prices"),
        (_auth(reference=" "), "reference is missing"),
        (_auth(basis="internal_synthetic"), "real providers need"),
        (_auth(permits_booking_redirects=False), "redirects are not permitted"),
        (replace(SYNTH_CONTRACT, data_mapping=""), "data mapping"),
        (replace(SYNTH_CONTRACT, info=replace(SYNTH_INFO, booking_hosts=frozenset())), "no allowed hosts"),
        (replace(SYNTH_CONTRACT, expire_after=timedelta(minutes=1)), "expire_after"),
        (replace(SYNTH_CONTRACT, currency="uzs"), "ISO 4217"),
        (
            replace(
                SYNTH_CONTRACT, ingestion=replace(SYNTH_CONTRACT.ingestion, update_interval_minutes=None)
            ),
            "update_interval_minutes",
        ),
        (
            replace(DEMO_CONTRACT, info=replace(DEMO_CONTRACT.info, booking_hosts=frozenset({"x.test"}))),
            "never be bookable",
        ),
    ],
)
def test_contract_problems_block_enablement(contract, expected):
    problems = contract_problems(contract, TODAY)
    assert any(expected in p for p in problems), problems


def test_invalid_contract_keeps_provider_disabled(app_factory, monkeypatch):
    import app.main as main

    broken = replace(
        DEMO_CONTRACT, authorization=replace(DEMO_CONTRACT.authorization, permits_booking_redirects=True)
    )
    monkeypatch.setattr(main, "DEMO_CONTRACT", broken)
    with TestClient(app_factory(providers=None)) as c:
        assert c.app.state.providers == []
        r = c.get(
            "/api/v1/journeys/search",
            params={"origin": "tashkent", "destination": "samarkand", "date": TOMORROW.isoformat()},
        )
    assert r.status_code == 200 and r.json()["total"] == 0 and r.json()["sources"] == []


# -- conformance ----------------------------------------------------------------------------
def _queries(adapter, days=3):
    return [
        (o, d, TOMORROW + timedelta(days=i)) for i in range(days) for o, d in sorted(adapter.served_routes())
    ]


def test_demo_adapter_conforms(demo, catalog):
    report = run(check_conformance(demo, DEMO_CONTRACT, catalog, _queries(demo), NOW))
    assert report.ok, report.violations[:5]
    assert report.departures > 0 and report.offers >= report.departures


def test_feed_adapter_conforms(synth, catalog):
    report = run(check_conformance(synth, SYNTH_CONTRACT, catalog, _queries(synth, 7), NOW))
    assert report.ok, report.violations[:5]
    assert report.departures == 5 * 7 - 2 * 3  # SR211 and SR212 each skip Tue/Thu/Sat


def _bad(**kw) -> Departure:
    base = dict(
        id="A",
        provider_id="synthrail",
        service_code="A",
        operator_name="Op",
        mode=TransportMode.TRAIN,
        origin_station_id="tashkent-rail",
        destination_station_id="samarkand-rail",
        schedule_type=ScheduleType.SCHEDULED,
        duration_minutes=120,
        departure_utc=NOW + timedelta(days=1),
        arrival_utc=NOW + timedelta(days=1, hours=2),
        retrieved_at=NOW,
        source_updated_at=None,
    )
    base.update(kw)
    return Departure(**base)


def _offer(**kw) -> Offer:
    base = dict(
        id="A.o",
        provider_id="synthrail",
        departure_id="A",
        fare_name="Std",
        price=Decimal(100),
        currency="UZS",
        retrieved_at=NOW,
    )
    base.update(kw)
    return Offer(**base)


@pytest.mark.parametrize(
    ("departures", "offers", "code"),
    [
        ([_bad(arrival_utc=NOW + timedelta(hours=20))], [], "chronology"),
        ([_bad(duration_minutes=90)], [], "duration_mismatch"),
        ([_bad(destination_station_id="atlantis-rail")], [], "unknown_station"),
        ([_bad(destination_station_id="tashkent-bus")], [], "same_location"),
        ([_bad(provider_id="other")], [], "wrong_provider"),
        ([_bad(), _bad()], [], "duplicate_departure"),
        ([_bad(id="has space")], [], "bad_id"),
        ([_bad(mode=TransportMode.FLIGHT)], [], "undeclared_mode"),
        (
            [_bad(schedule_type=ScheduleType.ON_DEMAND, departure_utc=None, arrival_utc=None)],
            [],
            "undeclared_on_demand",
        ),
        ([_bad(departure_utc=None)], [], "missing_times"),
        ([_bad(retrieved_at=NOW + timedelta(hours=1))], [], "future_timestamp"),
        ([_bad()], [_offer(departure_id="ZZ")], "orphan_offer"),
        ([_bad()], [_offer(price=Decimal(0))], "bad_price"),
        ([_bad()], [_offer(currency="USD")], "currency"),
        ([_bad()], [_offer(price_max=Decimal(50), is_estimate=True)], "bad_price_range"),
        ([_bad()], [_offer(price_max=Decimal(150))], "range_not_estimate"),
        ([_bad()], [_offer(), _offer(id="A.o2")], "duplicate_fare"),
        ([_bad()], [_offer(booking_url="https://evil.test/x")], "booking_host"),
        ([_bad()], [_offer(booking_url="http://tickets.synthrail.test/x")], "booking_host"),
    ],
)
def test_validate_records_detects_violations(catalog, departures, offers, code):
    codes = {v.code for v in validate_records(SYNTH_CONTRACT, catalog, departures, offers, NOW)}
    assert code in codes, codes


def test_wrong_travel_date_detected(catalog):
    v = validate_records(SYNTH_CONTRACT, catalog, [_bad()], [], NOW, travel_dates={"A": TODAY})
    assert {x.code for x in v} == {"wrong_date"}


def test_demo_booking_url_is_a_violation(catalog):
    o = Offer(
        id="x",
        provider_id="demo",
        departure_id="d",
        fare_name="Std",
        price=Decimal(1),
        currency="UZS",
        retrieved_at=NOW,
        booking_url="https://example.com/",
    )
    assert "booking_not_permitted" in {v.code for v in validate_records(DEMO_CONTRACT, catalog, [], [o], NOW)}


def test_conformance_flags_misrouted_adapter(catalog):
    class Misrouted(FakeAdapter):
        async def get_departures(self, origin, destination, travel_date, modes):
            return [dep("X1", depart=NOW + timedelta(days=1))]  # always Tashkent->Samarkand

    a = Misrouted(provider_id="synthrail")
    a.info = SYNTH_INFO
    report = run(check_conformance(a, SYNTH_CONTRACT, catalog, [("samarkand", "tashkent", TOMORROW)], NOW))
    assert {"wrong_route", "wrong_provider"} <= {v.code for v in report.violations}


# -- feed loading ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "mutate",
    [
        lambda f: f["services"][0].update(depart="25:00"),
        lambda f: f["services"][0].update(mode="teleport"),
        lambda f: f["services"][0]["fares"][0].update(price="-1"),
        lambda f: f["services"][0].update(days=[7]),
        lambda f: f["services"][1].update(code=f["services"][0]["code"]),
        lambda f: f["services"][0].update(**{"from": "atlantis-rail"}),
        lambda f: f.update(generated_at="2026-11-10T00:00:00"),  # naive timestamp
        lambda f: f.update(unexpected="field"),
        lambda f: f.update(timezone="Mars/Olympus"),
    ],
)
def test_malformed_feeds_are_rejected(catalog, clock, mutate):
    feed = synth_feed()
    mutate(feed)
    with pytest.raises(FeedError):
        FeedAdapter(SYNTH_INFO, feed, catalog, clock)


# -- mixed real and demo sources ---------------------------------------------------------------
def _service(catalog, clock, *providers, overrides=None):
    return SearchService(
        catalog,
        list(providers),
        clock,
        FreshnessPolicy(timedelta(minutes=15), timedelta(hours=6)),
        freshness_by_provider=overrides,
    )


def test_mixed_sources_keep_labels_and_booking_rules(catalog, clock, demo, synth):
    r = run(_service(catalog, clock, demo, synth).search(SearchQuery("tashkent", "samarkand", TOMORROW)))
    ids = {s.provider.id for s in r.sources}
    assert ids == {"demo", "synthrail"}
    for j in r.journeys:
        if j.legs[0].departure.provider_id == "demo":
            assert j.is_demo and j.booking_url is None
        elif j.transfers == 0:
            assert not j.is_demo and j.booking_url.startswith("https://tickets.synthrail.test/")


def test_provider_specific_freshness(catalog, demo, synth):
    from app.core.clock import FixedClock

    later = FixedClock(NOW + timedelta(minutes=30))  # demo stale after 15 min, synthrail after 1 h
    svc = _service(
        catalog,
        later,
        demo,
        synth,
        overrides={"synthrail": SYNTH_CONTRACT.freshness, "demo": DEMO_CONTRACT.freshness},
    )
    # Both adapters stamped their data at NOW; 30 minutes later only demo's 15-minute policy has lapsed.
    r = run(svc.search(SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0)))
    by_provider = {}
    for j in r.journeys:
        by_provider.setdefault(j.legs[0].departure.provider_id, set()).add(j.freshness.value)
    assert by_provider == {"demo": {"stale"}, "synthrail": {"fresh"}}
    svc_late = _service(
        catalog,
        FixedClock(NOW + timedelta(hours=7)),
        synth,
        overrides={"synthrail": SYNTH_CONTRACT.freshness},
    )
    late = run(svc_late.search(SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0)))
    assert late.total > 0 and all(j.freshness.value == "stale" for j in late.journeys)
    svc_global = _service(catalog, FixedClock(NOW + timedelta(hours=7)), synth)  # global 6 h expiry
    assert run(svc_global.search(SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0))).total == 0


def test_outage_of_one_source_does_not_hide_others(catalog, clock, synth):
    broken = FakeAdapter(fail=True, provider_id="broken")
    svc = _service(catalog, clock, synth, broken)
    r = run(svc.search(SearchQuery("tashkent", "samarkand", TOMORROW)))
    assert r.total > 0 and any(not s.ok for s in r.sources)
    assert svc.stats["broken"].failures_total == 1 and svc.stats["synthrail"].failures_total == 0


def test_mixed_sources_via_api(app_factory, demo, synth):
    with TestClient(app_factory(providers=[demo, synth], contracts=[DEMO_CONTRACT, SYNTH_CONTRACT])) as c:
        body = c.get(
            "/api/v1/journeys/search",
            params={
                "origin": "tashkent",
                "destination": "samarkand",
                "date": TOMORROW.isoformat(),
                "max_transfers": 0,
            },
        ).json()
        assert body["contains_demo_data"] is True
        synth_item = next(j for j in body["items"] if j["id"].startswith("synthrail~"))
        detail = c.get(f"/api/v1/journeys/{synth_item['id']}").json()["journey"]
    assert detail["is_demo"] is False and detail["booking_url"].startswith("https://tickets.synthrail.test/")


# -- onboarding records, operations, quarantine -------------------------------------------------
@pytest.mark.parametrize(
    ("contract", "expected"),
    [
        (replace(SYNTH_CONTRACT, onboarding=None), "onboarding record is missing"),
        (
            replace(SYNTH_CONTRACT, onboarding=replace(SYNTH_CONTRACT.onboarding, contact_escalation=" ")),
            "lacks contact_escalation",
        ),
        (
            replace(SYNTH_CONTRACT, onboarding=replace(SYNTH_CONTRACT.onboarding, access_method="synthetic")),
            "synthetic access method",
        ),
        (
            replace(
                SYNTH_CONTRACT,
                capabilities=replace(
                    SYNTH_CONTRACT.capabilities, operations=frozenset({"schedules", "offers"})
                ),
            ),
            "'booking_links' is not a declared operation",
        ),
        (replace(SYNTH_CONTRACT, enabled=False), "disabled"),
        (
            replace(SYNTH_CONTRACT, ingestion=replace(SYNTH_CONTRACT.ingestion, requests_per_minute=0)),
            "requests_per_minute",
        ),
        (
            replace(SYNTH_CONTRACT, ingestion=replace(SYNTH_CONTRACT.ingestion, max_rejected_ratio=0.5)),
            "max_rejected_ratio",
        ),
        (
            replace(
                SYNTH_CONTRACT, price_stale_after=timedelta(hours=2), price_expire_after=timedelta(hours=1)
            ),
            "price_expire_after",
        ),
    ],
)
def test_onboarding_and_operational_rules(contract, expected):
    assert any(expected in p for p in contract_problems(contract, TODAY)), contract_problems(contract, TODAY)


def test_partition_keeps_valid_records_only(catalog):
    from app.providers.contracts import partition_valid

    good, bad = _bad(id="G"), _bad(id="B", arrival_utc=NOW)  # B arrives before it departs
    offers = [
        _offer(id="G.o", departure_id="G"),
        _offer(id="B.o", departure_id="B"),
        _offer(id="G.x", departure_id="G", fare_name="Other", currency="USD"),
    ]
    violations = validate_records(SYNTH_CONTRACT, catalog, [good, bad], offers, NOW)
    part = partition_valid([good, bad], offers, violations)
    assert [d.id for d in part.departures] == ["G"] and [o.id for o in part.offers] == ["G.o"]
    assert (part.rejected_departures, part.rejected_offers) == (1, 2)


def test_diagnostics_do_not_echo_payloads(catalog):
    o = _offer(booking_url="https://evil.test/steal?token=SECRET123")
    msgs = [v.message for v in validate_records(SYNTH_CONTRACT, catalog, [_bad()], [o], NOW)]
    assert msgs and not any("SECRET123" in m for m in msgs)
