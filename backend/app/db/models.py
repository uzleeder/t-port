"""SQLAlchemy 2 ORM models (PostgreSQL in production; portable enough for SQLite tests).

Conventions:
* All timestamps are stored as UTC (``UTCDateTime`` guarantees aware datetimes).
* Local time zones are preserved explicitly (``locations.timezone``,
  ``departures.departure_tz``) rather than encoded in stored timestamps.
* Money is ``Numeric(14, 2)`` with an ISO 4217 ``currency`` column.
* No raw IP addresses, passwords or AI prompt text are stored.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; use timezone-aware UTC values")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


JSONType = JSON().with_variant(JSONB(), "postgresql")
Money = Numeric(14, 2)
# BIGINT on PostgreSQL, INTEGER on SQLite (needed for SQLite autoincrement).
BigId = BigInteger().with_variant(Integer(), "sqlite")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, server_default=func.now()
    )


# --- accounts ------------------------------------------------------------------------
class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-cased
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    sessions: Mapped[list[Session]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id", "user_id"), Index("ix_sessions_expires_at", "expires_at"))

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # SHA-256 of the opaque session token; the token itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="sessions")


# --- reference data -------------------------------------------------------------------
class Provider(TimestampMixin, Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    attribution: Mapped[str] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    booking_hosts: Mapped[list[str]] = mapped_column(JSONType, default=list)
    # Documented basis for using this data (licence/agreement reference). Required for live data.
    access_basis: Mapped[str] = mapped_column(Text)
    update_frequency: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


class LocationRow(TimestampMixin, Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2))
    region: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list)

    __table_args__ = (Index("ix_locations_country_name", "country_code", "name"),)


class StationRow(TimestampMixin, Base):
    __tablename__ = "stations"
    __table_args__ = (Index("ix_stations_location_id", "location_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(32))
    code: Mapped[str | None] = mapped_column(String(8))


# --- timetable & fares -------------------------------------------------------------------
class DataImport(Base):
    __tablename__ = "data_imports"
    __table_args__ = (
        Index("ix_data_imports_provider_started", "provider_id", "started_at"),
        CheckConstraint(
            "status in ('pending','running','validating','publishing','succeeded','failed','cancelled')",
            name="ck_data_imports_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"))
    source_reference: Mapped[str] = mapped_column(String(255))  # e.g. dataset version / file name
    # pending -> running -> validating -> publishing -> succeeded; or failed / cancelled
    status: Mapped[str] = mapped_column(String(16), default="pending")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    source_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    departures_count: Mapped[int] = mapped_column(Integer, default=0)
    offers_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    retries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rejected_records: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    requests_total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    requests_done: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # Up to 50 sample contract violations {code, subject, message}. Never source payloads or secrets.
    diagnostics: Mapped[list[dict] | None] = mapped_column(JSONType)


class RateLimitCounter(Base):
    """Shared fixed-window counters (auth/AI limits, failed logins). Keys are SHA-256 hashes."""

    __tablename__ = "rate_limit_counters"
    __table_args__ = (Index("ix_rate_limit_counters_expires_at", "expires_at"),)

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ProviderImportLock(Base):
    """At most one import per provider at a time. A lock past ``expires_at`` may be taken over."""

    __tablename__ = "provider_import_locks"

    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True)
    holder: Mapped[str] = mapped_column(String(64))
    acquired_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Service(TimestampMixin, Base):
    """A recurring timetabled service (template) published by a provider."""

    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("provider_id", "service_code", name="uq_services_provider_code"),
        Index("ix_services_route", "origin_station_id", "destination_station_id"),
        CheckConstraint("duration_minutes > 0", name="ck_services_duration_positive"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"))
    service_code: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16))
    operator_name: Mapped[str] = mapped_column(String(120))
    origin_station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    destination_station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    schedule_type: Mapped[str] = mapped_column(String(16))
    depart_local_time: Mapped[time | None] = mapped_column(Time)
    timezone: Mapped[str] = mapped_column(String(64))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    days_of_week: Mapped[list[int]] = mapped_column(JSONType)  # Monday=0


class DepartureRow(Base):
    __tablename__ = "departures"
    __table_args__ = (
        UniqueConstraint("provider_id", "external_id", name="uq_departures_provider_external"),
        Index("ix_departures_route_time", "origin_station_id", "destination_station_id", "travel_date"),
        CheckConstraint("duration_minutes > 0", name="ck_departures_duration_positive"),
        CheckConstraint(
            "arrival_utc IS NULL OR departure_utc IS NULL OR arrival_utc > departure_utc",
            name="ck_departures_chronology",
        ),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(64))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id", ondelete="SET NULL"))
    data_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_imports.id", ondelete="SET NULL")
    )
    service_code: Mapped[str] = mapped_column(String(32))
    operator_name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(16))
    schedule_type: Mapped[str] = mapped_column(String(16))
    origin_station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    destination_station_id: Mapped[str] = mapped_column(ForeignKey("stations.id"))
    travel_date: Mapped[date] = mapped_column(Date)  # local date at origin
    departure_tz: Mapped[str] = mapped_column(String(64))
    departure_utc: Mapped[datetime | None] = mapped_column(UTCDateTime)
    arrival_utc: Mapped[datetime | None] = mapped_column(UTCDateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime)
    source_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    offers: Mapped[list[OfferRow]] = relationship(back_populates="departure", cascade="all, delete-orphan")


class OfferRow(Base):
    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("departure_id", "fare_name", name="uq_offers_departure_fare"),
        CheckConstraint("price > 0", name="ck_offers_price_positive"),
        CheckConstraint("price_max IS NULL OR price_max >= price", name="ck_offers_price_range"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    departure_id: Mapped[int] = mapped_column(ForeignKey("departures.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(96))
    fare_name: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal] = mapped_column(Money)
    price_max: Mapped[Decimal | None] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    is_estimate: Mapped[bool] = mapped_column(Boolean, default=False)
    booking_url: Mapped[str | None] = mapped_column(String(2048))
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime)
    source_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    departure: Mapped[DepartureRow] = relationship(back_populates="offers")


# --- user activity ---------------------------------------------------------------------------
class JourneySearch(Base):
    """Anonymous-by-default search log for product analytics. No IP or free text stored."""

    __tablename__ = "journey_searches"
    __table_args__ = (
        Index("ix_journey_searches_created_at", "created_at"),
        Index("ix_journey_searches_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    origin_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    destination_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    travel_date: Mapped[date] = mapped_column(Date)
    modes: Mapped[list[str]] = mapped_column(JSONType, default=list)
    sort: Mapped[str] = mapped_column(String(16))
    result_count: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(16), default="form")  # form | ai
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SavedJourney(Base):
    __tablename__ = "saved_journeys"
    __table_args__ = (
        UniqueConstraint("user_id", "journey_id", name="uq_saved_journeys_user_journey"),
        Index("ix_saved_journeys_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    journey_id: Mapped[str] = mapped_column(String(128))
    origin_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    destination_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    travel_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(280))
    # What the user saw when saving (price/times/provider). Displayed as a dated snapshot,
    # never as current data.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType)
    snapshot_taken_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AIRequest(Base):
    """Metadata only: the user's text is NOT stored (it may contain personal data)."""

    __tablename__ = "ai_requests"
    __table_args__ = (
        Index("ix_ai_requests_created_at", "created_at"),
        CheckConstraint(
            "outcome in ('ok','fallback','invalid_output','provider_error','rejected')",
            name="ck_ai_requests_outcome",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    engine: Mapped[str] = mapped_column(String(32))  # e.g. "rules", "anthropic"
    model: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16))
    input_chars: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class UserPreferences(Base):
    """Search defaults a signed-in user chose. Only enumerated values: no free text, no history."""

    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("max_transfers >= 0 AND max_transfers <= 2", name="ck_user_preferences_transfers"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    modes: Mapped[list[str]] = mapped_column(JSONType, default=list)  # default filter; empty = all
    prefer_modes: Mapped[list[str]] = mapped_column(JSONType, default=list)  # ranking only
    sort: Mapped[str] = mapped_column(String(16), default="recommended")
    max_transfers: Mapped[int] = mapped_column(Integer, default=1)
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class BookingRedirectCount(Base):
    """Aggregate redirects to operators' booking pages per provider and day.

    Deliberately no user, session, IP, journey or URL: only how many hand-offs happened.
    """

    __tablename__ = "booking_redirect_counts"

    provider_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
