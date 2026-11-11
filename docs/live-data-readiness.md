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
| Transient failures | retries only `retryable` errors/timeouts, exponential backoff, honours `Retry-After` | retry tests |
| No overlapping runs | lease lock per provider (`provider_import_locks`); stale locks taken over after TTL | lock tests |
| No partial data | validation before write; the window is replaced in one transaction | rollback and rejection tests |
| No duplicates | window replacement + unique constraints | repeated-import test |
| Source-specific freshness | each contract sets `stale_after`/`expire_after`; search applies them per record | freshness tests |
| Outage isolation | a failing provider produces a warning; others still return results | outage tests |
| Observability | per-provider call stats, import lag, failure streaks; `/health/providers`, `/metrics` (token), CLI `provider-health` with exit codes | health tests |
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
