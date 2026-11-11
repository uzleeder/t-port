"""Bounded, time-dependent journey graph.

Nodes are canonical locations (each location groups its stations, airports and door-to-door point).
Edges are the location pairs providers actually serve (``ProviderAdapter.served_routes()``), each
carrying time-dependent departures fetched on demand for a given date. Station changes inside a
location are transfer connections, validated by ``check_connection`` (minimum connection time,
station change, flight check-in buffer, maximum wait, same country).

Search is deliberately bounded so it stays predictable on the pilot dataset and safe as it grows:
* at most ``max_legs`` legs (3 = two transfers) and no revisited locations;
* at most ``max_paths`` location paths, shortest first, then lexicographic (deterministic);
* at most ``per_step`` onward departures kept per partial chain (earliest feasible first);
* at most ``max_candidates`` complete chains before Pareto filtering.

No graph database: the network is small (tens of locations, hundreds of daily departures).
Benchmarks are in docs/performance-benchmarks.md.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GraphLimits:
    max_legs: int = 3
    max_paths: int = 40
    per_step: int = 6
    max_candidates: int = 300


class JourneyGraph:
    """Location-level adjacency built from the routes providers serve."""

    def __init__(self, routes: Iterable[tuple[str, str]]) -> None:
        self.adj: dict[str, set[str]] = defaultdict(set)
        for a, b in routes:
            if a != b:
                self.adj[a].add(b)

    @classmethod
    def from_providers(cls, providers) -> JourneyGraph:
        routes: set[tuple[str, str]] = set()
        for p in providers:
            served = p.served_routes()
            if served is None:  # unknown routes: assume any pair of its locations (bounded below)
                locs = sorted(p.supported_location_ids())
                served = {(a, b) for a in locs for b in locs if a != b}
            routes |= set(served)
        return cls(routes)

    def location_paths(self, origin: str, destination: str, limits: GraphLimits) -> list[tuple[str, ...]]:
        """Simple paths origin -> destination with 2..max_legs legs (direct trips are handled separately)."""
        found: list[tuple[str, ...]] = []

        def walk(path: tuple[str, ...]) -> None:
            if len(path) - 1 >= limits.max_legs:
                return
            for nxt in sorted(self.adj.get(path[-1], ())):
                if nxt in path:
                    continue
                if nxt == destination:
                    if len(path) >= 2:  # at least one intermediate stop
                        found.append((*path, nxt))
                    continue
                walk((*path, nxt))

        walk((origin,))
        found.sort(key=lambda p: (len(p), p))
        return found[: limits.max_paths]
