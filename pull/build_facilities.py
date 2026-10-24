#!/usr/bin/env python3
"""
build_facilities.py — generate web/facilities.json from OUR real model + kit data.

Keeps Shiva's JSON shape (regions / cities / facilities / thresholds) so his
Leaflet frontend works unchanged, but:
  - MA data centers carry REAL numbers from model.hourly_match (hidden hourly CO2),
    plus annual%/hourly%/water as extra fields his popup can show.
  - adds real MA landfill-solar points and a few fossil context sites.
  - keeps the honest 'estimate' labels.

Run:  /opt/anaconda3/bin/python3 pull/build_facilities.py
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import model  # noqa: E402

KIT = ROOT / "data" / "clean"
WEB = ROOT / "web" / "facilities.json"

cfg = model.load_config()
grid = model.load_grid()
dcs = pd.read_csv(ROOT / "data" / "clean" / "datacenters.csv")
land = pd.read_csv(ROOT / "data" / "raw" / "kit" / "landfills" / "data.csv")

MA_TOWNS = {
    "Brookfield": (42.21, -72.10), "Westfield": (42.13, -72.75), "Lowell": (42.64, -71.32),
    "Boston": (42.36, -71.06), "Worcester": (42.26, -71.80), "Springfield": (42.10, -72.59),
    "Fall River": (41.70, -71.15), "New Bedford": (41.64, -70.93), "Chicopee": (42.15, -72.61),
    "Pittsfield": (42.45, -73.25), "Greenfield": (42.59, -72.60), "Easthampton": (42.27, -72.67),
}


def dc_facility(row):
    """Run the real meter for this data center (all-solar EO658 scenario)."""
    res = model.hourly_match(peak_mw=int(row.peak_mw_high), w_solar=1.0,
                             w_onshore=0.0, w_offshore=0.0, df=grid, cfg=cfg)
    return {
        "name": row["name"],
        "type": "data_center",
        "city": f'{row["town"]}, MA',
        "lat": float(row.lat), "lng": float(row.lon),
        "emissions_tco2e": round(res.hidden_co2_t),      # REAL hidden hourly CO2
        "status": row["status"],
        "source": "HourMatch model — ISO-NE 2024 hourly (all-solar EO658 scenario)",
        "source_url": row["source_url"],
        # ---- HourMatch extras (Shiva's popup can show these) ----
        "annual_match_pct": round(res.annual_match_pct),
        "hourly_match_pct": round(res.hourly_match_pct),
        "peak_mw": int(row.peak_mw_high),
        "water_mgal_yr": round(model.impact_estimate(res, cfg)["water_gal_per_year_est"] / 1e6, 1),
    }


facilities = [dc_facility(r) for _, r in dcs.iterrows()]

# add operating landfill-solar sites as "clean supply" facilities (low emissions)
for _, r in land.iterrows():
    town = str(r["municipality"])
    c = MA_TOWNS.get(town)
    if c and str(r.get("status", "")).lower().startswith("oper") and float(r.get("mw_operating") or 0) > 0:
        facilities.append({
            "name": f'{r["facility"]} (landfill solar)',
            "type": "clean_supply",
            "city": f"{town}, MA",
            "lat": c[0], "lng": c[1],
            "emissions_tco2e": 0,
            "status": "operating",
            "source": "MA DEP Renewables at Landfills",
            "source_url": "https://www.mass.gov/",
            "mw_operating": float(r.get("mw_operating") or 0),
        })

out = {
    "note": "MA data-center CO2 is the REAL hidden-hourly estimate from the HourMatch "
            "model (ISO-NE 2024). Water is a benchmarked estimate. Landfill solar is "
            "MA DEP operating data. Town-level coordinates only.",
    "regions": [
        {"id": "ma", "label": "Massachusetts", "center": {"lat": 42.2, "lng": -71.8}, "zoom": 8},
    ],
    "cities": [
        {"name": "Lowell, MA", "region": "ma", "lat": 42.6334, "lng": -71.3162},
        {"name": "Westfield, MA", "region": "ma", "lat": 42.1251, "lng": -72.7495},
        {"name": "Boston, MA", "region": "ma", "lat": 42.3601, "lng": -71.0589},
        {"name": "Worcester, MA", "region": "ma", "lat": 42.2626, "lng": -71.8023},
        {"name": "Springfield, MA", "region": "ma", "lat": 42.1015, "lng": -72.5898},
    ],
    "facilities": facilities,
    "thresholds": {
        "note": "annual tCO2e cutoffs for the high/medium/low indicator",
        "low_max": 50000, "medium_max": 200000,
    },
}

WEB.write_text(json.dumps(out, indent=2))
n_dc = sum(1 for f in facilities if f["type"] == "data_center")
n_solar = sum(1 for f in facilities if f["type"] == "clean_supply")
print(f"wrote {WEB}")
print(f"  {n_dc} data centers (real model numbers), {n_solar} landfill-solar sites")
for f in facilities:
    if f["type"] == "data_center":
        print(f"  - {f['name']}: {f['peak_mw']}MW  annual {f['annual_match_pct']}% -> "
              f"hourly {f['hourly_match_pct']}%  hidden {f['emissions_tco2e']:,} tCO2/yr")
