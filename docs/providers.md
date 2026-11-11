# Data sources and provider adapters

## Current sources

| Provider | Type | Authorization | Bookable | Enabled |
|---|---|---|---|---|
| `demo`: T-Port Demo Dataset | Simulated timetable (`backend/app/providers/demo/dataset.py`) | `internal_synthetic` | No | Yes |

**There are no live integrations.** T-Port has no confirmed API access, data licences or booking
agreements with any transport operator, aggregator or ticketing platform. All operator names in the
demo data ("Demo Rail Express", "Demo Air", …) are fictional. The `synthrail` provider used in tests
(`backend/tests/fixtures/synthetic_rail_feed.json`) is also fictional and is never registered.

Integration status, blockers and owners: [provider-integration-status.md](provider-integration-status.md).
For a query-API provider, start from the REST adapter template in `backend/app/providers/template/`.

## How a source is described: `ProviderContract`

Every provider is declared in `backend/app/providers/registry.py` as a `ProviderContract`
(`backend/app/providers/contracts.py`):

| Part | What it records |
|---|---|
| `info` | id, display name, `is_demo`, attribution, allowed booking hosts |
| `authorization` | basis (`licence`, `written_agreement`, `open_data_terms`, or `internal_synthetic` for demo), reference, required attribution, whether prices may be shown, whether booking redirects are allowed, who verified it and when, expiry |
| `capabilities` | modes, live prices vs published tariffs, seat availability, on-demand services |
| `ingestion` | `live` (queried per search) or `stored` (imported snapshots), max concurrency, retry attempts and backoff, offer batch size, lock TTL, expected update interval |
| `stale_after` / `expire_after` | freshness policy for **this** source |
| `currency`, `timezone`, `data_mapping` | how the source's stations, times and money map to T-Port |

### Enablement rules (`contract_problems`)
A provider starts only if its contract has no problems. For non-demo sources this means:
- a real basis (not `internal_synthetic`), a reference, and a **named person who verified it, with a date**
- not expired
- permission to display prices (T-Port has no use for a source whose fares can't be shown)
- a documented data mapping
- booking hosts listed **if and only if** redirects are permitted

Demo providers must use `internal_synthetic` and can never be bookable. An invalid contract is logged
at startup and the provider stays disabled; the rest of the app keeps working.

## Adapter interface (`backend/app/providers/base.py`)

| Capability | Method / field |
|---|---|
| Location lookup | `supported_location_ids()`, plus optional `served_routes()` so imports query only real routes |
| Schedule retrieval | `get_departures(origin, destination, date, modes)`, `get_departure(id)` |
| Offer retrieval | `get_offers(departure_ids)`: missing fares are simply absent, never invented |
| Source timestamps | every `Departure`/`Offer` carries `retrieved_at` and `source_updated_at` |
| Errors | raise `ProviderError(retryable=…)` or `ProviderRateLimited(retry_after_seconds=…)` |
| Rate limits | `rate_limit: RateLimitPolicy` (timeout); import concurrency comes from the contract |

Ready-made adapters:
- `DemoAdapter`: the synthetic dataset.
- `FeedAdapter` (`providers/feed.py`): serves a provider-supplied **JSON timetable feed** with a
  strict schema (unknown fields, bad times, unmapped stations, duplicate codes or naive timestamps
  reject the whole feed). This is the expected path for operators that deliver files.
- `StoredTimetableAdapter`: serves the last imported snapshot from PostgreSQL.

## Conformance checks

`validate_records()` enforces, for every record: correct provider id, known and mapped stations,
declared modes, arrival after departure, duration consistent with times, departure on the requested
local date, timezone-aware timestamps not in the future, positive prices in the contract currency,
price ranges flagged as estimates, no duplicate departures or fares, offers referring to returned
departures, and booking URLs only on permitted HTTPS hosts.

- The **importer** runs it before writing: any violation rejects the whole import (the previous
  snapshot stays live) and the count is stored in `data_imports.rejected_records`.
- `check_conformance()` exercises an adapter through the real interface, including round-tripping
  `get_departure()`. Run it with `python -m app.cli check-provider demo`; CI runs it on every push.

## Provider record (required before enabling a real source)

Every item below must be filled in the provider's `Onboarding` record (`contract.onboarding`) or the
named contract field. `contract_problems` refuses to start a real provider with any of them missing.

| # | Item | Where it is recorded |
|---|---|---|
| 1 | Official provider identity | `onboarding.official_identity` |
| 2 | Data access method (`rest_api`, `gtfs_static`, `gtfs_realtime`, `licensed_file`, `provider_export`) | `onboarding.access_method` |
| 3 | Authorization or licence basis | `authorization.basis`, `.reference`, `.verified_by`, `.verified_on`, `.expires_on` |
| 4 | Allowed data usage | `onboarding.allowed_usage` |
| 5 | Redistribution restrictions | `onboarding.redistribution_restrictions` |
| 6 | Commercial-use restrictions | `onboarding.commercial_use_restrictions` |
| 7 | Rate limits | `onboarding.rate_limit_terms` + enforced `ingestion.requests_per_minute`, `max_concurrency` |
| 8 | Attribution requirements | `authorization.attribution` (shown with every leg) |
| 9 | Data refresh expectations | `onboarding.refresh_expectations` + `ingestion.update_interval_minutes`, freshness policies |
| 10 | Booking redirect permissions | `authorization.permits_booking_redirects`, `info.booking_hosts`, `capabilities.operations` |
| 11 | Contact and escalation procedure | `onboarding.contact_escalation` (role-based, not personal numbers) |
| 12 | Technical documentation reference | `onboarding.technical_docs` |
| 13 | Supported locations | adapter `supported_location_ids()` / `served_routes()` |
| 14 | Supported transport modes | `capabilities.modes` |
| 15 | Test environment availability | `onboarding.test_environment` |

Also required: `capabilities.live_prices` (only live prices can show as "confirmed"), separate
`price_stale_after`/`price_expire_after` when prices age faster than timetables, `freshness_basis`, and
`max_rejected_ratio` (share of invalid records that may be quarantined before an import is rejected).
Set `enabled=False` to switch a provider off without touching its paperwork.

**Source types.** File-based sources (licensed timetables, provider exports, GTFS static converted to the
feed format) use `FeedAdapter`. API sources (REST, GTFS-Realtime) need a new adapter class that makes
every request through `core.outbound.guarded_client(contract hosts)`. That client allows HTTPS only, to the
contract's hosts only, never internal addresses, and follows no redirects.

No unverified provider may be described as "integrated" anywhere: in the product, docs or sales material.

## Onboarding a real provider

1. **Paperwork first.** Obtain written permission (licence, agreement or open-data terms) covering
   display, caching duration, attribution wording, price display and, separately, booking redirects
   with exact hosts. Never scrape, bypass logins, or ignore rate limits or robots rules.
2. **Record it** in a `ProviderContract`, with `verified_by`/`verified_on` set by the person who
   checked the documents, and an `expires_on` if the agreement has one.
3. **Map the data**: station IDs to the T-Port catalog (extend `data/reference.py`, migrating to the
   `stations` table as coverage grows), time zone, currency. Describe it in `data_mapping`.
4. **Pick the delivery mode**: `FeedAdapter` for files, or a new adapter class for an API. Return
   `served_routes()` if the source can list them.
5. **Set freshness** from the source's real update frequency: published timetables can tolerate hours;
   live prices need minutes.
6. **Test with recorded fixtures**: conformance, malformed input, timeouts, rate limits and outages
   (see `tests/test_provider_contracts.py` and `tests/test_import_recovery.py` for patterns).
7. **Stage it**: enable on staging only, run imports on schedule for at least a week, and compare a
   sample of schedules and fares against the operator's own published information.
8. **Launch** behind the pilot checklist in [pilot-runbook.md](pilot-runbook.md).

Real-time availability and live prices must only be shown when such a source provides them.
