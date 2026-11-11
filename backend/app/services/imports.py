"""Snapshot import: pull a date window from a provider adapter into the database.

Each run is recorded in ``data_imports`` (status, counts, source timestamp) and
replaces that provider's departures for the window atomically.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from itertools import permutations

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.db.repositories import TimetableRepository
from app.db.session import transaction
from app.domain.models import Departure, Offer
from app.providers.base import ProviderAdapter

log = logging.getLogger("tport.imports")


async def _collect(
    adapter: ProviderAdapter, start: date, days: int
) -> tuple[list[Departure], list[Offer], dict[str, date]]:
    departures: list[Departure] = []
    travel_dates: dict[str, date] = {}
    locs = sorted(adapter.supported_location_ids())
    for offset in range(days):
        day = start + timedelta(days=offset)
        for origin, destination in permutations(locs, 2):
            for dep in await adapter.get_departures(origin, destination, day, frozenset()):
                departures.append(dep)
                travel_dates[dep.id] = day
    offers = list(await adapter.get_offers([d.id for d in departures])) if departures else []
    return departures, offers, travel_dates


def import_snapshot(
    adapter: ProviderAdapter,
    factory: sessionmaker[Session],
    clock: Clock,
    *,
    start: date,
    days: int,
    source_reference: str,
    timezone: str = "Asia/Tashkent",
) -> dict:
    if not 1 <= days <= 120:
        raise ValueError("days must be between 1 and 120")
    end = start + timedelta(days=days - 1)
    with transaction(factory) as db:
        imp = TimetableRepository(db).start_import(adapter.id, source_reference, clock.now())
        import_id = imp.id
    try:
        departures, offers, travel_dates = asyncio.run(_collect(adapter, start, days))
        source_updated = max((d.source_updated_at for d in departures if d.source_updated_at), default=None)
        with transaction(factory) as db:
            repo = TimetableRepository(db)
            imp = db.merge(imp)
            repo.replace_window(adapter.id, start, end, departures, offers, imp, travel_dates, timezone)
            repo.finish_import(
                imp,
                clock.now(),
                departures=len(departures),
                offers=len(offers),
                source_updated_at=source_updated,
            )
    except Exception as exc:
        log.exception("import %s failed", import_id)
        with transaction(factory) as db:
            imp = db.merge(imp)
            TimetableRepository(db).finish_import(
                imp,
                clock.now(),
                departures=0,
                offers=0,
                source_updated_at=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        raise
    return {
        "import_id": str(import_id),
        "departures": len(departures),
        "offers": len(offers),
        "window": [start.isoformat(), end.isoformat()],
    }
