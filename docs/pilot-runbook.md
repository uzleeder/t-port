# Pilot runbook

How to run a small invited T-Port pilot safely, measure it honestly and respond when something breaks.
**No metric in this document has been achieved yet.** Targets must be agreed before the pilot starts and
results reported only once measured.

## 1. Pilot preparation

### Scope
| Item | Pilot setting |
|---|---|
| Participants | invited group of about 20–50 people, subject to support capacity; no public marketing |
| Supported routes for accuracy checks | Tashkent ↔ Samarkand, Tashkent ↔ Bukhara (other routes visible but out of scope) |
| Supported providers | only providers whose contract passes `contract_problems` (today: the demo dataset) |
| Booking | redirect only, and only for providers with written permission and verified hosts (none today) |
| Payments, ticketing | not offered |

### Data-source status (keep current)
| Provider | Type | Authorization | Status | Bookable |
|---|---|---|---|---|
| `demo`: T-Port Demo Dataset | synthetic | internal | enabled, labelled "Demo data" everywhere | never |
| *(first real source)* | *pending* | *pending signed agreement* | not enabled | — |

While only demo data is enabled, the pilot validates **usability and comprehension**, not schedule or price
accuracy. Accuracy metrics start the day an authorized source is enabled.

### Deployment checklist
- [ ] Release commit has green CI: backend on PostgreSQL, migration up/down/check, provider conformance,
      frontend lint/types/unit/build, Playwright, smoke test, dependency audits, Docker builds
- [ ] Migrations reviewed with the safety procedure in [deployment.md](deployment.md)
- [ ] Deployed to **staging**; `deploy/smoke_test.py` passed there
- [ ] Fresh production backup or PITR point confirmed; restore drill done this month (section 4)
- [ ] Production deployed; `deploy/smoke_test.py https://<host> --ops-token …` passed (attach output)
- [ ] `TPORT_OPS_TOKEN` set; `/metrics` scraped; alerts below configured and test-fired once
- [ ] `scheduler` container running (or cron jobs configured)
- [ ] `TPORT_ENABLE_FAULT_SIMULATION` is off (startup refuses it in production)
- [ ] Demo banner and labels visible; no booking action on demo journeys
- [ ] Privacy and terms checklist (below) completed
- [ ] On-call person named; this runbook read

### Privacy and terms review checklist (needs legal review; not a compliance claim)
- [ ] Privacy notice lists the data stored (email, optional name, password hash, saved journeys, searches
      linked to the account, AI request metadata without text) and the retention period (180 days)
- [ ] Explains account deletion (dashboard, takes effect immediately)
- [ ] Discloses, if `TPORT_AI_ENGINE=anthropic`, that request text is sent to the AI provider
- [ ] Terms state that T-Port is a planning tool, does not sell tickets, and that schedules and prices
      come from listed sources and must be confirmed with the operator
- [ ] Attribution wording required by each enabled provider is displayed
- [ ] Cookie use described (session and CSRF cookies only; no tracking cookies)
- [ ] Counsel has reviewed both documents against Uzbekistan's personal-data law and any market entered

### Known limitations (tell participants)
Demo data only (no real schedules or fares yet); no booking or payments; no email verification or
password reset; at most one transfer per journey; travel time to and from stations is not included;
connections are never guaranteed.

## 2. Pilot testing

### What to measure, and how
| Metric | Definition | Source | Target (agree before start) |
|---|---|---|---|
| Search success rate | searches with ≥ 1 result on pilot corridors / all pilot-corridor searches | `journey_searches`, `tport_searches_total` | TBD |
| Search latency | p50 / p95 of `/api/v1/journeys/search` | `tport_http_request_duration_seconds` | TBD |
| Result usefulness | share of participants rating results useful (survey, 1–5) | survey | TBD |
| Schedule accuracy | sampled departures matching the operator's published schedule | manual spot checks, real sources only | TBD |
| Price accuracy | sampled prices within an agreed tolerance of the operator's price | manual spot checks, real sources only | TBD |
| Provider failure rate | failed / total provider calls | `tport_provider_failures_total`, `/health/providers` | TBD |
| Stale-result frequency | journeys shown with `freshness != fresh` / journeys shown | `tport_journeys_shown_total` | TBD |
| AI interpretation accuracy | sampled assistant requests interpreted as intended (manual review of a labelled test set; prompts are not stored) | test set | TBD |
| Booking redirect success | redirects reaching a working operator page | only once a provider authorizes redirects | TBD |
| User-reported issues | count and severity of reports | feedback channel | — |
| Label comprehension | participants who correctly tell demo, indicative, stale and confirmed apart | short survey | TBD |

### Smoke and scenario checks during the pilot
Run `deploy/smoke_test.py` after every deployment. On staging (where fault simulation may be enabled),
walk through `/search?origin=tashkent&destination=samarkand&simulate=outage` and `…&simulate=stale` with
new support staff so they recognise how outages and stale data look to users.

### Alerts (Prometheus examples; any scraper of the text format works)
```yaml
- alert: TPortProviderUnavailable        # repeated provider failures / expired data
  expr: tport_provider_up == 0
  for: 5m
- alert: TPortImportsLate                # missed import windows (set per contract interval)
  expr: tport_provider_import_lag_seconds > 2 * 3600
- alert: TPortImportFailing
  expr: tport_provider_import_failures_consecutive >= 3
- alert: TPortNoValidOffers              # no valid offers after an import / volume drop
  expr: tport_provider_up == 0.5 and on(provider) tport_provider_last_import_departures == 0
- alert: TPortHighErrorRate
  expr: sum(rate(tport_http_requests_total{status="5xx"}[5m])) / sum(rate(tport_http_requests_total[5m])) > 0.02
  for: 10m
- alert: TPortDatabaseDown
  expr: tport_database_up == 0
  for: 2m
- alert: TPortRateLimitSpike
  expr: sum(rate(tport_rate_limited_total[5m])) > 1
  for: 10m
```
Volume drops (departures falling below half the previous good import) show as `degraded` with a reason in
`/health/providers`. Without Prometheus, cron `python -m app.cli provider-health` and alert on exit code 1
(degraded or unknown) or 2 (unavailable).

## 3. Support and incidents
| Symptom | First checks | Action |
|---|---|---|
| `/health` returns 503 | database reachable? credentials rotated? | restore connectivity or fail over; the API serves nothing without it |
| A provider is `unavailable` | `/health/providers` reasons; `data_imports.error_message`, `diagnostics` | leave it: other sources still serve and users see "didn't respond" |
| Imports rejected (`contract violation`) | `rejected_records`, `diagnostics` | the source changed format; the old snapshot stays live until it expires; contact the provider |
| Import exits 75 repeatedly | another import running; locks older than their TTL are taken over automatically | look for a stuck job; `cancel-import <id>` stops it at its next checkpoint |
| User reports a wrong time or fare | compare with the operator's published data | if confirmed, disable the provider (contract `enabled=False` or remove it), deploy, tell users |
| Many 429 responses | client IPs forwarded correctly? (deployment.md) | fix the proxy before raising limits |
| Account locked after failed logins | per-account throttle (5 per 15 min) | wait for the window; no manual unlock needed |

Severity: **S1** service down or wrong data shown as current: respond immediately and consider pausing
the pilot. **S2** a provider down or a feature broken: same day. **S3** cosmetic or minor: next release.

## 4. Rollback and recovery

### Application rollback
1. Redeploy the previous image tag: `docker compose … up -d` with the old tag.
2. Phase 2 migrations (0002–0005) are additive, so the previous release runs on the new schema; no
   downgrade is needed to roll back the application.
3. Only if a migration itself is faulty: take a backup, then `alembic downgrade <revision>`. Read the
   table in deployment.md first, because 0003's downgrade needs every location to have coordinates.
4. Run the smoke test.

### Pulling a bad data source quickly
Set the provider's contract `enabled=False` (or let its authorization expire) and redeploy: it shows as
`disabled` and stops serving at startup, without affecting other providers.

### Restore drill (monthly, on staging)
1. Restore the latest production backup or a PITR point into a **new** database.
2. Point a staging API at it, run `alembic current`, then `deploy/smoke_test.py`.
3. Record the duration and any problems in the ops log, then delete the restored copy.

## 5. Pilot exit criteria
The pilot may move toward a wider launch only when **all** of these hold:
- [ ] No open S1/S2 bugs
- [ ] Security review findings addressed or explicitly accepted ([security-review.md](security-review.md)),
      and an external penetration test scheduled
- [ ] At least one data source authorized (signed, verified contract) for the launch corridors
- [ ] Measured schedule and price accuracy meet the targets agreed before the pilot
- [ ] Monitoring and alerts operational and test-fired
- [ ] Backups verified by a restore drill within the last month
- [ ] User-facing limitations, privacy notice and terms published and reviewed
