"""AI interpreter: deterministic parsing, structured-output validation, fallback, grounding."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.ai import rules
from app.ai.intent import RawIntent, validate_intent
from app.ai.llm import InterpreterError, LLMResult
from app.db import models as m
from app.domain.models import TransportMode
from app.services.search import SortKey
from tests.conftest import TODAY

FRIDAY = date(2026, 11, 13)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Find the cheapest way from Tashkent to Samarkand tomorrow.",
            dict(
                origin_id="tashkent",
                destination_id="samarkand",
                travel_date="2026-11-12",
                budget_preference="lowest",
            ),
        ),
        (
            "to Bukhara from Toshkent on Friday by train",
            dict(origin_id="tashkent", destination_id="bukhara", travel_date="2026-11-13", modes=["train"]),
        ),
        (
            "Samarqanddan Buxoroga ertaga poyezd",
            dict(origin_id="samarkand", destination_id="bukhara", travel_date="2026-11-12", modes=["train"]),
        ),
        (
            "Ташкент → Хива завтра",
            dict(origin_id="tashkent", destination_id="khiva", travel_date="2026-11-12"),
        ),
        (
            "fastest Tashkent - Fergana 20 November, no taxi",
            dict(
                origin_id="tashkent",
                destination_id="fergana",
                travel_date="2026-11-20",
                excluded_modes=["taxi"],
                time_preference="fastest",
            ),
        ),
        (
            "flight to Termez under 900k in the morning",
            dict(
                origin_id=None,
                destination_id="termez",
                modes=["flight"],
                max_price_uzs=900_000,
                time_preference="morning",
            ),
        ),
        ("Urgench to Khiva 2026-11-25 evening", dict(travel_date="2026-11-25", time_preference="evening")),
        ("book me a hotel please", dict(origin_id=None, destination_id=None)),
    ],
)
def test_rules_parser(catalog, text, expected):
    intent = rules.parse(text, catalog, TODAY)
    for key, value in expected.items():
        assert getattr(intent, key) == value, (key, intent)


def test_rules_flag_unsupported_requests(catalog):
    assert rules.parse("book me a hotel please", catalog, TODAY).unsupported_reason


def _raw(**kw) -> RawIntent:
    base = dict(
        origin_id="tashkent",
        destination_id="samarkand",
        travel_date=None,
        modes=[],
        excluded_modes=[],
        budget_preference="any",
        max_price_uzs=None,
        time_preference="any",
        unsupported_reason=None,
    )
    base.update(kw)
    return RawIntent(**base)


def test_structured_output_schema_is_strict():
    with pytest.raises(ValidationError):
        RawIntent.model_validate({**_raw().model_dump(), "price": 1000})  # extra field (invented fact)
    with pytest.raises(ValidationError):
        RawIntent.model_validate({**_raw().model_dump(), "modes": ["teleport"]})
    with pytest.raises(ValidationError):
        RawIntent.model_validate({**_raw().model_dump(), "time_preference": "sometime"})


def test_validate_intent(catalog):
    v = validate_intent(_raw(budget_preference="lowest"), catalog, TODAY, 90)
    assert v.complete and v.sort == SortKey.PRICE and v.travel_date == TODAY
    v = validate_intent(_raw(destination_id="atlantis"), catalog, TODAY, 90)
    assert not v.complete and "destination" in v.missing and v.problems
    assert validate_intent(_raw(travel_date="2020-01-01"), catalog, TODAY, 90).problems
    assert validate_intent(_raw(travel_date="2026-13-45"), catalog, TODAY, 90).problems
    assert validate_intent(_raw(destination_id="tashkent"), catalog, TODAY, 90).problems
    all_out = validate_intent(_raw(excluded_modes=["train", "bus", "flight", "taxi"]), catalog, TODAY, 90)
    assert all_out.problems
    no_taxi = validate_intent(_raw(excluded_modes=["taxi"]), catalog, TODAY, 90)
    assert no_taxi.modes == frozenset({TransportMode.TRAIN, TransportMode.BUS, TransportMode.FLIGHT})
    morning = validate_intent(_raw(time_preference="morning"), catalog, TODAY, 90)
    assert morning.depart_after.hour == 5 and morning.depart_before.hour == 12


def test_interpret_endpoint_uses_real_search_results(client):
    r = client.post(
        "/api/v1/ai/interpret", json={"text": "cheapest train from Tashkent to Samarkand tomorrow"}
    )
    body = r.json()
    assert r.status_code == 200 and body["engine"] == "rules" and not body["needs_clarification"]
    assert body["intent"]["sort"] == "price" and body["intent"]["modes"] == ["train"]
    results = body["results"]
    assert results["total"] > 0 and all("train" in j["modes"] for j in results["items"])
    # The explanation's price must be the first result's real price.
    top_price = f"{int(float(results['items'][0]['price'])):,}"
    assert top_price in body["explanation"]
    direct = client.get(
        "/api/v1/journeys/search",
        params={
            "origin": "tashkent",
            "destination": "samarkand",
            "date": "2026-11-12",
            "modes": "train",
            "sort": "price",
        },
    ).json()
    assert [j["id"] for j in direct["items"]][:5] == [j["id"] for j in results["items"]]


def test_interpret_asks_for_missing_information(client):
    body = client.post("/api/v1/ai/interpret", json={"text": "I want to go to Bukhara on Friday"}).json()
    assert body["needs_clarification"] and body["results"] is None
    assert "starting" in body["clarification"].lower()
    body = client.post("/api/v1/ai/interpret", json={"text": "hotel in Samarkand"}).json()
    assert body["needs_clarification"]


def test_interpret_explains_empty_results(client):
    body = client.post(
        "/api/v1/ai/interpret", json={"text": "flight from Tashkent to Samarkand tomorrow"}
    ).json()
    assert body["results"]["total"] == 0
    assert "couldn't find" in body["explanation"]


def test_interpret_input_limits(client):
    assert client.post("/api/v1/ai/interpret", json={"text": "   "}).status_code == 422
    assert client.post("/api/v1/ai/interpret", json={"text": "x" * 600}).status_code == 422
    assert client.post("/api/v1/ai/interpret", json={}).status_code == 422


class FakeLLM:
    engine = "anthropic"
    model = "fake-model"

    def __init__(self, result: RawIntent | None = None, error: str | None = None) -> None:
        self.result, self.error = result, error

    async def interpret(self, text, today, locations):
        if self.error:
            raise InterpreterError(self.error)
        return LLMResult(self.result, self.model, 120, 40)


def test_llm_output_is_used_when_valid(app_factory):
    llm = FakeLLM(_raw(destination_id="bukhara", travel_date=FRIDAY.isoformat(), modes=["flight"]))
    with TestClient(app_factory(llm=llm)) as c:
        body = c.post("/api/v1/ai/interpret", json={"text": "whatever"}).json()
    assert body["engine"] == "anthropic" and not body["fallback_used"]
    assert body["intent"]["destination_id"] == "bukhara" and body["results"]["total"] >= 1


@pytest.mark.parametrize("code", ["invalid_output", "timeout", "rate_limited", "http_500"])
def test_llm_failure_falls_back_to_rules(app_factory, db_factory, code):
    with TestClient(app_factory(llm=FakeLLM(error=code))) as c:
        body = c.post("/api/v1/ai/interpret", json={"text": "Tashkent to Bukhara tomorrow"}).json()
    assert body["engine"] == "rules" and body["fallback_used"]
    assert body["intent"]["destination_id"] == "bukhara" and body["results"]["total"] > 0
    with db_factory() as db:
        row = db.scalar(select(m.AIRequest))
    assert row.error_code == code and row.outcome in ("invalid_output", "provider_error")


def test_llm_cannot_inject_unknown_locations(app_factory):
    llm = FakeLLM(_raw(origin_id="tashkent", destination_id="paris"))
    with TestClient(app_factory(llm=llm)) as c:
        body = c.post("/api/v1/ai/interpret", json={"text": "Tashkent to Paris"}).json()
    assert body["needs_clarification"] and body["results"] is None
    assert body["intent"]["destination_id"] is None


def test_ai_metadata_does_not_store_prompt_text(client, db_factory):
    secret = "my passport AB1234567 Tashkent to Samarkand tomorrow"
    client.post("/api/v1/ai/interpret", json={"text": secret})
    with db_factory() as db:
        row = db.scalar(select(m.AIRequest))
        values = [str(getattr(row, c.key)) for c in m.AIRequest.__table__.columns]
    assert row.input_chars == len(secret)
    assert not any("AB1234567" in v for v in values)
