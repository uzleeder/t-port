"""Provider-aware job scheduling without an external queue.

``run_due_imports`` imports every stored-mode provider whose last successful import is older than
its contract's ``update_interval_minutes`` (failed attempts back off for one interval too, so a
broken source isn't hammered). ``Scheduler.tick`` also runs daily housekeeping. Overlapping
schedulers on several hosts are safe: each import takes the provider's lease lock.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.db.repositories import ActivityRepository, SessionRepository, TimetableRepository
from app.db.session import transaction
from app.providers.base import ProviderAdapter
from app.providers.contracts import ProviderContract
from app.services.catalog import LocationCatalog
from app.services.imports import ImportLocked, import_snapshot

log = logging.getLogger("tport.scheduler")
AdapterFactory = Callable[[], ProviderAdapter]


@dataclass(frozen=True, slots=True)
class DueResult:
    provider_id: str
    outcome: str  # succeeded | failed | locked | not_due | no_adapter
    detail: str = ""


def is_due(contract: ProviderContract, imports: Sequence, now: datetime) -> bool:
    interval = timedelta(minutes=contract.ingestion.update_interval_minutes or 60)
    last_ok = next((i for i in imports if i.status == "succeeded" and i.finished_at), None)
    if last_ok is None:
        last_attempt = imports[0].started_at if imports else None
        return last_attempt is None or now - last_attempt >= interval  # back off after failures
    return now - last_ok.finished_at >= interval


def run_due_imports(
    contracts: Sequence[ProviderContract],
    factories: dict[str, AdapterFactory],
    factory: sessionmaker[Session],
    clock: Clock,
    catalog: LocationCatalog,
    *,
    days: int = 14,
    market_timezone: str = "Asia/Tashkent",
    source_reference: Callable[[str], str] = lambda pid: f"{pid}-scheduled",
) -> list[DueResult]:
    results: list[DueResult] = []
    now = clock.now()
    for c in contracts:
        if c.ingestion.mode != "stored":
            continue
        pid = c.info.id
        with factory() as db:
            history = TimetableRepository(db).recent_imports(pid, limit=5)
        if not is_due(c, history, now):
            results.append(DueResult(pid, "not_due"))
            continue
        make = factories.get(pid)
        if make is None:
            results.append(DueResult(pid, "no_adapter"))
            continue
        try:
            summary = import_snapshot(
                make(),
                factory,
                clock,
                start=now.astimezone(ZoneInfo(market_timezone)).date(),
                days=days,
                source_reference=source_reference(pid),
                contract=c,
                catalog=catalog,
                trigger="schedule",
            )
            results.append(DueResult(pid, "succeeded", f"{summary['departures']} departures"))
        except ImportLocked:
            results.append(DueResult(pid, "locked"))
        except Exception as exc:  # noqa: BLE001 - recorded in data_imports; keep other providers going
            results.append(DueResult(pid, "failed", type(exc).__name__))
    return results


@dataclass
class Scheduler:
    contracts: Sequence[ProviderContract]
    factories: dict[str, AdapterFactory]
    session_factory: sessionmaker[Session]
    clock: Clock
    catalog: LocationCatalog
    retention_days: int = 180
    market_timezone: str = "Asia/Tashkent"
    _last_housekeeping: datetime | None = field(default=None, init=False)

    def tick(self) -> dict:
        """One scheduling pass. Call every minute; it decides what is due."""
        now = self.clock.now()
        imports = run_due_imports(
            self.contracts,
            self.factories,
            self.session_factory,
            self.clock,
            self.catalog,
            market_timezone=self.market_timezone,
        )
        housekeeping = None
        if self._last_housekeeping is None or now - self._last_housekeeping >= timedelta(days=1):
            with transaction(self.session_factory) as db:
                sessions = SessionRepository(db).purge_expired(now)
                searches, ai = ActivityRepository(db).purge_older_than(
                    now - timedelta(days=self.retention_days)
                )
            housekeeping = {"sessions": sessions, "search_logs": searches, "ai_requests": ai}
            self._last_housekeeping = now
        for r in imports:
            if r.outcome not in ("not_due",):
                log.info("scheduled import %s: %s %s", r.provider_id, r.outcome, r.detail)
        return {
            "imports": [
                {"provider": r.provider_id, "outcome": r.outcome, "detail": r.detail} for r in imports
            ],
            "housekeeping": housekeeping,
        }
