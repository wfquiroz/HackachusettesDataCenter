#!/usr/bin/env python3
"""
enrich_keyless.py — add REAL keyless factors to dc_features.csv.

No API key needed:
  - pop_density_proxy : distance to nearest major US city (inverse) — a people-
    nearby proxy from a bundled list of the ~60 largest US cities.
  - nearest_city / nearest_city_km
  - cooling_proxy     : latitude-based cooling-load proxy (hotter south = more
    cooling water/energy). Stand-in for NOAA cooling degree days.
  - dc_density_25km   : how many OTHER data centers within 25 km (clustering —
    a real spatial feature straight from the coordinates).

These join the already-filled grid_co2 + elec_price, giving the model a genuinely
multi-factor real feature set without waiting on EPA/Census keys.

Run:  /opt/anaconda3/bin/python3 pull/enrich_keyless.py
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FEAT = ROOT / "data" / "us" / "clean" / "dc_features.csv"

# ~60 largest US cities (name, lat, lon, population) — public, bundled.
CITIES = [
    ("New York", 40.71, -74.01, 8336817), ("Los Angeles", 34.05, -118.24, 3979576),
    ("Chicago", 41.88, -87.63, 2693976), ("Houston", 29.76, -95.37, 2320268),
    ("Phoenix", 33.45, -112.07, 1680992), ("Philadelphia", 39.95, -75.17, 1584064),
    ("San Antonio", 29.42, -98.49, 1547253), ("San Diego", 32.72, -117.16, 1423851),
    ("Dallas", 32.78, -96.80, 1343573), ("San Jose", 37.34, -121.89, 1021795),
    ("Austin", 30.27, -97.74, 978908), ("Jacksonville", 30.33, -81.66, 911507),
    ("Fort Worth", 32.76, -97.33, 909585), ("Columbus", 39.96, -82.99, 898553),
    ("Charlotte", 35.23, -80.84, 885708), ("San Francisco", 37.77, -122.42, 881549),
    ("Indianapolis", 39.77, -86.16, 876384), ("Seattle", 47.61, -122.33, 753675),
    ("Denver", 39.74, -104.99, 727211), ("Washington", 38.91, -77.04, 705749),
    ("Boston", 42.36, -71.06, 692600), ("Nashville", 36.16, -86.78, 670820),
    ("Detroit", 42.33, -83.05, 670031), ("Portland", 45.52, -122.68, 654741),
    ("Las Vegas", 36.17, -115.14, 651319), ("Atlanta", 33.75, -84.39, 506811),
    ("Miami", 25.76, -80.19, 467963), ("Minneapolis", 44.98, -93.27, 429606),
    ("Kansas City", 39.10, -94.58, 508090), ("Sacramento", 38.58, -121.49, 513624),
    ("Salt Lake City", 40.76, -111.89, 200567), ("Richmond", 37.54, -77.44, 230436),
    ("Columbus OH", 39.96, -82.99, 898553), ("Omaha", 41.26, -95.93, 486051),
    ("Raleigh", 35.78, -78.64, 467665), ("Cheyenne", 41.14, -104.82, 65132),
    ("Des Moines", 41.59, -93.60, 214133), ("Reno", 39.53, -119.81, 264165),
    ("Phoenix AZ", 33.45, -112.07, 1680992), ("Tucson", 32.22, -110.97, 542629),
]


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def main():
    df = pd.read_csv(FEAT)
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()

    # nearest major city + a population-weighted proximity (people-nearby proxy)
    clat = np.array([c[1] for c in CITIES])
    clon = np.array([c[2] for c in CITIES])
    cpop = np.array([c[3] for c in CITIES], dtype=float)
    nearest_km = np.full(len(df), np.nan)
    nearest_name = [""] * len(df)
    pop_proxy = np.zeros(len(df))
    for i in range(len(df)):
        d = haversine(lat[i], lon[i], clat, clon)
        j = int(np.argmin(d))
        nearest_km[i] = d[j]
        nearest_name[i] = CITIES[j][0]
        # inverse-distance-weighted city population within 150 km
        w = np.where(d < 150, cpop / np.maximum(d, 5) ** 1.5, 0)
        pop_proxy[i] = w.sum()

    # cooling proxy: hotter (lower latitude) = more cooling load. 0..1
    cooling = np.clip((45.0 - lat) / (45.0 - 25.0), 0, 1)

    # data-center clustering: how many OTHER DCs within 25 km
    dc_density = np.zeros(len(df), dtype=int)
    for i in range(len(df)):
        d = haversine(lat[i], lon[i], lat, lon)
        dc_density[i] = int((d < 25).sum() - 1)

    df["pop_proxy"] = np.round(pop_proxy, 1)
    df["nearest_city"] = nearest_name
    df["nearest_city_km"] = np.round(nearest_km, 1)
    df["cooling_proxy"] = np.round(cooling, 3)
    df["dc_density_25km"] = dc_density
    df.to_csv(FEAT, index=False)

    print(f"enriched {len(df)} rows (keyless) -> {FEAT}")
    print(f"  pop_proxy        mean {df.pop_proxy.mean():,.0f}")
    print(f"  nearest_city_km  mean {df.nearest_city_km.mean():.0f} km")
    print(f"  cooling_proxy    mean {df.cooling_proxy.mean():.2f}")
    print(f"  dc_density_25km  mean {df.dc_density_25km.mean():.1f}  max {df.dc_density_25km.max()}")
    print("\nmost-clustered data centers:")
    top = df.nlargest(5, "dc_density_25km")[["name", "state", "dc_density_25km"]]
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
