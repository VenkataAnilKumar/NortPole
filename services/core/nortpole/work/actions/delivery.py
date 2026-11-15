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
import os
import re
import smtplib
import socket
from email.message import EmailMessage
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
        # Certificates are always verified. A deployment with a private CA names its bundle here.
        session.verify = os.environ.get("NORTPOLE_ACTIONS_CA_BUNDLE") or True
        session.mount(f"{scheme}://", _PinnedAdapter(host, address, port))
        r = session.post(
            url,
            json=payload,
            headers={
                "Idempotency-Key": idempotency_key,
                "User-Agent": "NortPole-Action/1",
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


# ---- email -------------------------------------------------------------------
# The recipients are fixed by the administrator when the target is registered
# ("mailto:a@x.com,b@y.com"); an owner never types an address. The mail server is
# the deployment's own (SMTP_* settings), not anything an owner or a draft names.

_ADDRESS = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")
MAX_RECIPIENTS = 5


def parse_mailto(value: str) -> list[str]:
    """Return the recipient addresses, or raise UnsafeTarget. Control characters and
    anything that is not a plain address are refused, so no header can be injected."""
    if not value.startswith("mailto:"):
        raise UnsafeTarget("An email target must look like mailto:name@example.com (several addresses separated by commas).")
    addrs = [a.strip() for a in value[len("mailto:"):].split(",") if a.strip()]
    if not addrs or len(addrs) > MAX_RECIPIENTS:
        raise UnsafeTarget(f"An email target needs between 1 and {MAX_RECIPIENTS} addresses.")
    bad = [a for a in addrs if not _ADDRESS.match(a) or len(a) > 254]
    if bad:
        raise UnsafeTarget(f"Not a valid email address: {bad[0][:60]}")
    return addrs


def _one_line(text: str, limit: int = 150) -> str:
    return " ".join(text.split())[:limit]


def deliver_email(value: str, payload: dict[str, Any], idempotency_key: str) -> DeliveryResult:
    from nortpole.configs import app_configs as cfg

    try:
        recipients = parse_mailto(value)
    except UnsafeTarget as e:
        return DeliveryResult(False, None, str(e))
    if not (cfg.SMTP_SERVER and cfg.EMAIL_FROM):
        return DeliveryResult(False, None, "This deployment has no mail server configured (SMTP_SERVER and EMAIL_FROM).")
    msg = EmailMessage()
    msg["From"], msg["To"] = cfg.EMAIL_FROM, ", ".join(recipients)
    msg["Subject"] = _one_line(str(payload.get("title") or "Reviewed draft"))
    msg["Message-ID"] = f"<{idempotency_key}@nortpole.local>"
    msg.set_content(str(payload.get("markdown") or ""))
    try:
        with smtplib.SMTP(cfg.SMTP_SERVER, cfg.SMTP_PORT, timeout=TIMEOUT_S) as smtp:
            if cfg.SMTP_STARTTLS:
                smtp.starttls()
            if cfg.SMTP_USER:
                smtp.login(cfg.SMTP_USER, cfg.SMTP_PASS)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        # Nothing about the server's answer is stored. A retry reuses the Message-ID,
        # but email has no way to refuse a duplicate, so the owner is told it may have arrived.
        return DeliveryResult(False, None, "The mail server did not accept the message. It may or may not have been delivered; check before retrying.")
    return DeliveryResult(True, 250, None)
