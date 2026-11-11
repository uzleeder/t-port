"""Search engine: validation, filtering, sorting, freshness, provider failure."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.errors import NotFound, ProvidersUnavailable, ValidationFailed
from app.domain.models import Freshness, TransportMode
from app.services.search import SearchQuery, SortKey
from tests.conftest import NOW, TODAY, TOMORROW, FakeAdapter, dep, make_service, offer


def run(coro):
    return asyncio.run(coro)


def q(**kw) -> SearchQuery:
    base = dict(origin_id="tashkent", destination_id="samarkand", travel_date=TOMORROW)
    base.update(kw)
    return SearchQuery(**base)


# -- validation -----------------------------------------------------------------------
def test_same_origin_and_destination_rejected(service):
    with pytest.raises(ValidationFailed, match="different"):
        run(service.search(q(destination_id="tashkent")))


def test_unknown_location_is_not_found(service):
    with pytest.raises(NotFound) as exc:
        run(service.search(q(origin_id="atlantis")))
    assert exc.value.details[0]["field"] == "origin"


def test_past_date_rejected(service):
    with pytest.raises(ValidationFailed) as exc:
        run(service.search(q(travel_date=TODAY - timedelta(days=1))))
    assert exc.value.details[0]["field"] == "date"


def test_date_beyond_window_rejected(service):
    with pytest.raises(ValidationFailed):
        run(service.search(q(travel_date=TODAY + timedelta(days=91))))


def test_today_allowed_and_departed_services_hidden(service):
    # It is 10:00 local; the 06:10 regional and 08:00 express have already left.
    result = run(service.search(q(travel_date=TODAY)))
    assert result.excluded.already_departed >= 2
    for j in result.journeys:
        assert j.departure_utc is None or j.departure_utc > NOW


# -- filtering & sorting ------------------------------------------------------------
def test_mode_filter(service):
    result = run(service.search(q(modes=frozenset({TransportMode.BUS}))))
    assert result.total == 2
    assert all(j.modes == (TransportMode.BUS,) for j in result.journeys)


def test_max_price_filter(service):
    result = run(service.search(q(max_price=Decimal(100_000))))
    assert result.total > 0
    assert all(j.price <= 100_000 for j in result.journeys)
    assert result.excluded.over_budget > 0


def test_sort_by_price(service):
    prices = [j.price for j in run(service.search(q(sort=SortKey.PRICE))).journeys]
    assert prices == sorted(prices)


def test_sort_by_duration(service):
    mins = [j.total_minutes for j in run(service.search(q(sort=SortKey.DURATION))).journeys]
    assert mins == sorted(mins)


def test_sort_by_departure_puts_on_demand_last(service):
    journeys = run(service.search(q(sort=SortKey.DEPARTURE))).journeys
    scheduled = [j.departure_utc for j in journeys if j.departure_utc]
    assert scheduled == sorted(scheduled)
    assert journeys[-1].departure_utc is None  # taxi


def test_ranking_is_deterministic(service):
    a = [j.id for j in run(service.search(q())).journeys]
    b = [j.id for j in run(service.search(q())).journeys]
    assert a == b


def test_summary_identifies_best_options(service):
    r = run(service.search(q()))
    by_id = {j.id: j for j in r.journeys}
    assert by_id[r.summary.cheapest_id].price == min(j.price for j in r.journeys)
    assert by_id[r.summary.fastest_id].total_minutes == min(j.total_minutes for j in r.journeys)


def test_pagination(service):
    full = run(service.search(q(page_size=50)))
    page2 = run(service.search(q(page=2, page_size=2)))
    assert page2.total == full.total
    assert [j.id for j in page2.journeys] == [j.id for j in full.journeys[2:4]]


def test_empty_results_for_unserved_pair(service):
    r = run(service.search(q(origin_id="khiva", destination_id="termez", max_transfers=0)))
    assert r.total == 0 and r.journeys == [] and r.summary.cheapest_id is None


def test_weekend_surcharge_is_deterministic(service):
    bus = frozenset({TransportMode.BUS})
    thu = run(service.search(q(modes=bus, sort=SortKey.PRICE)))
    fri = run(service.search(q(travel_date=TOMORROW + timedelta(days=1), modes=bus, sort=SortKey.PRICE)))
    assert thu.journeys[0].price == Decimal(90_000)
    assert fri.journeys[0].price == Decimal(99_000)


# -- data quality -----------------------------------------------------------------------
def test_missing_offers_are_excluded(catalog, clock):
    fake = FakeAdapter([dep("A"), dep("B")], [offer("A", 100_000)])
    r = run(make_service(catalog, clock, [fake]).search(q()))
    assert [j.id for j in r.journeys] == ["fake~A"]
    assert r.excluded.missing_offers == 1


def test_expired_data_is_excluded_with_warning(catalog, clock):
    old = NOW - timedelta(hours=7)
    fake = FakeAdapter(
        [dep("A", retrieved_at=old), dep("B")], [offer("A", 1), offer("B", 2, retrieved_at=old)]
    )
    r = run(make_service(catalog, clock, [fake]).search(q()))
    assert r.total == 0
    assert r.excluded.expired_data == 2
    assert any("out of date" in w for w in r.warnings)


def test_stale_data_is_flagged_not_hidden(catalog, clock):
    stale = NOW - timedelta(minutes=30)
    fake = FakeAdapter([dep("A", retrieved_at=stale)], [offer("A", 100)])
    r = run(make_service(catalog, clock, [fake]).search(q()))
    assert r.journeys[0].freshness == Freshness.STALE
    assert any("may be out of date" in w for w in r.warnings)


def test_mixed_currency_offers_skipped(catalog, clock):
    fake = FakeAdapter([dep("A")], [offer("A", 100), offer("A", 5, currency="USD")])
    assert run(make_service(catalog, clock, [fake]).search(q())).total == 0


def test_booking_url_only_when_verified(catalog, clock):
    fake = FakeAdapter(
        [dep("A"), dep("B")],
        [
            offer("A", 100, booking_url="https://book.example.com/x"),
            offer("B", 100, booking_url="https://evil.test/x"),
        ],
        booking_hosts=frozenset({"book.example.com"}),
    )
    r = run(make_service(catalog, clock, [fake]).search(q()))
    urls = {j.id: j.booking_url for j in r.journeys}
    assert urls == {"fake~A": "https://book.example.com/x", "fake~B": None}


def test_demo_data_never_bookable(service):
    assert all(j.booking_url is None and j.is_demo for j in run(service.search(q())).journeys)


# -- provider failures ------------------------------------------------------------------
def test_partial_provider_failure_returns_other_results(catalog, clock, demo):
    svc = make_service(catalog, clock, [demo, FakeAdapter(fail=True)])
    r = run(svc.search(q()))
    assert r.total > 0
    assert any(not s.ok for s in r.sources)
    assert any("unavailable" in w for w in r.warnings)


def test_all_providers_failing_raises(catalog, clock):
    svc = make_service(catalog, clock, [FakeAdapter(fail=True)])
    with pytest.raises(ProvidersUnavailable):
        run(svc.search(q()))


# -- journey detail -----------------------------------------------------------------------
def test_get_journey_roundtrip(service):
    first = run(service.search(q())).journeys[0]
    journey, origin, destination = run(service.get_journey(first.id))
    assert journey.id == first.id and journey.price == first.price
    assert (origin.id, destination.id) == ("tashkent", "samarkand")


@pytest.mark.parametrize(
    "bad",
    ["", "demo", "demo~", "nope~TR101.20261112", "demo~XX999.20261112", "demo~TR101.20261399", "../etc"],
)
def test_get_journey_invalid_ids(service, bad):
    with pytest.raises(NotFound):
        run(service.get_journey(bad))


def test_get_journey_already_departed(service):
    # Express TR101 departs 08:00 local today; it is now 10:00.
    with pytest.raises(NotFound, match="already left"):
        run(service.get_journey("demo~TR101.20261111"))
