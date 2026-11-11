"""User search preferences and the external booking hand-off."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1.routes import _booking_target
from app.core.clock import FixedClock
from app.core.config import Settings
from app.db import models as m
from app.providers.feed import FeedAdapter
from app.providers.registry import DEMO_CONTRACT
from tests.conftest import NOW, SYNTH_CONTRACT, SYNTH_INFO, TOMORROW, csrf_headers, register, synth_feed

PREFS = "/api/v1/me/preferences"


# --- preferences ------------------------------------------------------------------------------
def test_preferences_require_sign_in_and_csrf(client):
    assert client.get(PREFS).status_code == 401
    register(client)
    body = client.get(PREFS).json()
    assert body == {
        "modes": [],
        "prefer_modes": [],
        "sort": "recommended",
        "max_transfers": 1,
        "max_price": None,
        "updated_at": None,
    }
    assert client.put(PREFS, json={"sort": "price"}).status_code == 403  # no CSRF header


def test_preferences_round_trip_and_normalisation(client):
    register(client)
    r = client.put(
        PREFS,
        json={
            "modes": ["train", "bus", "train"],
            "prefer_modes": ["train"],
            "sort": "transfers",
            "max_transfers": 2,
            "max_price": "450000",
        },
        headers=csrf_headers(client),
    )
    assert r.status_code == 200
    saved = client.get(PREFS).json()
    assert saved["modes"] == ["bus", "train"] and saved["prefer_modes"] == ["train"]
    assert saved["sort"] == "transfers" and saved["max_transfers"] == 2 and saved["max_price"] == "450000.00"
    assert saved["updated_at"] is not None
    every = client.put(
        PREFS, json={"modes": ["train", "bus", "flight", "taxi"]}, headers=csrf_headers(client)
    )
    assert every.json()["modes"] == []  # all modes == no filter


@pytest.mark.parametrize(
    "body",
    [
        {"max_transfers": 3},
        {"sort": "evil"},
        {"modes": ["rocket"]},
        {"max_price": "-1"},
        {"email": "someone@example.com"},  # unknown fields (and personal data) are rejected
        {"modes": ["bus"], "prefer_modes": ["train"]},  # preference outside the searched modes
    ],
)
def test_preferences_validation(client, body):
    register(client)
    assert client.put(PREFS, json=body, headers=csrf_headers(client)).status_code == 422


def test_preferences_are_per_user_and_deleted_with_the_account(app_factory, db_factory):
    with TestClient(app_factory()) as a, TestClient(app_factory()) as b:
        register(a, "a@example.com")
        register(b, "b@example.com")
        a.put(PREFS, json={"sort": "price"}, headers=csrf_headers(a))
        assert b.get(PREFS).json()["sort"] == "recommended"
        r = a.request("DELETE", "/api/v1/me", json={"password": "correct horse 42"}, headers=csrf_headers(a))
        assert r.status_code == 204
    with db_factory() as db:
        assert db.scalar(select(m.UserPreferences)) is None


# --- booking hand-off -------------------------------------------------------------------------
def _bookable_app(app_factory, demo, clock, catalog, *, adapter_clock=None):
    synth = FeedAdapter(SYNTH_INFO, synth_feed(), catalog, adapter_clock or clock)
    return app_factory(providers=[demo, synth], contracts=[DEMO_CONTRACT, SYNTH_CONTRACT], clock=clock)


def _first(c, provider, **params):
    q = {"origin": "tashkent", "destination": "samarkand", "date": TOMORROW.isoformat(), "max_transfers": 0}
    items = c.get("/api/v1/journeys/search", params={**q, **params, "page_size": 50}).json()["items"]
    return next(j for j in items if j["legs"][0]["provider"]["id"] == provider)


def test_booking_info_explains_the_hand_off(app_factory, demo, clock, catalog):
    with TestClient(_bookable_app(app_factory, demo, clock, catalog)) as c:
        j = _first(c, "synthrail")
        info = c.get(f"/api/v1/journeys/{j['id']}/booking").json()
    assert info["bookable"] and info["booking_host"] == "tickets.synthrail.test"
    assert info["provider"]["name"] == "SynthRail (test fixture)"
    assert info["price"] == j["price"] and info["price_retrieved_at"] is not None


def test_redirect_adds_nothing_and_counts_only_aggregates(app_factory, demo, clock, catalog, db_factory):
    with TestClient(_bookable_app(app_factory, demo, clock, catalog), follow_redirects=False) as c:
        register(c)  # signed in: still nothing about the user may reach the operator or the counter
        j = _first(c, "synthrail")
        r1 = c.get(f"/api/v1/journeys/{j['id']}/book")
        r2 = c.get(f"/api/v1/journeys/{j['id']}/book")
        metrics = c.app.state.metrics.render()
    assert r1.status_code == 303 and r1.headers["location"] == j["booking_url"]
    assert "traveller" not in r1.headers["location"] and "example.com" not in r1.headers["location"]
    assert r1.headers["referrer-policy"] == "no-referrer" and r1.headers["cache-control"] == "no-store"
    assert r2.status_code == 303
    assert 'tport_booking_redirects_total{provider="synthrail"} 2' in metrics
    with db_factory() as db:
        rows = db.scalars(select(m.BookingRedirectCount)).all()
    assert [(r.provider_id, r.count) for r in rows] == [("synthrail", 2)]
    assert {c.key for c in m.BookingRedirectCount.__table__.columns} == {"provider_id", "day", "count"}


def test_demo_and_multi_leg_journeys_are_not_redirected(app_factory, demo, clock, catalog):
    with TestClient(_bookable_app(app_factory, demo, clock, catalog), follow_redirects=False) as c:
        d = _first(c, "demo")
        info = c.get(f"/api/v1/journeys/{d['id']}/booking").json()
        assert not info["bookable"] and "Demo" in info["reason"]
        r = c.get(f"/api/v1/journeys/{d['id']}/book")
        assert r.status_code == 409 and r.json()["error"]["code"] == "booking_unavailable"
        items = c.get(
            "/api/v1/journeys/search",
            params={
                "origin": "samarkand",
                "destination": "khiva",
                "date": TOMORROW.isoformat(),
                "max_transfers": 2,
            },
        ).json()["items"]
        multi = next(j for j in items if j["transfers"] >= 1)
        info = c.get(f"/api/v1/journeys/{multi['id']}/booking").json()
        assert not info["bookable"] and len(info["leg_journey_ids"]) == multi["transfers"] + 1
        for leg_id in info["leg_journey_ids"]:
            assert c.get(f"/api/v1/journeys/{leg_id}").status_code == 200
        assert c.get(f"/api/v1/journeys/{multi['id']}/book").status_code == 409


def test_stale_price_blocks_the_redirect(app_factory, demo, catalog):
    later = FixedClock(NOW + timedelta(hours=2))  # SynthRail prices go stale after 1 hour
    app = _bookable_app(app_factory, demo, later, catalog, adapter_clock=FixedClock(NOW))
    with TestClient(app, follow_redirects=False) as c:
        j = _first(c, "synthrail")
        assert j["booking_url"] is None
        info = c.get(f"/api/v1/journeys/{j['id']}/booking").json()
        assert not info["bookable"] and "out of date" in info["reason"]
        assert c.get(f"/api/v1/journeys/{j['id']}/book").status_code == 409


def test_link_is_revalidated_against_the_provider_hosts(app_factory, demo, clock, catalog):
    import asyncio

    with TestClient(_bookable_app(app_factory, demo, clock, catalog)) as c:
        j = _first(c, "synthrail")
        journey, _, _ = asyncio.run(c.app.state.search.get_journey(j["id"]))
    assert _booking_target(journey)[0] == j["booking_url"]
    tampered = replace(journey, booking_url="https://tickets.synthrail.test.evil.example/pay")
    assert _booking_target(tampered) == (
        None,
        "This provider has not authorised booking links for this journey.",
    )
    plain_http = replace(journey, booking_url="http://tickets.synthrail.test/book")
    assert _booking_target(plain_http)[0] is None


def test_unknown_journey_booking(client):
    assert client.get("/api/v1/journeys/demo~NOPE.20261112/booking").status_code == 404
    assert client.get("/api/v1/journeys/demo~NOPE.20261112/book", follow_redirects=False).status_code == 404


def test_synthetic_booking_provider_is_dev_only(app_factory, settings):
    with pytest.raises(ValueError, match="TPORT_ENABLE_SYNTHETIC_BOOKING"):
        Settings(
            environment="production",
            enable_synthetic_booking=True,
            database_url="postgresql+psycopg://u:strong-secret@db/tport",
            cors_origins=["https://tport.example"],
        )
    dev = settings.model_copy(update={"enable_synthetic_booking": True})
    with TestClient(app_factory(settings=dev)) as c:
        j = _first(c, "synthbook")
        assert j["booking_url"].startswith("https://booking.synthrail.test/book?")
        assert "TEST" in j["legs"][0]["provider"]["name"]
    with TestClient(app_factory()) as c:  # off by default
        ids = {
            s["provider"]["id"]
            for s in c.get(
                "/api/v1/journeys/search",
                params={"origin": "tashkent", "destination": "samarkand", "date": TOMORROW.isoformat()},
            ).json()["sources"]
        }
        assert "synthbook" not in ids
