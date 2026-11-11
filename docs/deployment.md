# Deployment

## Recommended production shape

```
Internet ──443──> Caddy (TLS, HSTS) ──> web (Next.js) ──> api (FastAPI) ──TLS──> managed PostgreSQL
```

- **Database:** use a managed PostgreSQL 16+ service with automated backups, point-in-time recovery,
  TLS and private networking. Never publish a database port to the internet.
- **API:** not published. Only the web container can reach it, on a private network.
- **Admin surfaces:** `/docs` and `/openapi.json` are disabled when `TPORT_ENVIRONMENT=production`.

`deploy/docker-compose.prod.yml` + `deploy/Caddyfile` implement this on a single host.

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
5. Check health: `curl https://your.domain/health` should return `{"status":"ok",…}`.

Platform alternatives (container services such as Fly.io, Render or Cloud Run, plus a managed
database) work the same way: deploy the two images, keep the API private or IP-restricted, and
put TLS termination in front of the web service. Build the web image with
`--build-arg API_INTERNAL_URL=<private API address>`, because rewrites are fixed at build time.

## Client IPs and rate limiting
Caddy overwrites `X-Forwarded-For` with the real client IP. Next.js forwards it unchanged. Uvicorn
trusts it only from `FORWARDED_ALLOW_IPS` (the private network). Do not set `FORWARDED_ALLOW_IPS`
to `*` unless every path to the API goes through a proxy that overwrites the header.

## Scheduled jobs (cron or the platform scheduler)

| Schedule | Command (in the API image) |
|---|---|
| Daily | `python -m app.cli purge-sessions` |
| Daily | `python -m app.cli purge-activity` |
| Every 10 min, only with `TPORT_DEMO_PROVIDER_MODE=stored` | `python -m app.cli import-demo --days 14` |

## Logging and health
- All containers log to stdout (JSON from Caddy, plain lines from the API). Ship them to your
  platform's log store. API access logs exclude query strings, bodies and cookies.
- `GET /health` returns `200` with database status, AI engine and providers, or `503` if the
  database is unreachable. Both Dockerfiles define container health checks.
- Watch for 5xx rates, 429 spikes, `providers_unavailable`, AI `fallback` outcomes (the
  `ai_requests` table) and import failures (`data_imports.status = 'failed'`).

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
