"""Guard for outbound HTTP requests made by provider adapters.

T-Port never fetches user-supplied URLs. Provider adapters may only call hosts listed in their
contract, over HTTPS, and never internal addresses (SSRF protection). Use ``guarded_client`` to
build the HTTP client for any REST/GTFS-RT adapter.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

import httpx


class OutboundBlocked(ValueError):
    pass


def _is_internal(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return any(
        (
            addr.is_private,
            addr.is_loopback,
            addr.is_link_local,
            addr.is_multicast,
            addr.is_reserved,
            addr.is_unspecified,
        )
    )


def check_outbound_url(url: str, allowed_hosts: frozenset[str], *, resolve: bool = True) -> str:
    """Return the URL if it is HTTPS on an allowed host that resolves only to public addresses."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise OutboundBlocked("only https is allowed")
    if parts.username or parts.password:
        raise OutboundBlocked("credentials in URLs are not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or host not in {h.lower() for h in allowed_hosts}:
        raise OutboundBlocked("host is not in the provider's allow-list")
    try:
        literal = _is_internal(host)  # IP literal?
    except ValueError:
        literal = False  # a hostname; checked after resolution below
    if literal:
        raise OutboundBlocked("internal addresses are not allowed")
    if resolve:
        try:
            infos = socket.getaddrinfo(host, parts.port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise OutboundBlocked("host does not resolve") from exc
        if any(_is_internal(info[4][0]) for info in infos):
            raise OutboundBlocked("host resolves to an internal address")
    return url


def guarded_client(
    allowed_hosts: frozenset[str], timeout: float, *, resolve: bool = True
) -> httpx.AsyncClient:
    """Async client that checks every request (including redirects) against the allow-list."""

    async def check(request: httpx.Request) -> None:
        check_outbound_url(str(request.url), allowed_hosts, resolve=resolve)

    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        event_hooks={"request": [check]},
        headers={"User-Agent": "T-Port-ingestion/1.0"},
    )
