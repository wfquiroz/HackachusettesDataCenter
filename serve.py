#!/usr/bin/env python3
"""
serve.py — run Shiva's web/ frontend WITHOUT Node.

Shiva's server.js serves web/public/ statically and exposes /api/facilities
(the contents of web/facilities.json) plus /healthz. This is a byte-for-byte
Python stand-in so the demo runs on a machine without Node. When Node is
available, `node web/server.js` serves the exact same thing.

Run:  /opt/anaconda3/bin/python3 serve.py   (then open http://127.0.0.1:5173)
"""
import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "web"
PUBLIC = ROOT / "public"
FACILITIES = ROOT / "facilities.json"
PORT = 5173


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(PUBLIC), **k)

    def do_GET(self):
        if self.path.startswith("/api/facilities"):
            return self._json(FACILITIES.read_bytes())
        if self.path.startswith("/api/layers"):
            return self._json((ROOT / "layers.json").read_bytes())
        if self.path.startswith("/api/surfaces"):
            return self._json((ROOT / "surfaces.json").read_bytes())
        if self.path.startswith("/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        return super().do_GET()

    def _json(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"HourMatch map (Python shim for Shiva's web/) at http://127.0.0.1:{PORT}")
        httpd.serve_forever()
