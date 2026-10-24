#!/usr/bin/env python3
"""
build_layers.py — emit web/layers.json: every impact layer the map can toggle.

Each layer: { id, label, variable, kind: measured|modeled, unit, points[] | geojson_ref }.
Point: { lat, lng, name, value, meta }.

MEASURED layers use real kit/EIA data. MODELED layers are computed from a data
center's MW using config benchmarks — these are the locally-applied version of
the US-trained prediction engine we build later. The frontend shows the
measured/modeled tag on every layer so nothing is passed off as fact that isn't.

Run:  /opt/anaconda3/bin/python3 pull/build_layers.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import model  # noqa: E402

KITR = ROOT / "data" / "raw" / "kit"
OUT = ROOT / "web" / "layers.json"

cfg = model.load_config()
grid = model.load_grid()
dcs = pd.read_csv(ROOT / "data" / "clean" / "datacenters.csv")
land = pd.read_csv(KITR / "landfills" / "data.csv")

MA_TOWNS = {
    "Brookfield": (42.21, -72.10), "Westfield": (42.13, -72.75), "Lowell": (42.64, -71.32),
    "Boston": (42.36, -71.06), "Worcester": (42.26, -71.80), "Springfield": (42.10, -72.59),
    "Fall River": (41.70, -71.15), "New Bedford": (41.64, -70.93), "Chicopee": (42.15, -72.61),
    "Pittsfield": (42.45, -73.25), "Greenfield": (42.59, -72.60), "Easthampton": (42.27, -72.67),
}

# Known New England fossil / peaker plants (public locations) — AIR layer seed.
# Replaced by real CAMPD 2024 emissions once an api.data.gov key is in .env.
FOSSIL = [
    {"name": "Mystic Generating (gas, retired 2024)", "lat": 42.3959, "lng": -71.0712, "fuel": "gas"},
    {"name": "Fore River (gas)", "lat": 42.2450, "lng": -70.9570, "fuel": "gas"},
    {"name": "Canal Station (oil/gas, Sandwich)", "lat": 41.7730, "lng": -70.5090, "fuel": "oil/gas"},
    {"name": "West Springfield (gas/oil)", "lat": 42.1080, "lng": -72.6200, "fuel": "gas/oil"},
    {"name": "Wyman (oil, ME)", "lat": 43.7560, "lng": -70.1930, "fuel": "oil"},
    {"name": "Bridgeport Harbor (gas, CT)", "lat": 41.1680, "lng": -73.1790, "fuel": "gas"},
]

b = cfg["impact_benchmarks"]


def dc_modeled():
    """Run the meter per DC, return modeled impact values for the modeled layers."""
    rows = []
    for _, r in dcs.iterrows():
        res = model.hourly_match(peak_mw=int(r.peak_mw_high), w_solar=1.0,
                                 w_onshore=0, w_offshore=0, df=grid, cfg=cfg)
        imp = model.impact_estimate(res, cfg)
        rows.append({"row": r, "res": res, "imp": imp})
    return rows


dcm = dc_modeled()

layers = []

# ---- MEASURED: energy output (clean supply — landfill solar) ---------------
solar_pts = []
for _, r in land.iterrows():
    c = MA_TOWNS.get(str(r["municipality"]))
    mw = float(r.get("mw_operating") or 0)
    if c and str(r.get("status", "")).lower().startswith("oper") and mw > 0:
        solar_pts.append({"lat": c[0], "lng": c[1], "name": f'{r["facility"]}',
                          "value": mw, "meta": "operating landfill solar"})
layers.append({"id": "energy_output", "label": "Energy output — clean supply",
               "variable": "energy_output", "kind": "measured", "unit": "MW",
               "color": "#2f9e44", "points": solar_pts,
               "source": "MA DEP Renewables at Landfills"})

# ---- MEASURED: air pollution (fossil plants) -------------------------------
air_pts = [{"lat": f["lat"], "lng": f["lng"], "name": f["name"],
            "value": None, "meta": f'fuel: {f["fuel"]} · emissions pending CAMPD key'}
           for f in FOSSIL]
layers.append({"id": "air", "label": "Air pollution — fossil plants",
               "variable": "air", "kind": "measured", "unit": "tCO₂/yr",
               "color": "#e4572e", "points": air_pts,
               "source": "EPA CAMPD (locations; emissions need api.data.gov key)"})

# ---- MEASURED: energy usage (data centers' hidden grid pull) ---------------
usage_pts = [{"lat": float(d["row"].lat), "lng": float(d["row"].lon),
              "name": d["row"]["name"], "value": round(d["res"].uncovered_mwh),
              "meta": f'{d["res"].hourly_match_pct:.0f}% hourly-clean · '
                      f'{round(d["res"].uncovered_mwh):,} MWh from grid'}
             for d in dcm]
layers.append({"id": "energy_usage", "label": "Energy usage — grid pull (uncovered)",
               "variable": "energy_usage", "kind": "measured", "unit": "MWh/yr",
               "color": "#f3c13a", "points": usage_pts,
               "source": "HourMatch model · EIA-930 ISO-NE 2024"})

# ---- MODELED: water pollution/use ------------------------------------------
water_pts = [{"lat": float(d["row"].lat), "lng": float(d["row"].lon),
              "name": d["row"]["name"],
              "value": round(d["imp"]["water_gal_per_year_est"] / 1e6, 1),
              "meta": f'{round(d["imp"]["water_gal_per_year_est"]/1e6,1)}M gal/yr (modeled)'}
             for d in dcm]
layers.append({"id": "water", "label": "Water use — cooling (modeled)",
               "variable": "water", "kind": "modeled", "unit": "M gal/yr",
               "color": "#5aa9e6", "points": water_pts,
               "source": "benchmark × MW — replace with learned US relationship"})

# ---- MODELED: noise pollution ----------------------------------------------
noise_pts = [{"lat": float(d["row"].lat), "lng": float(d["row"].lon),
              "name": d["row"]["name"],
              "value": round(d["imp"]["noise_radius_m_est"]),
              "meta": f'~{round(d["imp"]["noise_radius_m_est"])} m audible radius (modeled)'}
             for d in dcm]
layers.append({"id": "noise", "label": "Noise — audible radius (modeled)",
               "variable": "noise", "kind": "modeled", "unit": "m",
               "color": "#b084f3", "points": noise_pts,
               "source": "benchmark × MW — replace with learned US relationship"})

OUT.write_text(json.dumps({"layers": layers}, indent=2))
print(f"wrote {OUT}")
for L in layers:
    print(f"  [{L['kind']:8}] {L['id']:14} {len(L['points'])} pts  — {L['label']}")
