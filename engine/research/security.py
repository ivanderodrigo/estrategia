"""Network guardrails for research performed from untrusted public URLs."""

from __future__ import annotations

import ipaddress
import socket
from functools import lru_cache
from urllib.parse import urlparse


class UnsafeUrl(ValueError):
    pass


def _is_public_ip(raw: str) -> bool:
    address = ipaddress.ip_address(raw)
    return not any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


@lru_cache(maxsize=2_048)
def _public_dns(host: str) -> bool:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        return False
    return bool(addresses) and all(_is_public_ip(address) for address in addresses)


def validate_public_url(url: str, *, resolve_dns: bool = True) -> str:
    """Reject credentials, unusual ports and private/link-local destinations."""

    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrl("Only absolute HTTP(S) URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeUrl("Credentials in URLs are not allowed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrl("Invalid URL port") from exc
    if port not in {None, 80, 443}:
        raise UnsafeUrl("Only standard web ports are allowed")
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise UnsafeUrl("Local destinations are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if resolve_dns and not _public_dns(host):
            raise UnsafeUrl("Host does not resolve exclusively to public addresses")
    else:
        if not _is_public_ip(str(address)):
            raise UnsafeUrl("Private or reserved IP destination")
    return parsed.geturl()
