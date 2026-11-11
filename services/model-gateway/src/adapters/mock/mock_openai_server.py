#!/usr/bin/env python3
"""Deterministic OpenAI-compatible mock model (fixture adapter, PF-07.01).

Used to develop and test routing, policy and the chat interface without a live
model or any credentials. It returns a fixed, clearly labelled reply that echoes
the last user message. It performs no inference and is not a real model.

Run one instance per mock route, for example:

    python mock_openai_server.py --name local-mock --port 18001
    python mock_openai_server.py --name cloud-mock --port 18002
"""
import argparse
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def last_user_text(messages):
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, list):
                return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            return str(c or "")
    return ""


def reply_text(route, model, messages):
    said = last_user_text(messages).strip().replace("\n", " ")
    if len(said) > 300:
        said = said[:300] + "..."
    return (
        f"[{route} / {model}] This is a deterministic test reply from the mock route, "
        f"not a real model. You said: \"{said}\""
    )


class Handler(BaseHTTPRequestHandler):
    route = "mock"
    model = "mock-1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep output quiet
        pass

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json(200, {"object": "list", "data": [
                {"id": self.model, "object": "model", "created": 0, "owned_by": self.route}]})
        elif self.path in ("/health", "/"):
            self._json(200, {"status": "ok", "route": self.route})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._json(400, {"error": {"message": "invalid json"}})
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "not found"}})
        model = req.get("model") or self.model
        text = reply_text(self.route, model, req.get("messages"))
        cid = "chatcmpl-" + uuid.uuid4().hex[:12]
        now = int(time.time())
        usage = {"prompt_tokens": 10, "completion_tokens": max(1, len(text.split())),
                 "total_tokens": 10 + max(1, len(text.split()))}
        if not req.get("stream"):
            return self._json(200, {
                "id": cid, "object": "chat.completion", "created": now, "model": model,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text}}],
                "usage": usage})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def send(obj):
            payload = ("data: " + (obj if isinstance(obj, str) else json.dumps(obj)) + "\n\n").encode()
            self.wfile.write(f"{len(payload):x}\r\n".encode() + payload + b"\r\n")
            self.wfile.flush()

        base = {"id": cid, "object": "chat.completion.chunk", "created": now, "model": model}
        send({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})
        for word in text.split(" "):
            send({**base, "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}]})
        send({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage})
        send("[DONE]")
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default="mock", help="route label shown in replies")
    ap.add_argument("--model", default=None, help="model id (default: <name>-1)")
    ap.add_argument("--port", type=int, default=18001)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    Handler.route = args.name
    Handler.model = args.model or f"{args.name}-1"
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mock route '{args.name}' model '{Handler.model}' on http://{args.host}:{args.port}/v1", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
