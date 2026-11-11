"""Fault simulation for demos, end-to-end tests and pilot training (never in production).

Enabled only with ``TPORT_ENABLE_FAULT_SIMULATION=true`` (rejected when TPORT_ENVIRONMENT=production).
A search request may then pass ``simulate=stale`` and/or ``simulate=outage``:

* ``stale``: every provider's records look older than its stale threshold, so the UI's
  stale-data warnings and hidden booking links can be exercised with demo data.
* ``outage``: adds a clearly labelled demo provider that always fails, to exercise the
  "provider unavailable" path. It reports nothing to real provider health statistics.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import replace
from datetime import date, timedelta

from app.domain.models import Departure, Offer, ProviderInfo, TransportMode
from app.providers.base import ProviderAdapter, ProviderError
from app.services.provider_health import ProviderCallStats

SIMULATIONS = frozenset({"stale", "outage"})
OUTAGE_PROVIDER = ProviderInfo(
    id="demo-outage",
    name="Demo outage simulator",
    is_demo=True,
    attribution="Simulated provider used to demonstrate outages. Never real data.",
)


class _Aged(ProviderAdapter):
    """Wraps an adapter so every record looks ``age`` older than it is."""

    def __init__(self, inner: ProviderAdapter, age: timedelta) -> None:
        self.inner, self.age = inner, age
        self.info, self.rate_limit = inner.info, inner.rate_limit

    def supported_location_ids(self) -> frozenset[str]:
        return self.inner.supported_location_ids()

    def served_routes(self):
        return self.inner.served_routes()

    def _d(self, d: Departure) -> Departure:
        return replace(d, retrieved_at=d.retrieved_at - self.age)

    async def get_departures(
        self, o: str, d: str, day: date, modes: frozenset[TransportMode]
    ) -> Sequence[Departure]:
        return [self._d(x) for x in await self.inner.get_departures(o, d, day, modes)]

    async def get_departure(self, departure_id: str) -> Departure | None:
        found = await self.inner.get_departure(departure_id)
        return self._d(found) if found else None

    async def get_offers(self, ids: Sequence[str]) -> Sequence[Offer]:
        return [replace(o, retrieved_at=o.retrieved_at - self.age) for o in await self.inner.get_offers(ids)]


class _Outage(ProviderAdapter):
    info = OUTAGE_PROVIDER

    def __init__(self, locations: frozenset[str]) -> None:
        self._locations = locations

    def supported_location_ids(self) -> frozenset[str]:
        return self._locations

    async def get_departures(self, *a, **kw):
        raise ProviderError(self.id, "simulated outage", retryable=True)

    async def get_departure(self, departure_id: str):
        raise ProviderError(self.id, "simulated outage", retryable=True)

    async def get_offers(self, ids):
        raise ProviderError(self.id, "simulated outage", retryable=True)


def parse_simulations(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",")) & SIMULATIONS


def simulated(search, simulations: frozenset[str]):
    """A copy of ``search`` with simulated faults; the original service is untouched."""
    if not simulations:
        return search
    clone = copy.copy(search)
    providers = dict(search._providers)
    if "stale" in simulations:
        providers = {
            pid: _Aged(p, search.source_policy(pid).timetable.stale_after + timedelta(minutes=1))
            for pid, p in providers.items()
        }
    if "outage" in simulations:
        locations = frozenset().union(*(p.supported_location_ids() for p in providers.values()))
        providers[OUTAGE_PROVIDER.id] = _Outage(locations)
    clone._providers = providers
    clone.stats = {pid: ProviderCallStats() for pid in providers}  # never pollute real health stats
    return clone
