"""The destination check must hold at the moment of connection, not just before."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from evolvxsi.actions import delivery
from evolvxsi.actions.delivery import UnsafeTarget, check_target_url, deliver, resolve_safe


def _info(*addrs: str):  # type: ignore[no-untyped-def]
    return lambda host, port, **kw: [(socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addrs]


@pytest.mark.parametrize("addr", ["169.254.169.254", "::ffff:169.254.169.254", "fe80::1", "0.0.0.0", "224.0.0.1", "240.0.0.1", "::"])
def test_forbidden_addresses_are_refused_however_they_are_written(addr: str) -> None:
    with patch.object(delivery.socket, "getaddrinfo", _info(addr)):
        with pytest.raises(UnsafeTarget):
            resolve_safe("http://example.test/hook")


def test_a_name_that_also_points_somewhere_forbidden_is_refused() -> None:
    with patch.object(delivery.socket, "getaddrinfo", _info("93.184.216.34", "169.254.169.254")):
        with pytest.raises(UnsafeTarget):
            resolve_safe("http://example.test/hook")


@pytest.mark.parametrize("url", ["http://user:pw@example.test/x", "http://u@example.test/x", "file:///etc/passwd", "gopher://example.test/"])
def test_credentials_in_the_url_and_other_schemes_are_refused(url: str) -> None:
    with patch.object(delivery.socket, "getaddrinfo", _info("93.184.216.34")):
        with pytest.raises(UnsafeTarget):
            check_target_url(url)


def test_a_name_that_does_not_resolve_is_refused() -> None:
    def boom(host, port, **kw):  # type: ignore[no-untyped-def]
        raise socket.gaierror("no such host")

    with patch.object(delivery.socket, "getaddrinfo", boom):
        with pytest.raises(UnsafeTarget):
            resolve_safe("http://nowhere.test/x")


def test_dns_rebinding_cannot_redirect_the_connection() -> None:
    """The name answers with a safe address the first time and a forbidden one
    after. The connection must go to the address that was checked."""
    hits: list[str] = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # type: ignore[no-untyped-def]
            hits.append(self.headers.get("Host", ""))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):  # type: ignore[no-untyped-def]
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    calls = {"n": 0}

    seen: list[str] = []
    real = socket.getaddrinfo

    def flipping(host, port, *a, **kw):  # type: ignore[no-untyped-def]
        seen.append(str(host))
        if str(host) == "rebind.test":  # only the name is faked; literal addresses resolve as themselves
            calls["n"] += 1
            addr = "127.0.0.1" if calls["n"] == 1 else "169.254.169.254"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, port))]
        return real(host, port, *a, **kw)

    try:
        with patch.object(delivery.socket, "getaddrinfo", flipping), patch("socket.getaddrinfo", flipping):
            result = deliver(f"http://rebind.test:{srv.server_port}/hook", {"x": 1}, "key-1")
    finally:
        srv.shutdown()
    assert result.ok, result.error
    assert hits == [f"rebind.test:{srv.server_port}"], "reached the checked address, with the real Host header"
    assert calls["n"] == 1, f"the name was looked up more than once: {seen}"
    assert seen.count("rebind.test") == 1


def test_proxy_environment_variables_are_ignored() -> None:
    import os

    srv_hits: list[int] = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # type: ignore[no-untyped-def]
            srv_hits.append(1)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):  # type: ignore[no-untyped-def]
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "http_proxy": "http://127.0.0.1:1"}):
            result = deliver(f"http://127.0.0.1:{srv.server_port}/hook", {}, "k")
    finally:
        srv.shutdown()
    assert result.ok and srv_hits == [1], "a proxy setting must not reroute the send"


def test_redirects_are_not_followed() -> None:
    other: list[int] = []

    class Target(BaseHTTPRequestHandler):
        def do_POST(self):  # type: ignore[no-untyped-def]
            other.append(1)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):  # type: ignore[no-untyped-def]
            pass

    t = HTTPServer(("127.0.0.1", 0), Target)
    threading.Thread(target=t.serve_forever, daemon=True).start()

    class Redirector(BaseHTTPRequestHandler):
        def do_POST(self):  # type: ignore[no-untyped-def]
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{t.server_port}/elsewhere")
            self.end_headers()

        def log_message(self, *a):  # type: ignore[no-untyped-def]
            pass

    r = HTTPServer(("127.0.0.1", 0), Redirector)
    threading.Thread(target=r.serve_forever, daemon=True).start()
    try:
        result = deliver(f"http://127.0.0.1:{r.server_port}/hook", {}, "k")
    finally:
        r.shutdown()
        t.shutdown()
    assert not result.ok and result.status == 307
    assert other == [], "the redirect target must never be contacted"


def test_https_keeps_the_real_host_name_for_certificate_checks() -> None:
    from evolvxsi.actions.delivery import _PinnedAdapter

    adapter = _PinnedAdapter("hooks.example.test", "93.184.216.34", 443)
    kw = adapter.poolmanager.connection_pool_kw
    assert kw["server_hostname"] == "hooks.example.test" and kw["assert_hostname"] == "hooks.example.test"
