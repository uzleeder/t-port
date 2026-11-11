"""Provider adapter contract.

Every data source (demo dataset, a licensed operator API, a GTFS import, ...)
implements :class:`ProviderAdapter`. Adapters return domain objects stamped with
``retrieved_at`` / ``source_updated_at`` so the search engine can judge freshness
and show provenance. Adapters must never invent data they did not receive.

Live adapters may only be added after documenting authorised access, permitted
usage, update frequency and reliability (see docs/providers.md).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from app.domain.models import Departure, Offer, ProviderInfo, TransportMode


class ProviderError(Exception):
    """A provider failed to answer. ``retryable`` hints whether a retry may succeed."""

    def __init__(self, provider_id: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(f"[{provider_id}] {message}")
        self.provider_id = provider_id
        self.retryable = retryable


class ProviderRateLimited(ProviderError):
    def __init__(self, provider_id: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(provider_id, "rate limit exceeded", retryable=True)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """Upstream limits the adapter must respect (documented per provider)."""

    requests_per_minute: int | None = None
    timeout_seconds: float = 10.0


class ProviderAdapter(ABC):
    info: ProviderInfo
    rate_limit: RateLimitPolicy = RateLimitPolicy()

    @property
    def id(self) -> str:
        return self.info.id

    @abstractmethod
    def supported_location_ids(self) -> frozenset[str]:
        """Canonical location IDs this provider can serve (location lookup)."""

    @abstractmethod
    async def get_departures(
        self,
        origin_location_id: str,
        destination_location_id: str,
        travel_date: date,
        modes: frozenset[TransportMode],
    ) -> Sequence[Departure]:
        """Direct departures on ``travel_date`` (local date at origin)."""

    @abstractmethod
    async def get_departure(self, departure_id: str) -> Departure | None:
        """Re-fetch a single departure by its provider-scoped ID."""

    @abstractmethod
    async def get_offers(self, departure_ids: Sequence[str]) -> Sequence[Offer]:
        """Fares for the given departures. Missing fares are simply absent."""

    def validate_booking_url(self, url: str | None) -> str | None:
        return validate_booking_url(url, self.info.booking_hosts)


def validate_booking_url(url: str | None, allowed_hosts: frozenset[str]) -> str | None:
    """Return ``url`` only if it is an https URL on an explicitly allowed host.

    Rejects other schemes, credentials in the URL, non-default ports, and hosts
    that merely *end with* an allowed name (``evil-example.com``). Subdomains of
    an allowed host are accepted only when written as ``.example.com``.
    """
    if not url or not allowed_hosts:
        return None
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return None
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return None
    for allowed in allowed_hosts:
        allowed = allowed.lower()
        if allowed.startswith("."):
            if host.endswith(allowed) and len(host) > len(allowed):
                return url.strip()
        elif host == allowed:
            return url.strip()
    return None
