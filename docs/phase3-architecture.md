# Phase 3 architecture changes

Phase 3 keeps the modular monolith and the rule that **search is deterministic and AI only
interprets and explains**. This page covers what changed; [architecture.md](architecture.md) has the
overall picture.

## Request flow

```
Search form / assistant / compare page / booking page  (Next.js, server components + small client islands)
        │  /api/* rewrite (X-Forwarded-For and session cookie forwarded)
        ▼
FastAPI routes ── preferences (account) ── booking info / redirect ── compare
        │
        ▼
SearchService ── direct legs ──────────────┐
        │                                   ├── ProviderAdapter(s): demo · feed · (REST template) · TEST
        └── JourneyGraph ── location paths ─┘        each behind a ProviderContract
                 │
                 ▼
        chain legs → check_connection → Pareto front → rank (sort + preferred-mode bonus) → filters
```

## Routing (`services/journey_graph.py`, `services/route_optimizer.py`)

* **Graph:** nodes are catalogue locations; edges are the location pairs providers actually serve
  (`served_routes()`, or every pair of a provider's locations when it can't say). Stations inside a
  location are joined by transfer connections checked by `check_connection` (minimum connection,
  station change, flight check-in buffer, maximum wait, same country).
* **Time dependence:** departures are fetched per leg and local date. After each leg, onward legs
  come from the arrival's local day and the next day, so overnight legs connect next morning.
* **Bounds (`GraphLimits`):** at most 3 legs, 40 location paths (shortest first, then
  lexicographic), 6 onward departures per partial chain (earliest feasible first), 300 complete
  candidates. Results are reproducible.
* **Optimisation:** candidates are reduced to the Pareto front on (price, total time, changes),
  keeping ties; then at most 20 connections join the direct journeys for ranking.
* **Ranking:** sorts `recommended`, `price`, `duration`, `departure`, and new `transfers` (fewest
  changes, then time, then price). `prefer_modes` subtracts up to 0.25 from the recommended score in
  proportion to legs in a preferred mode; it never filters.
* **Filters:** `arrive_before` (local time at the destination; journeys without a fixed arrival are
  excluded and counted), departure window, budget, modes, `max_transfers` 0–2.

## Assistant (`ai/intent.py`, `ai/rules.py`, `ai/service.py`)

* `RawIntent` (the only thing an interpreter may produce) gained `arrive_before`,
  `depart_after/before`, `transfer_preference`, `max_transfers`, `prefer_modes`, `compare_modes`,
  `budget_amount/currency`. Defaults keep older outputs valid; `extra="forbid"` and patterns keep it
  strict.
* `validate_intent` maps them to a `SearchQuery` (`search_query_for`), and `query_string` gives the
  exact `/search` URL for the same search.
* `explain` is a template over the results: route, top journey (modes, operators, times, changes and
  hubs, duration, price), price type, staleness, sources, constraints applied, best option per mode
  when comparing, and reasons when nothing matched (budget, time, departed, expired data,
  unreachable sources).
* Metrics: requests by engine/outcome, latency, errors, clarifications, tokens, and cost only from
  operator-configured prices.

## Comparison (`services/comparison.py`, `GET /journeys/compare`, `/compare`)

Re-resolves 2–4 journeys from current data; reports unavailable ones; returns the best IDs per
criterion (ties kept) and caveats. The page is a table on wide screens and labelled cards on
phones; selection lives in `sessionStorage` (`lib/compare-store.ts`) through
`useSyncExternalStore`.

## Preferences and booking

* `user_preferences` (migration 0006): enumerated search defaults. The search form applies them
  when it starts a new search; result-page controls then change the URL as usual.
* Booking hand-off: details page → `/book/[id]` (explains provider, host, price, price type and
  age) → `GET /api/v1/journeys/{id}/book` (re-validates, `303`, `no-referrer`, counts
  provider/day in `booking_redirect_counts`). Multi-leg journeys list each leg's own booking page.

## Providers

* `providers/template/`: REST adapter skeleton (schemas, stop-code mapping, outbound guard, error
  mapping) and a contract the gate rejects on purpose. Proven with `check_conformance` on synthetic
  responses.
* `providers/synthetic_booking.py`: fictional bookable TEST provider (Tashkent ↔ Namangan,
  `booking.synthrail.test`), only with `TPORT_ENABLE_SYNTHETIC_BOOKING=true`, refused in production.

## Data model changes

| Migration | Change |
|---|---|
| 0006 | `user_preferences` (PK `user_id`, cascade), `booking_redirect_counts` (PK `provider_id, day`) |
| 0007 | `ix_departures_provider_date`; `ix_journey_searches_user_created` replaces `ix_journey_searches_user_id` |

Both are additive and reversible (`alembic downgrade 0005`).
