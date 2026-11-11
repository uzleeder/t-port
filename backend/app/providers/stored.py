"""Adapter that serves a provider's most recent *imported* snapshot from PostgreSQL.

Provenance is preserved: ``retrieved_at`` is the time the import fetched the data,
so freshness checks degrade results naturally when imports stop running.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from app.db.repositories import TimetableRepository
from app.domain.models import Departure, Offer, ProviderInfo, TransportMode
from app.providers.base import ProviderAdapter, ProviderError, RateLimitPolicy
from app.services.catalog import LocationCatalog


class StoredTimetableAdapter(ProviderAdapter):
    rate_limit = RateLimitPolicy(timeout_seconds=5.0)

    def __init__(
        self,
        info: ProviderInfo,
        catalog: LocationCatalog,
        factory: sessionmaker[Session],
        location_ids: frozenset[str],
    ) -> None:
        self.info = info
        self._catalog = catalog
        self._factory = factory
        self._locations = location_ids

    def supported_location_ids(self) -> frozenset[str]:
        return self._locations

    def _stations(self, location_id: str) -> list[str]:
        return [s.id for s in self._catalog.stations_for(location_id)]

    async def _run(self, fn):
        def work():
            with self._factory() as db:
                return fn(TimetableRepository(db))

        try:
            return await asyncio.to_thread(work)
        except Exception as exc:  # database errors become provider errors (isolated per provider)
            raise ProviderError(self.id, f"stored timetable unavailable: {type(exc).__name__}") from exc

    async def get_departures(
        self,
        origin_location_id: str,
        destination_location_id: str,
        travel_date: date,
        modes: frozenset[TransportMode],
    ) -> Sequence[Departure]:
        o, d = self._stations(origin_location_id), self._stations(destination_location_id)
        return await self._run(lambda repo: repo.departures(self.id, o, d, travel_date, modes))

    async def get_departure(self, departure_id: str) -> Departure | None:
        return await self._run(lambda repo: repo.departure(self.id, departure_id))

    async def get_offers(self, departure_ids: Sequence[str]) -> Sequence[Offer]:
        ids = list(departure_ids)
        return await self._run(lambda repo: repo.offers(self.id, ids))
