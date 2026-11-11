"""Migrations, repositories, constraints and the stored-timetable provider."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.data.reference import LOCATIONS, STATIONS
from app.db import models as m
from app.db.repositories import ReferenceRepository, TimetableRepository
from app.db.session import transaction
from app.main import seed_reference
from app.providers.demo.adapter import DEMO_PROVIDER
from app.providers.registry import DEMO_CONTRACT
from app.providers.stored import StoredTimetableAdapter
from app.services.imports import import_snapshot
from app.services.search import SearchQuery
from tests.conftest import NOW, TODAY, TOMORROW, make_service

BACKEND = Path(__file__).resolve().parents[1]
STORED_DEMO = replace(DEMO_CONTRACT, ingestion=replace(DEMO_CONTRACT.ingestion, mode="stored"))


def test_migrations_upgrade_downgrade_and_match_models(tmp_path):
    url = os.environ.get("TPORT_TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    env = {**os.environ, "TPORT_DATABASE_URL": url}

    def alembic(*args):
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    for args in (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
        r = alembic(*args)
        assert r.returncode == 0, r.stderr
    check = alembic("check")
    assert check.returncode == 0, check.stdout + check.stderr
    alembic("downgrade", "base")


def test_reference_seed_is_idempotent(db_factory):
    seed_reference(db_factory)
    seed_reference(db_factory)
    with db_factory() as db:
        assert db.query(m.LocationRow).count() == len(LOCATIONS)
        assert db.query(m.StationRow).count() == len(STATIONS)
        provider = db.get(m.Provider, "demo")
        assert provider.is_demo and provider.access_basis.startswith("internal_synthetic")
        locs, stations = ReferenceRepository(db).load_locations()
    assert {loc.id for loc in locs} == {loc.id for loc in LOCATIONS}


def test_money_is_exact_and_constraints_enforced(db_factory, demo):
    seed_reference(db_factory)
    with transaction(db_factory) as db:
        imp = TimetableRepository(db).start_import("demo", "test", NOW)
        dep = m.DepartureRow(
            provider_id="demo",
            external_id="A",
            data_import_id=imp.id,
            service_code="A",
            operator_name="Op",
            mode="train",
            schedule_type="scheduled",
            origin_station_id="tashkent-rail",
            destination_station_id="samarkand-rail",
            travel_date=TOMORROW,
            departure_tz="Asia/Tashkent",
            departure_utc=NOW + timedelta(hours=1),
            arrival_utc=NOW + timedelta(hours=3),
            duration_minutes=120,
            retrieved_at=NOW,
        )
        dep.offers = [
            m.OfferRow(
                provider_id="demo",
                external_id="A.e",
                fare_name="Economy",
                price=Decimal("270000.55"),
                currency="UZS",
                retrieved_at=NOW,
            )
        ]
        db.add(dep)
    with db_factory() as db:
        offer = db.scalar(select(m.OfferRow))
        assert offer.price == Decimal("270000.55")
        assert db.scalar(select(m.DepartureRow)).departure_utc.tzinfo is not None

    bad_rows = [
        m.OfferRow(
            departure_id=1,
            provider_id="demo",
            external_id="neg",
            fare_name="Neg",
            price=Decimal("-1"),
            currency="UZS",
            retrieved_at=NOW,
        ),
        m.OfferRow(
            departure_id=1,
            provider_id="demo",
            external_id="dup",
            fare_name="Economy",
            price=Decimal("1"),
            currency="UZS",
            retrieved_at=NOW,
        ),
        m.DepartureRow(
            provider_id="demo",
            external_id="B",
            service_code="B",
            operator_name="Op",
            mode="train",
            schedule_type="scheduled",
            origin_station_id="tashkent-rail",
            destination_station_id="samarkand-rail",
            travel_date=TOMORROW,
            departure_tz="Asia/Tashkent",
            departure_utc=NOW + timedelta(hours=3),
            arrival_utc=NOW + timedelta(hours=1),
            duration_minutes=120,
            retrieved_at=NOW,
        ),  # arrives before it departs
    ]
    for row in bad_rows:
        with pytest.raises(IntegrityError), transaction(db_factory) as db:
            db.add(row)


def test_naive_datetimes_are_rejected(db_factory):
    seed_reference(db_factory)
    with pytest.raises(Exception, match="naive"), transaction(db_factory) as db:
        db.add(m.DataImport(provider_id="demo", source_reference="x", started_at=NOW.replace(tzinfo=None)))


def test_import_snapshot_and_stored_adapter_match_live_results(db_factory, demo, catalog, clock):
    seed_reference(db_factory)
    summary = import_snapshot(
        demo,
        db_factory,
        clock,
        start=TODAY,
        days=3,
        source_reference="demo-test",
        contract=STORED_DEMO,
        catalog=catalog,
    )
    assert summary["departures"] > 0 and summary["offers"] >= summary["departures"]
    with db_factory() as db:
        imp = TimetableRepository(db).latest_import("demo")
        assert imp.status == "succeeded" and imp.departures_count == summary["departures"]

    stored = StoredTimetableAdapter(DEMO_PROVIDER, catalog, db_factory, demo.supported_location_ids())
    q = SearchQuery("tashkent", "bukhara", TOMORROW)
    live = asyncio.run(make_service(catalog, clock, [demo]).search(q))
    from_db = asyncio.run(make_service(catalog, clock, [stored]).search(q))
    assert [(j.id, j.price) for j in live.journeys] == [(j.id, j.price) for j in from_db.journeys]

    # Re-import replaces the window instead of duplicating it.
    import_snapshot(
        demo,
        db_factory,
        clock,
        start=TODAY,
        days=3,
        source_reference="demo-test",
        contract=STORED_DEMO,
        catalog=catalog,
    )
    with db_factory() as db:
        assert db.query(m.DepartureRow).count() == summary["departures"]
        assert db.query(m.DataImport).count() == 2


def test_stored_data_ages_into_expiry(db_factory, demo, catalog, clock):
    from app.core.clock import FixedClock

    seed_reference(db_factory)
    import_snapshot(
        demo,
        db_factory,
        clock,
        start=TODAY,
        days=2,
        source_reference="demo-test",
        contract=STORED_DEMO,
        catalog=catalog,
    )
    stored = StoredTimetableAdapter(DEMO_PROVIDER, catalog, db_factory, demo.supported_location_ids())
    later = FixedClock(NOW + timedelta(hours=7))  # beyond the 6h expiry used in tests
    r = asyncio.run(
        make_service(catalog, later, [stored]).search(SearchQuery("tashkent", "bukhara", TOMORROW))
    )
    assert r.total == 0 and r.excluded.expired_data > 0


def test_stored_adapter_database_failure_is_a_provider_error(catalog, clock):
    from sqlalchemy.orm import sessionmaker

    from app.core.errors import ProvidersUnavailable
    from app.db.session import make_engine

    broken = sessionmaker(make_engine("postgresql+psycopg://nobody:x@127.0.0.1:1/none"))
    stored = StoredTimetableAdapter(DEMO_PROVIDER, catalog, broken, frozenset({"tashkent", "bukhara"}))
    with pytest.raises(ProvidersUnavailable):
        asyncio.run(
            make_service(catalog, clock, [stored]).search(SearchQuery("tashkent", "bukhara", TOMORROW))
        )
