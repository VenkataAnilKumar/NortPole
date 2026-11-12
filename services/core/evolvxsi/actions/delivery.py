"""Send an approved action to its target. Safety rules, in code:

* The destination is the administrator's registered URL, never owner input.
* A destination that resolves to a link-local or metadata address is refused
  (cloud metadata services live there), whatever the administrator typed.
* The request carries an Idempotency-Key, stable for one approved action, so a
  retry after an unknown outcome cannot produce a second effect at a receiver
  that honours it.
* Redirects are not followed, the timeout is short, and the response body is
  not stored (only the status), so a target cannot push content into our records.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

TIMEOUT_S = 10


class UnsafeTarget(Exception):
    pass


def _addresses(host: str, port: int) -> list[str]:
    return sorted({info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})


def _forbidden(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # An IPv4 address written as IPv6 (::ffff:169.254.169.254) is judged as the IPv4 address.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved


def resolve_safe(url: str) -> tuple[str, str, int, str]:
    """Look the host up once and return (scheme, host, port, address) for an
    address that is allowed. Every address the name resolves to must be allowed,
    so a name that also points somewhere forbidden is refused."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeTarget("The target must be an http or https URL.")
    if parts.username or parts.password:
        raise UnsafeTarget("The target address must not contain a user name or password.")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        addrs = _addresses(parts.hostname, port)
    except OSError as e:
        raise UnsafeTarget("The target host does not resolve.") from e
    if not addrs:
        raise UnsafeTarget("The target host does not resolve.")
    for a in addrs:
        if _forbidden(ipaddress.ip_address(a)):
            raise UnsafeTarget("The target resolves to an address that is not allowed (link-local, metadata or reserved).")
    return parts.scheme, parts.hostname, port, addrs[0]


def check_target_url(url: str) -> None:
    resolve_safe(url)


class _PinnedAdapter(HTTPAdapter):
    """Connect to a fixed, already-checked address while keeping the real host
    name for the Host header and for TLS (certificate and SNI), so a second DNS
    answer cannot redirect the connection."""

    def __init__(self, host: str, address: str, port: int) -> None:
        self._host, self._address, self._port = host, address, port
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **kw):  # type: ignore[no-untyped-def]
        super().init_poolmanager(connections, maxsize, block=block, server_hostname=self._host, assert_hostname=self._host, **kw)

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):  # type: ignore[no-untyped-def]
        # Route to the pinned address; the original URL still names the host.
        pool = super().get_connection_with_tls_context(request, verify, proxies=proxies, cert=cert)
        pool.host = self._address
        return pool


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    status: int | None
    error: str | None


def deliver(url: str, payload: dict[str, Any], idempotency_key: str) -> DeliveryResult:
    try:
        scheme, host, port, address = resolve_safe(url)
        session = requests.Session()
        session.trust_env = False  # no proxy settings: the connection goes where we checked
        session.mount(f"{scheme}://", _PinnedAdapter(host, address, port))
        r = session.post(
            url,
            json=payload,
            headers={
                "Idempotency-Key": idempotency_key,
                "User-Agent": "EvolvXSI-Action/1",
                # The connection goes to the checked address, so the name is sent explicitly.
                "Host": host if port in (80, 443) else f"{host}:{port}",
            },
            timeout=TIMEOUT_S,
            allow_redirects=False,
        )
    except UnsafeTarget as e:
        return DeliveryResult(False, None, str(e))
    except requests.RequestException:
        # The send may or may not have happened; the same key makes a retry safe.
        return DeliveryResult(False, None, "The target did not answer. You can retry; the same request key is reused.")
    if 200 <= r.status_code < 300:
        return DeliveryResult(True, r.status_code, None)
    return DeliveryResult(False, r.status_code, f"The target answered with status {r.status_code}.")
