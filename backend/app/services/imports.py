"""Snapshot import: pull a date window from a provider into the database, safely.

Guarantees:
* **One import per provider at a time**: a lease lock in ``provider_import_locks``; a lock
  older than the contract's TTL is presumed dead and may be taken over.
* **Bounded load on the source**: requests run with at most ``max_concurrency`` in flight, and
  only for routes the source serves when it declares them (``served_routes``).
* **Controlled retries**: retryable errors (``ProviderError.retryable``, timeouts) are retried
  with exponential backoff up to ``max_attempts``; anything else fails the import at once.
* **Validate before write**: every record is checked against the provider contract. Any
  violation rejects the whole import and the previous snapshot stays live.
* **All-or-nothing**: the window is replaced in a single transaction, so readers see either the
  old snapshot or the new one, never a mix. Re-running an import never duplicates rows.
Each attempt is recorded in ``data_imports`` (status, counts, retries, rejected records, trigger).
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import permutations
from typing import TypeVar

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.db.repositories import TimetableRepository
from app.db.session import transaction
from app.domain.models import Departure, Offer
from app.providers.base import ProviderAdapter, ProviderError
from app.providers.contracts import IngestionPolicy, ProviderContract, Violation, validate_records
from app.services.catalog import LocationCatalog

log = logging.getLogger("tport.imports")
T = TypeVar("T")
Sleep = Callable[[float], Awaitable[None]]


class ImportLocked(Exception):
    """Another import for this provider is running (or crashed less than the lock TTL ago)."""


class ImportRejected(Exception):
    def __init__(self, violations: list[Violation]) -> None:
        self.violations = violations
        sample = "; ".join(f"{v.code}@{v.subject}" for v in violations[:5])
        super().__init__(f"{len(violations)} contract violation(s): {sample}")


@dataclass(slots=True)
class _Counters:
    retries: int = 0
    in_flight: int = 0
    max_in_flight: int = 0


def default_holder() -> str:
    return f"{socket.gethostname()[:40]}:{os.getpid()}"


async def _with_retry(
    call: Callable[[], Awaitable[T]], policy: IngestionPolicy, sleep: Sleep, c: _Counters
) -> T:
    delay = policy.backoff_seconds
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await call()
        except (ProviderError, TimeoutError) as exc:
            retryable = isinstance(exc, TimeoutError) or exc.retryable
            if not retryable or attempt == policy.max_attempts:
                raise
            c.retries += 1
            wait = getattr(exc, "retry_after_seconds", None) or delay
            log.warning("retryable provider error (attempt %d/%d): %s", attempt, policy.max_attempts, exc)
            await sleep(wait)
            delay *= 2
    raise AssertionError("unreachable")  # pragma: no cover


async def _all_or_nothing(coros: Iterable[Awaitable[T]]) -> list[T]:
    """Run concurrently; on the first failure cancel everything still queued (stop hitting the source)."""
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(c) for c in coros]
    except BaseExceptionGroup as group:
        raise group.exceptions[0] from None
    return [t.result() for t in tasks]


async def _collect(
    adapter: ProviderAdapter, policy: IngestionPolicy, start: date, days: int, sleep: Sleep, c: _Counters
) -> tuple[list[Departure], list[Offer], dict[str, date]]:
    routes = adapter.served_routes()
    if routes is None:  # source can't list its routes: fall back to every ordered pair
        routes = frozenset(permutations(sorted(adapter.supported_location_ids()), 2))
    sem = asyncio.Semaphore(policy.max_concurrency)
    timeout = adapter.rate_limit.timeout_seconds

    async def bounded(make: Callable[[], Awaitable[T]]) -> T:
        async with sem:
            c.in_flight += 1
            c.max_in_flight = max(c.max_in_flight, c.in_flight)
            try:
                return await _with_retry(lambda: asyncio.wait_for(make(), timeout), policy, sleep, c)
            finally:
                c.in_flight -= 1

    jobs = [
        (day, origin, destination)
        for day in (start + timedelta(days=i) for i in range(days))
        for origin, destination in sorted(routes)
    ]
    results = await _all_or_nothing(
        bounded(lambda o=o, d=d, day=day: adapter.get_departures(o, d, day, frozenset()))
        for day, o, d in jobs
    )
    departures: list[Departure] = []
    travel_dates: dict[str, date] = {}
    for (day, _, _), deps in zip(jobs, results, strict=True):
        for dep in deps:
            departures.append(dep)
            travel_dates[dep.id] = day

    ids = [d.id for d in departures]
    size = policy.offer_batch_size
    batches = await _all_or_nothing(
        bounded(lambda chunk=ids[i : i + size]: adapter.get_offers(chunk)) for i in range(0, len(ids), size)
    )
    offers = [o for batch in batches for o in batch]
    return departures, offers, travel_dates


def import_snapshot(
    adapter: ProviderAdapter,
    factory: sessionmaker[Session],
    clock: Clock,
    *,
    start: date,
    days: int,
    source_reference: str,
    contract: ProviderContract,
    catalog: LocationCatalog,
    trigger: str = "manual",
    holder: str | None = None,
    sleep: Sleep = asyncio.sleep,
) -> dict:
    if not 1 <= days <= 120:
        raise ValueError("days must be between 1 and 120")
    if contract.info.id != adapter.id:
        raise ValueError("contract does not belong to this adapter")
    policy = contract.ingestion
    holder = holder or default_holder()
    end = start + timedelta(days=days - 1)

    with transaction(factory) as db:
        repo = TimetableRepository(db)
        if not repo.acquire_lock(adapter.id, holder, clock.now(), timedelta(seconds=policy.lock_ttl_seconds)):
            raise ImportLocked(f"an import for {adapter.id!r} is already running")
        imp = repo.start_import(adapter.id, source_reference, clock.now(), trigger)
        import_id = imp.id

    counters = _Counters()
    try:
        try:
            departures, offers, travel_dates = asyncio.run(
                _collect(adapter, policy, start, days, sleep, counters)
            )
            violations = validate_records(
                contract, catalog, departures, offers, clock.now(), travel_dates=travel_dates
            )
            if violations:
                raise ImportRejected(violations)
            source_updated = max(
                (d.source_updated_at for d in departures if d.source_updated_at), default=None
            )
            with transaction(factory) as db:  # single transaction: old or new snapshot, never a mix
                repo = TimetableRepository(db)
                imp = db.merge(imp)
                repo.replace_window(
                    adapter.id, start, end, departures, offers, imp, travel_dates, contract.timezone
                )
                repo.finish_import(
                    imp,
                    clock.now(),
                    departures=len(departures),
                    offers=len(offers),
                    source_updated_at=source_updated,
                    retries=counters.retries,
                )
        except Exception as exc:
            log.error("import %s for %s failed: %s", import_id, adapter.id, exc)
            rejected = len(exc.violations) if isinstance(exc, ImportRejected) else 0
            with transaction(factory) as db:
                TimetableRepository(db).finish_import(
                    db.merge(imp),
                    clock.now(),
                    departures=0,
                    offers=0,
                    source_updated_at=None,
                    error=f"{type(exc).__name__}: {exc}",
                    retries=counters.retries,
                    rejected_records=rejected,
                )
            raise
    finally:
        with transaction(factory) as db:
            TimetableRepository(db).release_lock(adapter.id, holder)

    return {
        "import_id": str(import_id),
        "provider": adapter.id,
        "departures": len(departures),
        "offers": len(offers),
        "retries": counters.retries,
        "max_in_flight": counters.max_in_flight,
        "window": [start.isoformat(), end.isoformat()],
    }
