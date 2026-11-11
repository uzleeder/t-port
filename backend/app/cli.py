"""Operational commands.

python -m app.cli seed                 # reference locations/stations/providers (idempotent)
python -m app.cli import-demo --days 14
python -m app.cli purge-sessions                 # expired/revoked sessions
python -m app.cli purge-activity [--days 180]    # search logs + AI request metadata
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.data.reference import LOCATIONS, STATIONS
from app.db.repositories import ActivityRepository, ReferenceRepository, SessionRepository
from app.db.session import make_engine, make_session_factory, transaction
from app.providers.demo.adapter import DemoAdapter
from app.providers.demo.dataset import DATASET_VERSION
from app.providers.registry import REGISTRATIONS
from app.services.catalog import LocationCatalog
from app.services.imports import import_snapshot


def seed_reference(factory) -> None:
    with transaction(factory) as db:
        repo = ReferenceRepository(db)
        repo.sync_locations(LOCATIONS, STATIONS)
        for reg in REGISTRATIONS:
            repo.upsert_provider(
                reg.info, access_basis=reg.access_basis, update_frequency=reg.update_frequency
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    imp = sub.add_parser("import-demo")
    imp.add_argument("--days", type=int, default=14)
    sub.add_parser("purge-sessions")
    purge = sub.add_parser("purge-activity")
    purge.add_argument("--days", type=int, default=None, help="default: TPORT_ACTIVITY_RETENTION_DAYS")
    args = parser.parse_args(argv)

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database_url))
    clock = SystemClock()

    if args.cmd == "seed":
        seed_reference(factory)
        print("Reference data seeded.")
    elif args.cmd == "import-demo":
        seed_reference(factory)
        catalog = LocationCatalog(LOCATIONS, STATIONS)
        start = clock.now().astimezone(ZoneInfo(settings.market_timezone)).date()
        result = import_snapshot(
            DemoAdapter(catalog, clock),
            factory,
            clock,
            start=start,
            days=args.days,
            source_reference=DATASET_VERSION,
        )
        print(json.dumps(result))
    elif args.cmd == "purge-sessions":
        with transaction(factory) as db:
            print(f"Removed {SessionRepository(db).purge_expired(clock.now())} sessions.")
    elif args.cmd == "purge-activity":
        days = args.days or settings.activity_retention_days
        cutoff = clock.now() - timedelta(days=days)
        with transaction(factory) as db:
            searches, ai = ActivityRepository(db).purge_older_than(cutoff)
        print(f"Removed {searches} search logs and {ai} AI request records older than {days} days.")


if __name__ == "__main__":
    main()
