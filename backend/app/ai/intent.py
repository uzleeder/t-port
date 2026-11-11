"""Structured journey intent: the ONLY thing an interpreter may produce.

Interpreters (rules or LLM) output ``RawIntent``. ``validate_intent`` then checks
it against the location catalog and the date window. Prices, times, providers
and availability never come from an interpreter — they come from the search
engine afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import TransportMode
from app.services.catalog import LocationCatalog
from app.services.search import SortKey

ModeName = Literal["train", "bus", "flight", "taxi"]
BudgetPref = Literal["lowest", "any"]
TimePref = Literal["earliest", "fastest", "morning", "afternoon", "evening", "night", "any"]
TransferPref = Literal["direct", "fewest", "any"]
Currency = Literal["UZS", "USD", "EUR", "RUB"]
_HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class RawIntent(BaseModel):
    """Interpreter output schema. Also used as the LLM structured-output format."""

    model_config = ConfigDict(extra="forbid")

    origin_id: str | None = Field(description="Location ID from the allowed list, or null if not stated.")
    destination_id: str | None = Field(
        description="Location ID from the allowed list, or null if not stated."
    )
    travel_date: str | None = Field(description="YYYY-MM-DD, or null if the user gave no date.")
    modes: list[ModeName] = Field(description="Transport modes the user wants. Empty list means any mode.")
    excluded_modes: list[ModeName] = Field(description="Modes the user explicitly does not want.")
    budget_preference: BudgetPref = Field(description="'lowest' if the user wants the cheapest option.")
    max_price_uzs: int | None = Field(
        description="Upper price limit in UZS if the user stated one, else null."
    )
    time_preference: TimePref = Field(description="Departure-time or speed preference.")
    # Phase 3 fields. Defaults keep older interpreter output valid.
    depart_after: str | None = Field(
        default=None, pattern=_HHMM, description="Earliest local departure time HH:MM (24h) if stated."
    )
    depart_before: str | None = Field(
        default=None, pattern=_HHMM, description="Latest local departure time HH:MM (24h) if stated."
    )
    arrive_before: str | None = Field(
        default=None,
        pattern=_HHMM,
        description="Latest local arrival time HH:MM (24h) if the user must arrive by a time, else null.",
    )
    transfer_preference: TransferPref = Field(
        default="any", description="'direct' = no changes, 'fewest' = as few changes as possible."
    )
    max_transfers: int | None = Field(
        default=None, ge=0, le=2, description="Maximum number of changes (0-2) if stated, else null."
    )
    prefer_modes: list[ModeName] = Field(
        default_factory=list,
        description="Modes the user prefers but does not require (ranking only). Empty if none.",
    )
    compare_modes: bool = Field(
        default=False, description="True if the user asked to compare transport modes."
    )
    budget_amount: int | None = Field(
        default=None, ge=1, description="Budget amount as stated, in budget_currency, if any."
    )
    budget_currency: Currency | None = Field(
        default=None, description="Currency of budget_amount as stated by the user, else null."
    )
    unsupported_reason: str | None = Field(
        description="Short reason if the request is not a journey search (e.g. hotel booking), else null."
    )


TIME_WINDOWS: dict[str, tuple[time | None, time | None]] = {
    "morning": (time(5, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), time(22, 0)),
    "night": (time(20, 0), None),
}


@dataclass(slots=True)
class ValidatedIntent:
    origin_id: str | None
    destination_id: str | None
    travel_date: date | None
    modes: frozenset[TransportMode]
    budget_preference: BudgetPref
    max_price: Decimal | None
    time_preference: TimePref
    sort: SortKey
    depart_after: time | None
    depart_before: time | None
    arrive_before: time | None = None
    max_transfers: int = 1
    transfer_preference: TransferPref = "any"
    prefer_modes: frozenset[TransportMode] = frozenset()
    compare_modes: bool = False
    missing: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None

    @property
    def complete(self) -> bool:
        return not self.missing and not self.problems and not self.unsupported_reason


def validate_intent(
    raw: RawIntent, catalog: LocationCatalog, today: date, max_days_ahead: int
) -> ValidatedIntent:
    problems: list[str] = []
    origin = raw.origin_id if raw.origin_id and catalog.get(raw.origin_id) else None
    destination = raw.destination_id if raw.destination_id and catalog.get(raw.destination_id) else None
    if raw.origin_id and origin is None:
        problems.append("The starting point isn't a city T-Port covers yet.")
    if raw.destination_id and destination is None:
        problems.append("The destination isn't a city T-Port covers yet.")
    if origin and origin == destination:
        problems.append("Origin and destination are the same place.")

    travel_date: date | None = None
    if raw.travel_date:
        try:
            travel_date = date.fromisoformat(raw.travel_date)
        except ValueError:
            problems.append("The travel date could not be understood.")
        else:
            if travel_date < today:
                problems.append("That date is in the past.")
            elif travel_date > today + timedelta(days=max_days_ahead):
                problems.append(f"Dates more than {max_days_ahead} days ahead are not searchable yet.")

    modes = {TransportMode(m) for m in raw.modes}
    excluded = {TransportMode(m) for m in raw.excluded_modes}
    if excluded and not modes:
        modes = set(TransportMode) - excluded
    else:
        modes -= excluded
    if (raw.modes or raw.excluded_modes) and not modes:
        problems.append("Every transport mode was excluded.")

    max_price = Decimal(raw.max_price_uzs) if raw.max_price_uzs and raw.max_price_uzs > 0 else None
    if raw.budget_amount and raw.budget_currency:
        if raw.budget_currency == "UZS":
            max_price = max_price or Decimal(raw.budget_amount)
        else:
            # No exchange rates are invented: prices are shown in UZS, so ask for a UZS budget.
            problems.append(
                f"Fares are listed in UZS and T-Port does not convert currencies; "
                f"please give your budget in UZS instead of {raw.budget_currency}."
            )

    def _clock(value: str | None, label: str) -> time | None:
        if value is None:
            return None
        try:
            return time.fromisoformat(value)
        except ValueError:
            problems.append(f"The {label} time could not be understood.")
            return None

    arrive_before = _clock(raw.arrive_before, "arrival")
    explicit_after = _clock(raw.depart_after, "departure")
    explicit_before = _clock(raw.depart_before, "departure")

    if raw.max_transfers is not None:
        max_transfers = raw.max_transfers
    elif raw.transfer_preference == "direct":
        max_transfers = 0
    elif raw.transfer_preference == "fewest":
        max_transfers = 2  # widest search, ranked by fewest changes
    else:
        max_transfers = 2 if arrive_before else 1
    if raw.transfer_preference == "direct" and raw.max_transfers:
        max_transfers = 0

    if raw.time_preference == "fastest":
        sort = SortKey.DURATION
    elif raw.time_preference == "earliest":
        sort = SortKey.DEPARTURE
    elif raw.budget_preference == "lowest":
        sort = SortKey.PRICE
    elif raw.transfer_preference == "fewest":
        sort = SortKey.TRANSFERS
    else:
        sort = SortKey.RECOMMENDED
    after, before = TIME_WINDOWS.get(raw.time_preference, (None, None))
    after = explicit_after or after
    before = explicit_before or before
    if after and before and before <= after and raw.time_preference != "night":
        problems.append("The latest departure time is before the earliest one.")

    prefer = {TransportMode(m) for m in raw.prefer_modes} - excluded

    missing = [name for name, value in (("origin", origin), ("destination", destination)) if value is None]
    return ValidatedIntent(
        origin_id=origin,
        destination_id=destination,
        travel_date=travel_date or today,
        modes=frozenset(modes) if len(modes) < len(TransportMode) else frozenset(),
        budget_preference=raw.budget_preference,
        max_price=max_price,
        time_preference=raw.time_preference,
        sort=sort,
        depart_after=after,
        depart_before=before,
        arrive_before=arrive_before,
        max_transfers=max_transfers,
        transfer_preference=raw.transfer_preference,
        prefer_modes=frozenset(prefer),
        compare_modes=raw.compare_modes and len(modes) != 1,
        missing=missing,
        problems=problems,
        unsupported_reason=raw.unsupported_reason,
    )
