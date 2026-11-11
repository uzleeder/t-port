"""In-memory location/station catalog with alias-aware search."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from app.domain.models import Location, Station

_APOSTROPHES = str.maketrans("", "", "'’‘`ʻʼ")


def _fold(text: str) -> str:
    """Case/diacritic-insensitive key; also drops apostrophes (Qo'qon == Qoqon)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold().translate(_APOSTROPHES).strip()


class LocationCatalog:
    def __init__(self, locations: Iterable[Location], stations: Iterable[Station]) -> None:
        self._locations = {loc.id: loc for loc in locations}
        self._stations = {st.id: st for st in stations}
        self._stations_by_location: dict[str, list[Station]] = {}
        for st in self._stations.values():
            if st.location_id not in self._locations:
                raise ValueError(f"Station {st.id} references unknown location {st.location_id}")
            self._stations_by_location.setdefault(st.location_id, []).append(st)

    def get(self, location_id: str) -> Location | None:
        return self._locations.get(location_id)

    def station(self, station_id: str) -> Station | None:
        return self._stations.get(station_id)

    def stations_for(self, location_id: str) -> list[Station]:
        return list(self._stations_by_location.get(location_id, []))

    def search(self, query: str | None) -> list[Location]:
        """Rank exact, prefix, then substring matches, with ties sorted by name."""
        locations = sorted(self._locations.values(), key=lambda loc: loc.name)
        if not query or not query.strip():
            return locations
        q = _fold(query)
        ranked: list[tuple[int, Location]] = []
        for loc in locations:
            keys = [_fold(loc.name), *(_fold(a) for a in loc.aliases)]
            if q == _fold(loc.id) or q in keys:
                ranked.append((0, loc))
            elif any(k.startswith(q) for k in keys):
                ranked.append((1, loc))
            elif any(q in k for k in keys):
                ranked.append((2, loc))
        ranked.sort(key=lambda pair: (pair[0], pair[1].name))
        return [loc for _, loc in ranked]
