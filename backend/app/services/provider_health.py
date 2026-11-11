"""Per-provider health: live call statistics plus stored-import lag, turned into a status.

Statuses:
* ``healthy``: data is current and recent calls/imports succeed.
* ``degraded``: usable but needs attention (stale data, intermittent failures, imports late).
* ``down``: users get nothing useful from this source (expired data, mostly failing calls).
* ``unknown``: no evidence yet (no traffic since start, never imported).

Health is never inferred from one data point: thresholds need several calls or imports.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from app.db import models as m
from app.providers.contracts import ProviderContract

Status = Literal["healthy", "degraded", "down", "unknown"]
_ORDER: dict[Status, int] = {"healthy": 0, "unknown": 1, "degraded": 2, "down": 3}
_WINDOW = 50  # recent live calls considered


@dataclass(slots=True)
class ProviderCallStats:
    """Thread-safe rolling record of live calls to one provider (in-process only)."""

    calls_total: int = 0
    failures_total: int = 0
    timeouts_total: int = 0
    latency_ms_total: float = 0.0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    recent: deque[bool] = field(default_factory=lambda: deque(maxlen=_WINDOW))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def success(self, latency_ms: float, now: datetime) -> None:
        with self._lock:
            self.calls_total += 1
            self.latency_ms_total += latency_ms
            self.last_success_at = now
            self.recent.append(True)

    def failure(self, error: BaseException, now: datetime) -> None:
        with self._lock:
            self.calls_total += 1
            self.failures_total += 1
            if isinstance(error, TimeoutError):
                self.timeouts_total += 1
            self.last_failure_at = now
            self.last_error = type(error).__name__  # never the message: it may echo request data
            self.recent.append(False)

    @property
    def recent_failure_rate(self) -> float | None:
        with self._lock:
            return None if not self.recent else 1 - sum(self.recent) / len(self.recent)


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider_id: str
    name: str
    is_demo: bool
    mode: str
    status: Status
    reasons: tuple[str, ...]
    last_import_status: str | None = None
    last_successful_import_at: datetime | None = None
    import_lag_seconds: float | None = None
    consecutive_import_failures: int = 0
    calls_total: int = 0
    failures_total: int = 0
    recent_failure_rate: float | None = None
    last_error: str | None = None


def _worst(a: Status, b: Status) -> Status:
    return a if _ORDER[a] >= _ORDER[b] else b


def assess_provider(
    contract: ProviderContract,
    stats: ProviderCallStats | None,
    imports: Sequence[m.DataImport],  # newest first
    now: datetime,
) -> ProviderHealth:
    status: Status = "healthy"
    reasons: list[str] = []
    mode = contract.ingestion.mode

    # Live calls (both modes: stored providers are also called, against the database).
    rate = stats.recent_failure_rate if stats else None
    sample = len(stats.recent) if stats else 0
    failed = round(rate * sample) if rate is not None else 0
    if sample >= 5:  # integer comparisons: no floating-point edge at exactly 10% or 50%
        if failed * 2 >= sample:
            status = _worst(status, "down")
            reasons.append(f"{failed} of the last {sample} calls failed")
        elif failed * 10 >= sample:
            status = _worst(status, "degraded")
            reasons.append(f"{failed} of the last {sample} calls failed")
    elif mode == "live" and sample == 0:
        status = _worst(status, "unknown")
        reasons.append("no calls since the service started")

    # Stored snapshots: lag since the last successful import, and failure streaks.
    last_ok = next((i for i in imports if i.status == "succeeded"), None)
    failures = 0
    for i in imports:
        if i.status == "failed":
            failures += 1
        elif i.status == "succeeded":
            break
    lag = (now - last_ok.finished_at).total_seconds() if last_ok and last_ok.finished_at else None
    if mode == "stored":
        interval = timedelta(minutes=contract.ingestion.update_interval_minutes or 60)
        if last_ok is None:
            status = _worst(status, "down" if imports else "unknown")
            reasons.append("no successful import yet")
        elif lag is not None:
            if lag >= contract.expire_after.total_seconds():
                status = _worst(status, "down")
                reasons.append("last good import is older than the expiry limit: results are hidden")
            elif lag >= contract.stale_after.total_seconds() or lag >= 2 * interval.total_seconds():
                status = _worst(status, "degraded")
                reasons.append(f"imports are late (last success {lag / 60:.0f} min ago)")
        if failures >= 3:
            status = _worst(status, "degraded")
            reasons.append(f"{failures} imports failed in a row")

    if not reasons:
        reasons.append("ok")
    return ProviderHealth(
        provider_id=contract.info.id,
        name=contract.info.name,
        is_demo=contract.info.is_demo,
        mode=mode,
        status=status,
        reasons=tuple(reasons),
        last_import_status=imports[0].status if imports else None,
        last_successful_import_at=last_ok.finished_at if last_ok else None,
        import_lag_seconds=lag,
        consecutive_import_failures=failures,
        calls_total=stats.calls_total if stats else 0,
        failures_total=stats.failures_total if stats else 0,
        recent_failure_rate=rate,
        last_error=stats.last_error if stats else None,
    )


def overall(statuses: Sequence[Status]) -> Status:
    worst: Status = "healthy"
    for s in statuses:
        worst = _worst(worst, s)
    return worst


def prometheus_metrics(health: Sequence[ProviderHealth], now: datetime) -> str:
    """Prometheus text exposition of provider health (scrape with an ops token)."""
    lines = [
        "# HELP tport_provider_up 1 healthy, 0.5 degraded or unknown, 0 down.",
        "# TYPE tport_provider_up gauge",
    ]
    up = {"healthy": 1, "degraded": 0.5, "unknown": 0.5, "down": 0}
    for h in health:
        lines.append(f'tport_provider_up{{provider="{h.provider_id}",mode="{h.mode}"}} {up[h.status]}')
    lines += [
        "# HELP tport_provider_calls_total Live calls since process start.",
        "# TYPE tport_provider_calls_total counter",
    ]
    lines += [f'tport_provider_calls_total{{provider="{h.provider_id}"}} {h.calls_total}' for h in health]
    lines += [
        "# HELP tport_provider_failures_total Failed live calls.",
        "# TYPE tport_provider_failures_total counter",
    ]
    lines += [
        f'tport_provider_failures_total{{provider="{h.provider_id}"}} {h.failures_total}' for h in health
    ]
    lines += [
        "# HELP tport_provider_import_lag_seconds Seconds since the last successful import.",
        "# TYPE tport_provider_import_lag_seconds gauge",
    ]
    lines += [
        f'tport_provider_import_lag_seconds{{provider="{h.provider_id}"}} {h.import_lag_seconds:.0f}'
        for h in health
        if h.import_lag_seconds is not None
    ]
    lines += [
        "# HELP tport_provider_import_failures_consecutive Failed imports since the last success.",
        "# TYPE tport_provider_import_failures_consecutive gauge",
    ]
    name = "tport_provider_import_failures_consecutive"
    lines += [f'{name}{{provider="{h.provider_id}"}} {h.consecutive_import_failures}' for h in health]
    lines.append(f"# generated {now.isoformat()}")
    return "\n".join(lines) + "\n"
