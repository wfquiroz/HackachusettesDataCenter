#!/usr/bin/env python3
"""
predict.py — hypothetical-MA impact + placement optimization.

MVP: predict(lat, lon, mw) -> per-factor impact for a hypothetical MA data center.
Stretch: sweep the predict over a MA grid -> a PLACEMENT surface (green=good site,
red=bad), driven by the SAME feature weights, read as "where should it go".

Design note — honest about data size:
  With only a handful of US data centers, a fully TRAINED model overfits. So the
  engine is a TRANSPARENT weighted score now, with weights that are the stand-in
  for learned feature importances (config: placement_weights + impact drivers).
  When enough real rows exist, train.py replaces `_feature_importances()` with
  the model's real importances and predict() calls the trained estimator — the
  app and the API do not change.

Run:  /opt/anaconda3/bin/python3 us_model/predict.py        # sample + self-test
      /opt/anaconda3/bin/python3 us_model/predict.py sweep  # write MA placement surface
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

cfg = model.load_config()
grid = model.load_grid()

# eGRID subregion carbon used to weight "grid dirtiness" of a MA location.
NEWE_RATE = 528.0  # lb CO2/MWh, all of MA is NEWE


# --- feature importances (stand-in for the trained model's; see docstring) ---
def feature_importances() -> dict:
    """What drives a data center's local impact. Sums to 1.

    These are the hand-set weights that become the TRAINED model's feature
    importances once the US dataset is large enough. Keep them in one place so
    the optimization story ('impact is driven mostly by grid carbon + people')
    reads straight off this dict.
    """
    return {
        "grid_carbon": 0.34,    # how dirty the power it pulls is
        "people_near": 0.29,    # population / EJ burden exposed
        "water_stress": 0.16,   # local water pressure
        "existing_fossil": 0.13, # already-polluted air nearby
        "grid_headroom": 0.08,  # transmission presence (proxy)
    }


# --- per-location factor lookups (reuse the MA surfaces we already built) -----
def _load_surfaces():
    s = json.loads((ROOT / "web" / "surfaces.json").read_text())
    idx = {x["id"]: np.array(x["grid"]).reshape(s["ny"], s["nx"]) for x in s["surfaces"]}
    return s, idx


SURF_META, SURF = _load_surfaces()


def _sample_surface(sid, lat, lon):
    """Read a 0..1 surface value at a lat/lon (bilinear-ish nearest)."""
    lon0, lat0, lon1, lat1 = SURF_META["bbox"]
    nx, ny = SURF_META["nx"], SURF_META["ny"]
    fx = (lon - lon0) / (lon1 - lon0)
    fy = (lat - lat0) / (lat1 - lat0)
    if not (0 <= fx <= 1 and 0 <= fy <= 1):
        return None
    x = min(nx - 1, int(fx * (nx - 1)))
    y = min(ny - 1, int(fy * (ny - 1)))
    return float(SURF[sid][y, x])


def predict(lat: float, lon: float, mw: float) -> dict:
    """Predicted impact of a hypothetical MA data center at (lat,lon) of size mw.

    Returns per-factor 0..1 intensities, an overall impact score (0..100,
    higher = worse), the size-scaled physical estimates, and a confidence band.
    """
    people = _sample_surface("ej_burden", lat, lon)
    fossil = _sample_surface("air_fossil", lat, lon)
    water = _sample_surface("water_stress", lat, lon)
    energy = _sample_surface("energy_demand", lat, lon)
    if people is None:
        return {"error": "outside Massachusetts bbox"}

    # size factor: bigger DC = bigger footprint, saturating
    size = float(np.clip(mw / 300.0, 0.1, 1.5))

    fi = feature_importances()
    # grid carbon is ~constant across MA (all NEWE); use normalized demand as
    # the local 'how stressed is this grid node' proxy
    comps = {
        "grid_carbon": (NEWE_RATE / 1500.0) * 0.6 + 0.4 * energy,
        "people_near": people,
        "water_stress": water,
        "existing_fossil": fossil,
        "grid_headroom": 1.0 - energy,  # less loaded node = more headroom = lower impact
    }
    score01 = sum(fi[k] * comps[k] for k in fi) * (0.6 + 0.4 * size)
    score01 = float(np.clip(score01, 0, 1))

    # physical size-scaled estimates (same benchmarks as the app)
    b = cfg["impact_benchmarks"]
    e_mwh = mw * cfg["defaults"]["load_factor"] * 8760
    res = model.hourly_match(peak_mw=mw, w_solar=1, w_onshore=0, w_offshore=0,
                             df=grid, cfg=cfg)

    # confidence band widens with fewer data points behind the estimate
    band = 0.12  # +/- on score01; shrinks when a trained model replaces this
    return {
        "lat": lat, "lon": lon, "mw": mw,
        "impact_score": round(100 * score01, 1),
        "impact_score_low": round(100 * max(0, score01 - band), 1),
        "impact_score_high": round(100 * min(1, score01 + band), 1),
        "factors": {k: round(v, 3) for k, v in comps.items()},
        "weights": fi,
        "hidden_co2_t_yr": round(res.hidden_co2_t),
        "hourly_match_pct": round(res.hourly_match_pct),
        "water_mgal_yr": round(e_mwh * b["water_gal_per_mwh"] / 1e6, 1),
        "noise_radius_m": round(b["noise_audible_radius_m_per_100mw"] * mw / 100),
        "basis": "weighted score (stand-in for trained feature importances)",
    }


def sweep_placement(mw: float = 150.0):
    """Score every MA grid cell -> placement surface. Lower score = better site."""
    lon0, lat0, lon1, lat1 = SURF_META["bbox"]
    nx, ny = SURF_META["nx"], SURF_META["ny"]
    out = np.zeros((ny, nx))
    for y in range(ny):
        lat = lat0 + (lat1 - lat0) * y / (ny - 1)
        for x in range(nx):
            lon = lon0 + (lon1 - lon0) * x / (nx - 1)
            p = predict(lat, lon, mw)
            out[y, x] = p.get("impact_score", 0) / 100.0
    # placement GOODNESS = 1 - impact (so green = build here)
    good = 1.0 - out
    surf = {
        "bbox": SURF_META["bbox"], "nx": nx, "ny": ny,
        "surfaces": [{
            "id": "placement", "label": f"Placement score — {int(mw)} MW (green = better)",
            "kind": "modeled", "unit": "suitability",
            "color": "#2f9e44",
            "grid": [round(float(v), 3) for v in good.ravel()],
            "source": "HourMatch optimization — feature-weighted impact score",
        }],
    }
    p = ROOT / "web" / "placement.json"
    p.write_text(json.dumps(surf))
    print(f"wrote {p}  (sweep at {mw} MW)")
    print(f"  best cell goodness {good.max():.2f}  worst {good.min():.2f}")


def _selftest():
    tests = {
        "rural west (Pittsfield)": (42.45, -73.25),
        "metro Boston": (42.36, -71.06),
        "Lowell": (42.64, -71.32),
    }
    print("predict() self-test at 150 MW:\n")
    for name, (la, lo) in tests.items():
        p = predict(la, lo, 150)
        print(f"  {name:24} impact {p['impact_score']:5.1f} "
              f"[{p['impact_score_low']}-{p['impact_score_high']}]  "
              f"people {p['factors']['people_near']:.2f}")
    print("\nfeature importances (what drives impact):")
    for k, v in feature_importances().items():
        print(f"  {k:16} {v:.0%}")
    # sanity: metro Boston should score worse than rural west
    assert predict(42.36, -71.06, 150)["impact_score"] > predict(42.45, -73.25, 150)["impact_score"]
    print("\nSANITY PASS: metro Boston impact > rural west impact")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        sweep_placement(float(sys.argv[2]) if len(sys.argv) > 2 else 150.0)
    else:
        _selftest()
