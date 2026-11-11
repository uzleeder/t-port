"""Account deletion, data retention and production configuration safety."""

from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings
from app.db import models as m
from app.db.repositories import ActivityRepository
from app.db.session import transaction
from tests.conftest import NOW, TOMORROW, csrf_headers, register


def _delete(client, password):
    return client.request("DELETE", "/api/v1/me", json={"password": password}, headers=csrf_headers(client))


def test_account_deletion_removes_personal_data(client, db_factory):
    register(client)
    jid = client.get(
        "/api/v1/journeys/search",
        params={"origin": "tashkent", "destination": "samarkand", "date": TOMORROW.isoformat()},
    ).json()["items"][0]["id"]
    client.post("/api/v1/saved", json={"journey_id": jid}, headers=csrf_headers(client))

    assert client.request("DELETE", "/api/v1/me", json={"password": "correct horse 42"}).status_code == 403
    assert _delete(client, "wrong password").status_code == 401
    assert _delete(client, "correct horse 42").status_code == 204

    with db_factory() as db:
        for model in (m.User, m.Session, m.SavedJourney):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        # Anonymous analytics rows remain but are no longer linked to anyone.
        assert db.scalar(select(func.count()).select_from(m.JourneySearch)) == 1
        assert db.scalar(select(m.JourneySearch.user_id)) is None
    assert client.get("/api/v1/me").status_code == 401


def test_activity_retention_purge(client, db_factory):
    client.get(
        "/api/v1/journeys/search",
        params={"origin": "tashkent", "destination": "bukhara", "date": TOMORROW.isoformat()},
    )
    client.post("/api/v1/ai/interpret", json={"text": "Tashkent to Bukhara tomorrow"})
    with transaction(db_factory) as db:
        assert ActivityRepository(db).purge_older_than(NOW - timedelta(days=1)) == (0, 0)
    with transaction(db_factory) as db:
        searches, ai = ActivityRepository(db).purge_older_than(NOW + timedelta(seconds=1))
    assert searches >= 1 and ai == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {},  # development database password
        {"database_url": "postgresql+psycopg://a:b@db/x", "cors_origins": ["http://insecure.example"]},
        {"database_url": "postgresql+psycopg://a:b@db/x", "database_echo": True},
    ],
)
def test_production_rejects_unsafe_settings(overrides):
    base = {"environment": "production", "cors_origins": ["https://tport.example"]}
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings(**{**base, **overrides})


def test_production_settings_accepted_and_docs_hidden(app_factory):
    from fastapi.testclient import TestClient

    s = Settings(
        environment="production",
        cors_origins=["https://tport.example"],
        database_url="postgresql+psycopg://app:s3cret@db.internal/tport",
    )
    with TestClient(app_factory(settings=s)) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
        assert c.get("/health").status_code == 200
