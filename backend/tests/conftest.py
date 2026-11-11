"""Shared fixtures. Time is frozen so tests never depend on the real date."""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.clock import FixedClock
from app.core.config import Settings
from app.data.reference import LOCATIONS, STATIONS
from app.db.models import Base
from app.db.session import make_engine, make_session_factory
from app.domain.models import (
    Departure,
    Offer,
    ProviderInfo,
    ScheduleType,
    TransportMode,
)
from app.main import create_app
from app.providers.base import ProviderAdapter, ProviderError
from app.providers.demo.adapter import DemoAdapter
from app.services.catalog import LocationCatalog
from app.services.freshness import FreshnessPolicy
from app.services.search import SearchService

# Wednesday 2026-11-11 10:00 in Tashkent (UTC+5).
NOW = datetime(2026, 11, 11, 5, 0, tzinfo=UTC)
TODAY = date(2026, 11, 11)
TOMORROW = date(2026, 11, 12)  # Thursday: no weekend surcharge
POLICY = FreshnessPolicy(timedelta(minutes=15), timedelta(hours=6))


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def catalog() -> LocationCatalog:
    return LocationCatalog(LOCATIONS, STATIONS)


@pytest.fixture
def demo(catalog, clock) -> DemoAdapter:
    return DemoAdapter(catalog, clock)


def make_service(catalog, clock, providers) -> SearchService:
    return SearchService(catalog, providers, clock, POLICY, max_days_ahead=90, max_page_size=50)


@pytest.fixture
def service(catalog, clock, demo) -> SearchService:
    return make_service(catalog, clock, [demo])


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        rate_limit_per_minute=1000,
        auth_rate_limit_per_minute=1000,
        ai_rate_limit_per_minute=1000,
        cors_origins=["http://localhost:2028"],
    )


@pytest.fixture
def db_factory():
    """In-memory SQLite by default; set TPORT_TEST_DATABASE_URL to run against PostgreSQL."""
    url = os.environ.get("TPORT_TEST_DATABASE_URL", "sqlite://")
    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield make_session_factory(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def app_factory(settings, clock, db_factory):
    def build(**kwargs):
        kwargs.setdefault("clock", clock)
        kwargs.setdefault("session_factory", db_factory)
        return create_app(kwargs.pop("settings", settings), **kwargs)

    return build


@pytest.fixture
def client(app_factory):
    with TestClient(app_factory()) as c:  # context manager runs lifespan (reference seeding)
        yield c


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("tport_csrf", "")}


def register(client: TestClient, email: str = "traveller@example.com", password: str = "correct horse 42"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


class FakeAdapter(ProviderAdapter):
    """Configurable provider for edge cases (stale data, missing offers, failures)."""

    def __init__(
        self,
        departures: Sequence[Departure] = (),
        offers: Sequence[Offer] = (),
        *,
        fail: bool = False,
        provider_id: str = "fake",
        booking_hosts: frozenset[str] = frozenset(),
    ) -> None:
        self.info = ProviderInfo(provider_id, "Fake Provider", False, "test", booking_hosts)
        self._departures = list(departures)
        self._offers = list(offers)
        self._fail = fail

    def supported_location_ids(self) -> frozenset[str]:
        return frozenset({"tashkent", "samarkand"})

    async def get_departures(self, origin, destination, travel_date, modes):
        if self._fail:
            raise ProviderError(self.id, "boom")
        return [d for d in self._departures if not modes or d.mode in modes]

    async def get_departure(self, departure_id):
        if self._fail:
            raise ProviderError(self.id, "boom")
        return next((d for d in self._departures if d.id == departure_id), None)

    async def get_offers(self, departure_ids):
        return [o for o in self._offers if o.departure_id in departure_ids]


def dep(
    dep_id: str,
    *,
    depart: datetime | None = datetime(2026, 11, 12, 3, 0, tzinfo=UTC),
    minutes: int = 120,
    retrieved_at: datetime = NOW,
    mode: TransportMode = TransportMode.TRAIN,
) -> Departure:
    return Departure(
        id=dep_id,
        provider_id="fake",
        service_code=dep_id,
        operator_name="Fake Rail",
        mode=mode,
        origin_station_id="tashkent-rail",
        destination_station_id="samarkand-rail",
        schedule_type=ScheduleType.SCHEDULED if depart else ScheduleType.ON_DEMAND,
        duration_minutes=minutes,
        departure_utc=depart,
        arrival_utc=depart + timedelta(minutes=minutes) if depart else None,
        retrieved_at=retrieved_at,
        source_updated_at=None,
    )


def offer(
    dep_id: str,
    price: int,
    *,
    retrieved_at: datetime = NOW,
    currency: str = "UZS",
    booking_url: str | None = None,
) -> Offer:
    return Offer(
        id=f"{dep_id}.o{price}",
        provider_id="fake",
        departure_id=dep_id,
        fare_name="Std",
        price=Decimal(price),
        currency=currency,
        retrieved_at=retrieved_at,
        booking_url=booking_url,
    )


# --- synthetic non-demo provider (fixture feed + test-only contract) ---------------------------
import json  # noqa: E402
from pathlib import Path  # noqa: E402

from app.providers.contracts import Authorization, Capabilities, IngestionPolicy, ProviderContract  # noqa: E402
from app.providers.feed import FeedAdapter  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
SYNTH_INFO = ProviderInfo(
    "synthrail",
    "SynthRail (test fixture)",
    False,
    "Timetable: SynthRail (test fixture)",
    frozenset({"tickets.synthrail.test"}),
)
SYNTH_CONTRACT = ProviderContract(
    info=SYNTH_INFO,
    authorization=Authorization(
        basis="written_agreement",
        reference="TEST-ONLY-0001",
        attribution=SYNTH_INFO.attribution,
        permits_price_display=True,
        permits_booking_redirects=True,
        verified_by="QA reviewer",
        verified_on=date(2026, 11, 1),
        expires_on=date(2027, 11, 1),
    ),
    capabilities=Capabilities(
        modes=frozenset({TransportMode.TRAIN, TransportMode.BUS}), live_prices=False, seat_availability=False
    ),
    ingestion=IngestionPolicy(
        mode="stored", max_concurrency=3, max_attempts=3, backoff_seconds=0.5, update_interval_minutes=60
    ),
    stale_after=timedelta(hours=1),
    expire_after=timedelta(hours=24),
    data_mapping="Feed uses T-Port station IDs; times local to Asia/Tashkent; UZS.",
)


def synth_feed() -> dict:
    return json.loads((FIXTURES / "synthetic_rail_feed.json").read_text(encoding="utf-8"))


@pytest.fixture
def synth(catalog, clock) -> FeedAdapter:
    return FeedAdapter(SYNTH_INFO, synth_feed(), catalog, clock)
