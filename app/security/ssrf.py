from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.config import get_settings


class UnsafeUrlError(ValueError):
    """Raised when a user-supplied URL targets a disallowed/internal address."""


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    # Block anything that isn't a normal public address. This also covers the
    # cloud metadata endpoint (169.254.169.254) via the link-local check.
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_outbound_url(url: str) -> None:
    """Validate a user-supplied MCP server URL before connecting.

    Resolves the hostname and rejects private/internal targets to prevent SSRF.
    Resolution happens here, but note that a fully robust defense also pins the
    resolved IP for the actual connection to defeat DNS-rebinding (TODO: wire a
    pinned-IP httpx transport into the MCP client).
    """
    settings = get_settings()
    if settings.allow_private_networks:
        return

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"Unsupported scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise UnsafeUrlError("URL has no host")

    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Could not resolve host: {parsed.hostname}") from exc

    for info in infos:
        addr = info[4][0]
        ip = ipaddress.ip_address(addr)
        if _ip_is_blocked(ip):
            raise UnsafeUrlError(f"Host resolves to a disallowed address: {addr}")
