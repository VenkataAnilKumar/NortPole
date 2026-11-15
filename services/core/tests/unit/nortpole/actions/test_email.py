"""Email as an action target: fixed recipients, no header injection, real SMTP exchange."""

import socket
import threading
from unittest.mock import patch

import pytest

from nortpole.work.actions import delivery
from nortpole.work.actions.delivery import UnsafeTarget, deliver_email, parse_mailto
from nortpole.configs import app_configs as cfg


def test_recipients_are_parsed_and_limited() -> None:
    assert parse_mailto("mailto:a@example.com, b@example.org") == ["a@example.com", "b@example.org"]
    for bad in ["a@example.com", "mailto:", "mailto:not-an-address", "mailto:a@b.com\r\nBcc: x@y.com",
                "mailto:" + ",".join(f"u{i}@example.com" for i in range(6)), "mailto:a b@example.com"]:
        with pytest.raises(UnsafeTarget):
            parse_mailto(bad)


def test_no_mail_server_means_a_clear_failure_not_a_crash() -> None:
    with patch.object(cfg, "SMTP_SERVER", ""):
        r = deliver_email("mailto:a@example.com", {"title": "T", "markdown": "x"}, "k")
    assert not r.ok and "no mail server" in r.error


class _Sink:
    """A minimal SMTP receiver: records the message it is given."""

    def __init__(self) -> None:
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.data = ""
        self.rcpt: list[str] = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        c, _ = self.sock.accept()
        f = c.makefile("rwb")
        w = lambda t: (f.write((t + "\r\n").encode()), f.flush())  # noqa: E731
        w("220 sink")
        in_data, lines = False, []
        while (raw := f.readline()):
            line = raw.decode().rstrip("\r\n")
            if in_data:
                if line == ".":
                    in_data = False
                    self.data = "\n".join(lines)
                    w("250 ok")
                else:
                    lines.append(line)
                continue
            u = line.upper()
            if u.startswith("EHLO") or u.startswith("HELO"):
                w("250 sink")
            elif u.startswith("RCPT"):
                self.rcpt.append(line.split(":", 1)[1].strip(" <>"))
                w("250 ok")
            elif u.startswith("DATA"):
                in_data = True
                w("354 go")
            elif u.startswith("QUIT"):
                w("221 bye")
                break
            else:
                w("250 ok")
        c.close()


def test_a_message_reaches_only_the_registered_recipients() -> None:
    sink = _Sink()
    with patch.object(cfg, "SMTP_SERVER", "127.0.0.1"), patch.object(cfg, "SMTP_PORT", sink.port), \
         patch.object(cfg, "SMTP_STARTTLS", False), patch.object(cfg, "SMTP_USER", ""), patch.object(cfg, "EMAIL_FROM", "noreply@example.com"):
        r = deliver_email("mailto:a@example.com,b@example.org",
                          {"title": "Q3\r\nBcc: evil@example.com", "markdown": "Body line"}, "key123")
    assert r.ok
    assert sink.rcpt == ["a@example.com", "b@example.org"]
    headers = sink.data.split("\n\n")[0].split("\n")
    assert not any(h.lower().startswith("bcc:") for h in headers), "the title cannot add a header"
    assert "Subject: Q3 Bcc: evil@example.com" in sink.data  # folded into one line, not a header
    assert "Message-ID: <key123@nortpole.local>" in sink.data and "Body line" in sink.data


def test_a_refused_connection_is_a_failure_that_warns_about_duplicates() -> None:
    with patch.object(cfg, "SMTP_SERVER", "127.0.0.1"), patch.object(cfg, "SMTP_PORT", 1), \
         patch.object(cfg, "SMTP_STARTTLS", False), patch.object(cfg, "EMAIL_FROM", "n@example.com"):
        r = deliver_email("mailto:a@example.com", {"title": "T", "markdown": "x"}, "k")
    assert not r.ok and "may or may not" in r.error
