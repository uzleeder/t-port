"""Template for a query-API (REST) provider adapter. NOT a real integration.

Copy this package to ``app/providers/<provider_id>/`` once a provider has signed off on access,
then replace the response schema, the endpoint paths and the stop-code mapping with the ones from
the provider's technical documentation. File-based sources (published timetables) should use
``app/providers/feed.py`` instead.

What the template already does for you:

* every request goes through the outbound guard (HTTPS, allow-listed host, no internal addresses);
* responses are schema-validated; anything unexpected becomes a ``ProviderError`` instead of
  half-parsed data;
* provider stop codes are mapped to T-Port station IDs through an explicit table, and unknown codes
  are rejected, never guessed;
* HTTP 429 becomes ``ProviderRateLimited`` (honouring ``Retry-After``), 5xx and timeouts are
  retryable, other 4xx are not;
* fares are taken only from the response, stamped with ``retrieved_at`` and ``source_updated_at``.

``TEMPLATE_CONTRACT`` is deliberately incomplete: ``contract_problems`` rejects it, so it can never
be enabled by accident. See docs/provider-integration-status.md.
"""
