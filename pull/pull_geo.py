#!/usr/bin/env python3
"""
pull_geo.py — fetch REAL geometry for the map layers from the live ArcGIS/HIFLD
endpoints named in the brief. The kit CSVs have attributes but no shapes; the map
needs shapes. Saves GeoJSON to data/clean/geo/.

Run:  /opt/anaconda3/bin/python3 pull/pull_geo.py
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode

OUT = Path(__file__).resolve().parent.parent / "data" / "clean" / "geo"
OUT.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "HourMatch/1.0 (hackathon)"}


def _get(url: str, timeout=60) -> dict:
    req = Request(url, headers=UA)
    with urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_paged(base: str, params: dict, page=1000, max_records=5000) -> dict:
    """Fetch an ArcGIS FeatureServer/MapServer query, paginating resultOffset."""
    feats = []
    offset = 0
    while True:
        q = dict(params)
        q["resultOffset"] = offset
        q["resultRecordCount"] = page
        url = base + "?" + urlencode(q)
        data = _get(url)
        batch = data.get("features", [])
        feats.extend(batch)
        if len(batch) < page or len(feats) >= max_records:
            break
        offset += page
        time.sleep(0.3)
    return {"type": "FeatureCollection", "features": feats}


def save(name: str, fc: dict):
    p = OUT / name
    p.write_text(json.dumps(fc))
    print(f"  {name}: {len(fc.get('features', []))} features -> {p}")


def main() -> int:
    print("Fetching live geometry (needs network)...")

    # EJ block groups (polygons) — cap to keep file light for the demo.
    try:
        ej = fetch_paged(
            "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/EJ2020/MapServer/0/query",
            {"where": "EJ='Yes'",
             "outFields": "MUNICIPALITY,TOTAL_POP,PCT_MINORITY,LIMENGHHPCT,BG_MHHI,EJ,EJ_CRIT_DESC",
             "returnGeometry": "true", "outSR": "4326", "f": "geojson"},
            page=1000, max_records=4000)
        save("ej_blockgroups.geojson", ej)
    except Exception as e:
        print(f"  EJ failed: {e}", file=sys.stderr)

    # Transmission lines (HIFLD) within a MA bbox.
    try:
        tx = fetch_paged(
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0/query",
            {"geometry": "-73.5081,41.1870,-69.9284,42.8868",
             "geometryType": "esriGeometryEnvelope", "inSR": "4326",
             "spatialRel": "esriSpatialRelIntersects",
             "outFields": "OWNER,VOLTAGE,VOLT_CLASS,TYPE,STATUS",
             "returnGeometry": "true", "outSR": "4326", "f": "geojson"},
            page=1000, max_records=2000)
        save("transmission_lines.geojson", tx)
    except Exception as e:
        print(f"  Transmission failed: {e}", file=sys.stderr)

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
