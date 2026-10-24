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
            return self._json((ROOT / "surfaces.json").read_bytes())
        if self.path.startswith("/api/timeline"):
            return self._timeline()
        if self.path.startswith("/api/openspace"):
            return self._openspace()
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

    # Proxy MassGIS Protected & Recreational OpenSpace (ArcGIS REST) so the
    # browser can read it without cross-origin issues. Two modes:
    #   /api/openspace?bbox=minLon,minLat,maxLon,maxLat   -> GeoJSON polygons to draw
    #   /api/openspace?point=lon,lat                      -> {on_protected, sites[]}
    # This only fetches public state data; it changes no model logic.
    def _openspace(self):
        import urllib.parse as up
        import urllib.request as ur
        BASE = ("https://gis.eea.mass.gov/server/rest/services/"
                "Protected_and_Recreational_OpenSpace_Polygons/MapServer/0/query")
        q = up.parse_qs(up.urlparse(self.path).query)
        try:
            if "point" in q:
                lon, lat = [float(x) for x in q["point"][0].split(",")]
                params = {
                    "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
                    "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "SITE_NAME,PRIM_PURP,OWNER_TYPE,LEV_PROT",
                    "returnGeometry": "false", "f": "json",
                }
                url = BASE + "?" + up.urlencode(params)
                with ur.urlopen(url, timeout=30) as r:
                    data = json.load(r)
                feats = data.get("features", [])
                out = {
                    "on_protected": len(feats) > 0,
                    "sites": [f.get("attributes", {}) for f in feats[:5]],
                }
                return self._json(json.dumps(out).encode())
            else:
                bbox = q.get("bbox", ["-73.51,41.18,-69.90,42.89"])[0]  # all MA
                params = {
                    "geometry": bbox, "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "SITE_NAME,PRIM_PURP,LEV_PROT",
                    "returnGeometry": "true", "outSR": "4326",
                    "resultRecordCount": "2000", "f": "geojson",
                }
                url = BASE + "?" + up.urlencode(params)
                with ur.urlopen(url, timeout=45) as r:
                    body = r.read()
                return self._json(body)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

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

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"HourMatch map (Python shim for Shiva's web/) at http://127.0.0.1:{PORT}")
        httpd.serve_forever()
