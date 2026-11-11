"""Provider health: status rules, ops endpoints, metrics, outage visibility."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.db import models as m
from app.providers.registry import DEMO_CONTRACT
from app.services.provider_health import ProviderCallStats, assess_provider, overall, prometheus_metrics
from tests.conftest import NOW, SYNTH_CONTRACT, TOMORROW, FakeAdapter

TOKEN = "t" * 40


def _imp(status: str, minutes_ago: float, departures: int = 40, offers: int = 50) -> m.DataImport:
    t = NOW - timedelta(minutes=minutes_ago)
    return m.DataImport(
        provider_id="synthrail",
        source_reference="x",
        status=status,
        started_at=t,
        finished_at=t,
        departures_count=departures,
        offers_count=offers,
        rejected_records=0,
    )


def _stats(ok: int, failed: int) -> ProviderCallStats:
    s = ProviderCallStats()
    for _ in range(ok):
        s.success(10, NOW)
    for _ in range(failed):
        s.failure(TimeoutError(), NOW)
    return s


@pytest.mark.parametrize(
    ("imports", "status", "reason"),
    [
        ([], "unknown", "no successful import"),
        ([_imp("failed", 5), _imp("failed", 70)], "unavailable", "no successful import"),
        ([_imp("succeeded", 10)], "healthy", "ok"),
        ([_imp("succeeded", 90)], "degraded", "imports are late"),  # stale after 1 h
        ([_imp("succeeded", 25 * 60)], "unavailable", "expiry limit"),  # expired after 24 h
        (
            [_imp("failed", 3), _imp("failed", 6), _imp("failed", 9), _imp("succeeded", 12)],
            "degraded",
            "3 imports failed in a row",
        ),
    ],
)
def test_stored_provider_health_rules(imports, status, reason):
    h = assess_provider(SYNTH_CONTRACT, None, imports, NOW)
    assert h.status == status and any(reason in r for r in h.reasons), h.reasons


def test_import_lag_and_streak_are_reported():
    h = assess_provider(SYNTH_CONTRACT, None, [_imp("failed", 1), _imp("succeeded", 30)], NOW)
    assert h.import_lag_seconds == 30 * 60 and h.consecutive_import_failures == 1
    assert h.last_import_status == "failed" and h.status == "healthy"  # one failure isn't an outage


@pytest.mark.parametrize(
    ("ok", "failed", "status"),
    [(0, 0, "unknown"), (2, 2, "healthy"), (9, 1, "degraded"), (5, 5, "unavailable"), (20, 0, "healthy")],
)
def test_live_provider_health_from_call_failures(ok, failed, status):
    assert assess_provider(DEMO_CONTRACT, _stats(ok, failed), [], NOW).status == status


def test_overall_takes_the_worst_status():
    assert overall(["healthy", "degraded", "unknown"]) == "degraded"
    assert overall(["healthy", "unavailable"]) == "unavailable"
    assert overall(["healthy", "disabled"]) == "healthy"  # switched-off sources aren't outages
    assert overall([]) == "healthy"


def test_error_messages_are_not_kept():
    s = ProviderCallStats()
    s.failure(RuntimeError("password=hunter2 for user@example.com"), NOW)
    assert s.last_error == "RuntimeError"


def test_metrics_format():
    h = [assess_provider(SYNTH_CONTRACT, _stats(3, 0), [_imp("succeeded", 10)], NOW)]
    text = prometheus_metrics(h, NOW)
    assert 'tport_provider_up{provider="synthrail",mode="stored"} 1' in text
    assert 'tport_provider_calls_total{provider="synthrail"} 3' in text
    assert 'tport_provider_import_lag_seconds{provider="synthrail"} 600' in text


@pytest.fixture
def ops_settings(settings):
    return settings.model_copy(update={"ops_token": SecretStr(TOKEN)})


def test_ops_endpoints_require_the_token(app_factory, ops_settings, client):
    assert client.get("/health/providers").status_code == 404  # no token configured at all
    with TestClient(app_factory(settings=ops_settings)) as c:
        assert c.get("/health/providers").status_code == 404
        assert c.get("/health/providers", headers={"Authorization": "Bearer wrong"}).status_code == 404
        assert c.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}x"}).status_code == 404
        ok = c.get("/health/providers", headers={"Authorization": f"Bearer {TOKEN}"})
        assert ok.status_code == 200 and ok.json()["providers"][0]["provider_id"] == "demo"
        metrics = c.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
        assert metrics.status_code == 200 and "tport_provider_up" in metrics.text


def test_provider_outage_is_observable_and_isolated(app_factory, ops_settings, demo):
    broken = FakeAdapter(fail=True, provider_id="synthrail")  # registered under the synthetic contract
    broken.info = SYNTH_CONTRACT.info
    broken.supported_location_ids = lambda: frozenset({"tashkent", "samarkand"})
    app = app_factory(
        settings=ops_settings, providers=[demo, broken], contracts=[DEMO_CONTRACT, SYNTH_CONTRACT]
    )
    auth = {"Authorization": f"Bearer {TOKEN}"}
    params = {
        "origin": "tashkent",
        "destination": "samarkand",
        "date": TOMORROW.isoformat(),
        "max_transfers": 0,
    }
    with TestClient(app) as c:
        for _ in range(5):
            r = c.get("/api/v1/journeys/search", params=params)
            assert r.status_code == 200 and r.json()["total"] > 0  # demo results still served
        health = c.get("/health/providers", headers=auth)
        metrics = c.get("/metrics", headers=auth).text
    body = {p["provider_id"]: p for p in health.json()["providers"]}
    assert body["demo"]["status"] == "healthy"
    assert body["synthrail"]["status"] == "unavailable" and body["synthrail"]["failures_total"] == 5
    assert health.status_code == 503 and health.json()["status"] == "unavailable"
    assert 'tport_provider_failures_total{provider="synthrail"} 5' in metrics


def test_ops_token_length_enforced_in_production():
    with pytest.raises(ValueError, match="OPS_TOKEN"):
        Settings(
            environment="production",
            cors_origins=["https://tport.example"],
            database_url="postgresql+psycopg://a:b@db/x",
            ops_token="short",
        )


def test_stored_mode_contract_is_used_for_health(app_factory, ops_settings, db_factory):
    from app.main import seed_reference

    seed_reference(db_factory)
    stored = ops_settings.model_copy(update={"demo_provider_mode": "stored"})
    with TestClient(app_factory(settings=stored, providers=None)) as c:
        body = c.get("/health/providers", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    demo = body["providers"][0]
    assert demo["mode"] == "stored" and demo["status"] == "unknown"  # never imported yet
    assert replace(DEMO_CONTRACT).ingestion.mode == "live"  # registry contract itself unchanged


def test_no_valid_offers_and_volume_drop_are_flagged():
    empty = assess_provider(SYNTH_CONTRACT, None, [_imp("succeeded", 5, departures=40, offers=0)], NOW)
    assert empty.status == "degraded" and any("no valid offers" in r for r in empty.reasons)
    drop = assess_provider(
        SYNTH_CONTRACT, None, [_imp("succeeded", 5, departures=10), _imp("succeeded", 70)], NOW
    )
    assert drop.status == "degraded" and any("dropped from 40 to 10" in r for r in drop.reasons)


def test_disabled_providers_are_reported_not_alarmed():
    h = assess_provider(SYNTH_CONTRACT, None, [], NOW, problems=["authorization expired on 2026-01-01"])
    assert h.status == "disabled" and h.reasons == ("authorization expired on 2026-01-01",)
    assert assess_provider(replace(SYNTH_CONTRACT, enabled=False), None, [], NOW).status == "disabled"


def test_import_statistics_are_exposed():
    last = _imp("failed", 2)
    last.duration_ms, last.rejected_records = 1500, 3
    h = assess_provider(SYNTH_CONTRACT, None, [last, _imp("succeeded", 20)], NOW)
    assert h.last_import_duration_ms == 1500 and h.last_rejected_records == 3
    assert h.last_attempted_import_at == NOW - timedelta(minutes=2) and h.failed_imports_recent == 1
    assert h.last_departures == 40 and h.last_offers == 50


def test_metrics_include_api_search_and_database(app_factory, ops_settings):
    auth = {"Authorization": f"Bearer {TOKEN}"}
    params = {"origin": "tashkent", "destination": "samarkand", "date": TOMORROW.isoformat()}
    with TestClient(app_factory(settings=ops_settings)) as c:
        c.get("/api/v1/journeys/search", params=params)
        c.get("/api/v1/journeys/demo~ZZ000.20261112")
        text = c.get("/metrics", headers=auth).text
    assert 'tport_http_requests_total{method="GET",route="/api/v1/journeys/search",status="2xx"} 1' in text
    assert 'route="/api/v1/journeys/{journey_id}",status="4xx"' in text  # template, not the raw id
    assert "tport_http_request_duration_seconds_bucket" in text and "tport_database_up 1" in text
    assert 'tport_searches_total{outcome="results"} 1' in text
    assert 'tport_journeys_shown_total{freshness="fresh",price_type="demo"}' in text


def test_rate_limits_are_counted(app_factory, ops_settings):
    limited = ops_settings.model_copy(update={"rate_limit_per_minute": 1})
    with TestClient(app_factory(settings=limited)) as c:
        c.get("/api/v1/locations")
        assert c.get("/api/v1/locations").status_code == 429
        text = c.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"}).text
    assert 'tport_rate_limited_total{scope="api"} 1' in text


def test_json_logs_contain_no_extra_fields(capsys):
    import json
    import logging

    from app.core.metrics import JsonFormatter

    record = logging.LogRecord("tport", logging.INFO, __file__, 1, "GET %s %s", ("/api/v1/me", 401), None)
    line = json.loads(JsonFormatter().format(record))
    assert line["msg"] == "GET /api/v1/me 401" and set(line) == {"ts", "level", "logger", "msg"}


def test_scheduler_runs_due_imports_and_backs_off(db_factory, catalog, clock):
    from app.core.clock import FixedClock
    from app.main import seed_reference
    from app.providers.feed import FeedAdapter
    from app.services.scheduler import Scheduler, is_due
    from tests.conftest import SYNTH_INFO, synth_feed

    seed_reference(db_factory)
    with db_factory() as db:
        db.add(
            m.Provider(
                id="synthrail",
                name="x",
                is_demo=False,
                attribution="t",
                booking_hosts=[],
                access_basis="TEST",
            )
        )
        db.commit()
    factories = {"synthrail": lambda: FeedAdapter(SYNTH_INFO, synth_feed(), catalog, clock)}
    sched = Scheduler([SYNTH_CONTRACT], factories, db_factory, clock, catalog)
    first = sched.tick()
    assert first["imports"][0]["outcome"] == "succeeded" and first["housekeeping"] is not None
    assert sched.tick()["imports"][0]["outcome"] == "not_due"  # interval is 60 minutes
    later = Scheduler(
        [SYNTH_CONTRACT], factories, db_factory, FixedClock(NOW + timedelta(minutes=61)), catalog
    )
    assert later.tick()["imports"][0]["outcome"] == "succeeded"
    # After a failure the provider is retried only after another interval (no hammering).
    assert not is_due(SYNTH_CONTRACT, [_imp("failed", 10)], NOW)
    assert is_due(SYNTH_CONTRACT, [_imp("failed", 61)], NOW)
