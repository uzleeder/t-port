# T-Port

**One Destination. Every Way to Get There.**
AI-assisted multimodal journey planning for Uzbekistan: compare trains, buses, flights and taxis in one place.

> **Phase 1 status: pilot MVP with demonstration data.** Every schedule, fare and operator in this
> build is simulated and labelled as such. T-Port is a planning tool. It does not sell tickets, and it
> has no agreements with transport operators yet (see [docs/providers.md](docs/providers.md)).

## What works

| Area | Implemented |
|---|---|
| Search | City autocomplete (English/Uzbek/Russian spellings), date, mode filters, sort by recommended / price / duration / departure, pagination |
| Results | Price and duration comparison, cheapest/fastest/earliest highlights, data source and freshness for every result, clear empty and error states |
| Journeys | Detail pages with legs, fares, timestamps, provenance. One-transfer journeys with checked connection times |
| Accounts | Register, sign in, sign out, dashboard, saved journeys, recent searches, account deletion |
| AI assistant | Plain-language requests → validated search parameters → real results. Deterministic parser by default; optional LLM with fallback |
| Booking | Redirects only to provider-allowed HTTPS hosts. None are configured (demo data is never bookable) |

## Repository layout

```
backend/            FastAPI API (Python 3.12+), SQLAlchemy 2, Alembic, pytest
  app/api/          HTTP layer (routes, schemas, dependencies)
  app/services/     search, transfers, freshness, auth, imports (business logic)
  app/providers/    adapter interface, demo provider, stored-snapshot provider, registry
  app/ai/           intent schema, deterministic parser, LLM adapter, assistant
  app/db/           ORM models, repositories, sessions
  migrations/       Alembic migrations
frontend/           Next.js 16 (App Router), TypeScript, Tailwind CSS 4, Vitest, Playwright
deploy/             Production compose example + Caddy (HTTPS)
docs/               Architecture, API, security, data sources, deployment
docker-compose.yml  Local development stack
```

## Run locally

Prerequisites: Python 3.12+, Node.js 22+, and PostgreSQL 16+ (or Docker).

```bash
cp .env.example .env
```

```bash
docker compose up -d db
```

Backend (from `backend/`):

```bash
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --reload --port 8000
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev
```

Open http://localhost:2028. API docs (non-production only): http://localhost:8000/docs.

Without Docker you can point `TPORT_DATABASE_URL` at a SQLite file for a quick local run
(`sqlite:///./.local/dev.db`). PostgreSQL is the supported database for anything beyond that.

Full stack in containers: `docker compose up --build`, then open http://localhost:2028.

## Tests

| Command (directory) | What it covers |
|---|---|
| `pytest` (backend) | Search filtering/sorting, date and location validation, empty results, freshness, transfer chronology and feasibility, auth, authorization, saved journeys, AI output validation and fallback, migrations, provider failures, privacy |
| `TPORT_TEST_DATABASE_URL=postgresql+psycopg://… pytest` | Same suite against PostgreSQL (CI does this) |
| `npm test` (frontend) | Formatting, URL/query handling, redirect safety |
| `npx playwright test` (frontend) | Primary user journey, assistant, error states (desktop + mobile). Needs API on :8000 and web on :2028 |
| `npm run lint && npm run typecheck` | ESLint and TypeScript |

## Operations

```bash
python -m app.cli import-demo --days 14   # snapshot demo data into the DB (TPORT_DEMO_PROVIDER_MODE=stored)
```

```bash
python -m app.cli scheduler               # due provider imports + daily housekeeping (long-running)
```

```bash
python -m app.cli import-provider demo    # one-off import; also: import-due, cancel-import <id>
```

```bash
python -m app.cli check-provider demo     # provider contract conformance (exit 1 on violations)
```

```bash
python deploy/smoke_test.py https://your.domain --ops-token TOKEN   # post-deployment verification
```

```bash
python -m app.cli provider-health         # per-provider status; exit 0 ok, 1 degraded, 2 down
```

```bash
python -m app.cli purge-sessions          # remove expired/revoked sessions (run daily)
```

```bash
python -m app.cli purge-activity          # apply the activity retention period (run daily)
```

See [docs/deployment.md](docs/deployment.md) for HTTPS, managed PostgreSQL, logging, health checks and backups.

## Documentation

- [Architecture](docs/architecture.md): modules, data flow, routing engine, AI boundaries
- [API](docs/api.md): endpoints, errors, pagination, rate limits
- [Data sources](docs/providers.md): provider contracts, adapters and the checklist for adding real data
- [Live-data readiness](docs/live-data-readiness.md): what the ingestion pipeline guarantees today
- [Pilot runbook](docs/pilot-runbook.md): staging, go-live checklist, alerts, incidents, rollback
- [Security review](docs/security-review.md) and [Phase 2 audit](docs/phase2-audit.md)
- [Security](docs/security.md): sessions, CSRF, data handling, known limitations
- [Deployment](docs/deployment.md): production setup, HTTPS, backup and restore
