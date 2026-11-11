# Pilot runbook

How to run a small, invited T-Port pilot safely, and what to do when something breaks. Targets for
the metrics below are **not set or claimed**: measure first, then agree on thresholds.

## Scope
- **Users:** invited testers only (no public marketing), with a feedback channel.
- **Corridors:** Tashkent–Samarkand and Tashkent–Bukhara first; other routes stay visible but are not
  part of the pilot's accuracy checks.
- **Data:** demo data until an authorized source is enabled. Demo labels stay on every page either
  way, and demo data is never bookable.

## Environments
| | Staging | Production |
|---|---|---|
| Purpose | every merge to `main`; provider trials; restore drills | invited pilot users |
| Database | separate managed PostgreSQL (or an isolated instance) | managed PostgreSQL with PITR |
| Data | demo + candidate providers | demo + approved providers only |
| Access | team only (basic auth or IP allow-list at the proxy) | invited users |
| Ops token | its own `TPORT_OPS_TOKEN` | a different token |

Staging uses the same images and `deploy/docker-compose.prod.yml`, with a different domain and
`.env.staging`. Never point staging at the production database.

## Go-live checklist
- [ ] CI green on the release commit (backend on PostgreSQL, frontend, e2e, Docker build, conformance)
- [ ] Release deployed to staging; smoke test passed (below)
- [ ] `alembic upgrade head` applied to production. Migrations are additive, so the previous release
      still runs against the new schema
- [ ] Backups: automated + PITR enabled, and a **restore drill completed this month** (below)
- [ ] `TPORT_OPS_TOKEN` set; `/metrics` scraped; alerts configured (below)
- [ ] Scheduled jobs configured (see deployment.md), including `provider-health` every 5 minutes
- [ ] Privacy notice and terms reviewed by counsel and linked in the footer
- [ ] Demo banners visible; no booking buttons on demo journeys
- [ ] Rollback plan below read by whoever is on call

## Smoke test (staging, then production)
1. `curl -fsS https://<host>/health` → `"status":"ok"`.
2. `curl -fsS -H "Authorization: Bearer $TPORT_OPS_TOKEN" https://<host>/health/providers` → each
   provider `healthy` (or `unknown` right after a live-mode start).
3. Search Tashkent → Samarkand for tomorrow: results, sources section and demo labels shown.
4. Open a journey and register a test account; save, view the dashboard, delete the account.
5. Ask the assistant "cheapest way from Tashkent to Bukhara tomorrow".

## Alerts (Prometheus examples)
```yaml
- alert: TPortProviderDown
  expr: tport_provider_up == 0
  for: 5m
- alert: TPortProviderDegraded
  expr: tport_provider_up == 0.5
  for: 30m
- alert: TPortImportsLate
  expr: tport_provider_import_lag_seconds > 2 * 3600   # adjust to each contract's update interval
- alert: TPortImportFailures
  expr: tport_provider_import_failures_consecutive >= 3
```
Without Prometheus: run `python -m app.cli provider-health` from cron and alert on a non-zero exit
(1 degraded/unknown, 2 down).

## Incidents
| Symptom | First checks | Action |
|---|---|---|
| `/health` returns 503 | database reachable? credentials rotated? | fail over / restore DB; API serves nothing without it |
| A provider is `down` | `/health/providers` reasons; `data_imports.error_message` | if the source is broken, leave it: results show without it and users see "temporarily unavailable" |
| Imports keep failing with `contract violation` | `rejected_records`, sample violations in `error_message` | the source changed format: the old snapshot stays live until it expires; contact the provider |
| Import exits 75 every run | a lock older than its TTL is taken over automatically; a fresh lock means another import is running | check for a stuck job; do not delete the lock while it is running |
| Wrong fares or times reported by a user | compare with the operator's published data | disable the provider (remove from registry or expire its contract), deploy, tell users |
| Many 429 responses | client IPs correctly forwarded? (deployment.md) | fix the proxy before raising limits |

## Rollback
1. Redeploy the previous image tag (`docker compose ... up -d` with the old tag). Phase 2 migrations
   only add a table and columns with defaults, so the previous release runs on the new schema.
2. Only if a migration itself is faulty: `alembic downgrade -1` **after** taking a backup. The
   downgrade drops `provider_import_locks` and the new `data_imports` columns (audit details only).
3. To pull a bad data source quickly, set the provider's contract to expired (or remove it from
   `CONTRACTS`) and redeploy: it stops serving at startup.

## Restore drill (monthly)
1. Restore the latest production backup (or a PITR point) into a **new** database.
2. Point a staging API at it, run `alembic current`, and complete the smoke test.
3. Record how long it took and any problems in the ops log, then delete the restored copy.

## What to measure during the pilot
Search success rate (searches with ≥1 result on pilot corridors), response latency (p50/p95),
schedule accuracy against manual spot checks, stale-result frequency (`warnings` containing
"out of date"), and whether users understand the demo and source labels (short survey). Report
measured values only.
