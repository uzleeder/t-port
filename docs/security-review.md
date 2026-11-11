# Phase 2 security review

An internal engineering review of the code on `feat/phase2-live-data-readiness`. It is **not** an external
audit or penetration test, and makes no compliance claim.

## Fixed in this branch

| Severity | Finding | Fix | Test |
|---|---|---|---|
| High | Auth and AI rate limits were in-memory per worker; the production image runs 2 workers, so every limit was effectively doubled (and multiplied by replicas) | Shared fixed-window counters in PostgreSQL (`rate_limit_counters`, hashed keys) for auth/AI | `test_auth_limit_is_shared_between_app_instances` |
| High | Password guessing against one account from many IPs was only limited per IP | Per-account failed-login throttle (5 per 15 min by default), applied to unknown emails too so it reveals nothing | `test_failed_logins_lock_the_account_not_the_ip`, `test_unknown_emails_are_throttled_identically` |
| High | No guard existed for outbound calls a future REST adapter would make (SSRF) | `core/outbound.py`: HTTPS only, contract host allow-list, no credentials in URLs, internal and metadata addresses blocked (literal and after DNS resolution), redirects not followed | `test_outbound_guard_*`, `test_guarded_client_checks_every_request` |
| High | Provider data was written without validation | Contract validation before publication; invalid records quarantined; booking hosts enforced per contract | `test_validate_records_detects_violations` and others |
| Medium | Booking links could be shown with an out-of-date price | Links only for non-demo data with a fresh price; the reason is shown otherwise | `test_booking_link_requires_fresh_price` |
| Medium | Ops diagnostics could leak operational detail | `/health/providers` and `/metrics` need `TPORT_OPS_TOKEN` (≥ 32 chars in production, constant-time compare) and return 404 otherwise; stored error text is the exception type only | `test_ops_endpoints_require_the_token`, `test_error_messages_are_not_kept` |
| Low | uvicorn's access log duplicated request lines including query strings | `--no-access-log`; the app logs method, route and status only (optionally as JSON) | — |

Found and fixed during this review's own testing: the internal-address check for IP literals in the new outbound
guard initially swallowed its own exception (a metadata address would have passed); the import cancellation
checkpoint was unreachable; finishing an import could overwrite progress and cancellation flags.

## Reviewed, no change needed
- **Sessions:** 256-bit opaque tokens, SHA-256 at rest, HttpOnly + SameSite=Lax, Secure in production,
  rotation on login, server-side revocation.
- **CSRF:** double-submit token on every state-changing session request, plus an Origin check.
- **CORS:** explicit origins only; production requires `https://`.
- **Input validation:** Pydantic and domain checks on every endpoint; 64 KB body limit.
- **Secrets:** environment variables only; production refuses development passwords; `.env*` git-ignored.
- **Migrations 0002–0005:** additive; downgrades documented; checked up/down/check on SQLite locally and on
  PostgreSQL in CI.
- **Dependencies:** `pip-audit` and `npm audit --omit=dev` run in CI.

## Remaining risks (accepted for the pilot, tracked)
| Severity | Risk | Plan |
|---|---|---|
| Medium | General API limit (120/min) is still per process | acceptable for pilot load; move to the shared limiter if abuse appears |
| Medium | Shared limiter fails open if the database is down (availability over strictness) | the in-memory limit still applies; DB outages page anyway |
| Medium | No email verification or password reset (no email provider selected) | follow-up once a provider is chosen |
| Medium | CSP still allows inline scripts (Next.js streaming) | nonce-based CSP follow-up |
| Low | Database role used by the app owns the schema | create a separate migration role and a least-privilege runtime role in production (deployment.md) |
| — | No external penetration test | schedule before a public launch |

# Phase 3 additions

Reviewed on `feat/phase3-journey-intelligence`: journey graph, assistant extensions, comparison,
preferences, the booking hand-off, the REST adapter template and the dev-only bookable provider.
Same caveat: an internal engineering review, not an external audit.

## Fixed in this branch

| Severity | Finding | Fix | Test |
|---|---|---|---|
| Medium | A blank optional number in `.env` (e.g. `TPORT_AI_INPUT_USD_PER_MTOK=`) stopped the API from starting | Settings treat empty environment values as unset | `test_blank_optional_settings_are_treated_as_unset` |
| Medium | The security-headers middleware overwrote stricter `Referrer-Policy` values set by routes | It now only sets the default when a route has not set one; the booking redirect sends `no-referrer` | `test_redirect_adds_nothing_and_counts_only_aggregates` |
| Low | Assistant parser cost ~60 ms of CPU per request (regex cache thrash), making `/ai/interpret` the cheapest way to load the API | One precompiled pattern per catalogue; 0.47 ms per parse | AI test suites; `scripts/benchmark.py` |

## Reviewed, no change needed

- **Booking redirect (open-redirect risk):** the target URL never comes from the request. The
  journey is re-resolved from provider data and the link re-checked on every hand-off: direct
  journeys only, never demo data, HTTPS on a host in the provider's contract allow-list
  (exact host or declared subdomain; look-alike suffixes rejected), fresh price when required.
  T-Port appends nothing to the URL, sends `Referrer-Policy: no-referrer` and `Cache-Control: no-store`,
  and stores only `(provider_id, day, count)`.
- **Hand-off counting:** a GET with a side effect, so it is a plain link that Next.js does not
  prefetch (`/api/*` is never prefetched; the interstitial uses `<a>`). Counts are analytics, not
  billing, and can be inflated by bots; documented as such.
- **Preferences:** session + CSRF for writes, `extra="forbid"` with enumerated values only (no free
  text, so no personal data can be stored there), deleted with the account.
- **Comparison:** 2–4 distinct IDs of at most 128 characters; at most 4 lookups per request under
  the general rate limit; unavailable journeys are reported without detail beyond the public reason.
- **Assistant:** the message is treated as data (system prompt says so); the LLM receives only the
  message, today's date and the location catalogue, never provider data; its output must match a
  strict schema (`extra="forbid"`, enumerations, `HH:MM` patterns, 0–2 changes) and is re-validated;
  explanations are template-built from search results, so injected text cannot add facts. Budgets
  in other currencies are not converted (no invented exchange rates).
- **AI metrics:** labels are engine, outcome, error code, model and token direction; request text
  never becomes a label. Cost is reported only from operator-configured prices.
- **REST adapter template:** every request passes the outbound guard; no redirects; schema drift
  is rejected; API keys only in the `Authorization` header; its contract cannot pass the gate.
- **Dev-only bookable provider:** off by default, refused by the production settings validator,
  points at the reserved `.test` domain, labelled "TEST (fictional, dev only)".
- **Compare selection storage:** `sessionStorage` holds journey IDs only.
- **Migrations 0006–0007:** additive tables and indexes; checked up, `alembic check` and down to
  base on SQLite locally; PostgreSQL in CI.

## Remaining risks (accepted for the beta, tracked)

| Severity | Risk | Plan |
|---|---|---|
| Medium | Booking hand-off counts can be inflated by automated requests | treat as indicative; add bot filtering before using them commercially |
| Medium | Everything in the Phase 2 list above that is still open (per-process general limit, no email verification, inline-script CSP, schema-owner DB role, no pen test) | unchanged; required before a public launch |
| Low | Compare can trigger up to 4 provider lookups per request | covered by the general rate limit; revisit with a real provider |
