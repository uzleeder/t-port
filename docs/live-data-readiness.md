# Live-data readiness

Status of T-Port's ability to take a real, authorized data source safely. This describes what is
**implemented and tested**; it is not a claim that any live source is connected (none is).

## What is in place

| Concern | Implementation | Evidence |
|---|---|---|
| Permission before data | `ProviderContract` + `contract_problems`: unverified, expired or price-restricted sources never start | `test_provider_contracts.py` |
| Data correctness | `validate_records` checks mapping, chronology, dates, currency, price ranges, duplicates, booking hosts | 20 violation cases tested |
| Adapter conformance | `check_conformance` through the real interface; CLI `check-provider`; runs in CI | demo and fixture feed pass |
| File-based sources | `FeedAdapter` with strict JSON schema | malformed-feed tests |
| Scalable collection | queries only `served_routes()` (42 demo routes instead of 182 city pairs) | call-count test |
| Bounded load | semaphore with per-contract `max_concurrency`; queued requests cancelled on a fatal error | peak-concurrency test |
| Transient failures | retries only `retryable` errors/timeouts, exponential backoff with jitter, honours `Retry-After`; auth, malformed data and contract violations are never retried | retry tests |
| Provider throttling | `requests_per_minute` spacing, per-request and whole-import timeouts | throttle and deadline tests |
| Import lifecycle | `pending → running → validating → publishing → succeeded`, or `failed`/`cancelled`; progress, cancellation (`cancel-import`), duration, diagnostics | lifecycle and cancellation tests |
| Malformed records | quarantined with sample diagnostics (code, record id, message; never payloads); the import is rejected above `max_rejected_ratio` | quarantine tests |
| Scheduling | `scheduler` / `import-due` run each provider on its contract interval, with backoff after failures | scheduler test |
| No overlapping runs | lease lock per provider (`provider_import_locks`); stale locks taken over after TTL | lock tests |
| No partial data | validation before write; the window is replaced in one transaction | rollback and rejection tests |
| No duplicates | window replacement + unique constraints | repeated-import test |
| Source-specific freshness | timetable and price policies per contract; `unknown` when the needed timestamp is missing | `test_freshness.py` |
| Honest labels | price type (confirmed/indicative/estimated/demo); booking links only with a fresh, permitted price; demo and real legs never combined | `test_freshness.py`, e2e |
| Outage isolation | a failing provider produces a warning; others still return results | outage tests |
| Observability | provider states healthy/degraded/unavailable/disabled/unknown; import lag, duration, counts, rejections, no-valid-offers and volume-drop detection; HTTP latency/error, rate-limit, search-quality and database metrics; JSON logs | `test_provider_health.py` |
| Audit trail | `data_imports`: trigger, status, counts, retries, rejected records, error | — |

## Known limits

- **Call statistics are per process** and reset on restart. Import history survives in the database.
  Several API processes each report their own view; Prometheus can aggregate them.
- **Imports replace the whole window** in one transaction. That is simple and safe for timetables
  covering days or weeks. A source with very large volumes or minute-level price changes would need
  incremental upserts by departure, which is not built yet.
- **`max_in_flight` and retry tuning** have only been exercised against synthetic adapters. Real
  limits come from each provider's terms and must be set in its contract.
- **Station mapping lives in code** (`data/reference.py`). A real network needs a mapping table
  and tooling to review unmapped stations.
- **No live provider yet.** Accuracy, attribution and reliability can only be verified against a
  real authorized source, in its own PR, following [providers.md](providers.md).

## Next PR (real provider)
1. Signed authorization covering display, caching, attribution and price display.
2. Adapter (feed or API) plus recorded fixtures from the real source.
3. Contract with real freshness and concurrency limits.
4. A week on staging with scheduled imports, then a manual accuracy comparison on the pilot corridors
   (Tashkent–Samarkand, Tashkent–Bukhara).

## Request counts and memory
Per import: `days × routes` departure requests plus `ceil(departures / offer_batch_size)` offer requests.
The demo source over 14 days makes 14 × 42 = 588 departure requests and 7 offer batches (1,388
departures), instead of 14 × 182 = 2,548 with the old all-pairs scan. Concurrency is capped by
`max_concurrency`, the request rate by `requests_per_minute`, and wall time by `import_timeout_seconds`.
Memory holds one import window at a time (about 1 KB per departure with its fares, so roughly 1.5 MB for
the demo window). Publication is a single transaction per provider window.
