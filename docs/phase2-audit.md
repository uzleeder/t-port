# Phase 2 technical audit

- **Repository:** uzleeder/t-port
- **Baseline:** `main` @ `fd757cb7c4bdea1ff4a5085d3adfd8c30d14e51a`
- **Working branch:** `feat/phase2-live-data-readiness` (first commit `93f3886`)
- **Date:** 2026-11-11

## Baseline (main)
- Modular monolith: Next.js 16 web (App Router, server-side API proxy) → FastAPI API → PostgreSQL.
- Features: alias-aware location search, deterministic direct + one-transfer search and ranking, journey
  detail, demo provider (live or stored snapshot), auth with Argon2id + hashed sessions + CSRF, saved
  journeys, dashboard, account deletion, AI interpreter (rules + optional LLM with fallback).
- Tests on main (CI run 43016641424): backend **116 passed on PostgreSQL**, frontend unit 9, Playwright 6,
  Docker builds OK, pip-audit and npm audit clean.

## Findings against the Phase 2 specification

| # | Area | Finding on main | Severity | Resolution on this branch |
|---|---|---|---|---|
| 1 | Providers | No capability or permission model: any adapter could be enabled | High | `ProviderContract` + `contract_problems` gate startup |
| 2 | Ingestion | `_collect` queries every ordered location pair per day (O(N²)) | High | route enumeration via `served_routes()` |
| 3 | Ingestion | No retries, throttling, concurrency bound, locking or validation | High | bounded, throttled, retrying, locked, validated imports |
| 4 | Ingestion | Lifecycle only `running/succeeded/failed`; no progress or cancellation | Medium | full lifecycle, progress, cancellation, timeout |
| 5 | Validation | One bad record would be written as-is | High | quarantine invalid records; reject imports above the threshold |
| 6 | Freshness | One global policy; no separation of timetable and price age; no UNKNOWN | Medium | per-provider, per-data-type policies, UNKNOWN status |
| 7 | Search | A connection could combine a demo leg with a real leg | Medium | mixed demo/real connections are not composed |
| 8 | UI | Price certainty and booking eligibility not shown; no retry on provider failure | Medium | price type, source, updated time, booking eligibility, retry |
| 9 | Observability | Only `/health`; no provider status, API metrics or structured logs | Medium | provider health, `/metrics`, JSON logs |
| 10 | Security | Rate limits in-memory per worker, but the image runs 2 workers | High | shared database-backed limits for auth and AI |
| 11 | Security | No per-account protection against password guessing from many IPs | High | failed-login throttling per account |
| 12 | Security | uvicorn access log duplicates requests including query strings | Low | access log disabled; app log keeps path only |
| 13 | Ops | No staging definition, scheduler, smoke test or migration-safety procedure | Medium | staging compose/Caddy, scheduler service, smoke test, docs |

## Migration risks
All Phase 2 migrations are additive (new tables, nullable columns or columns with server defaults, a widened
check constraint), so the previous release keeps running on the new schema. The downgrade drops only Phase 2
audit and lock tables and columns. Each is tested up/down/up plus `alembic check`, on SQLite locally and on
PostgreSQL in CI.

## External dependencies (not solvable in code)
- A signed authorization from a transport data source covering Tashkent–Samarkand or Tashkent–Bukhara.
- A server or hosting account, domain and managed PostgreSQL for staging and the pilot.
- Legal review of the privacy notice and terms.
- An email provider (needed for account recovery and email verification).
