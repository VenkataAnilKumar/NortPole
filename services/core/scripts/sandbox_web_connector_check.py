"""Sandbox only. Runs the real web connector against a local three-page site, with and without the private-address guard. Needs the preinstalled chromium at /opt/pw-browsers/chromium; the guard patches below exist only to allow a loopback site."""
import sys, threading, os
os.environ['PLAYWRIGHT_BROWSERS_PATH']='/opt/pw-browsers'
sys.path.insert(0, ".")
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from playwright.sync_api import BrowserType
_l = BrowserType.launch
BrowserType.launch = lambda self, **k: _l(self, executable_path='/opt/pw-browsers/chromium', **{**k, 'args': k.get('args', []) + ['--no-sandbox']})
PAGES = {
 "/": "<html><title>Handbook</title><body><h1>Handbook</h1><p>Welcome.</p><a href='/travel'>Travel</a> <a href='/approvals'>Approvals</a> <a href='https://example.org/outside'>Outside</a></body></html>",
 "/travel": "<html><title>Travel</title><body><p>Receipts are due within 30 days of the trip.</p></body></html>",
 "/approvals": "<html><title>Approvals</title><body><p>Claims over 5,000 need director sign-off.</p></body></html>",
}
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b = PAGES.get(self.path)
        self.send_response(200 if b else 404); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write((b or "nope").encode())
    def log_message(self, *a): pass
srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_port}/"
from nortpole.connectors.web import connector as w
c = w.WebConnector(base_url=base)
try:
    for batch in c.load_from_state(): print("guarded: got", len(batch))
except Exception as e: print("guarded:", type(e).__name__, str(e)[:120])
from nortpole.utils import playwright_fetch as pf
import nortpole.utils.url as U
from urllib.parse import urlparse as _up
with patch.object(U, "_validate_and_resolve_url", lambda u: ('127.0.0.1', _up(u).hostname, _up(u).port or 80)), patch.object(w, "protected_url_check", lambda u: None), patch.object(pf, "_ssrf_allows", lambda *a, **k: True), patch.object(pf, "install_ssrf_guard", lambda *a, **k: None), patch.object(w, "install_ssrf_guard", lambda *a, **k: None, create=True):
    c = w.WebConnector(base_url=base)
    docs = [d for batch in c.load_from_state() for d in batch]
for d in docs: print(d.id, "|", d.semantic_identifier, "|", d.sections[0].text[:70].replace("\n"," "), "| ext:", getattr(d, "external_access", None))
