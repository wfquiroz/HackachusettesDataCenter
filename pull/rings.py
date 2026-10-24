#!/usr/bin/env python3
"""
rings.py — radius-of-impact + buildout timeline for a dropped data center.

Given a dropped site (lat, lon, target_mw, buildout_years) and a year, return:
  - ring geometry (1/3/5/10/25 km)
  - REAL counts inside each ring: population, EJ block groups, fossil plants
  - MODELED impact intensity that decays with distance and GROWS as MW ramps

"Press play" = step `year` from 1..N. MW ramps up each year (phased buildout,
which is how large campuses are actually permitted), so the rings fill in and
intensify over time. Labeled projected buildout, NOT measured history.

Precomputes EJ polygon centroids once -> web/ej_centroids.json (small).

Run:  /opt/anaconda3/bin/python3 pull/rings.py            # build centroids + self-test
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import model  # noqa: E402

GEO = ROOT / "data" / "clean" / "geo" / "ej_blockgroups.geojson"
EJC = ROOT / "web" / "ej_centroids.json"
RINGS_KM = [1, 3, 5, 10, 25]


def _poly_centroid(geom):
    """Rough centroid of a GeoJSON Polygon/MultiPolygon (average of outer ring)."""
    try:
        if geom["type"] == "Polygon":
            ring = geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            ring = geom["coordinates"][0][0]
        else:
            return None
        arr = np.array(ring)
        return float(arr[:, 1].mean()), float(arr[:, 0].mean())  # lat, lon
    except Exception:
        return None


def build_centroids():
    d = json.loads(GEO.read_text())
    pts = []
    for f in d["features"]:
        c = _poly_centroid(f.get("geometry") or {})
        if not c:
            continue
        p = f["properties"]
        pts.append({
            "lat": round(c[0], 4), "lon": round(c[1], 4),
            "pop": float(p.get("TOTAL_POP") or 0),
            "minority_pct": float(p.get("PCT_MINORITY") or 0),
            "town": p.get("MUNICIPALITY"),
        })
    EJC.write_text(json.dumps(pts))
    print(f"wrote {EJC}  ({len(pts)} EJ centroids)")
    return pts


def _load_centroids():
    if not EJC.exists():
        return build_centroids()
    return json.loads(EJC.read_text())


EJ = _load_centroids()
_ej_lat = np.array([e["lat"] for e in EJ])
_ej_lon = np.array([e["lon"] for e in EJ])
_ej_pop = np.array([e["pop"] for e in EJ])
_ej_min = np.array([e["minority_pct"] for e in EJ])

FOSSIL = [(42.3959, -71.0712), (42.2450, -70.9570), (41.7730, -70.5090),
          (42.1080, -72.6200)]


def _km(lat, lon, alat, alon):
    dlat = (alat - lat) * 111.0
    dlon = (alon - lon) * 111.0 * np.cos(np.radians(lat))
    return np.sqrt(dlat**2 + dlon**2)


def impact_timeline(lat, lon, target_mw, buildout_years=5):
    """Return per-year rings for the 'press play' animation."""
    d = _km(lat, lon, _ej_lat, _ej_lon)
    grid = model.load_grid()          # load ONCE, not per year
    cfg = model.load_config()

    # Sample the LOCAL impact surfaces so air & water vary by location.
    # 0..1 surface value -> a multiplier centred on 1.0 (clean spot ~0.7x,
    # dirty/stressed spot ~1.5x). Makes the same MW hurt more in a bad place.
    def _surf_mult(sid, lo=0.7, hi=1.5):
        try:
            s = json.loads((ROOT / "web" / "surfaces.json").read_text())
            nx, ny = s["nx"], s["ny"]; lon0, la0, lon1, la1 = s["bbox"]
            g = next(x["grid"] for x in s["surfaces"] if x["id"] == sid)
            fx = (lon - lon0) / (lon1 - lon0); fy = (lat - la0) / (la1 - la0)
            if not (0 <= fx <= 1 and 0 <= fy <= 1):
                return 1.0
            v = g[min(ny - 1, int(fy * (ny - 1))) * nx + min(nx - 1, int(fx * (nx - 1)))]
            return lo + (hi - lo) * v
        except Exception:
            return 1.0
    carbon_mult = _surf_mult("air_fossil")
    water_mult = _surf_mult("water_stress")

    years = []
    for yr in range(1, buildout_years + 1):
        # phased ramp: MW comes online over the buildout period (S-curve-ish)
        frac = yr / buildout_years
        mw = target_mw * frac
        res = model.hourly_match(peak_mw=max(mw, 1), w_solar=1, w_onshore=0,
                                 w_offshore=0, df=grid, cfg=cfg)
        rings = []
        prev = 0
        for rk in RINGS_KM:
            inside = d <= rk
            band = inside & (d > prev)
            pop = float(_ej_pop[inside].sum())
            pop_band = float(_ej_pop[band].sum())
            minority = float(np.average(_ej_min[inside], weights=np.maximum(_ej_pop[inside], 1))) if inside.any() else 0
            fossil = sum(1 for fl, fo in FOSSIL if _km(lat, lon, fl, fo) <= rk)
            # modeled intensity: decays with distance, scales with MW online
            intensity = frac * float(np.exp(-(rk / 8.0)))
            rings.append({
                "km": rk, "pop_within": round(pop), "pop_in_band": round(pop_band),
                "minority_pct": round(minority, 1), "fossil_within": fossil,
                "intensity": round(intensity, 3),
            })
            prev = rk
        years.append({
            "year": yr, "mw_online": round(mw),
            "hidden_co2_t": round(res.hidden_co2_t),
            "hourly_match_pct": round(res.hourly_match_pct),
            "factors": model.four_factor_impact(res, cfg, max(mw, 1),
                        grid_carbon_mult=carbon_mult, water_stress_mult=water_mult),
            "rings": rings,
        })
    return {"lat": lat, "lon": lon, "target_mw": target_mw,
            "buildout_years": buildout_years, "years": years,
            "ring_km": RINGS_KM,
            "note": "Projected phased buildout, not measured history. "
                    "Ring counts (population, EJ, plants) are REAL; intensity is modeled."}


if __name__ == "__main__":
    build_centroids()
    # self-test on Westfield
    t = impact_timeline(42.1251, -72.7495, 274, 5)
    print(f"\nWestfield 274 MW over {t['buildout_years']} yrs:")
    for y in t["years"]:
        r25 = y["rings"][-1]
        print(f"  year {y['year']}: {y['mw_online']:>3} MW online · "
              f"{r25['pop_within']:>7,} people within 25km · "
              f"hidden CO2 {y['hidden_co2_t']:>7,} t")
