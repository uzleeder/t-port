"""Snapshot import: pull a date window from a provider into the database, safely.

Lifecycle (``data_imports.status``)::

    pending -> running -> validating -> publishing -> succeeded
                 |            |             |
                 +------------+-------------+--> failed
                 +--> cancelled  (cancellation requested via ``request_cancel``)

Guarantees:
* **One import per provider at a time**: a lease lock in ``provider_import_locks``; a lock older than
  the contract's TTL is presumed dead and may be taken over.
* **Bounded load**: at most ``max_concurrency`` requests in flight, at most ``requests_per_minute``
  started per minute, each with ``request_timeout_seconds``; the whole import must finish within
  ``import_timeout_seconds``. Only routes the source serves are queried when it declares them.
* **Controlled retries**: only retryable errors (``ProviderError.retryable``, timeouts) are retried,
  with exponential backoff plus jitter, honouring ``Retry-After``. Authentication, authorization,
  malformed data and contract violations are never retried.
* **Quarantine, then publish**: every record is checked against the contract. Invalid records are
  held back (with sample diagnostics); if their share exceeds ``max_rejected_ratio`` the whole
  import is rejected and the previous snapshot stays live.
* **All-or-nothing publication** in one transaction: readers see the old or the new snapshot, never
  a mix. Re-running an import never duplicates rows.

Expected request count per import: ``days x routes`` departure requests (``routes`` = served routes,
or every ordered pair of supported locations when unknown) plus ``ceil(departures / offer_batch_size)``
offer requests. Memory holds one window of records at a time (~1 KB per departure with its fares).
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import random
import socket
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from itertools import permutations
from typing import TypeVar

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.db.repositories import TimetableRepository
from app.db.session import transaction
from app.domain.models import Departure, Offer
from app.providers.base import ProviderAdapter, ProviderError
from app.providers.contracts import (
    IngestionPolicy,
    ProviderContract,
    Violation,
    partition_valid,
    validate_records,
)
from app.services.catalog import LocationCatalog

log = logging.getLogger("tport.imports")
T = TypeVar("T")
Sleep = Callable[[float], Awaitable[None]]


class ImportLocked(Exception):
    """Another import for this provider is running (or crashed less than the lock TTL ago)."""


class ImportCancelled(Exception):
    """Cancellation was requested while the import was running."""


class ImportTimedOut(Exception):
    def __init__(self, seconds: int) -> None:
        super().__init__(f"import exceeded its {seconds}s deadline")


class ImportRejected(Exception):
    def __init__(self, violations: list[Violation], rejected: int, total: int) -> None:
        self.violations = violations
        self.rejected, self.total = rejected, total
        sample = "; ".join(f"{v.code}@{v.subject}" for v in violations[:5])
        super().__init__(f"{rejected}/{total} records violate the contract: {sample}")


@dataclass(slots=True)
class _Counters:
    retries: int = 0
    in_flight: int = 0
    max_in_flight: int = 0
    done: int = 0
    total: int = 0
    waits: list[float] = field(default_factory=list)


class Throttle:
    """Starts at most ``per_minute`` requests per minute, evenly spaced."""

    def __init__(
        self, per_minute: int | None, sleep: Sleep, monotonic: Callable[[], float] = time.monotonic
    ) -> None:
        self.interval = 60.0 / per_minute if per_minute else 0.0
        self._sleep, self._now = sleep, monotonic
        self._next = 0.0

    async def wait(self) -> None:
        if not self.interval:
            return
        now = self._now()  # no await between read and update: safe on one event loop
        slot = max(now, self._next)
        self._next = slot + self.interval
        if slot > now:
            await self._sleep(slot - now)


def default_holder() -> str:
    return f"{socket.gethostname()[:40]}:{os.getpid()}"


async def _with_retry(
    call: Callable[[], Awaitable[T]], policy: IngestionPolicy, sleep: Sleep, c: _Counters, rng: random.Random
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
            retry_after = getattr(exc, "retry_after_seconds", None)
            # The provider's Retry-After is respected exactly; our own backoff gets jitter.
            wait = retry_after if retry_after else delay * (1 + rng.uniform(-policy.jitter, policy.jitter))
            c.waits.append(wait)
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
    adapter: ProviderAdapter,
    policy: IngestionPolicy,
    start: date,
    days: int,
    sleep: Sleep,
    c: _Counters,
    rng: random.Random,
    checkpoint: Callable[[int, int], Awaitable[None]],
) -> tuple[list[Departure], list[Offer], dict[str, date]]:
    routes = adapter.served_routes()
    if routes is None:  # source can't list its routes: fall back to every ordered pair
        routes = frozenset(permutations(sorted(adapter.supported_location_ids()), 2))
    sem = asyncio.Semaphore(policy.max_concurrency)
    throttle = Throttle(policy.requests_per_minute, sleep)
    timeout = min(policy.request_timeout_seconds, adapter.rate_limit.timeout_seconds or math.inf)
    step = 1

    async def bounded(make: Callable[[], Awaitable[T]]) -> T:
        async with sem:
            await throttle.wait()
            c.in_flight += 1
            c.max_in_flight = max(c.max_in_flight, c.in_flight)
            try:
                result = await _with_retry(lambda: asyncio.wait_for(make(), timeout), policy, sleep, c, rng)
            finally:
                c.in_flight -= 1
                c.done += 1
            # Progress and cancellation checkpoint (outside finally: never masks an error).
            if c.done % step == 0 or c.done == c.total:
                await checkpoint(c.done, c.total)
            return result

    jobs = [
        (day, origin, destination)
        for day in (start + timedelta(days=i) for i in range(days))
        for origin, destination in sorted(routes)
    ]
    c.total = len(jobs)
    step = max(1, c.total // 20)  # ~20 progress/cancellation checkpoints
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
    batches = range(0, len(ids), size)
    c.total += len(batches)
    batch_results = await _all_or_nothing(
        bounded(lambda chunk=ids[i : i + size]: adapter.get_offers(chunk)) for i in batches
    )
    offers = [o for batch in batch_results for o in batch]
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
    rng: random.Random | None = None,
) -> dict:
    if not 1 <= days <= 120:
        raise ValueError("days must be between 1 and 120")
    if contract.info.id != adapter.id:
        raise ValueError("contract does not belong to this adapter")
    policy = contract.ingestion
    holder = holder or default_holder()
    rng = rng or random.Random()  # noqa: S311 - jitter, not security
    end = start + timedelta(days=days - 1)

    with transaction(factory) as db:
        repo = TimetableRepository(db)
        if not repo.acquire_lock(adapter.id, holder, clock.now(), timedelta(seconds=policy.lock_ttl_seconds)):
            raise ImportLocked(f"an import for {adapter.id!r} is already running")
        imp = repo.start_import(adapter.id, source_reference, clock.now(), trigger)
        import_id = imp.id

    def set_status(status: str) -> None:
        with transaction(factory) as db:
            TimetableRepository(db).set_status(import_id, status)

    async def checkpoint(done: int, total: int) -> None:
        """Progress write + cancellation check. Runs inline (~20 tiny writes per import): a thread
        would add concurrency to the session pool for no benefit."""
        with transaction(factory) as db:
            cancel = TimetableRepository(db).update_progress(import_id, done, total)
        if cancel:
            raise ImportCancelled(f"import {import_id} cancelled after {done}/{total} requests")

    counters = _Counters()

    async def run() -> tuple[list[Departure], list[Offer], dict[str, date]]:
        try:
            async with asyncio.timeout(policy.import_timeout_seconds):
                return await _collect(adapter, policy, start, days, sleep, counters, rng, checkpoint)
        except TimeoutError as exc:
            if counters.retries == 0 and counters.done >= counters.total > 0:
                raise  # a per-request timeout surfaced after the work finished
            raise ImportTimedOut(policy.import_timeout_seconds) from exc

    rejected = 0
    diagnostics: list[dict] | None = None
    try:
        try:
            set_status("running")
            departures, offers, travel_dates = asyncio.run(run())

            set_status("validating")
            violations = validate_records(
                contract, catalog, departures, offers, clock.now(), travel_dates=travel_dates
            )
            total_records = len(departures) + len(offers)
            if violations:
                part = partition_valid(departures, offers, violations)
                rejected = part.rejected
                diagnostics = [asdict(v) for v in violations[:50]]
                if total_records == 0 or rejected / total_records > policy.max_rejected_ratio:
                    raise ImportRejected(violations, rejected, total_records)
                log.warning("import %s quarantined %d of %d records", import_id, rejected, total_records)
                departures, offers = part.departures, part.offers
                travel_dates = {d.id: travel_dates[d.id] for d in departures}

            set_status("publishing")
            source_updated = max(
                (d.source_updated_at for d in departures if d.source_updated_at), default=None
            )
            with transaction(factory) as db:  # single transaction: old or new snapshot, never a mix
                repo = TimetableRepository(db)
                imp = db.get(type(imp), import_id)  # fresh row: never overwrite progress/cancel flags
                repo.replace_window(
                    adapter.id, start, end, departures, offers, imp, travel_dates, contract.timezone
                )
                repo.update_progress(import_id, counters.done, counters.total)
                repo.finish_import(
                    imp,
                    clock.now(),
                    departures=len(departures),
                    offers=len(offers),
                    source_updated_at=source_updated,
                    retries=counters.retries,
                    rejected_records=rejected,
                    diagnostics=diagnostics,
                )
        except Exception as exc:
            cancelled = isinstance(exc, ImportCancelled)
            if isinstance(exc, ImportRejected):
                rejected, diagnostics = exc.rejected, [asdict(v) for v in exc.violations[:50]]
            log.error(
                "import %s for %s %s: %s", import_id, adapter.id, "cancelled" if cancelled else "failed", exc
            )
            with transaction(factory) as db:
                repo = TimetableRepository(db)
                repo.update_progress(import_id, counters.done, counters.total)
                repo.finish_import(
                    db.get(type(imp), import_id),
                    clock.now(),
                    departures=0,
                    offers=0,
                    source_updated_at=None,
                    error=f"{type(exc).__name__}: {exc}",
                    retries=counters.retries,
                    rejected_records=rejected,
                    status="cancelled" if cancelled else "failed",
                    diagnostics=diagnostics,
                )
            raise
    finally:
        with transaction(factory) as db:
            TimetableRepository(db).release_lock(adapter.id, holder)

    return {
        "import_id": str(import_id),
        "provider": adapter.id,
        "status": "succeeded",
        "departures": len(departures),
        "offers": len(offers),
        "rejected_records": rejected,
        "retries": counters.retries,
        "requests": counters.total,
        "max_in_flight": counters.max_in_flight,
        "window": [start.isoformat(), end.isoformat()],
    }
