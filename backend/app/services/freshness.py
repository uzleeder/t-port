"""Data freshness assessment based on when data was retrieved from its source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.models import Freshness


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    stale_after: timedelta
    expire_after: timedelta

    def __post_init__(self) -> None:
        if self.expire_after < self.stale_after:
            raise ValueError("expire_after must be >= stale_after")

    def assess(self, retrieved_at: datetime | None, now: datetime) -> Freshness:
        if retrieved_at is None:
            return Freshness.UNKNOWN
        age = now - retrieved_at
        if age >= self.expire_after:
            return Freshness.EXPIRED
        if age >= self.stale_after:
            return Freshness.STALE
        return Freshness.FRESH


def worst(*levels: Freshness) -> Freshness:
    order = [Freshness.FRESH, Freshness.STALE, Freshness.UNKNOWN, Freshness.EXPIRED]
    return max(levels, key=order.index, default=Freshness.FRESH)


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    """Everything search needs to know about one provider's data reliability."""

    timetable: FreshnessPolicy
    price: FreshnessPolicy
    basis: str = "retrieved_at"  # or "source_updated_at" (a missing timestamp => UNKNOWN)
    live_prices: bool = False  # only live, fresh prices are shown as "confirmed"
    booking_requires_fresh_price: bool = True

    @classmethod
    def from_contract(cls, contract) -> SourcePolicy:
        return cls(
            contract.freshness,
            contract.price_freshness,
            contract.freshness_basis,
            contract.capabilities.live_prices,
            contract.booking_requires_fresh_price,
        )
