"""Side-by-side journey comparison: which option is best on each criterion, and caveats.

Purely deterministic: works on journeys already resolved from provider data. Ties are reported
for every journey sharing the best value. Estimated prices are compared by their lower bound,
and a caveat says so; journeys with no fixed arrival time never win "earliest arrival".
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.domain.models import Freshness, Journey, PriceType

MAX_COMPARE = 4


@dataclass(frozen=True, slots=True)
class Comparison:
    cheapest: list[str] = field(default_factory=list)
    fastest: list[str] = field(default_factory=list)
    fewest_transfers: list[str] = field(default_factory=list)
    earliest_departure: list[str] = field(default_factory=list)
    earliest_arrival: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


def _best(journeys: Sequence[Journey], key: Callable[[Journey], object | None]) -> list[str]:
    scored = [(key(j), j.id) for j in journeys]
    scored = [(v, i) for v, i in scored if v is not None]
    if len(scored) < 2:  # nothing to compare on this criterion
        return []
    best = min(v for v, _ in scored)
    return [i for v, i in scored if v == best]


def compare(journeys: Sequence[Journey]) -> Comparison:
    caveats: list[str] = []
    if len({j.currency for j in journeys}) > 1:
        caveats.append("Prices are in different currencies and are not compared.")
        cheapest: list[str] = []
    else:
        cheapest = _best(journeys, lambda j: j.price)
    types = {j.price_type for j in journeys}
    if PriceType.ESTIMATED in types and len(types) > 1:
        caveats.append("Estimated prices are compared by the lower end of their range.")
    if PriceType.DEMO in types:
        caveats.append("Demonstration data is included; its prices and times are not real.")
    if any(j.freshness in (Freshness.STALE, Freshness.UNKNOWN) for j in journeys):
        caveats.append("Some data has not been refreshed recently; check before you travel.")
    routes = {(j.legs[0].origin.location_id, j.legs[-1].destination.location_id) for j in journeys}
    if len(routes) > 1:
        caveats.append("These journeys are for different routes.")
    days = {j.departure_utc.date() for j in journeys if j.departure_utc}
    if len(days) > 1:
        caveats.append("These journeys depart on different days.")
    return Comparison(
        cheapest=cheapest,
        fastest=_best(journeys, lambda j: j.total_minutes),
        fewest_transfers=_best(journeys, lambda j: j.transfers),
        earliest_departure=_best(journeys, lambda j: j.departure_utc),
        earliest_arrival=_best(journeys, lambda j: j.arrival_utc),
        caveats=caveats,
    )
