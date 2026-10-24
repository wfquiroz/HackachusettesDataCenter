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
import json
import socketserver
import sys
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
            return self._surfaces_with_placement()
        if self.path.startswith("/api/bestsite"):
            return self._bestsite()
        if self.path.startswith("/api/timeline"):
            return self._timeline()
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

    def _timeline(self):
        import urllib.parse as up
        q = up.parse_qs(up.urlparse(self.path).query)
        try:
            lat = float(q.get("lat", ["42.12"])[0])
            lon = float(q.get("lon", ["-72.75"])[0])
            mw = float(q.get("mw", ["274"])[0])
            yrs = int(q.get("years", ["5"])[0])
            sys.path.insert(0, str(ROOT.parent))
            import importlib
            rings = importlib.import_module("pull.rings")
            body = json.dumps(rings.impact_timeline(lat, lon, mw, yrs)).encode()
            self._json(body)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _surfaces_with_placement(self):
        """Serve the impact surfaces PLUS the placement-optimizer surface."""
        base = json.loads((ROOT / "surfaces.json").read_text())
        pfile = ROOT / "placement.json"
        if pfile.exists():
            p = json.loads(pfile.read_text())
            for s in p.get("surfaces", []):
                s["kind"] = "modeled"
                base["surfaces"].append(s)
        self._json(json.dumps(base).encode())

    def _bestsite(self):
        """Return the top-scoring placement cell as a lat/lon + score."""
        try:
            p = json.loads((ROOT / "placement.json").read_text())
            s = p["surfaces"][0]
            nx, ny = p["nx"], p["ny"]
            lon0, lat0, lon1, lat1 = p["bbox"]
            grid = s["grid"]
            best_i = max(range(len(grid)), key=lambda i: grid[i])
            y, x = divmod(best_i, nx)
            lat = lat0 + (lat1 - lat0) * y / (ny - 1)
            lon = lon0 + (lon1 - lon0) * x / (nx - 1)
            self._json(json.dumps({
                "lat": round(lat, 4), "lon": round(lon, 4),
                "score": round(grid[best_i] * 100, 1),
            }).encode())
        except Exception as e:
            self.send_response(500); self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"HourMatch map (Python shim for Shiva's web/) at http://127.0.0.1:{PORT}")
        httpd.serve_forever()
