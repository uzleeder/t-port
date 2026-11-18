"""Minimal in-process metrics (Prometheus text format) and structured logging.

No vendor dependency: ``/metrics`` can be scraped by Prometheus, Grafana Agent, the OpenTelemetry
collector or anything that reads the text format. Counters are per process (each API worker reports
its own; aggregate with ``sum``). Labels never contain user input beyond route templates.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict

_BUCKETS = (0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self.hist: dict[tuple[str, str], list[float]] = {}  # (method, route) -> bucket counts + sum + count

    def inc(self, name: str, value: float = 1, **labels: str) -> None:
        with self._lock:
            self.counters[(name, tuple(sorted(labels.items())))] += value

    def observe_request(self, method: str, route: str, status: int, seconds: float) -> None:
        with self._lock:
            self.counters[
                (
                    "tport_http_requests_total",
                    (("method", method), ("route", route), ("status", f"{status // 100}xx")),
                )
            ] += 1
            h = self.hist.setdefault((method, route), [0.0] * (len(_BUCKETS) + 2))
            for i, b in enumerate(_BUCKETS):
                if seconds <= b:
                    h[i] += 1
            h[-2] += seconds
            h[-1] += 1

    def render(self, gauges: dict[str, float] | None = None) -> str:
        lines: list[str] = []
        with self._lock:
            names = sorted({n for n, _ in self.counters})
            for name in names:
                lines.append(f"# TYPE {name} counter")
                for (n, labels), v in sorted(self.counters.items()):
                    if n == name:
                        lbl = ",".join(f'{k}="{_esc(val)}"' for k, val in labels)
                        lines.append(f"{name}{{{lbl}}} {v:g}" if lbl else f"{name} {v:g}")
            if self.hist:
                lines.append("# TYPE tport_http_request_duration_seconds histogram")
                for (method, route), h in sorted(self.hist.items()):
                    base = f'method="{method}",route="{_esc(route)}"'
                    for i, b in enumerate(_BUCKETS):
                        lines.append(
                            f'tport_http_request_duration_seconds_bucket{{{base},le="{b}"}} {h[i]:g}'
                        )
                    lines.append(f'tport_http_request_duration_seconds_bucket{{{base},le="+Inf"}} {h[-1]:g}')
                    lines.append(f"tport_http_request_duration_seconds_sum{{{base}}} {h[-2]:.6f}")
                    lines.append(f"tport_http_request_duration_seconds_count{{{base}}} {h[-1]:g}")
        for name, value in sorted((gauges or {}).items()):
            lines += [f"# TYPE {name} gauge", f"{name} {value:g}"]
        return "\n".join(lines) + "\n"


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Only the message and safe metadata: no request bodies or headers."""

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            out["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(out, ensure_ascii=False)


def configure_logging(level: str, fmt: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if getattr(root, "_tport_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter()
        if fmt == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.handlers = [handler]
    root._tport_configured = True  # type: ignore[attr-defined]
