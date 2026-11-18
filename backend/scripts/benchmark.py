"""Reproducible latency benchmark for search, routing, comparison and the assistant.

Usage (from backend/):  python scripts/benchmark.py [--iterations 30] [--json out.json]

Runs in-process against the demo dataset with a fixed clock, so numbers are comparable between
commits on the same machine. It does NOT measure network, TLS, PostgreSQL or the Next.js server;
see docs/performance-benchmarks.md for what that means for production.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.clock import FixedClock  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.data.reference import LOCATIONS, STATIONS  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.session import make_engine, make_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.demo.adapter import DemoAdapter  # noqa: E402
from app.services.catalog import LocationCatalog  # noqa: E402
from app.services.freshness import FreshnessPolicy  # noqa: E402
from app.services.journey_graph import GraphLimits, JourneyGraph  # noqa: E402
from app.services.search import SearchQuery, SearchService  # noqa: E402

NOW = datetime(2026, 11, 11, 5, 0, tzinfo=UTC)
DAY = date(2026, 11, 12)
PAIRS = [
    ("tashkent", "samarkand"),
    ("tashkent", "bukhara"),
    ("tashkent", "khiva"),
    ("samarkand", "khiva"),
    ("samarkand", "termez"),
    ("bukhara", "tashkent"),
]


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1))))
    return ordered[k]


def summary(ms: list[float]) -> dict:
    return {
        "n": len(ms),
        "p50_ms": round(statistics.median(ms), 2),
        "p95_ms": round(pct(ms, 95), 2),
        "max_ms": round(max(ms), 2),
    }


def engine_bench(iterations: int) -> dict:
    catalog = LocationCatalog(LOCATIONS, STATIONS)
    clock = FixedClock(NOW)
    demo = DemoAdapter(catalog, clock)
    policy = FreshnessPolicy(timedelta(minutes=15), timedelta(hours=6))
    out = {}
    for transfers in (0, 1, 2):
        svc = SearchService(catalog, [demo], clock, policy)
        times, results = [], []
        for _ in range(3):  # warm-up
            asyncio.run(svc.search(SearchQuery(*PAIRS[0], DAY, max_transfers=transfers)))
        for _ in range(iterations):
            for origin, destination in PAIRS:
                q = SearchQuery(origin, destination, DAY, max_transfers=transfers, page_size=50)
                t0 = time.perf_counter()
                r = asyncio.run(svc.search(q))
                times.append((time.perf_counter() - t0) * 1000)
                results.append(r.total)
        mean_results = round(statistics.mean(results), 1)
        out[f"max_transfers={transfers}"] = summary(times) | {"mean_results": mean_results}
    graph = JourneyGraph.from_providers([demo])
    out["graph"] = {
        "locations": len({*graph.adj, *(b for v in graph.adj.values() for b in v)}),
        "edges": sum(len(v) for v in graph.adj.values()),
        "paths_tashkent_khiva_2_transfers": len(
            graph.location_paths("tashkent", "khiva", GraphLimits(max_legs=3))
        ),
    }
    return out


def api_bench(iterations: int) -> dict:
    tmp = tempfile.mkdtemp()
    engine = make_engine(f"sqlite:///{os.path.join(tmp, 'bench.db')}")
    Base.metadata.create_all(engine)  # same schema as the migrations (alembic check keeps them equal)
    settings = Settings(
        environment="test",
        rate_limit_per_minute=100_000,
        auth_rate_limit_per_minute=100_000,
        ai_rate_limit_per_minute=100_000,
        cors_origins=["http://localhost:2028"],
        log_level="WARNING",
    )
    app = create_app(settings, clock=FixedClock(NOW), session_factory=make_session_factory(engine))
    with TestClient(app) as c:
        base = {"origin": "tashkent", "destination": "bukhara", "date": DAY.isoformat()}
        first = c.get("/api/v1/journeys/search", params={**base, "max_transfers": 2, "page_size": 50})
        items = first.json()["items"]
        ids = ",".join(j["id"] for j in items[:3])
        cases = {
            "GET /journeys/search (max_transfers=2)": lambda: c.get(
                "/api/v1/journeys/search", params={**base, "max_transfers": 2}
            ),
            "GET /journeys/{id}": lambda: c.get(f"/api/v1/journeys/{items[0]['id']}"),
            "GET /journeys/compare (3 ids)": lambda: c.get("/api/v1/journeys/compare", params={"ids": ids}),
            "POST /ai/interpret (rules engine)": lambda: c.post(
                "/api/v1/ai/interpret",
                json={"text": "Samarkand to Khiva tomorrow, arrive by 6 pm, fewest changes"},
            ),
        }
        out = {}
        for name, call in cases.items():
            for _ in range(3):
                call()
            times = []
            for _ in range(iterations):
                t0 = time.perf_counter()
                r = call()
                times.append((time.perf_counter() - t0) * 1000)
                assert r.status_code == 200, (name, r.status_code, r.text[:200])
            out[name] = summary(times)
        with app.state.session_factory() as db:
            out["rows_written"] = {
                "journey_searches": db.scalar(text("SELECT count(*) FROM journey_searches")),
                "ai_requests": db.scalar(text("SELECT count(*) FROM ai_requests")),
            }
    engine.dispose()
    return out


QUERIES = {
    "stored departures by route and date": (
        "SELECT * FROM departures WHERE provider_id = 'demo' AND origin_station_id IN ('tashkent-rail') "
        "AND destination_station_id IN ('samarkand-rail') AND travel_date = '2026-11-12'"
    ),
    "import publish: delete provider departures in a date range": (
        "DELETE FROM departures WHERE provider_id = 'demo' AND travel_date >= '2026-11-12' "
        "AND travel_date <= '2026-12-12'"
    ),
    "dashboard: recent searches of a user": (
        "SELECT * FROM journey_searches WHERE user_id = X'00' ORDER BY created_at DESC LIMIT 5"
    ),
    "dashboard: saved journeys of a user": (
        "SELECT * FROM saved_journeys WHERE user_id = X'00' ORDER BY created_at DESC LIMIT 10"
    ),
    "booking counts since a day": "SELECT provider_id, sum(count) FROM booking_redirect_counts "
    "WHERE day >= '2026-11-01' GROUP BY provider_id",
}


def query_plans() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_engine(f"sqlite:///{os.path.join(tmp, 'plan.db')}")
        Base.metadata.create_all(engine)
        plans = {}
        with engine.connect() as conn:
            for name, sql in QUERIES.items():
                rows = conn.execute(text(f"EXPLAIN QUERY PLAN {sql}")).all()
                plans[name] = [r[-1] for r in rows]
        engine.dispose()
    return plans


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system() + " " + platform.release(),
            "machine": platform.machine(),
            "cpus": os.cpu_count(),
        },
        "engine": engine_bench(args.iterations),
        "api": api_bench(args.iterations * 2),
        "query_plans_sqlite": query_plans(),
    }
    print(json.dumps(report, indent=2))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
