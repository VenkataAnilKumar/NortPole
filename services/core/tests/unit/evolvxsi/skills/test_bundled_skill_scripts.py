"""The company-search and image-generation skills' own scripts, run against a stand-in API server."""

import base64
import importlib.util
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from evolvxsi.skills.built_in import BUILTIN_SKILLS_PATH

_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


def _load(skill: str, script: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        script, BUILTIN_SKILLS_PATH / skill / f"{script}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Server:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str], dict[str, Any]]] = []
        self.reply: tuple[int, bytes] = (200, b"{}")


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Server]:
    state = _Server()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append((self.path, dict(self.headers), body))
            status, payload = state.reply
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_: Any) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "EVOLVXSI_SERVER_URL", f"http://127.0.0.1:{httpd.server_port}/api"
    )
    monkeypatch.setenv("EVOLVXSI_PAT", "pat-123")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    yield state
    httpd.shutdown()


def test_search_sends_filters_and_maps_results(
    server: _Server, capsys: pytest.CaptureFixture[str]
) -> None:
    server.reply = (
        200,
        json.dumps(
            {
                "results": [
                    {
                        "citation_id": 1,
                        "title": "Leave policy",
                        "content": "20 days",
                        "link": "https://drive/x",
                        "source_type": "google_drive",
                        "updated_at": "2026-11-01",
                    }
                ]
            }
        ).encode(),
    )
    script = _load("company-search", "company_search")
    assert (
        script.main(
            [
                "search",
                "leave",
                "--source",
                "slack, google_drive",
                "--days",
                "7",
                "--no-query-expansion",
            ]
        )
        == 0
    )
    path, headers, body = server.requests[0]
    assert path == "/api/search"
    assert headers["Authorization"] == "Bearer pat-123"
    assert body["query"] == "leave" and body["sources"] == ["slack", "google_drive"]
    assert body["skip_query_expansion"] is True and "time_cutoff" in body
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "results": [
            {
                "title": "Leave policy",
                "url": "https://drive/x",
                "source_type": "google_drive",
                "content": "20 days",
                "updated_at": "2026-11-01",
            }
        ]
    }


def test_several_queries_and_a_failure(
    server: _Server, capsys: pytest.CaptureFixture[str]
) -> None:
    server.reply = (403, b'{"detail":"no access"}')
    script = _load("company-search", "company_search")
    assert script.main(["search", "a", "b"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [s["query"] for s in out["searches"]] == ["a", "b"]
    assert all(s["results"] is None and "403" in s["error"] for s in out["searches"])
    assert script.main(["search", "a", "b", "c", "d"]) == 2


def test_search_needs_server_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVOLVXSI_PAT", raising=False)
    monkeypatch.setenv("EVOLVXSI_SERVER_URL", "http://127.0.0.1:1")
    assert _load("company-search", "company_search").main(["search", "x"]) == 2


def test_generate_saves_each_image_after_keepalives(
    server: _Server, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = [
        {"data_base64": _PNG, "mime_type": "image/png", "revised_prompt": "p"}
    ] * 2
    server.reply = (200, b"   \n  " + json.dumps({"images": images}).encode())
    script = _load("image-generation", "image_gen")
    assert (
        script.main(
            [
                "generate",
                "-p",
                "a mug",
                "-n",
                "2",
                "--shape",
                "landscape",
                "-o",
                str(tmp_path / "art.png"),
            ]
        )
        == 0
    )
    path, _, body = server.requests[0]
    assert path == "/api/image-generation/generate"
    assert (
        body["n"] == 2
        and body["shape"] == "landscape"
        and body["reference_images"] == []
    )
    printed = capsys.readouterr().out.split()
    assert printed == [str(tmp_path / "art_1.png"), str(tmp_path / "art_2.png")]
    assert (tmp_path / "art_1.png").read_bytes() == base64.b64decode(_PNG)


def test_edit_sends_input_images_and_reports_errors(
    server: _Server, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "in.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nsrc")
    server.reply = (
        200,
        json.dumps(
            {"error_code": "NOT_FOUND", "detail": "No provider configured."}
        ).encode(),
    )
    script = _load("image-generation", "image_gen")
    assert (
        script.main(
            ["edit", "-i", str(source), "-p", "sunset", "-o", str(tmp_path / "out.png")]
        )
        == 1
    )
    body = server.requests[0][2]
    assert (
        base64.b64decode(body["reference_images"][0]["data_base64"])
        == source.read_bytes()
    )
    assert "No provider configured." in capsys.readouterr().err
    assert not (tmp_path / "out.png").exists()
