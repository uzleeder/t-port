# API

Base path `/api/v1`. The full OpenAPI schema is served at `/openapi.json` and `/docs` in
non-production environments (both are disabled in production).

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | none | `200` when the database is reachable, `503` otherwise |
| GET | `/health/providers` | ops token | provider states and import statistics (404 without the token) |
| GET | `/metrics` | ops token | Prometheus text (404 without the token) |
| GET | `/api/v1/locations?q=&limit=&offset=` | none | Alias-aware city search, paginated |
| GET | `/api/v1/locations/{id}` | none | City with its stations |
| GET | `/api/v1/journeys/search` | optional | See parameters below |
| GET | `/api/v1/journeys/{id}` | none | Recomputed from current data |
| POST | `/api/v1/auth/register` | none | Sets session + CSRF cookies |
| POST | `/api/v1/auth/login` | none | Rotates any existing session |
| POST | `/api/v1/auth/logout` | session + CSRF | Revokes the session server-side |
| GET | `/api/v1/me` | session | Profile, saved count, recent searches |
| DELETE | `/api/v1/me` | session + CSRF + password | Deletes the account |
| GET | `/api/v1/saved?limit=&offset=` | session | Newest first |
| POST | `/api/v1/saved` | session + CSRF | `{journey_id, note?}`; only currently valid journeys |
| DELETE | `/api/v1/saved/{id}` | session + CSRF | `404` for other users' items |
| POST | `/api/v1/ai/interpret` | optional | `{text}` (≤500 chars) |

## Journey search parameters

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `origin`, `destination` | location ID | required | e.g. `tashkent`, `samarkand` (from `/locations`) |
| `date` | `YYYY-MM-DD` | required | Local date at the origin |
| `modes` | `train,bus,flight,taxi` | all | Comma list |
| `sort` | `recommended \| price \| duration \| departure` | `recommended` | |
| `max_price` | decimal | none | Same currency as results (UZS) |
| `depart_after`, `depart_before` | `HH:MM` | none | Local departure window; on-demand services always match |
| `max_transfers` | `0 \| 1` | `1` | `0` = direct journeys only |
| `page`, `page_size` | int | 1, 20 | `page_size` ≤ 50 |

The response contains `items`, `total`, `page`, `summary` (cheapest, fastest and earliest IDs, price
range, count per mode), `sources` (provider, retrieved time, freshness), `excluded` (counts of hidden
options and why), `warnings` and `contains_demo_data`.

## Errors

Every error has the same shape:

```json
{"error": {"code": "validation_error", "message": "Invalid search request.",
           "details": [{"field": "date", "message": "Travel date is in the past."}]}}
```

| Status | `code` |
|---|---|
| 401 | `unauthorized` |
| 403 | `forbidden` (missing/invalid CSRF token, cross-origin request) |
| 404 | `not_found` |
| 409 | `conflict` |
| 413 | `payload_too_large` (bodies over 64 KB) |
| 422 | `validation_error` |
| 429 | `rate_limited` (with `Retry-After`) |
| 503 | `providers_unavailable` |

## Rate limits (per client IP, per minute)

All `/api/*` requests: 120. Unsafe requests to `/api/v1/auth/*`: 10. `/api/v1/ai/*`: 20. All are
configurable. The auth and AI limits are shared by all API workers (PostgreSQL); the general limit is
counted per process. Failed logins are additionally limited per account (5 per 15 minutes).

## Reliability fields (added in Phase 2, backward compatible)
Each journey keeps `freshness` and `booking_url`, and adds:
- `price_type`: `confirmed` (a fresh live price), `indicative`, `estimated` or `demo`; for a connection,
  the least certain of its legs
- `booking_note`: why there is no booking link, when there isn't one

Each leg adds `timetable_freshness`, `price_freshness` (`fresh|stale|unknown|expired`), `price_type`
and `provider` (`id`, `name`, `is_demo`, `attribution`). `freshness` may now also be `unknown`.

Development and test only: with `TPORT_ENABLE_FAULT_SIMULATION=true` (refused in production), search
accepts `simulate=stale` and/or `simulate=outage` to exercise stale-data and outage handling.
