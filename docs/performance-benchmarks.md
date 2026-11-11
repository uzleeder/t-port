# Performance benchmarks (Phase 3)

Measured on 2026-11-11 with `python scripts/benchmark.py --iterations 30` (from `backend/`).

**What these numbers are:** in-process timings on a developer laptop (Windows 11, AMD64, 12 logical
CPUs, Python 3.13), against the synthetic demo dataset with a fixed clock, using SQLite. **What they
are not:** production latency. They exclude the network, TLS, Caddy, the Next.js server, PostgreSQL
and real provider APIs (whose latency will dominate once one exists). Re-run the script on staging
hardware before setting targets.

## Search engine (no HTTP)

Six origin/destination pairs, 30 rounds each, `page_size=50`.

| Max changes | Searches | p50 | p95 | max | Mean results |
|---|---|---|---|---|---|
| 0 (direct) | 180 | 0.88 ms | 1.11 ms | 1.44 ms | 2.5 |
| 1 | 180 | 2.29 ms | 2.58 ms | 2.80 ms | 3.2 |
| 2 | 180 | 3.45 ms | 5.14 ms | 6.12 ms | 3.5 |

Journey graph built from the demo provider's served routes: 14 locations, 42 directed edges; Tashkent →
Khiva has 3 location paths with up to two changes. The bounds in `GraphLimits` (3 legs, 40 paths, 6
onward departures per partial chain, 300 candidates) cap the work regardless of network size;
`test_search_expansion_is_bounded` checks that they hold.

## API (FastAPI TestClient, SQLite file database)

60 requests each after 3 warm-up requests, against a temporary SQLite file with the full schema. The
script asserts every response is 200 and reports the rows written (64 search-log rows and 63 assistant
metadata rows in this run), so the timings include the real writes.

| Endpoint | Writes per request | p50 | p95 | max |
|---|---|---|---|---|
| `GET /journeys/search` (Tashkent → Bukhara, max 2 changes) | 1 analytics row | 20.58 ms | 31.51 ms | 35.94 ms |
| `GET /journeys/{id}` | none | 2.72 ms | 3.14 ms | 3.62 ms |
| `GET /journeys/compare` (3 journeys) | none | 3.16 ms | 3.43 ms | 3.77 ms |
| `POST /ai/interpret` (rules engine, includes the search) | rate-limit counter, metadata row | 37.94 ms | 56.41 ms | 64.26 ms |

The gap between the read-only endpoints (~3 ms) and the writing ones is SQLite committing to disk
(a file sync per transaction on Windows). PostgreSQL with group commit behaves differently; measure
on staging. Analytics writes already run in a worker thread and never fail a search.

### Fixed during this measurement: assistant parser

An earlier run (10 requests, same machine, same conditions) measured `POST /ai/interpret` at
**63.6 ms p50** against **11.5 ms** after the fix, about 20× a search's compute. The deterministic
parser compiled one regular expression per location name and alias on every request: more than 600
patterns, which overflows Python's 512-entry `re` cache, so they were recompiled each time. It now
builds one compiled alternation per catalogue (`rules._name_index`); a single parse takes
**0.47 ms**. Behaviour is unchanged (all 54 assistant tests pass).

The benchmark script itself was also corrected during this work: its first version used an
in-memory database without the schema, so database writes failed silently and the API figures left
them out. Both figures in the paragraph above come from that version and are comparable to each
other, but not to the table, which includes the writes.

## Index review

Every query on a growing table was checked with `EXPLAIN QUERY PLAN` (SQLite; PostgreSQL plans are
checked by `alembic check` for schema parity in CI but not benchmarked here).

| Query | Before | After |
|---|---|---|
| Stored departures by route and date (search in stored mode) | `ix_departures_route_time` | unchanged |
| Import publication: delete a provider's departures in a date range | unique index on `provider_id` only, then scan of that provider's rows | **`ix_departures_provider_date (provider_id, travel_date)`** (migration 0007) |
| Dashboard: a user's 5 latest searches | `ix_journey_searches_user_id` + temporary B-tree sort | **`ix_journey_searches_user_created (user_id, created_at)`**, no sort (migration 0007) |
| Dashboard: a user's saved journeys | `ix_saved_journeys_user_created` | unchanged |
| Booking redirect totals since a day | primary key scan | unchanged: one row per provider per day |
| Session lookup, rate-limit counters, purges | unique/expiry indexes | unchanged |

## Known limits

* Provider calls dominate real latency. Each search calls each provider once per leg pair (cached
  within the search); a slow provider is bounded by its contract timeout and reported as a failed
  source rather than blocking results.
* Compare re-resolves up to 4 journeys sequentially (about 1 ms each on demo data). With a real
  provider this is up to 4 provider lookups; consider concurrent resolution if it shows in metrics.
* No load test (concurrency, PostgreSQL connection pool, two API workers) has been run. That needs
  the staging stack; the smoke test (`deploy/smoke_test.py`) checks function, not capacity.
