"""Import reliability: atomicity, idempotency, validation, retries, locking, bounded load."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.clock import FixedClock
from app.db import models as m
from app.db.repositories import TimetableRepository
from app.db.session import transaction
from app.main import seed_reference
from app.providers.base import ProviderError, ProviderRateLimited
from app.providers.feed import FeedAdapter
from app.providers.stored import StoredTimetableAdapter
from app.services.imports import ImportLocked, ImportRejected, import_snapshot
from app.services.search import SearchQuery
from tests.conftest import NOW, SYNTH_CONTRACT, SYNTH_INFO, TODAY, TOMORROW, make_service, synth_feed


class Recorder:
    """Fake sleep that records backoff delays instead of waiting."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.fixture
def seeded(db_factory):
    seed_reference(db_factory)
    with transaction(db_factory) as db:  # the synthetic provider must exist for FK constraints
        db.add(
            m.Provider(
                id="synthrail",
                name="SynthRail (test fixture)",
                is_demo=False,
                attribution="test",
                booking_hosts=["tickets.synthrail.test"],
                access_basis="TEST-ONLY",
            )
        )
    return db_factory


def _import(adapter, factory, clock, catalog, **kw):
    kw.setdefault("days", 3)
    kw.setdefault("sleep", Recorder())
    return import_snapshot(
        adapter,
        factory,
        clock,
        start=TODAY,
        source_reference="fixture",
        contract=kw.pop("contract", SYNTH_CONTRACT),
        catalog=catalog,
        **kw,
    )


def _counts(factory) -> tuple[int, int, list[str]]:
    with factory() as db:
        deps = db.scalar(select(func.count()).select_from(m.DepartureRow))
        offers = db.scalar(select(func.count()).select_from(m.OfferRow))
        statuses = [i.status for i in TimetableRepository(db).recent_imports("synthrail")][::-1]
        lock = db.get(m.ProviderImportLock, "synthrail")
    assert lock is None, "lock must be released after every import"
    return deps, offers, statuses


def test_synthetic_feed_ingests_and_serves_identically(seeded, catalog, clock, synth):
    summary = _import(synth, seeded, clock, catalog)
    assert summary["departures"] == 13 and summary["retries"] == 0  # Wed-Fri; SR211/212 run Wed and Fri
    stored = StoredTimetableAdapter(SYNTH_INFO, catalog, seeded, synth.supported_location_ids())
    q = SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0)
    live = asyncio.run(make_service(catalog, clock, [synth]).search(q))
    db = asyncio.run(make_service(catalog, clock, [stored]).search(q))
    assert [(j.id, j.price, j.booking_url) for j in live.journeys] == [
        (j.id, j.price, j.booking_url) for j in db.journeys
    ]


def test_repeated_imports_do_not_duplicate(seeded, catalog, clock, synth):
    first = _import(synth, seeded, clock, catalog)
    _import(synth, seeded, clock, catalog)
    _import(synth, seeded, clock, catalog)
    deps, offers, statuses = _counts(seeded)
    assert deps == first["departures"] and offers == first["offers"]
    assert statuses == ["succeeded"] * 3


class Flaky(FeedAdapter):
    """Raises the given errors on the first calls to get_departures, then behaves."""

    def __init__(self, *args, errors=(), **kw) -> None:
        super().__init__(*args, **kw)
        self.errors = list(errors)
        self.calls = 0

    async def get_departures(self, *a, **kw):
        self.calls += 1
        await asyncio.sleep(0.005)  # behave like network I/O so concurrency is real
        if self.errors:
            raise self.errors.pop(0)
        return await super().get_departures(*a, **kw)


def _flaky(catalog, clock, errors):
    return Flaky(SYNTH_INFO, synth_feed(), catalog, clock, errors=errors)


def test_interrupted_import_keeps_previous_snapshot(seeded, catalog, clock, synth):
    good = _import(synth, seeded, clock, catalog)
    broken = _flaky(catalog, clock, [ProviderError("synthrail", "auth revoked", retryable=False)])
    with pytest.raises(ProviderError):
        _import(broken, seeded, clock, catalog)
    deps, offers, statuses = _counts(seeded)
    assert (deps, offers) == (good["departures"], good["offers"])
    assert statuses == ["succeeded", "failed"]
    # Non-retryable: no retries, and queued requests were cancelled instead of hitting the source.
    # (at most one more request can start in the same event-loop step as the failure)
    assert broken.calls <= SYNTH_CONTRACT.ingestion.max_concurrency + 1 < 12


def test_failure_during_write_rolls_back(seeded, catalog, clock, synth, monkeypatch):
    good = _import(synth, seeded, clock, catalog)
    original = TimetableRepository.finish_import

    def explode(self, imp, now, **kw):
        if kw.get("error") is None:  # the success path, after replace_window already ran
            raise RuntimeError("disk full")
        return original(self, imp, now, **kw)

    monkeypatch.setattr(TimetableRepository, "finish_import", explode)
    changed = synth_feed()
    changed["services"] = changed["services"][:1]  # a much smaller snapshot
    with pytest.raises(RuntimeError):
        _import(FeedAdapter(SYNTH_INFO, changed, catalog, clock), seeded, clock, catalog)
    deps, _, statuses = _counts(seeded)
    assert deps == good["departures"]  # the delete inside the failed transaction was rolled back
    assert statuses == ["succeeded", "failed"]


def test_contract_violations_reject_the_whole_import(seeded, catalog, clock, synth):
    good = _import(synth, seeded, clock, catalog)
    narrow = replace(
        SYNTH_CONTRACT,
        capabilities=replace(
            SYNTH_CONTRACT.capabilities,
            modes=frozenset({SYNTH_CONTRACT.capabilities.modes.__iter__().__next__()}),
        ),
    )
    with pytest.raises(ImportRejected) as exc:
        _import(synth, seeded, clock, catalog, contract=narrow)  # feed has a mode this contract lacks
    assert exc.value.violations and {v.code for v in exc.value.violations} == {"undeclared_mode"}
    deps, _, statuses = _counts(seeded)
    assert deps == good["departures"] and statuses == ["succeeded", "failed"]
    with seeded() as db:
        last = TimetableRepository(db).recent_imports("synthrail")[0]
    assert last.rejected_records == len(exc.value.violations) and "contract violation" in last.error_message


def test_retryable_errors_are_retried_with_backoff(seeded, catalog, clock):
    sleep = Recorder()
    flaky = _flaky(catalog, clock, [ProviderError("synthrail", "502", retryable=True), TimeoutError()])
    serial = replace(SYNTH_CONTRACT, ingestion=replace(SYNTH_CONTRACT.ingestion, max_concurrency=1))
    summary = _import(flaky, seeded, clock, catalog, sleep=sleep, days=1, contract=serial)
    # Both errors hit the same request: backoff doubles (0.5 s, then 1 s) per the contract.
    assert summary["retries"] == 2 and sleep.waits == [0.5, 1.0]
    with seeded() as db:
        assert TimetableRepository(db).recent_imports("synthrail")[0].retries == 2


def test_rate_limit_retry_after_is_respected(seeded, catalog, clock):
    sleep = Recorder()
    flaky = _flaky(catalog, clock, [ProviderRateLimited("synthrail", retry_after_seconds=7)])
    _import(flaky, seeded, clock, catalog, sleep=sleep, days=1)
    assert sleep.waits == [7]


def test_retries_give_up_after_max_attempts(seeded, catalog, clock):
    errors = [ProviderError("synthrail", "503", retryable=True) for _ in range(3)]
    flaky = _flaky(catalog, clock, errors)
    with pytest.raises(ProviderError):
        _import(
            flaky,
            seeded,
            clock,
            catalog,
            days=1,
            contract=replace(SYNTH_CONTRACT, ingestion=replace(SYNTH_CONTRACT.ingestion, max_concurrency=1)),
        )
    _, _, statuses = _counts(seeded)
    assert statuses == ["failed"]


def test_overlapping_imports_are_prevented(seeded, catalog, clock, synth):
    with transaction(seeded) as db:
        assert TimetableRepository(db).acquire_lock("synthrail", "other-host:1", NOW, timedelta(minutes=15))
    with pytest.raises(ImportLocked):
        _import(synth, seeded, clock, catalog, holder="me:2")
    with seeded() as db:
        assert db.get(m.ProviderImportLock, "synthrail").holder == "other-host:1"  # untouched
        assert TimetableRepository(db).recent_imports("synthrail") == []  # nothing recorded


def test_stale_lock_is_taken_over(seeded, catalog, clock, synth):
    with transaction(seeded) as db:  # a crashed importer left this 20 minutes ago (TTL 15 min)
        TimetableRepository(db).acquire_lock(
            "synthrail", "dead:1", NOW - timedelta(minutes=20), timedelta(minutes=15)
        )
    _import(synth, seeded, clock, catalog, holder="me:2")
    _, _, statuses = _counts(seeded)
    assert statuses == ["succeeded"]


def test_lock_is_reentrant_for_the_same_holder_and_released(seeded):
    ttl = timedelta(minutes=15)
    with transaction(seeded) as db:
        repo = TimetableRepository(db)
        assert repo.acquire_lock("synthrail", "a", NOW, ttl)
        assert repo.acquire_lock("synthrail", "a", NOW, ttl)
        assert not repo.acquire_lock("synthrail", "b", NOW, ttl)
        repo.release_lock("synthrail", "b")  # someone else's release is a no-op
        assert not repo.acquire_lock("synthrail", "b", NOW, ttl)
        repo.release_lock("synthrail", "a")
        assert repo.acquire_lock("synthrail", "b", NOW, ttl)


class Slow(FeedAdapter):
    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.active = 0
        self.peak = 0
        self.calls: list[tuple[str, str]] = []

    async def get_departures(self, origin, destination, *a, **kw):
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.calls.append((origin, destination))
        await asyncio.sleep(0.01)
        self.active -= 1
        return await super().get_departures(origin, destination, *a, **kw)


def test_concurrency_is_bounded_and_only_served_routes_are_queried(seeded, catalog, clock):
    slow = Slow(SYNTH_INFO, synth_feed(), catalog, clock)
    summary = _import(slow, seeded, clock, catalog, days=4)
    assert slow.peak == SYNTH_CONTRACT.ingestion.max_concurrency == summary["max_in_flight"]
    assert len(slow.calls) == len(slow.served_routes()) * 4  # 4 routes x 4 days, not every city pair
    assert set(slow.calls) == set(slow.served_routes())


def test_imported_data_ages_by_its_contract(seeded, catalog, synth):
    _import(synth, seeded, FixedClock(NOW), catalog)
    stored = StoredTimetableAdapter(SYNTH_INFO, catalog, seeded, synth.supported_location_ids())
    q = SearchQuery("tashkent", "samarkand", TOMORROW + timedelta(days=1), max_transfers=0)

    def search_at(hours: int):
        from app.services.freshness import FreshnessPolicy
        from app.services.search import SearchService

        svc = SearchService(
            catalog,
            [stored],
            FixedClock(NOW + timedelta(hours=hours)),
            FreshnessPolicy(timedelta(minutes=15), timedelta(hours=6)),
            freshness_by_provider={"synthrail": SYNTH_CONTRACT.freshness},
        )
        return asyncio.run(svc.search(q))

    assert {j.freshness.value for j in search_at(0).journeys} == {"fresh"}
    assert {j.freshness.value for j in search_at(3).journeys} == {"stale"}  # contract: stale after 1 h
    late = search_at(30)  # contract: expired after 24 h
    assert late.total == 0 and late.excluded.expired_data > 0
