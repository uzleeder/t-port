# Deployment

## Recommended production shape

```
Internet ──443──> Caddy (TLS, HSTS) ──> web (Next.js) ──> api (FastAPI) ──TLS──> managed PostgreSQL
```

- **Database:** use a managed PostgreSQL 16+ service with automated backups, point-in-time recovery,
  TLS and private networking. Never publish a database port to the internet.
- **API:** not published. Only the web container can reach it, on a private network.
- **Admin surfaces:** `/docs` and `/openapi.json` are disabled when `TPORT_ENVIRONMENT=production`.

`deploy/docker-compose.prod.yml` + `deploy/Caddyfile` implement this on a single host: `caddy`, `web`,
`api` and a `scheduler` container (provider imports and housekeeping) built from the API image.

## Steps (single host with Docker)

1. Point your domain's DNS at the host and replace `tport.example` in `deploy/Caddyfile`.
2. Create `.env.production` from `.env.example` and set at least:
   - `TPORT_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require`
   - `TPORT_CORS_ORIGINS=["https://your.domain"]`
   - optional: `TPORT_AI_ENGINE=anthropic`, `TPORT_AI_API_KEY=…`
   Keep this file out of git and readable only by the deploy user (or use your platform's secret store).
3. Start the stack:
   ```bash
   docker compose -f deploy/docker-compose.prod.yml --env-file .env.production up -d --build
   ```
   The API container runs `alembic upgrade head` and the reference-data seed before serving. With
   several API replicas, run migrations once as a release step and set `TPORT_SKIP_MIGRATIONS=1`.
4. Caddy obtains and renews HTTPS certificates automatically. Ports 80 and 443 must be reachable.
5. Verify the deployment (this is the evidence a deployment worked; nothing else counts):
   ```bash
   python deploy/smoke_test.py https://your.domain --ops-token "$TPORT_OPS_TOKEN"
   ```
   It checks the frontend, API proxy, database, search, journey detail, demo labels, registration,
   saving, sign-out/sign-in, the assistant (or its fallback) and the ops endpoints, creating and then
   deleting one throwaway account. Exit code 0 means every check passed.

Platform alternatives (container services such as Fly.io, Render or Cloud Run, plus a managed
database) work the same way: deploy the two images, keep the API private or IP-restricted, and
put TLS termination in front of the web service. Build the web image with
`--build-arg API_INTERNAL_URL=<private API address>`, because rewrites are fixed at build time.

## Client IPs and rate limiting
Caddy overwrites `X-Forwarded-For` with the real client IP. Next.js forwards it unchanged. Uvicorn
trusts it only from `FORWARDED_ALLOW_IPS` (the private network). Do not set `FORWARDED_ALLOW_IPS`
to `*` unless every path to the API goes through a proxy that overwrites the header.

## Scheduled jobs
The `scheduler` container runs `python -m app.cli scheduler`: every minute it imports each stored-mode
provider whose contract interval has passed (failed providers wait a full interval before retrying),
and once a day it purges expired sessions, rate-limit counters and activity older than the retention
period. With several hosts, overlapping schedulers are safe because each import takes the provider's
lease lock.

Without the scheduler container, use cron or the platform scheduler instead:

| Schedule | Command (in the API image) |
|---|---|
| Every minute | `python -m app.cli import-due` |
| Daily | `python -m app.cli purge-sessions` and `python -m app.cli purge-activity` |
| Every 5 min | `python -m app.cli provider-health` (alert on a non-zero exit) |

Manual operations: `import-provider <id>` (one-off import), `cancel-import <id>` (stops a running import
at its next checkpoint, about every 5% of requests), `check-provider <id>` (contract conformance).
Import exit codes: `0` success, `1` failed (recorded in `data_imports`), `2` provider not enabled,
`75` another import holds the lock (skip this run; not an error).

## Staging
Staging uses the same images and compose file under a different project name, with its own `.env.staging`
(own database, ops token and `TPORT_CORS_ORIGINS`), its own subnet, and `deploy/Caddyfile.staging`
(team-only basic auth, `noindex`; `/health` stays open for uptime checks):

```bash
TPORT_ENV_FILE=../.env.staging CADDYFILE=./Caddyfile.staging TPORT_SUBNET=172.31.0.0/24 \
  docker compose -p tport-staging -f deploy/docker-compose.prod.yml --env-file .env.staging up -d --build
```

```bash
python deploy/smoke_test.py https://staging.your.domain --basic-auth team:PASSWORD --ops-token "$STAGING_OPS_TOKEN"
```

Never point staging at the production database. Deploy every merge to `main` to staging first; provider
trials and restore drills happen there. Secrets live in the host's env files (mode 600, owned by the deploy
user) or a secret manager, never in the repository or images.

## Database migrations: safety procedure
Before any migration reaches production:
1. **Review** the migration file. List every destructive operation (dropped column or table, type
   narrowing, new NOT NULL without a default, constraint that existing rows might violate).
2. **Back up**: confirm a fresh automated backup or PITR point exists (see below).
3. **Rehearse** on staging (or a restored copy): `alembic upgrade head`, run the smoke test, then
   `alembic downgrade -1` and `alembic upgrade head` again.
4. **Document rollback**: what the downgrade does and whether data is lost.
5. Apply in production. Destructive migrations need explicit approval and a maintenance window.

| Revision | Change | Destructive? | Downgrade |
|---|---|---|---|
| 0002 | `provider_import_locks`; `data_imports.trigger/retries/rejected_records` | No | drops them (audit detail only) |
| 0003 | `locations.latitude/longitude` nullable | No | fails if a location has no coordinates; remove those rows first |
| 0004 | import lifecycle columns; wider status check | No | maps new statuses to `failed`, drops the columns |
| 0005 | `rate_limit_counters` | No | drops the table (counters are transient) |

Use separate database roles in production: a **migration role** that owns the schema (used only by the
release step) and a **runtime role** with `SELECT/INSERT/UPDATE/DELETE` on the tables, so the running API
cannot alter the schema.

## Logging, health and metrics
- All containers log to stdout. Set `TPORT_LOG_FORMAT=json` for one JSON object per line from the API
  and scheduler. Access logs record method, path, status and duration: no query strings, bodies,
  cookies, tokens or authorization headers.
- `GET /health` returns `200` with database status, AI engine and providers, or `503` if the
  database is unreachable. Both Dockerfiles define container health checks.
- With `TPORT_OPS_TOKEN` set (≥ 32 characters in production):
  - `GET /health/providers` returns each provider's status (`healthy`, `degraded`, `unavailable`,
    `disabled`, `unknown`), with reasons, import lag, last import duration, counts, rejected records,
    failure streaks and call counts (`503` if any enabled provider is unavailable)
  - `GET /metrics` serves Prometheus text: HTTP requests and latency by route template, rate-limited
    requests, searches and the freshness/price type of results shown, expired results hidden, provider
    failures, `tport_database_up`, and per-provider health and import gauges
  Both need `Authorization: Bearer <token>` and return 404 without it. Scrape them over the private
  network or through the proxy. Example alert rules are in [pilot-runbook.md](pilot-runbook.md).
- Watch for 5xx rates, 429 spikes, `providers_unavailable`, AI `fallback` outcomes (the
  `ai_requests` table) and import failures (`data_imports.status = 'failed'`, `rejected_records`).

## Backup and restore
With a managed database, enable automated daily backups plus point-in-time recovery (7–30 days),
and **test a restore** into a separate instance at least once a quarter.

Logical backups as an extra safety net:

```bash
pg_dump --format=custom --no-owner --dbname "$TPORT_DATABASE_URL_PSQL" --file "tport-$(date +%F).dump"
```

```bash
pg_restore --clean --if-exists --no-owner --dbname "$RESTORE_TARGET_URL" tport-YYYY-MM-DD.dump
```

(`TPORT_DATABASE_URL_PSQL` is the URL without the `+psycopg` driver suffix.) Store dumps encrypted,
in a different account or region, with a retention matching your privacy policy. After restoring,
run `alembic current` to confirm the schema revision, then `alembic upgrade head` if needed.

Local Docker volume (development only):

```bash
docker compose exec db pg_dump -U tport -Fc tport > local.dump
```

## Pre-launch checklist
- [ ] Real domain, HTTPS working, HSTS header present
- [ ] `TPORT_ENVIRONMENT=production` (startup safety checks pass)
- [ ] Managed PostgreSQL with backups, PITR and a tested restore
- [ ] Secrets in a secret store, not in images or git
- [ ] Scheduled jobs configured
- [ ] Privacy notice and terms reviewed; AI data flow disclosed if the LLM engine is on
- [ ] Demo-data banners still visible (no live provider agreements exist yet)
- [ ] CI green, including the PostgreSQL test run and the Docker build job
