"""Deterministic journey optimisation helpers: Pareto filtering and preference-aware scoring."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.domain.models import Journey, TransportMode


def _vector(j: Journey) -> tuple[Decimal, int, int]:
    return (j.price, j.total_minutes, j.transfers)


def dominates(a: Journey, b: Journey) -> bool:
    """a is no worse than b on price, total time and transfers, and strictly better on one."""
    va, vb = _vector(a), _vector(b)
    return all(x <= y for x, y in zip(va, vb, strict=True)) and va != vb


def pareto_front(journeys: Sequence[Journey], against: Sequence[Journey] = ()) -> list[Journey]:
    """Journeys not dominated by any other candidate or by any journey in ``against``.

    Ties (identical vectors) are all kept; ordering of the result follows the input.
    """
    pool = list(journeys) + list(against)
    return [j for j in journeys if not any(dominates(o, j) for o in pool if o is not j)]


def preference_bonus(j: Journey, preferred: frozenset[TransportMode]) -> Decimal:
    """0..0.25 score reduction for the share of legs using a preferred mode."""
    if not preferred or not j.legs:
        return Decimal(0)
    share = Decimal(sum(1 for leg in j.legs if leg.departure.mode in preferred)) / Decimal(len(j.legs))
    return (Decimal("0.25") * share).quantize(Decimal("0.0001"))
