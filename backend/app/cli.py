"""Operational commands.

python -m app.cli seed                                   # locations/stations/providers (idempotent)
python -m app.cli import-provider demo [--days 14] [--trigger cron]
python -m app.cli import-demo [--days 14]                # alias of import-provider demo
python -m app.cli import-due                             # import every stored provider that is due
python -m app.cli cancel-import demo                     # ask a running import to stop
python -m app.cli scheduler [--interval 60] [--once]     # long-running: due imports + housekeeping
python -m app.cli check-provider demo [--days 2]         # contract conformance; exit 1 on violations
python -m app.cli provider-health                        # exit 0 ok, 1 degraded/unknown, 2 unavailable
python -m app.cli purge-sessions                         # expired/revoked sessions
python -m app.cli purge-activity [--days 180]            # search logs + AI request metadata

Exit code 75 (EX_TEMPFAIL) from an import means another import holds the lock: retry later.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import threading
from dataclasses import replace
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.clock import SystemClock
from app.core.config import Settings, get_settings
from app.core.metrics import configure_logging
from app.data.reference import LOCATIONS, STATIONS
from app.db.repositories import (
    ActivityRepository,
    ReferenceRepository,
    SessionRepository,
    TimetableRepository,
)
from app.db.session import make_engine, make_session_factory, transaction
from app.providers.contracts import ProviderContract, check_conformance, contract_problems
from app.providers.demo.dataset import DATASET_VERSION
from app.providers.registry import CONTRACTS, adapter_factories, contract_for
from app.services.catalog import LocationCatalog
from app.services.imports import ImportLocked, import_snapshot
from app.services.provider_health import assess_provider, overall
from app.services.scheduler import Scheduler, run_due_imports

EX_TEMPFAIL = 75
_EXIT = {"healthy": 0, "disabled": 0, "unknown": 1, "degraded": 1, "unavailable": 2}


def seed_reference(factory) -> None:
    with transaction(factory) as db:
        repo = ReferenceRepository(db)
        repo.sync_locations(LOCATIONS, STATIONS)
        for c in CONTRACTS:
            repo.upsert_provider(c.info, access_basis=c.access_basis, update_frequency=c.update_frequency)


def effective_contracts(settings: Settings) -> list[ProviderContract]:
    """Registered contracts as configured here (the demo provider may run in stored mode)."""
    stored_demo = settings.demo_provider_mode == "stored"
    return [
        replace(c, ingestion=replace(c.ingestion, mode="stored")) if stored_demo and c.info.is_demo else c
        for c in CONTRACTS
    ]


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:  # noqa: C901 - flat command dispatch
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    for name in ("import-provider", "import-demo"):
        imp = sub.add_parser(name)
        if name == "import-provider":
            imp.add_argument("provider")
        imp.add_argument("--days", type=int, default=14)
        imp.add_argument("--trigger", default="manual", choices=["manual", "cron", "deploy", "schedule"])
    sub.add_parser("import-due")
    cancel = sub.add_parser("cancel-import")
    cancel.add_argument("provider")
    sched = sub.add_parser("scheduler")
    sched.add_argument("--interval", type=int, default=60)
    sched.add_argument("--once", action="store_true")
    chk = sub.add_parser("check-provider")
    chk.add_argument("provider")
    chk.add_argument("--days", type=int, default=2)
    sub.add_parser("provider-health")
    sub.add_parser("purge-sessions")
    purge = sub.add_parser("purge-activity")
    purge.add_argument("--days", type=int, default=None, help="default: TPORT_ACTIVITY_RETENTION_DAYS")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    clock = SystemClock()
    catalog = LocationCatalog(LOCATIONS, STATIONS)
    today = clock.now().astimezone(ZoneInfo(settings.market_timezone)).date()
    factories = adapter_factories(catalog, clock)
    contracts = {c.info.id: c for c in effective_contracts(settings)}

    if args.cmd == "check-provider":  # no database needed
        contract = contract_for(args.provider)
        if contract is None or args.provider not in factories:
            print(f"Unknown provider or no adapter wired: {args.provider!r}", file=sys.stderr)
            return 2
        adapter = factories[args.provider]()
        routes = sorted(adapter.served_routes() or [])
        queries = [(o, d, today + timedelta(days=i + 1)) for i in range(args.days) for o, d in routes]
        report = asyncio.run(check_conformance(adapter, contract, catalog, queries, clock.now()))
        problems = contract_problems(contract, today)
        _print(
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
            }
        )
        return 0 if report.ok and not problems else 1

    factory = make_session_factory(make_engine(settings.database_url))

    if args.cmd == "seed":
        seed_reference(factory)
        print("Reference data seeded.")
    elif args.cmd in ("import-provider", "import-demo"):
        pid = getattr(args, "provider", "demo")
        contract = contracts.get(pid)
        if contract is None or pid not in factories:
            print(f"Unknown provider or no adapter wired: {pid!r}", file=sys.stderr)
            return 2
        problems = contract_problems(contract, today)
        if problems:
            print(f"provider {pid} is not enabled: {'; '.join(problems)}", file=sys.stderr)
            return 2
        if contract.ingestion.mode != "stored":  # one-off import of a live provider is allowed
            contract = replace(contract, ingestion=replace(contract.ingestion, mode="stored"))
        seed_reference(factory)
        try:
            result = import_snapshot(
                factories[pid](),
                factory,
                clock,
                start=today,
                days=args.days,
                source_reference=DATASET_VERSION if pid == "demo" else pid,
                contract=contract,
                catalog=catalog,
                trigger=args.trigger,
            )
        except ImportLocked as exc:
            print(str(exc), file=sys.stderr)
            return EX_TEMPFAIL
        except Exception as exc:  # noqa: BLE001 - recorded in data_imports; non-zero exit for alerts
            print(f"import failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result))
    elif args.cmd == "import-due":
        enabled = [c for c in contracts.values() if not contract_problems(c, today)]
        results = run_due_imports(
            enabled, factories, factory, clock, catalog, market_timezone=settings.market_timezone
        )
        _print([{"provider": r.provider_id, "outcome": r.outcome, "detail": r.detail} for r in results])
        return 1 if any(r.outcome == "failed" for r in results) else 0
    elif args.cmd == "cancel-import":
        with transaction(factory) as db:
            n = TimetableRepository(db).request_cancel(args.provider)
        print(f"Cancellation requested for {n} running import(s) of {args.provider}.")
    elif args.cmd == "scheduler":
        enabled = [c for c in contracts.values() if not contract_problems(c, today)]
        scheduler = Scheduler(
            enabled,
            factories,
            factory,
            clock,
            catalog,
            retention_days=settings.activity_retention_days,
            market_timezone=settings.market_timezone,
        )
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        seed_reference(factory)
        while not stop.is_set():
            try:
                outcome = scheduler.tick()
                if args.once:
                    _print(outcome)
                    return 0
            except Exception as exc:  # noqa: BLE001 - keep the scheduler alive; the error is logged
                print(f"scheduler tick failed: {type(exc).__name__}", file=sys.stderr)
                if args.once:
                    return 1
            stop.wait(args.interval)
    elif args.cmd == "provider-health":
        with factory() as db:
            repo = TimetableRepository(db)
            health = [
                assess_provider(
                    c, None, repo.recent_imports(c.info.id), clock.now(), problems=contract_problems(c, today)
                )
                for c in contracts.values()
            ]
        status = overall([h.status for h in health])
        _print(
            {
                "status": status,
                "providers": [
                    {
                        "provider": h.provider_id,
                        "mode": h.mode,
                        "status": h.status,
                        "reasons": list(h.reasons),
                        "import_lag_seconds": h.import_lag_seconds,
                        "last_departures": h.last_departures,
                        "last_rejected_records": h.last_rejected_records,
                    }
                    for h in health
                ],
            }
        )
        return _EXIT[status]
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
