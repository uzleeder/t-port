# Data sources and provider adapters

## Current sources

| Provider | Type | Access basis | Bookable |
|---|---|---|---|
| `demo`: T-Port Demo Dataset | Simulated timetable (`backend/app/providers/demo/dataset.py`) | Created by T-Port; no external source | No |

**There are no live integrations.** T-Port has no confirmed API access, data licences or booking
agreements with any transport operator, aggregator or ticketing platform. All operator names in the
demo data ("Demo Rail Express", "Demo Air", …) are fictional. City names, regions, coordinates and
airport IATA codes are public geographic facts. Station entries are generic anchor points, not a
verified registry.

## Adapter contract (`backend/app/providers/base.py`)

| Capability | Method / field |
|---|---|
| Identification | `info: ProviderInfo` (id, name, `is_demo`, attribution, website) |
| Location lookup | `supported_location_ids()` |
| Schedule retrieval | `get_departures(origin, destination, date, modes)`, `get_departure(id)` |
| Offer retrieval | `get_offers(departure_ids)`: missing fares are simply absent, never invented |
| Source timestamps | every `Departure`/`Offer` carries `retrieved_at` and `source_updated_at` |
| Booking URL validation | `validate_booking_url()`: HTTPS only, explicit host allow-list, no credentials or odd ports |
| Error handling | raise `ProviderError` / `ProviderRateLimited`; the search isolates failures per provider |
| Rate limits | `rate_limit: RateLimitPolicy` (requests/minute, timeout) |
| Data freshness | evaluated centrally from `retrieved_at` (stale after 15 min, expired after 6 h by default) |

Two delivery modes exist:
- **Live adapter**: queried per search (the demo adapter in `live` mode).
- **Stored snapshot**: a scheduled `import` copies the provider's data into `departures`/`offers`,
  recorded in `data_imports`. `StoredTimetableAdapter` serves it. If imports stop, the data ages
  into *stale* and then *expired* and disappears from results instead of being shown as current.

## Checklist before adding a real provider

A provider may be registered in `providers/registry.py` only when all of these are documented:

1. **Authorisation**: the agreement, licence or published terms that permit this use (link or
   reference stored in `access_basis`). No scraping, no bypassing logins, rate limits or robots rules.
2. **Permitted usage**: display, caching duration, attribution wording, whether prices may be shown,
   whether booking redirects (and to which hosts) are allowed.
3. **Update frequency**: how often schedules and prices change, and the matching freshness thresholds.
4. **Reliability**: uptime expectations, error behaviour, rate limits, support contact.
5. **Data mapping**: how their stations map to T-Port locations, their time zones, currency.
6. **Tests**: adapter tests with recorded fixtures, including failures, timeouts and malformed data.
7. **Booking hosts**: only after written permission. Add exact hosts to `ProviderInfo.booking_hosts`.

Real-time availability and live prices must only be shown when such a source provides them.
