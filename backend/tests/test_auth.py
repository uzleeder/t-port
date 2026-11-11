"""Authentication, sessions, CSRF and account authorization."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import models as m
from tests.conftest import csrf_headers, register


def test_register_sets_secure_session_cookies(client):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "traveller@example.com"
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("tport_session="))
    csrf = next(c for c in cookies if c.startswith("tport_csrf="))
    assert "HttpOnly" in session and "samesite=lax" in session.lower()
    assert "HttpOnly" not in csrf  # must be readable for the double-submit header


def test_session_token_is_stored_hashed(client, db_factory):
    register(client)
    token = client.cookies.get("tport_session")
    with db_factory() as db:
        stored = db.scalars(select(m.Session.token_hash)).all()
        user = db.scalar(select(m.User))
    assert stored and token not in stored and len(stored[0]) == 64
    assert user.password_hash.startswith("$argon2id$")


def test_production_cookies_are_secure(app_factory):
    s = Settings(
        environment="production",
        auth_rate_limit_per_minute=100,
        cors_origins=["https://tport.example"],
        database_url="postgresql+psycopg://app:s3cret@db.internal/tport",
    )
    with TestClient(app_factory(settings=s), base_url="https://testserver") as c:
        r = register(c)
    assert r.status_code == 201
    assert all("Secure" in c for c in r.headers.get_list("set-cookie"))


def test_registration_validation(client):
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, password="short").status_code == 422
    r = register(client, email="a@b.example", password="a@b.example")
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "password"


def test_duplicate_email_case_insensitive(client):
    assert register(client).status_code == 201
    client.cookies.clear()
    r = register(client, email="TRAVELLER@Example.com")
    assert r.status_code == 409


def test_login_errors_are_generic(client):
    register(client)
    client.cookies.clear()
    wrong_pw = client.post(
        "/api/v1/auth/login", json={"email": "traveller@example.com", "password": "nope nope 1"}
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope nope 1"}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_login_me_logout_flow(client):
    register(client)
    client.cookies.clear()
    assert client.get("/api/v1/me").status_code == 401
    r = client.post(
        "/api/v1/auth/login", json={"email": "Traveller@example.com ", "password": "correct horse 42"}
    )
    assert r.status_code == 200
    me = client.get("/api/v1/me").json()
    assert me["user"]["email"] == "traveller@example.com" and me["saved_count"] == 0

    assert client.post("/api/v1/auth/logout").status_code == 403  # no CSRF header
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "forged"}).status_code == 403
    token = client.cookies.get("tport_session")
    assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 204
    # The old token is revoked server-side even if a client keeps the cookie.
    client.cookies.set("tport_session", token)
    assert client.get("/api/v1/me").status_code == 401


def test_me_records_recent_searches(client):
    register(client)
    client.get(
        "/api/v1/journeys/search",
        params={"origin": "tashkent", "destination": "bukhara", "date": "2026-11-12"},
    )
    recent = client.get("/api/v1/me").json()["recent_searches"]
    assert recent[0]["origin_id"] == "tashkent" and recent[0]["destination_id"] == "bukhara"


def test_cross_origin_post_rejected(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "x@example.com", "password": "whatever 123"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "x@example.com", "password": "whatever 123"},
        headers={"Origin": "http://localhost:2028"},
    )
    assert ok.status_code == 401  # passed the origin check, failed credentials


def test_auth_rate_limit(app_factory):
    s = Settings(environment="test", auth_rate_limit_per_minute=3, cors_origins=["http://localhost:2028"])
    with TestClient(app_factory(settings=s)) as c:
        codes = [
            c.post(
                "/api/v1/auth/login", json={"email": "x@example.com", "password": "pw pw pw pw"}
            ).status_code
            for _ in range(4)
        ]
    assert codes == [401, 401, 401, 429]


def test_oversized_body_rejected(client):
    r = client.post("/api/v1/auth/login", content=b"x" * 70_000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
