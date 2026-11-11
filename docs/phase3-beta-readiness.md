# Phase 3 public beta readiness

_Assessed 2026-11-11 on `feat/phase3-journey-intelligence`._

## Verdict

**Not ready for a public beta.** The product works end to end on demonstration data, and the
engineering for real data, booking hand-offs and operations is in place, but three things outside
the code block a public launch:

1. **No authorized live data.** Every journey is demo data (or the dev-only TEST provider). A public
   beta would show only simulated travel information. See
   [provider-integration-status.md](provider-integration-status.md) (blockers B1–B7).
2. **Not deployed.** No staging or production server exists yet; the stack, smoke test and runbook
   are ready but unverified on real infrastructure.
3. **Launch prerequisites still open:** no privacy notice or terms pages, no email verification or
   password reset, no external penetration test.

A **closed demo beta** (invited testers, clearly labelled demo data) becomes possible as soon as a
server is provisioned and the staging checklist in [pilot-runbook.md](pilot-runbook.md) passes.

## Checklist

| Area | Item | Status | Evidence / owner |
|---|---|---|---|
| Product | Search, filters, sorts incl. fewest changes | Done | `test_search.py`, `test_route_optimizer.py`, e2e |
| Product | Journeys with up to 2 changes, overnight legs, local dates | Done | `test_journey_graph.py` |
| Product | Assistant: deadlines, changes, preferred modes, comparison, grounded text | Done | `test_ai_journey_planner.py`, e2e |
| Product | Side-by-side comparison, desktop and phone | Done | `test_comparison.py`, e2e on both viewports |
| Product | Saved preferences, saved-journey comparison, old-snapshot notice | Done | `test_preferences_booking.py`, e2e |
| Product | Booking hand-off (explained, re-validated, aggregate counts) | Done, exercised only with the TEST provider | `test_preferences_booking.py`, e2e |
| Data | Authorized live provider | **Blocked** (B1–B7) | Partnerships / legal |
| Data | REST adapter template, conformance on synthetic data | Done | `test_provider_template.py` |
| Quality | Backend tests, lint, migrations up/check/down | Done locally | see PR test results |
| Quality | Frontend unit tests, typecheck, lint, production build | Done locally | see PR test results |
| Quality | E2E desktop + mobile (8 scenarios) | Done locally | `frontend/e2e/` |
| Quality | Accessibility audit (axe or manual screen-reader pass) | Not done | Engineering |
| Performance | In-process benchmarks, index review | Done | [performance-benchmarks.md](performance-benchmarks.md) |
| Performance | Load test on staging hardware with PostgreSQL | Not done (needs a server) | Engineering |
| Security | Internal review of Phase 3 changes | Done | [security-review.md](security-review.md) |
| Security | External penetration test | Not done | UzLeeder |
| Security | Email verification, password reset | Not done (no email provider chosen) | Product |
| Security | Nonce-based CSP, least-privilege DB role | Not done | Engineering |
| Operations | Health, provider health, metrics, JSON logs, scheduler | Done | Phase 2 |
| Operations | Staging/production deployment | **Blocked** (server IP, SSH user, domain, database choice) | UzLeeder |
| Operations | Alert routing to a person on call | Not done (needs deployment) | Operations |
| Legal | Privacy notice, terms of use, cookie statement | Not done | Legal |
| Legal | Data-source attribution and redistribution terms | Blocked on agreements | Legal |

## Before a closed demo beta

1. Provision the server; deploy with `deploy/docker-compose.prod.yml`; run `deploy/smoke_test.py`.
2. Run the staging checklist in the pilot runbook; set `TPORT_OPS_TOKEN`; keep fault simulation and
   the TEST provider **off**.
3. Add privacy and terms pages; keep the demo notices on every results page.
4. Re-run `scripts/benchmark.py` and a short load test on the server.

## Before a public beta

Everything above, plus at least one authorized provider live in stored mode for a week in staging,
email verification and password reset, the external penetration test, and the legal pages reviewed.
