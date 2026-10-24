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

_MA_POLYS_CACHE = None


def _ma_polygons():
    """Load the MA boundary as a list of outer rings [(lon,lat),...]. Cached."""
    global _MA_POLYS_CACHE
    if _MA_POLYS_CACHE is not None:
        return _MA_POLYS_CACHE
    f = ROOT / "public" / "ma_boundary.geojson"
    polys = []
    try:
        d = json.loads(f.read_text())
        feats = d.get("features") or ([d] if d.get("type") == "Feature" else [])
        for feat in feats:
            geom = feat.get("geometry") or {}
            if geom.get("type") == "Polygon":
                polys.append(geom["coordinates"][0])
            elif geom.get("type") == "MultiPolygon":
                for poly in geom["coordinates"]:
                    polys.append(poly[0])
    except Exception:
        polys = []
    _MA_POLYS_CACHE = polys
    return polys


def _point_in_ring(lat, lon, ring):
    """Ray-casting point-in-polygon. ring = [(lon,lat),...]."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
           (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_ma(lat, lon, polys):
    return any(_point_in_ring(lat, lon, r) for r in polys)


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
        """Top-scoring placement cell(s). ?n=5 returns the N best sites spaced
        at least ~50 miles apart, CLIPPED to the Massachusetts boundary."""
        import math
        import urllib.parse as up
        try:
            q = up.parse_qs(up.urlparse(self.path).query)
            n = int(q.get("n", ["1"])[0])
            min_miles = float(q.get("spacing", ["50"])[0])
            p = json.loads((ROOT / "placement.json").read_text())
            s = p["surfaces"][0]
            nx, ny = p["nx"], p["ny"]
            lon0, lat0, lon1, lat1 = p["bbox"]
            grid = s["grid"]
            polys = _ma_polygons()

            def cell_ll(i):
                yy, xx = divmod(i, nx)
                return (lat0 + (lat1 - lat0) * yy / (ny - 1),
                        lon0 + (lon1 - lon0) * xx / (nx - 1))

            def miles(a, b):
                dlat = (a[0] - b[0]) * 69.0
                dlon = (a[1] - b[1]) * 69.0 * math.cos(math.radians(a[0]))
                return math.sqrt(dlat * dlat + dlon * dlon)

            order = sorted(range(len(grid)), key=lambda i: grid[i], reverse=True)
            picks = []
            for i in order:
                if len(picks) >= n:
                    break
                ll = cell_ll(i)
                if polys and not _point_in_ma(ll[0], ll[1], polys):
                    continue  # skip cells outside Massachusetts
                if all(miles(ll, pk[0]) >= min_miles for pk in picks):
                    picks.append((ll, grid[i]))
            sites = [{"lat": round(ll[0], 4), "lon": round(ll[1], 4),
                      "score": round(sc * 100, 1)} for ll, sc in picks]
            if n == 1:
                self._json(json.dumps(sites[0]).encode())
            else:
                self._json(json.dumps({"sites": sites,
                                       "spacing_miles": min_miles}).encode())
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
