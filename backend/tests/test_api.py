"""HTTP layer: routing, validation, structured errors, CORS, rate limiting."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.providers.base import validate_booking_url
from tests.conftest import TOMORROW


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["providers"][0]["is_demo"] is True


def test_locations_alias_search(client):
    names = [x["name"] for x in client.get("/api/v1/locations", params={"q": "Buxoro"}).json()["items"]]
    assert names == ["Bukhara"]
    assert client.get("/api/v1/locations", params={"q": "qoqon"}).json()["items"][0]["id"] == "kokand"


def test_locations_pagination(client):
    page = client.get("/api/v1/locations", params={"limit": 5, "offset": 5}).json()
    assert page["total"] == 14 and len(page["items"]) == 5 and page["offset"] == 5


def test_location_detail_includes_stations(client):
    body = client.get("/api/v1/locations/tashkent").json()
    assert {s["kind"] for s in body["stations"]} >= {"airport", "rail_station"}
    assert client.get("/api/v1/locations/nowhere").status_code == 404


def test_search_endpoint(client):
    r = client.get(
        "/api/v1/journeys/search",
        params={
            "origin": "tashkent",
            "destination": "samarkand",
            "date": TOMORROW.isoformat(),
            "modes": "train,bus",
            "sort": "price",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["contains_demo_data"] is True
    assert set(body["query"]["modes"]) == {"train", "bus"}
    assert all(set(j["modes"]) <= {"train", "bus"} for j in body["items"])
    leg = body["items"][0]["legs"][0]
    assert leg["departure_local"].endswith("+05:00")


def test_search_structured_errors(client):
    base = {"origin": "tashkent", "destination": "samarkand", "date": TOMORROW.isoformat()}
    cases = [
        ({**base, "destination": "tashkent"}, 422),
        ({**base, "origin": "atlantis"}, 404),
        ({**base, "date": "2020-01-01"}, 422),
        ({**base, "date": "not-a-date"}, 422),
        ({**base, "modes": "teleport"}, 422),
        ({**base, "sort": "random"}, 422),
        ({**base, "max_price": "-5"}, 422),
        ({"origin": "tashkent"}, 422),
    ]
    for params, status in cases:
        r = client.get("/api/v1/journeys/search", params=params)
        assert r.status_code == status, params
        err = r.json()["error"]
        assert err["code"] and err["message"]


def test_journey_detail_endpoint(client):
    search = client.get(
        "/api/v1/journeys/search",
        params={"origin": "tashkent", "destination": "bukhara", "date": TOMORROW.isoformat()},
    ).json()
    jid = search["items"][0]["id"]
    detail = client.get(f"/api/v1/journeys/{jid}").json()
    assert detail["journey"]["id"] == jid
    assert client.get("/api/v1/journeys/demo~ZZ000.20261112").status_code == 404


def test_cors_allows_only_known_origins(client):
    ok = client.options(
        "/api/v1/locations",
        headers={"Origin": "http://localhost:2028", "Access-Control-Request-Method": "GET"},
    )
    bad = client.options(
        "/api/v1/locations",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:2028"
    assert "access-control-allow-origin" not in bad.headers


def test_rate_limit(app_factory):
    c = TestClient(app_factory(settings=Settings(environment="test", rate_limit_per_minute=3)))
    codes = [c.get("/api/v1/locations").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert c.get("/api/v1/locations").json()["error"]["code"] == "rate_limited"


def test_security_headers(client):
    h = client.get("/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


def test_booking_url_validation():
    allowed = frozenset({"book.example.com", ".rail.example"})
    good = ["https://book.example.com/a?b=1", "https://tickets.rail.example/x"]
    bad = [
        None,
        "",
        "http://book.example.com/",
        "https://evil.com/",
        "https://book.example.com.evil.com/",
        "https://user:pw@book.example.com/",
        "https://book.example.com:8443/",
        "javascript:alert(1)",
        "https://rail.example/",
        "https://notbook.example.com/",
    ]
    assert all(validate_booking_url(u, allowed) == u for u in good)
    assert all(validate_booking_url(u, allowed) is None for u in bad)
    assert validate_booking_url("https://book.example.com/", frozenset()) is None
