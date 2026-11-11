"""Phase 2 security: shared rate limits, per-account login throttling, outbound URL guard."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.outbound import OutboundBlocked, check_outbound_url, guarded_client
from app.services.ratelimit import SharedRateLimiter, limiter_key
from tests.conftest import NOW, register

LOGIN = "/api/v1/auth/login"


def test_shared_limiter_counts_across_workers(db_factory):
    from app.main import seed_reference

    seed_reference(db_factory)
    a, b = SharedRateLimiter(db_factory), SharedRateLimiter(db_factory)  # two workers, one database
    key = limiter_key("ip", "/api/v1/auth/", "203.0.113.9")
    assert [a.hit(key, 60, NOW), b.hit(key, 60, NOW), a.hit(key, 60, NOW)] == [1, 2, 3]
    assert b.peek(key, 60, NOW) == 3
    assert a.hit(key, 60, NOW + timedelta(seconds=60)) == 1  # new window restarts
    assert a.purge(NOW + timedelta(minutes=5)) == 1


def test_keys_are_hashes_not_personal_data(db_factory):
    from sqlalchemy import select

    from app.db import models as m

    SharedRateLimiter(db_factory).hit(limiter_key("login-fail", "alice@example.com"), 900, NOW)
    with db_factory() as db:
        keys = db.scalars(select(m.RateLimitCounter.key)).all()
    assert keys and all(len(k) == 64 and "alice" not in k for k in keys)


def test_limiter_fails_open_when_database_is_down():
    def unreachable():
        raise ConnectionError("database unreachable")

    broken = SharedRateLimiter(unreachable)
    assert broken.hit("k", 60, NOW) == 0 and broken.peek("k", 60, NOW) == 0


def test_postgres_engine_fails_fast():
    import time

    from sqlalchemy import text

    from app.db.session import make_engine

    engine = make_engine("postgresql+psycopg://x:y@10.255.255.1:5432/none")  # unroutable address
    started = time.monotonic()
    with pytest.raises(Exception), engine.connect() as conn:  # noqa: B017 - any driver error
        conn.execute(text("SELECT 1"))
    assert time.monotonic() - started < 15


def test_auth_limit_is_shared_between_app_instances(app_factory):
    s = Settings(
        environment="test",
        auth_rate_limit_per_minute=3,
        cors_origins=["http://localhost:2028"],
        login_failure_limit=100,
    )
    worker1, worker2 = TestClient(app_factory(settings=s)), TestClient(app_factory(settings=s))
    with worker1, worker2:
        codes = [
            w.post(LOGIN, json={"email": f"u{i}@example.com", "password": "x" * 10}).status_code
            for i, w in enumerate([worker1, worker2, worker1, worker2])
        ]
    assert codes == [401, 401, 401, 429]  # in-memory limits would have allowed all four


def test_failed_logins_lock_the_account_not_the_ip(client):
    register(client, email="victim@example.com")
    client.cookies.clear()
    for _ in range(5):
        assert (
            client.post(LOGIN, json={"email": "victim@example.com", "password": "wrong pass 1"}).status_code
            == 401
        )
    blocked = client.post(LOGIN, json={"email": "Victim@Example.com", "password": "correct horse 42"})
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "rate_limited"
    # Other accounts from the same client are unaffected.
    register(client, email="other@example.com")
    client.cookies.clear()
    assert (
        client.post(LOGIN, json={"email": "other@example.com", "password": "correct horse 42"}).status_code
        == 200
    )


def test_unknown_emails_are_throttled_identically(client):
    for _ in range(5):
        client.post(LOGIN, json={"email": "nobody@example.com", "password": "wrong pass 1"})
    assert client.post(LOGIN, json={"email": "nobody@example.com", "password": "x" * 10}).status_code == 429


def test_successful_logins_do_not_count(client):
    register(client)
    for _ in range(7):
        client.cookies.clear()
        assert (
            client.post(
                LOGIN, json={"email": "traveller@example.com", "password": "correct horse 42"}
            ).status_code
            == 200
        )


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("http://api.provider.test/x", "only https"),
        ("https://evil.test/x", "allow-list"),
        ("https://user:pw@api.provider.test/x", "credentials"),
        ("https://127.0.0.1/x", "allow-list"),
    ],
)
def test_outbound_guard_rejects(url, reason):
    with pytest.raises(OutboundBlocked, match=reason):
        check_outbound_url(url, frozenset({"api.provider.test"}), resolve=False)


def test_outbound_guard_blocks_internal_targets(monkeypatch):
    import socket

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(None, None, None, "", ("10.0.0.5", 443))])
    with pytest.raises(OutboundBlocked, match="internal"):
        check_outbound_url("https://api.provider.test/x", frozenset({"api.provider.test"}))
    with pytest.raises(OutboundBlocked, match="internal"):
        check_outbound_url("https://169.254.169.254/latest", frozenset({"169.254.169.254"}), resolve=False)
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(None, None, None, "", ("93.184.216.34", 443))]
    )
    assert check_outbound_url("https://api.provider.test/x", frozenset({"api.provider.test"}))


def test_guarded_client_checks_every_request():
    import httpx

    async def go():
        async with guarded_client(frozenset({"api.provider.test"}), 1.0, resolve=False) as c:
            c._transport = httpx.MockTransport(lambda r: httpx.Response(200))
            ok = await c.get("https://api.provider.test/feed")
            with pytest.raises(OutboundBlocked):
                await c.get("https://elsewhere.test/feed")
            return ok.status_code

    assert asyncio.run(go()) == 200


def test_blank_optional_settings_are_treated_as_unset(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("TPORT_AI_INPUT_USD_PER_MTOK", "")
    monkeypatch.setenv("TPORT_OPS_TOKEN", "")
    s = Settings(_env_file=None)
    assert s.ai_input_usd_per_mtok is None and s.ops_token is None
