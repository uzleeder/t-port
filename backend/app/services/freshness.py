"""Data freshness assessment based on when data was retrieved from its source."""

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

    def assess(self, retrieved_at: datetime, now: datetime) -> Freshness:
        age = now - retrieved_at
        if age >= self.expire_after:
            return Freshness.EXPIRED
        if age >= self.stale_after:
            return Freshness.STALE
        return Freshness.FRESH


def worst(*levels: Freshness) -> Freshness:
    order = [Freshness.FRESH, Freshness.STALE, Freshness.EXPIRED]
    return max(levels, key=order.index, default=Freshness.FRESH)
