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

TIMEOUT_S = 10


class UnsafeTarget(Exception):
    pass


def _addresses(host: str) -> list[str]:
    return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})


def check_target_url(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeTarget("The target must be an http or https URL.")
    try:
        addrs = _addresses(parts.hostname)
    except OSError as e:
        raise UnsafeTarget("The target host does not resolve.") from e
    for a in addrs:
        ip = ipaddress.ip_address(a)
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise UnsafeTarget("The target resolves to an address that is not allowed (link-local, metadata or reserved).")


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    status: int | None
    error: str | None


def deliver(url: str, payload: dict[str, Any], idempotency_key: str) -> DeliveryResult:
    try:
        check_target_url(url)
        r = requests.post(
            url,
            json=payload,
            headers={"Idempotency-Key": idempotency_key, "User-Agent": "EvolvXSI-Action/1"},
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
