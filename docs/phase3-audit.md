# Phase 3 starting audit (milestone 3.1)

_Done 2026-11-11, before any Phase 3 code._

## Repository state

| Item | Finding | Consequence |
|---|---|---|
| `main` | `84f017e`: Phase 1 plus the first Phase 2 commit (merged PR #1) | Not a complete Phase 2 base |
| Phase 2 | Rest of Phase 2 on `feat/phase2-live-data-readiness` (`e48515f`), draft PR #2, unmerged | Phase 3 is **stacked on that branch**; its PR depends on PR #2 |
| Phase 2 verification (local, at `e48515f`) | backend 252 passed, Vitest 10, Playwright 12, smoke test 16/16, conformance 0 violations | Healthy base |
| Live providers | None; demo dataset only | Phase 3 cannot integrate a real provider (see provider-integration-status.md) |
| Deployment | No server provisioned; waiting on host, SSH user, domain and database choice | No staging or production verification possible in Phase 3 |

## Gaps found against the Phase 3 goals

| Area | Phase 2 state | Phase 3 work |
|---|---|---|
| Routing | One transfer, composed by trying every pair of the provider's locations | Bounded journey graph over served routes, up to 2 changes, Pareto filtering, arrival deadlines, preferred modes, "fewest changes" sort (3.2) |
| Assistant | Route, date, modes, budget (UZS), time-of-day, cheapest/fastest | Arrival deadlines, explicit clock times, transfer preferences, preferred vs required modes, mode comparison, foreign-currency budgets refused rather than converted, richer grounded explanations, AI metrics (3.3) |
| Comparison | Summary of cheapest/fastest/earliest within one result list | Side-by-side comparison of chosen journeys, plus filters for changes, arrival time and budget on the results page (3.4) |
| Providers | Contracts, feed adapter, conformance, ingestion | REST adapter template and an explicit blocker report (3.5) |
| Accounts | Saved journeys, recent searches | Saved search preferences; compare saved journeys; old-snapshot notice (3.6) |
| Booking | Link shown directly on the details page when allowed | Explained hand-off page, re-validated redirect, aggregate counting (3.6) |
| Performance | No measurements | Benchmark script, measured p50/p95, index review (3.7) |

## Defects found during the audit or Phase 3 work

| Defect | Where | Fixed in |
|---|---|---|
| Phase 1 test still asserted `max_transfers=2` is rejected | `test_transfers.py` | 3.3 commit |
| Blank optional numbers in `.env` stopped the API from starting | settings | 3.3 commit |
| Security-headers middleware overwrote stricter route `Referrer-Policy` | `main.py` | 3.6 commit |
| Assistant parser recompiled 600+ regexes per request (~60 ms) | `ai/rules.py` | 3.7 commit |
| Missing indexes for import publication and recent searches | models / migration 0007 | 3.7 commit |
