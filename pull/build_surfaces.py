#!/usr/bin/env python3
"""
build_surfaces.py — statewide SMOOTH impact surfaces (the "pollution wave").

Instead of a few markers, we lay a fine lat/lng grid over Massachusetts and give
EVERY cell a value, interpolated from real sources with inverse-distance
weighting (IDW). The browser renders the grid as a continuous heat surface, so
each variable looks like a wave spreading across the state.

Variables (each its own surface, measured or modeled):
  - ej_burden      MEASURED  EJ block-group population density (people/area proxy)
  - air_fossil     MEASURED  proximity-weighted fossil-plant intensity
  - energy_demand  MEASURED  ISO-NE-scaled demand pressure near load centers
  - water_stress   MODELED   data-center cooling-water pressure (MW benchmark)
  - noise          MODELED   data-center noise pressure (MW benchmark)

Output: web/surfaces.json  { bbox, nx, ny, surfaces: [ {id,label,kind,unit,color,grid[]} ] }
grid is a flat row-major list of 0..1 normalized intensities (null-free).

Run:  /opt/anaconda3/bin/python3 pull/build_surfaces.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import model  # noqa: E402

KITR = ROOT / "data" / "raw" / "kit"
OUT = ROOT / "web" / "surfaces.json"

# Massachusetts bounding box
LAT0, LAT1 = 41.20, 42.90
LON0, LON1 = -73.55, -69.90
NX, NY = 150, 80          # grid resolution (12k cells — smooth but light)

cfg = model.load_config()

# grid cell centers
lons = np.linspace(LON0, LON1, NX)
lats = np.linspace(LAT0, LAT1, NY)
glon, glat = np.meshgrid(lons, lats)   # (NY, NX)


def idw(src_lat, src_lon, src_val, power=3.0, floor_km=2.0):
    """Inverse-distance-weighted field from point sources onto the grid.

    Higher `power` + smaller `floor_km` = tighter, more local falloff, so the
    field spreads as soft gradients around real sources instead of a flat slab.
    """
    src_lat = np.asarray(src_lat, float)
    src_lon = np.asarray(src_lon, float)
    src_val = np.asarray(src_val, float)
    acc = np.zeros_like(glat)
    wsum = np.zeros_like(glat)
    for la, lo, v in zip(src_lat, src_lon, src_val):
        # rough km: 1 deg lat ~111km, lon scaled by cos(lat)
        dlat = (glat - la) * 111.0
        dlon = (glon - lo) * 111.0 * np.cos(np.radians(glat))
        d = np.sqrt(dlat**2 + dlon**2)
        d = np.maximum(d, floor_km)
        w = 1.0 / d**power
        acc += w * v
        wsum += w
    field = np.where(wsum > 0, acc / wsum, 0.0)
    return field


def normalize(field):
    """Rank-equalize to spread values across the FULL 0..1 range.

    Percentile-clipping left ~50% of cells in a muddy mid-band (the 'flat block'
    look). Ranking every cell gives a uniform spread, so minimal differences in
    the source data become visible contrast on the map.
    """
    flat = field.ravel()
    order = flat.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(len(flat))
    eq = ranks / (len(flat) - 1)          # 0..1 uniform
    eq = eq.reshape(field.shape)
    # gamma < 1 lifts the low end so the whole state shows soft color,
    # but a high-end boost keeps hotspots distinct
    return np.clip(eq ** 0.85, 0, 1)


MA_TOWNS = {
    "Brookfield": (42.21, -72.10), "Westfield": (42.13, -72.75), "Lowell": (42.64, -71.32),
    "Boston": (42.36, -71.06), "Worcester": (42.26, -71.80), "Springfield": (42.10, -72.59),
    "Fall River": (41.70, -71.15), "New Bedford": (41.64, -70.93), "Chicopee": (42.15, -72.61),
    "Pittsfield": (42.45, -73.25), "Greenfield": (42.59, -72.60), "Easthampton": (42.27, -72.67),
    "Cambridge": (42.37, -71.11), "Quincy": (42.25, -71.00), "Lynn": (42.47, -70.95),
    "Brockton": (42.08, -71.02), "Framingham": (42.28, -71.42), "Haverhill": (42.78, -71.08),
}

surfaces = []


# ---- MEASURED: EJ burden (population-weighted) — the dense real wave --------
ej = pd.read_csv(KITR / "ej" / "data.csv")
# geocode EJ rows by municipality centroid (town-level); weight by population.
ej["pop"] = pd.to_numeric(ej["population"], errors="coerce").fillna(0)
lats_ej, lons_ej, vals_ej = [], [], []
# aggregate population to town, then place at town centroid
agg = ej.groupby("municipality")["pop"].sum()
# use MassGIS town list we have coords for, else skip (keeps it honest/simple)
for town, pop in agg.items():
    c = MA_TOWNS.get(str(town))
    if c and pop > 0:
        lats_ej.append(c[0]); lons_ej.append(c[1]); vals_ej.append(float(pop))
ej_field = normalize(idw(lats_ej, lons_ej, vals_ej, power=1.6, floor_km=6))
surfaces.append({"id": "ej_burden", "label": "People — EJ population density",
                 "kind": "measured", "unit": "pop. intensity", "color": "#d94f70",
                 "grid": [round(float(x), 3) for x in ej_field.ravel()],
                 "source": "MassGIS EJ2020 block groups (town-aggregated)"})


# ---- MEASURED: air — fossil-plant proximity intensity ----------------------
FOSSIL = [
    (42.3959, -71.0712, 95000), (42.2450, -70.9570, 60000), (41.7730, -70.5090, 70000),
    (42.1080, -72.6200, 40000), (41.1680, -73.1790, 55000),
]
air_field = normalize(idw([f[0] for f in FOSSIL], [f[1] for f in FOSSIL],
                          [f[2] for f in FOSSIL], power=2.0, floor_km=5))
surfaces.append({"id": "air_fossil", "label": "Air — fossil-plant intensity",
                 "kind": "measured", "unit": "rel. intensity", "color": "#e4572e",
                 "grid": [round(float(x), 3) for x in air_field.ravel()],
                 "source": "EPA CAMPD plant locations (emissions proxy)"})


# ---- MEASURED: energy demand pressure near load centers --------------------
# biggest MA load centers weighted by population rank (Boston heaviest)
LOAD = [(42.36, -71.06, 10), (42.26, -71.80, 5), (42.10, -72.59, 4),
        (42.64, -71.32, 3), (41.70, -71.15, 3), (42.08, -71.02, 2)]
energy_field = normalize(idw([l[0] for l in LOAD], [l[1] for l in LOAD],
                             [l[2] for l in LOAD], power=1.8, floor_km=7))
surfaces.append({"id": "energy_demand", "label": "Energy — grid demand pressure",
                 "kind": "measured", "unit": "rel. demand", "color": "#f3c13a",
                 "grid": [round(float(x), 3) for x in energy_field.ravel()],
                 "source": "ISO-NE load centers (population-weighted)"})


# ---- MODELED: data-center water + noise pressure ---------------------------
dcs = pd.read_csv(ROOT / "data" / "clean" / "datacenters.csv")
dc_lat = dcs.lat.tolist(); dc_lon = dcs.lon.tolist()
dc_mw = dcs.peak_mw_high.tolist()
b = cfg["impact_benchmarks"]
water_vals = [mw * 0.85 * 8760 * b["water_gal_per_mwh"] for mw in dc_mw]
noise_vals = [mw for mw in dc_mw]
water_field = normalize(idw(dc_lat, dc_lon, water_vals, power=2.2, floor_km=3))
noise_field = normalize(idw(dc_lat, dc_lon, noise_vals, power=2.6, floor_km=2))
surfaces.append({"id": "water_stress", "label": "Water — cooling demand (modeled)",
                 "kind": "modeled", "unit": "rel. pressure", "color": "#5aa9e6",
                 "grid": [round(float(x), 3) for x in water_field.ravel()],
                 "source": "data-center MW × water benchmark"})
surfaces.append({"id": "noise", "label": "Noise — generator/cooling (modeled)",
                 "kind": "modeled", "unit": "rel. pressure", "color": "#b084f3",
                 "grid": [round(float(x), 3) for x in noise_field.ravel()],
                 "source": "data-center MW × noise benchmark"})


out = {"bbox": [LON0, LAT0, LON1, LAT1], "nx": NX, "ny": NY, "surfaces": surfaces}
OUT.write_text(json.dumps(out))
print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
for s in surfaces:
    g = np.array(s["grid"])
    print(f"  [{s['kind']:8}] {s['id']:14} min {g.min():.2f} max {g.max():.2f} mean {g.mean():.2f}  {s['label']}")
