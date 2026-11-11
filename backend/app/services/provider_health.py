"""Per-provider health: live call statistics plus stored-import lag, turned into a status.

Statuses:
* ``healthy``: data is current and recent calls/imports succeed.
* ``degraded``: usable but needs attention (stale data, intermittent failures, imports late).
* ``unavailable``: users get nothing useful from this source (expired data, mostly failing calls).
* ``disabled``: switched off (contract invalid, expired or ``enabled=False``); not an outage.
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

Status = Literal["healthy", "degraded", "unavailable", "disabled", "unknown"]
_ORDER: dict[Status, int] = {"disabled": 0, "healthy": 1, "unknown": 2, "degraded": 3, "unavailable": 4}
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
    last_attempted_import_at: datetime | None = None
    last_successful_import_at: datetime | None = None
    last_source_update_at: datetime | None = None
    import_lag_seconds: float | None = None  # age of the data users currently see
    last_import_duration_ms: int | None = None
    last_departures: int | None = None
    last_offers: int | None = None
    last_rejected_records: int | None = None
    consecutive_import_failures: int = 0
    failed_imports_recent: int = 0
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
    *,
    problems: Sequence[str] = (),
) -> ProviderHealth:
    status: Status = "healthy"
    reasons: list[str] = []
    mode = contract.ingestion.mode
    if problems or not contract.enabled:
        return ProviderHealth(
            provider_id=contract.info.id,
            name=contract.info.name,
            is_demo=contract.info.is_demo,
            mode=mode,
            status="disabled",
            reasons=tuple(problems) or ("disabled by contract",),
        )

    # Live calls (both modes: stored providers are also called, against the database).
    rate = stats.recent_failure_rate if stats else None
    sample = len(stats.recent) if stats else 0
    failed = round(rate * sample) if rate is not None else 0
    if sample >= 5:  # integer comparisons: no floating-point edge at exactly 10% or 50%
        if failed * 2 >= sample:
            status = _worst(status, "unavailable")
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
            status = _worst(status, "unavailable" if imports else "unknown")
            reasons.append("no successful import yet")
        elif lag is not None:
            if lag >= contract.expire_after.total_seconds():
                status = _worst(status, "unavailable")
                reasons.append("last good import is older than the expiry limit: results are hidden")
            elif lag >= contract.stale_after.total_seconds() or lag >= 2 * interval.total_seconds():
                status = _worst(status, "degraded")
                reasons.append(f"imports are late (last success {lag / 60:.0f} min ago)")
        if failures >= 3:
            status = _worst(status, "degraded")
            reasons.append(f"{failures} imports failed in a row")
        if last_ok is not None and not last_ok.offers_count:
            status = _worst(status, "degraded")
            reasons.append("last import published no valid offers")
        previous_ok = next((i for i in imports if i.status == "succeeded" and i is not last_ok), None)
        if last_ok and previous_ok and previous_ok.departures_count >= 20:
            if last_ok.departures_count < previous_ok.departures_count * 0.5:
                status = _worst(status, "degraded")
                reasons.append(
                    f"departures dropped from {previous_ok.departures_count} to {last_ok.departures_count}"
                )

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
        last_attempted_import_at=imports[0].started_at if imports else None,
        last_successful_import_at=last_ok.finished_at if last_ok else None,
        last_source_update_at=last_ok.source_updated_at if last_ok else None,
        import_lag_seconds=lag,
        last_import_duration_ms=imports[0].duration_ms if imports else None,
        last_departures=last_ok.departures_count if last_ok else None,
        last_offers=last_ok.offers_count if last_ok else None,
        last_rejected_records=imports[0].rejected_records if imports else None,
        consecutive_import_failures=failures,
        failed_imports_recent=sum(1 for i in imports if i.status == "failed"),
        calls_total=stats.calls_total if stats else 0,
        failures_total=stats.failures_total if stats else 0,
        recent_failure_rate=rate,
        last_error=stats.last_error if stats else None,
    )


def overall(statuses: Sequence[Status]) -> Status:
    """Worst status among enabled providers (disabled ones are ignored)."""
    worst: Status = "healthy"
    for st in statuses:
        if st != "disabled":
            worst = _worst(worst, st)
    return worst


def prometheus_metrics(health: Sequence[ProviderHealth], now: datetime) -> str:
    """Prometheus text exposition of provider health (scrape with an ops token)."""
    lines = [
        "# HELP tport_provider_up 1 healthy, 0.5 degraded or unknown, 0 unavailable, -1 disabled.",
        "# TYPE tport_provider_up gauge",
    ]
    up = {"healthy": 1, "degraded": 0.5, "unknown": 0.5, "unavailable": 0, "disabled": -1}
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
    lines += [
        "# HELP tport_provider_import_rejected_records Records quarantined by the last import.",
        "# TYPE tport_provider_import_rejected_records gauge",
    ]
    lines += [
        f'tport_provider_import_rejected_records{{provider="{h.provider_id}"}} {h.last_rejected_records}'
        for h in health
        if h.last_rejected_records is not None
    ]
    lines += [
        "# HELP tport_provider_last_import_departures Departures published by the last good import.",
        "# TYPE tport_provider_last_import_departures gauge",
    ]
    lines += [
        f'tport_provider_last_import_departures{{provider="{h.provider_id}"}} {h.last_departures}'
        for h in health
        if h.last_departures is not None
    ]
    lines.append(f"# generated {now.isoformat()}")
    return "\n".join(lines) + "\n"
