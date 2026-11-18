"""REST adapter template: conformance on synthetic data, error mapping, outbound guard, contract gate."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from app.core.outbound import OutboundBlocked
from app.providers.base import ProviderError, ProviderRateLimited
from app.providers.contracts import check_conformance, contract_problems
from app.providers.registry import contract_for, enabled_contracts
from app.providers.template.adapter import RestTemplateAdapter, StopMapping
from app.providers.template.contract import TEMPLATE_CONTRACT, TEMPLATE_INFO
from app.services.search import SearchQuery, SearchService
from tests.conftest import NOW, POLICY, TODAY, TOMORROW

BASE = "https://api.provider.example"
DATA = json.loads((Path(__file__).parent / "fixtures" / "template_api" / "trips.json").read_text("utf-8"))
STOPS = {"TAS-C": "tashkent-bus", "SAM-C": "samarkand-bus", "BUK-C": "bukhara-bus"}


class FakeServer:
    """In-process stand-in for the provider API, serving the synthetic fixture."""

    def __init__(self, data=DATA):
        self.data = data
        self.requests: list[httpx.Request] = []
        self.override: httpx.Response | Exception | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.override, Exception):
            raise self.override
        if self.override is not None:
            return self.override
        path = request.url.path
        if path == "/v1/trips":
            q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
            trips = [
                t
                for t in self.data["trips"]
                if t["from_stop"] == q["from"]
                and t["to_stop"] == q["to"]
                and t["departs_at"][:10] == q["date"]
            ]
            return httpx.Response(200, json={"generated_at": self.data["generated_at"], "trips": trips})
        if path.startswith("/v1/trips/"):
            trip_id = path.rsplit("/", 1)[1]
            trip = next((t for t in self.data["trips"] if t["trip_id"] == trip_id), None)
            if trip is None:
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(200, json={"generated_at": self.data["generated_at"], "trip": trip})
        return httpx.Response(404)


def _adapter(catalog, clock, server=None, **kw):
    server = server or FakeServer()
    client = httpx.AsyncClient(transport=httpx.MockTransport(server))
    adapter = RestTemplateAdapter(
        TEMPLATE_INFO, base_url=BASE, stops=StopMapping(STOPS, catalog), clock=clock, client=client, **kw
    )
    return adapter, server


def test_template_adapter_conforms_on_synthetic_data(catalog, clock):
    adapter, _ = _adapter(catalog, clock)
    report = asyncio.run(
        check_conformance(
            adapter,
            TEMPLATE_CONTRACT,
            catalog,
            [
                ("tashkent", "samarkand", TOMORROW),
                ("tashkent", "bukhara", TOMORROW),
                ("samarkand", "bukhara", TOMORROW),
            ],
            NOW,
        )
    )
    assert report.ok, report.violations
    assert report.departures == 4 and report.offers == 5


def test_template_feeds_the_search_engine(catalog, clock):
    adapter, _ = _adapter(catalog, clock)
    svc = SearchService(catalog, [adapter], clock, POLICY)
    r = asyncio.run(svc.search(SearchQuery("tashkent", "samarkand", TOMORROW, max_transfers=0)))
    assert [j.price for j in r.journeys] == sorted(j.price for j in r.journeys)
    assert {j.legs[0].departure.operator_name for j in r.journeys} == {
        "Example Coach Co (fictional test fixture)"
    }
    assert all(j.booking_url is None for j in r.journeys)  # no booking hosts: never bookable
    via = asyncio.run(svc.search(SearchQuery("tashkent", "bukhara", TOMORROW, max_transfers=1)))
    assert any(j.transfers == 1 for j in via.journeys)  # TAS -> SAM -> BUK through the journey graph


def test_template_contract_cannot_be_enabled():
    problems = contract_problems(TEMPLATE_CONTRACT, TODAY)
    for expected in (
        "authorization reference is missing",
        "authorization has not been verified by a named person",
        "source does not permit showing prices; T-Port cannot list its fares",
        "data mapping is undocumented",
        "onboarding record lacks official_identity",
        "provider is disabled by its contract",
    ):
        assert expected in problems
    assert contract_for("template") is None
    assert all(c.info.id != "template" for c in enabled_contracts(TODAY))


def test_schema_drift_is_rejected_not_half_parsed(catalog, clock):
    drifted = json.loads(json.dumps(DATA))
    drifted["trips"][0]["platform"] = "7"  # unexpected new field
    adapter, _ = _adapter(catalog, clock, FakeServer(drifted))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(adapter.get_departures("tashkent", "samarkand", TOMORROW, frozenset()))
    assert "invalid response" in str(exc.value) and not exc.value.retryable


def test_unmapped_stop_is_an_error(catalog, clock):
    data = json.loads(json.dumps(DATA))
    data["trips"][0]["to_stop"] = "XYZ"
    server = FakeServer(data)
    server.data["trips"][0]["from_stop"] = "TAS-C"
    adapter, _ = _adapter(catalog, clock, server)
    with pytest.raises(ProviderError, match="stop code"):
        asyncio.run(adapter.get_departure("EC100.20261112"))
    with pytest.raises(ValueError, match="unknown T-Port stations"):
        StopMapping({"TAS-C": "atlantis-bus"}, catalog)


@pytest.mark.parametrize(
    ("response", "kind", "retryable"),
    [
        (httpx.Response(429, headers={"Retry-After": "30"}), ProviderRateLimited, True),
        (httpx.Response(503), ProviderError, True),
        (httpx.Response(401), ProviderError, False),
        (httpx.Response(302, headers={"Location": "https://elsewhere.example/"}), ProviderError, False),
        (httpx.ReadTimeout("slow"), ProviderError, True),
        (httpx.ConnectError("down"), ProviderError, True),
    ],
)
def test_http_error_mapping(catalog, clock, response, kind, retryable):
    adapter, server = _adapter(catalog, clock)
    server.override = response
    with pytest.raises(kind) as exc:
        asyncio.run(adapter.get_departures("tashkent", "samarkand", TOMORROW, frozenset()))
    assert exc.value.retryable is retryable
    if kind is ProviderRateLimited:
        assert exc.value.retry_after_seconds == 30


def test_lookups_and_api_key_handling(catalog, clock):
    adapter, server = _adapter(catalog, clock, api_key="test-key-not-real")
    dep = asyncio.run(adapter.get_departure("EC102.20261112"))
    assert dep is not None and dep.origin_station_id == "tashkent-bus" and dep.duration_minutes == 270
    assert asyncio.run(adapter.get_departure("EC999.20261112")) is None  # 404 -> None
    before = len(server.requests)
    assert asyncio.run(adapter.get_departure("../../admin")) is None  # rejected before any request
    assert len(server.requests) == before
    offers = asyncio.run(adapter.get_offers(["EC102.20261112"]))
    assert sorted(o.fare_name for o in offers) == ["Comfort", "Standard"]
    for request in server.requests:
        assert request.headers["Authorization"] == "Bearer test-key-not-real"
        assert "test-key-not-real" not in str(request.url)


@pytest.mark.parametrize(
    "base_url", ["http://api.provider.example", "https://127.0.0.1", "https://10.0.0.5/api"]
)
def test_outbound_guard_rejects_unsafe_base_urls(catalog, clock, base_url):
    with pytest.raises(OutboundBlocked):
        RestTemplateAdapter(TEMPLATE_INFO, base_url=base_url, stops=StopMapping(STOPS, catalog), clock=clock)


def test_contract_with_paperwork_filled_in_passes_the_gate():
    """What onboarding must change: everything the gate lists, nothing else."""
    from datetime import date

    from app.providers.contracts import Onboarding

    filled = replace(
        TEMPLATE_CONTRACT,
        authorization=replace(
            TEMPLATE_CONTRACT.authorization,
            reference="AGR-TEST-1",
            permits_price_display=True,
            verified_by="Test reviewer",
            verified_on=date(2026, 11, 1),
            expires_on=date(2027, 11, 1),
        ),
        data_mapping="Stop codes per tests/test_provider_template.py STOPS; ISO 8601 with offset; UZS.",
        onboarding=Onboarding(
            official_identity="Fictional test operator",
            access_method="rest_api",
            allowed_usage="Tests only",
            redistribution_restrictions="n/a",
            commercial_use_restrictions="n/a",
            rate_limit_terms="30 rpm",
            refresh_expectations="On request",
            contact_escalation="Engineering",
            technical_docs="app/providers/template",
        ),
        enabled=True,
    )
    assert contract_problems(filled, TODAY) == []
