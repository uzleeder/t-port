# Architecture

T-Port is a **modular monolith**: one API process and one web process, with clear internal module
boundaries so pieces can be split out later if load justifies it. Nothing here has been load-tested,
and no scalability claim is made beyond a single-region pilot.

```
Browser ──HTTPS──> Caddy ──> Next.js (web, :2028) ──/api/* rewrite──> FastAPI (api, :8000) ──> PostgreSQL
                                   │ server components fetch the API directly (API_INTERNAL_URL)
```

The browser only ever talks to the web origin. The web server proxies `/api/*`, so session cookies
stay same-origin and the API is never exposed publicly.

## Backend modules (`backend/app`)

| Module | Responsibility | Depends on |
|---|---|---|
| `domain/` | Pure data types: Location, Station, Departure, Offer, Journey, Leg | nothing |
| `providers/` | `ProviderAdapter` interface; contracts and conformance checks; `DemoAdapter`, `FeedAdapter`, `StoredTimetableAdapter`; registry | domain |
| `services/search.py` | Validation, provider fan-out, filtering, ranking, pagination | providers, domain |
| `services/transfers.py` | Pure connection-feasibility rules | domain, catalog |
| `services/freshness.py` | Fresh / stale / expired policy | domain |
| `services/auth.py` | Password hashing, sessions, CSRF checks | db |
| `services/imports.py` | Locked, bounded, retrying, validated snapshot imports with an audit record | providers, db |
| `services/provider_health.py` | Per-provider status from call stats and import history; Prometheus output | db |
| `ai/` | Intent schema, deterministic parser, LLM adapter, grounded explanations | services |
| `db/` | ORM models, repositories (no business rules) | SQLAlchemy |
| `api/` | HTTP routes, request/response schemas, dependencies | everything above |

## Search pipeline (deterministic)

1. **Validate**: known locations, origin ≠ destination, date between today (Asia/Tashkent) and +90 days.
2. **Fetch**: every provider serving both cities is queried concurrently with a timeout. A failing
   provider produces a warning; if *all* fail, the API returns `503 providers_unavailable`.
3. **Clean**: drop departures that have left, have no priced offer, or whose data is **expired**
   under *that provider's* contract (freshness is per source).
   Mixed-currency offers are dropped. **Stale** data is kept but flagged.
4. **Compose transfers** (`max_transfers=1`, the default): for each hub city, pair scheduled first legs
   with second legs on the same or next day, keeping only connections that pass `check_connection`.
   A connection is dropped if a direct option is both cheaper-or-equal and faster-or-equal.
5. **Filter**: modes, max price, departure time window.
6. **Rank** with a fully deterministic key (journey ID is the final tiebreaker):
   - `price`: price, duration, departure
   - `duration`: duration, price, departure
   - `departure`: departure (on-demand last), price
   - `recommended`: price/min_price + duration/min_duration + 0.15 × transfers + 0.10 if the price is an estimate

### Transfer rules (`services/transfers.py`)

| Rule | Default (configurable) |
|---|---|
| Minimum connection, same station | 20 min |
| Minimum connection, station change in the same city | 60 min |
| Minimum connection before a flight | 120 min |
| Maximum wait | 6 h |
| On-demand legs (taxi) | Not used in connections: no fixed time to check |
| Different cities at the change point | Rejected |
| Border crossing | Rejected: no crossing-time data, so none is assumed |
| Guarantee | Never: separate tickets, delays not protected (shown to the user) |

`travel_minutes` is in-vehicle time. `total_minutes` is first departure to final arrival including waits.
Neither includes getting to or from stations; the UI says so.

## Journey identifiers

- Direct: `{provider}~{departure_id}` (e.g. `demo~TR101.20261112`)
- With a transfer: `x~{provider}:{departure}+{provider}:{departure}`

Journey details are always recomputed from current provider data. If a departure has left or its
data has expired, the detail page says so instead of showing old numbers. Saved journeys store a
dated **snapshot** that is displayed as "when saved", never as current data.

## AI boundary

```
text ──> interpreter (rules | LLM) ──> RawIntent (strict schema) ──> validate_intent ──> SearchService ──> explain()
```

- The interpreter can only output `RawIntent`: location IDs, date, modes, budget and time preferences.
  Extra fields are rejected (`extra="forbid"`).
- Location IDs are re-checked against the catalog, so a hallucinated city becomes "not covered".
- The explanation is a template filled from search results: every price, time and operator name
  comes from provider data.
- Any LLM failure (missing key, timeout, rate limit, refusal, invalid output) falls back to the
  deterministic parser and is recorded in `ai_requests` (metadata only, no prompt text).
- LangChain is not used. A single structured-output call doesn't need it, and the adapter interface
  (`ai/llm.py`) is where an alternative would plug in.

## Data model

See `backend/app/db/models.py` and `migrations/`. Highlights:
- UTC timestamps everywhere (`UTCDateTime` rejects naive datetimes). Local time zones are kept in
  `locations.timezone` and `departures.departure_tz`.
- Money is `NUMERIC(14,2)` with an explicit `currency`.
- Check constraints: positive prices, `price_max ≥ price`, `arrival > departure`, valid import status.
- Unique constraints: user email, session token hash, `(provider, service_code)`,
  `(provider, external_id)`, `(departure, fare_name)`, `(user, journey_id)` for saved journeys.

Redis is not used: there is no cache or background workload yet that justifies it. The in-memory
rate limiter is the first thing that would move there when running multiple API processes.
