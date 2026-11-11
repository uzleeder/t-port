"""Operational commands.

python -m app.cli seed                              # locations/stations/providers (idempotent)
python -m app.cli import-demo --days 14 [--trigger cron]
python -m app.cli check-provider demo [--days 2]    # contract conformance; exit 1 on violations
python -m app.cli provider-health                   # exit 0 ok, 1 degraded/unknown, 2 down
python -m app.cli purge-sessions                    # expired/revoked sessions
python -m app.cli purge-activity [--days 180]       # search logs + AI request metadata

Exit code 75 (EX_TEMPFAIL) from import-demo means another import holds the lock: retry later.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.data.reference import LOCATIONS, STATIONS
from app.db.repositories import (
    ActivityRepository,
    ReferenceRepository,
    SessionRepository,
    TimetableRepository,
)
from app.db.session import make_engine, make_session_factory, transaction
from app.providers.contracts import check_conformance, contract_problems
from app.providers.demo.adapter import DemoAdapter
from app.providers.demo.dataset import DATASET_VERSION
from app.providers.registry import CONTRACTS, DEMO_CONTRACT, contract_for
from app.services.catalog import LocationCatalog
from app.services.imports import ImportLocked, import_snapshot
from app.services.provider_health import assess_provider, overall

EX_TEMPFAIL = 75


def seed_reference(factory) -> None:
    with transaction(factory) as db:
        repo = ReferenceRepository(db)
        repo.sync_locations(LOCATIONS, STATIONS)
        for c in CONTRACTS:
            repo.upsert_provider(c.info, access_basis=c.access_basis, update_frequency=c.update_frequency)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    imp = sub.add_parser("import-demo")
    imp.add_argument("--days", type=int, default=14)
    imp.add_argument("--trigger", default="manual", choices=["manual", "cron", "deploy"])
    chk = sub.add_parser("check-provider")
    chk.add_argument("provider")
    chk.add_argument("--days", type=int, default=2)
    sub.add_parser("provider-health")
    sub.add_parser("purge-sessions")
    purge = sub.add_parser("purge-activity")
    purge.add_argument("--days", type=int, default=None, help="default: TPORT_ACTIVITY_RETENTION_DAYS")
    args = parser.parse_args(argv)

    settings = get_settings()
    clock = SystemClock()
    catalog = LocationCatalog(LOCATIONS, STATIONS)
    today = clock.now().astimezone(ZoneInfo(settings.market_timezone)).date()

    if args.cmd == "check-provider":  # no database needed
        contract = contract_for(args.provider)
        if contract is None:
            print(f"Unknown provider {args.provider!r}", file=sys.stderr)
            return 2
        problems = contract_problems(contract, today)
        adapter = DemoAdapter(catalog, clock) if contract.info.id == "demo" else None
        if adapter is None:
            print("No adapter wired for this provider in the CLI yet.", file=sys.stderr)
            return 2
        routes = sorted(adapter.served_routes() or [])
        queries = [(o, d, today + timedelta(days=i + 1)) for i in range(args.days) for o, d in routes]
        report = asyncio.run(check_conformance(adapter, contract, catalog, queries, clock.now()))
        print(
            json.dumps(
                {
                    "provider": report.provider_id,
                    "contract_problems": problems,
                    "queries": report.queries,
                    "departures": report.departures,
                    "offers": report.offers,
                    "violations": [
                        {"code": v.code, "subject": v.subject, "message": v.message}
                        for v in report.violations[:50]
                    ],
                },
                indent=2,
            )
        )
        return 0 if report.ok and not problems else 1

    factory = make_session_factory(make_engine(settings.database_url))

    if args.cmd == "seed":
        seed_reference(factory)
        print("Reference data seeded.")
    elif args.cmd == "import-demo":
        seed_reference(factory)
        contract = replace(DEMO_CONTRACT, ingestion=replace(DEMO_CONTRACT.ingestion, mode="stored"))
        try:
            result = import_snapshot(
                DemoAdapter(catalog, clock),
                factory,
                clock,
                start=today,
                days=args.days,
                source_reference=DATASET_VERSION,
                contract=contract,
                catalog=catalog,
                trigger=args.trigger,
            )
        except ImportLocked as exc:
            print(str(exc), file=sys.stderr)
            return EX_TEMPFAIL
        except Exception as exc:  # noqa: BLE001 - recorded in data_imports; non-zero exit for cron alerts
            print(f"import failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result))
    elif args.cmd == "provider-health":
        stored = settings.demo_provider_mode == "stored"
        contracts = [
            replace(c, ingestion=replace(c.ingestion, mode="stored")) if stored and c.info.is_demo else c
            for c in CONTRACTS
        ]
        with factory() as db:
            repo = TimetableRepository(db)
            health = [
                assess_provider(c, None, repo.recent_imports(c.info.id), clock.now()) for c in contracts
            ]
        status = overall([h.status for h in health])
        print(
            json.dumps(
                {
                    "status": status,
                    "providers": [
                        {
                            "provider": h.provider_id,
                            "mode": h.mode,
                            "status": h.status,
                            "reasons": list(h.reasons),
                            "import_lag_seconds": h.import_lag_seconds,
                        }
                        for h in health
                    ],
                },
                indent=2,
            )
        )
        return {"healthy": 0, "unknown": 1, "degraded": 1, "down": 2}[status]
    elif args.cmd == "purge-sessions":
        with transaction(factory) as db:
            print(f"Removed {SessionRepository(db).purge_expired(clock.now())} sessions.")
    elif args.cmd == "purge-activity":
        days = args.days or settings.activity_retention_days
        cutoff = clock.now() - timedelta(days=days)
        with transaction(factory) as db:
            searches, ai = ActivityRepository(db).purge_older_than(cutoff)
        print(f"Removed {searches} search logs and {ai} AI request records older than {days} days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
