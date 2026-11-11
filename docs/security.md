# Security

This describes what is implemented. **No compliance claim is made**: no legal or regulatory review
(e.g. under Uzbekistan's personal-data law or GDPR) has been carried out.

## Authentication and sessions
- Passwords hashed with **Argon2id** (`argon2-cffi`); rehashed automatically when parameters change.
  Minimum 10 characters, maximum 128, must differ from the email.
- Login errors are identical for unknown email and wrong password, and both paths run a hash
  verification to reduce timing differences. Registration does reveal an existing email (409);
  accept this or switch to email verification later.
- Sessions use a 256-bit random token in an **HttpOnly, SameSite=Lax** cookie, **Secure** in
  production. Only its SHA-256 hash is stored. Sessions expire after 14 days (configurable), can be
  revoked (logout) and are rotated on login. `purge-sessions` removes dead rows.

## CSRF and cross-origin
- Every state-changing endpoint that uses a session requires `X-CSRF-Token` matching the session's
  token (double-submit via the readable `tport_csrf` cookie, compared in constant time).
- Unsafe requests with an `Origin` header that isn't a configured origin (or the API host) are rejected.
- CORS allows only `TPORT_CORS_ORIGINS`. In production these must be `https://` (enforced at startup).
- Forms that send passwords use `method="post"`, so a submit before JavaScript loads can never put a
  password in a URL. Post-login redirects accept only same-site relative paths.

## Authorization
- Saved journeys are always queried by `(user_id, id)`. Another user's item returns `404`, which
  doesn't reveal that it exists. Covered by tests.
- Account deletion needs the session, a CSRF token and the password.

## Input and output
- All inputs are validated server-side (Pydantic + domain checks): lengths, enums, dates, UUIDs,
  prices and page sizes. Request bodies over 64 KB are rejected.
- Errors never include stack traces. Unhandled exceptions are logged by type only.
- Booking URLs are shown only if they are HTTPS on a provider's explicit host allow-list. The API
  makes **no outbound requests** to user-supplied URLs.
- Security headers: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`,
  `Cache-Control: no-store` on API responses, CSP in production builds, HSTS at the reverse proxy.
  The CSP uses `'unsafe-inline'` for scripts because Next.js streams inline scripts. Moving to
  nonce-based CSP is a hardening follow-up.

## Data handling
- Stored personal data: email, optional display name, password hash, saved journeys, and searches
  linked to the account while it exists. No IP addresses are stored.
- AI requests: metadata only (engine, outcome, latency, length). **Prompt text is never stored or
  logged.** With `TPORT_AI_ENGINE=anthropic`, request text is sent to the LLM provider; disclose this
  in the privacy notice before enabling it.
- Access logs record method, path, status and duration: no query strings, bodies or cookies.
- Retention: `purge-activity` deletes search logs and AI metadata older than
  `TPORT_ACTIVITY_RETENTION_DAYS` (default 180). Account deletion removes the account, sessions and
  saved journeys, and unlinks activity rows from the user.
- Secrets come only from environment variables. `.env*` files are git-ignored, except `.env.example`.
  Production refuses to start with the development database password, non-HTTPS origins or SQL echo.

## Rate limiting
In-memory, fixed one-minute windows per client IP: 120/min overall, 10/min on auth mutations,
20/min on the AI endpoint. Limitations:
- Counts are per process. Use a shared store (e.g. Redis) when running several API processes.
- Next.js rewrites forward `X-Forwarded-For` unchanged but do not set it. The client IP is only
  correct when a front proxy (Caddy in `deploy/`) overwrites that header and uvicorn trusts it only
  from the private network (`FORWARDED_ALLOW_IPS`). Without that, limits apply per web server.
- No account lockout beyond the IP limits; consider it before a public launch.

## Checks run
- `pip-audit` (Python) and `npm audit --omit=dev` (production JS): no known vulnerabilities at the
  time of writing. Both run in CI.
- Ruff security rules (`S`) on the backend.

## Not yet done
- Email verification and password reset.
- Nonce-based CSP, an external penetration test, and a dependency update policy (e.g. Dependabot).
- A privacy notice and terms of use reviewed by counsel.
