"""Response schema of the (hypothetical) provider API. Replace with the provider's documented schema.

``extra="forbid"`` is intentional while integrating: a field the provider adds or renames should be
noticed and mapped consciously. Relax it to ``"ignore"`` only once the provider guarantees
additive-only changes in writing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ApiFare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fare_id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,40}$")
    name: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    booking_url: str | None = Field(default=None, max_length=500)
    updated_at: AwareDatetime | None = None


class ApiTrip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,40}$")
    mode: Literal["train", "bus", "flight"]
    operator: str = Field(min_length=1, max_length=120)
    from_stop: str = Field(min_length=1, max_length=40)
    to_stop: str = Field(min_length=1, max_length=40)
    departs_at: AwareDatetime
    arrives_at: AwareDatetime
    fares: list[ApiFare] = Field(default_factory=list)

    @model_validator(mode="after")
    def _chronology(self) -> ApiTrip:
        if self.arrives_at <= self.departs_at:
            raise ValueError("arrives_at must be after departs_at")
        return self


class ApiTripList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generated_at: AwareDatetime
    trips: list[ApiTrip]


class ApiTripDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generated_at: AwareDatetime
    trip: ApiTrip
