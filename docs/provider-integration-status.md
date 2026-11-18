# Provider integration status

_Last updated: 2026-11-11 (Phase 3)._

**Bottom line: T-Port has no authorized live data provider.** Every journey shown today comes from
the synthetic demo dataset and is labelled as demonstration data. No real operator data, prices or
booking links are integrated, and none will be until the blockers below are cleared. This document is
the record of what exists, what is missing, and who has to act.

## Sources in the codebase

| Source | Type | Status | Where |
|---|---|---|---|
| T-Port Demo Dataset | Synthetic generator, fictional "Demo …" operators | **Enabled** (always labelled demo, never bookable) | `backend/app/providers/demo/` |
| SynthRail | Synthetic timetable feed | **Tests only**, not registered | `backend/tests/fixtures/synthetic_rail_feed.json` |
| Example Coach Co | Synthetic REST API responses | **Tests only**, not registered | `backend/tests/fixtures/template_api/trips.json` |
| REST adapter template | Code skeleton for a query API | **Cannot be enabled**: its contract fails the gate on purpose | `backend/app/providers/template/` |
| File/timetable feed adapter | Generic adapter for provider-supplied timetables | Ready for a licensed feed; no feed received | `backend/app/providers/feed.py` |

No contact with, agreement from or data supplied by any transport operator is recorded in this
repository. Nothing in the product claims otherwise.

## Blocker report

| # | Blocker | Why it blocks | Owner | Unblocks |
|---|---|---|---|---|
| B1 | **No written agreement, licence or open-data terms** for any operator | `contract_problems` refuses real providers without a reference, basis and expiry | Partnerships (UzLeeder) | Any real source |
| B2 | **No permission to display prices** | Without it T-Port may not list the source's fares at all (`permits_price_display`) | Partnerships + legal | Showing real fares |
| B3 | **No permission or host list for booking redirects** | Booking links are dropped unless redirects are permitted and hosts are listed | Partnerships | "Book on operator's site" |
| B4 | **No technical documentation or test environment** from a provider | The template's schema, endpoints and stop codes are placeholders | Provider's technical contact | Building the adapter |
| B5 | **No named person to verify the paperwork** | Contracts need `verified_by` and `verified_on` | UzLeeder management | Enabling the contract |
| B6 | **No stop-code mapping** from a provider's identifiers to T-Port stations | Unknown codes are rejected, never guessed | Engineering, with provider data | Correct stations/cities |
| B7 | **Attribution and redistribution terms unknown** | Wording and caching limits must be encoded in the contract | Legal | Compliance |

### Candidate source categories (to approach; none contacted from this codebase)

* National rail operator: timetables and tariffs, ideally a file feed (fits `feed.py`) or an API.
* Domestic airlines and airports: schedules; fares only with explicit permission.
* Intercity bus operators and bus terminals: timetables, often published per terminal.
* Taxi and ride-hailing apps: estimate ranges only, if their terms allow it.
* Government open-data portals: check for transport datasets with a usable open licence.

## What is ready on the engineering side

* **Contract gate** (`providers/contracts.py`): authorization basis, reference, verifier, expiry,
  price/booking permissions, onboarding record, data mapping, freshness and ingestion limits.
* **Adapters**: timetable feed (`feed.py`) and the REST template (`template/`), both schema-validated,
  both proven against synthetic fixtures with `check_conformance`.
* **REST template specifics**: outbound guard (HTTPS, allow-listed host, no internal addresses, no
  redirects), 429 → rate-limited with `Retry-After`, 5xx/timeouts retryable, schema drift rejected,
  API keys only in the `Authorization` header.
* **Ingestion**: import lifecycle with leases, retries, throttling, quarantine, single-transaction
  publication; scheduler; provider health states and metrics.
* **Product**: freshness and price-type labels, source attribution on every leg, booking only with a
  fresh permitted price, comparison and journey graph working on any provider's data.

## Onboarding steps once B1–B7 are cleared

1. Record the agreement in a `ProviderContract` (copy `template/contract.py`), including expiry and
   the verifier. Keep the paperwork itself outside the repository.
2. Copy `template/` to `providers/<id>/`; replace the schema, endpoints and stop-code table from the
   provider's documentation. File-based sources use `feed.py` instead.
3. Record real (anonymised if required) responses as fixtures; make `check_conformance` pass.
4. Register the adapter factory and contract in `registry.py`, pointed at the provider's test
   environment, and run `python -m app.cli check-provider <id>` until it reports no violations.
5. Start in stored mode with a long `update_interval_minutes` and watch `/health/providers` and the
   metrics for a week in staging before pointing it at production.
6. Only then enable booking redirects, if permitted.

Estimated engineering effort after the paperwork and documentation arrive: about 3–5 days per REST
source, 1–2 days per clean timetable file, plus the staging observation period.
