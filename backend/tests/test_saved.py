"""Saved journeys: authentication, CSRF, ownership, snapshots, pagination."""

from tests.conftest import TOMORROW, csrf_headers, register


def _journey_id(client, origin="tashkent", destination="samarkand") -> str:
    r = client.get(
        "/api/v1/journeys/search",
        params={"origin": origin, "destination": destination, "date": TOMORROW.isoformat()},
    )
    return r.json()["items"][0]["id"]


def _save(client, journey_id, note=None):
    return client.post(
        "/api/v1/saved", json={"journey_id": journey_id, "note": note}, headers=csrf_headers(client)
    )


def test_saving_requires_login_and_csrf(client):
    jid = _journey_id(client)
    assert client.post("/api/v1/saved", json={"journey_id": jid}).status_code == 401
    register(client)
    assert client.post("/api/v1/saved", json={"journey_id": jid}).status_code == 403
    assert client.get("/api/v1/saved").json()["total"] == 0


def test_save_list_delete(client):
    register(client)
    jid = _journey_id(client)
    r = _save(client, jid, note="  Grandma's visit  ")
    assert r.status_code == 201
    saved = r.json()
    assert saved["journey_id"] == jid and saved["note"] == "Grandma's visit"
    assert saved["snapshot"]["origin_name"] == "Tashkent" and saved["snapshot"]["is_demo"] is True
    assert saved["travel_date"] == TOMORROW.isoformat()

    assert _save(client, jid).status_code == 409  # duplicate
    page = client.get("/api/v1/saved").json()
    assert page["total"] == 1 and page["items"][0]["id"] == saved["id"]
    assert client.get("/api/v1/me").json()["saved_count"] == 1

    assert client.delete(f"/api/v1/saved/{saved['id']}").status_code == 403  # no CSRF
    assert client.delete(f"/api/v1/saved/{saved['id']}", headers=csrf_headers(client)).status_code == 204
    assert client.delete(f"/api/v1/saved/{saved['id']}", headers=csrf_headers(client)).status_code == 404


def test_only_real_journeys_can_be_saved(client):
    register(client)
    assert _save(client, "demo~ZZ999.20261112").status_code == 404
    assert _save(client, "demo~TR101.20261111").status_code == 404  # already departed
    assert (
        client.post("/api/v1/saved", json={"journey_id": "x"}, headers=csrf_headers(client)).status_code
        == 422
    )


def test_users_cannot_see_or_delete_each_others_journeys(client):
    register(client, email="alice@example.com")
    saved_id = _save(client, _journey_id(client)).json()["id"]
    client.cookies.clear()
    register(client, email="bob@example.com")
    assert client.get("/api/v1/saved").json()["total"] == 0
    r = client.delete(f"/api/v1/saved/{saved_id}", headers=csrf_headers(client))
    assert r.status_code == 404  # not 403: existence is not revealed
    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "correct horse 42"})
    assert client.get("/api/v1/saved").json()["total"] == 1


def test_saved_pagination(client):
    register(client)
    r = client.get(
        "/api/v1/journeys/search",
        params={
            "origin": "tashkent",
            "destination": "samarkand",
            "date": TOMORROW.isoformat(),
            "page_size": 50,
        },
    )
    ids = [j["id"] for j in r.json()["items"]][:3]
    for jid in ids:
        assert _save(client, jid).status_code == 201
    page = client.get("/api/v1/saved", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert client.get("/api/v1/saved", params={"limit": 0}).status_code == 422


def test_invalid_saved_id_format(client):
    register(client)
    assert client.delete("/api/v1/saved/not-a-uuid", headers=csrf_headers(client)).status_code == 422
