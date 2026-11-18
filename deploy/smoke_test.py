"""Post-deployment smoke test (standard library only).

    python deploy/smoke_test.py https://staging.tport.example [--ops-token TOKEN] [--basic-auth user:pass]

Exercises the deployed site through its public origin, as a browser would: frontend, API proxy,
database, search, journey detail, demo labelling, registration, saved journeys, sign-out and
sign-in, the AI assistant (fallback parser), and optionally the ops endpoints. It creates one
throwaway account and deletes it at the end. Exit code 0 only if every check passed.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import http.cookiejar
import json
import secrets
import sys
import urllib.error
import urllib.request


class Smoke:
    def __init__(self, base: str, basic_auth: str | None) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.auth = "Basic " + base64.b64encode(basic_auth.encode()).decode() if basic_auth else None
        self.results: list[tuple[str, bool, str]] = []

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)  # noqa: S310 - fixed base
        req.add_header("Origin", self.base)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.auth:
            req.add_header("Authorization", self.auth)
        csrf = next((c.value for c in self.jar if c.name == "tport_csrf"), None)
        if csrf and method != "GET":
            req.add_header("X-CSRF-Token", csrf)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with self.opener.open(req, timeout=20) as resp:
                raw = resp.read()
                return resp.status, raw
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def json(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        status, raw = self.request(method, path, body, headers)
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, None

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  - ' + detail) if detail and not ok else ''}")
        return bool(ok)


def run(base: str, ops_token: str | None, basic_auth: str | None) -> int:
    s = Smoke(base, basic_auth)
    tomorrow = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=5, days=1)).date().isoformat()

    status, html = s.request("GET", "/")
    s.check("frontend loads", status == 200 and b"T-PORT" in html.upper(), f"HTTP {status}")
    status, health = s.json("GET", "/health")
    s.check("API health (via proxy)", status == 200 and health and health.get("status") == "ok", f"{status} {health}")
    s.check("database connected", bool(health) and health.get("database") == "ok")

    status, locs = s.json("GET", "/api/v1/locations?q=Tashkent")
    s.check("location search", status == 200 and locs and locs["items"][0]["id"] == "tashkent", f"HTTP {status}")

    q = f"/api/v1/journeys/search?origin=tashkent&destination=samarkand&date={tomorrow}"
    status, res = s.json("GET", q)
    ok = status == 200 and res and res["total"] > 0
    s.check("journey search returns results", ok, f"HTTP {status}")
    if ok:
        demo = [j for j in res["items"] if j["is_demo"]]
        s.check("demo data labelled and not bookable",
                res["contains_demo_data"] == bool(demo)
                and all(j["booking_url"] is None and j["price_type"] == "demo" for j in demo))
        s.check("sources and freshness reported", bool(res["sources"]) and all("freshness" in x for x in res["sources"]))
        jid = res["items"][0]["id"]
        status, detail = s.json("GET", f"/api/v1/journeys/{jid}")
        s.check("journey detail", status == 200 and detail["journey"]["id"] == jid, f"HTTP {status}")

    email = f"smoke-{secrets.token_hex(6)}@example.com"
    password = secrets.token_urlsafe(16)
    status, _ = s.json("POST", "/api/v1/auth/register", {"email": email, "password": password})
    if s.check("registration", status == 201, f"HTTP {status}") and ok:
        status, saved = s.json("POST", "/api/v1/saved", {"journey_id": jid})
        s.check("save journey", status == 201, f"HTTP {status}")
        status, _ = s.json("POST", "/api/v1/auth/logout")
        s.check("sign out", status == 204, f"HTTP {status}")
        status, _ = s.json("POST", "/api/v1/auth/login", {"email": email, "password": password})
        s.check("sign in", status == 200, f"HTTP {status}")
        status, page = s.json("GET", "/api/v1/saved")
        s.check("saved journey persists", status == 200 and page and page["total"] == 1, f"HTTP {status}")
        status, _ = s.json("DELETE", "/api/v1/me", {"password": password})
        s.check("cleanup: account deleted", status == 204, f"HTTP {status}")

    status, ai = s.json("POST", "/api/v1/ai/interpret", {"text": "cheapest way from Tashkent to Samarkand tomorrow"})
    s.check("AI assistant (or its fallback) answers", status == 200 and ai and not ai["needs_clarification"],
            f"HTTP {status}")

    if ops_token:
        hdr = {"Authorization": f"Bearer {ops_token}"}
        status, ph = s.json("GET", "/health/providers", headers=hdr)
        s.check("provider health endpoint", status in (200, 503) and ph and ph.get("providers"), f"HTTP {status}")
        status, raw = s.request("GET", "/metrics", headers=hdr)
        s.check("metrics endpoint", status == 200 and b"tport_provider_up" in raw, f"HTTP {status}")
    status, _ = s.request("GET", "/metrics")
    s.check("metrics hidden without token", status == 404, f"HTTP {status}")

    failed = [r for r in s.results if not r[1]]
    print(f"\n{len(s.results) - len(failed)}/{len(s.results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("base_url")
    p.add_argument("--ops-token")
    p.add_argument("--basic-auth", help="user:pass for an access-restricted staging proxy")
    a = p.parse_args()
    sys.exit(run(a.base_url, a.ops_token, a.basic_auth))
