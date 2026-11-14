"""The destination check must hold at the moment of connection, not just before."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from nortpole.work.actions import delivery
from nortpole.work.actions.delivery import UnsafeTarget, check_target_url, deliver, resolve_safe


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
    from nortpole.work.actions.delivery import _PinnedAdapter

    adapter = _PinnedAdapter("hooks.example.test", "93.184.216.34", 443)
    kw = adapter.poolmanager.connection_pool_kw
    assert kw["server_hostname"] == "hooks.example.test" and kw["assert_hostname"] == "hooks.example.test"


def _hook_test_is_loopback():  # type: ignore[no-untyped-def]
    real = socket.getaddrinfo

    def fake(host, port, *a, **kw):  # type: ignore[no-untyped-def]
        return real("127.0.0.1" if host == "hook.test" else host, port, *a, **kw)

    return patch.object(delivery.socket, "getaddrinfo", fake)


def _cert(tmp_path, name: str):  # type: ignore[no-untyped-def]
    import subprocess

    crt, key = tmp_path / f"{name}.crt", tmp_path / f"{name}.key"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", f"/CN={name}",
                    "-addext", f"subjectAltName=DNS:{name}", "-keyout", str(key), "-out", str(crt)],
                   check=True, capture_output=True)
    return crt, key


def _tls_server(crt, key):  # type: ignore[no-untyped-def]
    import ssl

    hits: list[str] = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # type: ignore[no-untyped-def]
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            hits.append(self.headers.get("Host", ""))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):  # type: ignore[no-untyped-def]
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(crt), str(key))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, hits


def test_https_is_verified_against_the_real_host_name_over_the_pinned_address(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A live TLS handshake: the connection goes to the checked address, but the
    certificate must still be valid for the name the administrator registered."""
    crt, key = _cert(tmp_path, "hook.test")
    srv, hits = _tls_server(crt, key)
    url = f"https://hook.test:{srv.server_port}/x"
    try:
        with _hook_test_is_loopback():
            monkeypatch.setenv("NORTPOLE_ACTIONS_CA_BUNDLE", str(crt))
            assert deliver(url, {"a": 1}, "k").ok and hits == [f"hook.test:{srv.server_port}"]

            monkeypatch.delenv("NORTPOLE_ACTIONS_CA_BUNDLE")
            assert not deliver(url, {"a": 1}, "k").ok, "a certificate the system does not trust is refused"

            other, _ = _cert(tmp_path, "other.test")
            monkeypatch.setenv("NORTPOLE_ACTIONS_CA_BUNDLE", str(other))
            assert not deliver(url, {"a": 1}, "k").ok, "a certificate from a different authority is refused"
        assert len(hits) == 1
    finally:
        srv.shutdown()


def test_a_certificate_for_another_name_is_refused_even_if_trusted(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    crt, key = _cert(tmp_path, "wrong.test")
    srv, hits = _tls_server(crt, key)
    try:
        with _hook_test_is_loopback():
            monkeypatch.setenv("NORTPOLE_ACTIONS_CA_BUNDLE", str(crt))
            r = deliver(f"https://hook.test:{srv.server_port}/x", {"a": 1}, "k")
        assert not r.ok and hits == []
    finally:
        srv.shutdown()
