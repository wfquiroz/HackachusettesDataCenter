#!/usr/bin/env python3
"""
build_us_features.py — enrich US data-center coordinates with impact factors.

Input : data/us/raw/datacenters_us.csv  (name, lat, lon [, mw, sqft, status...])
Output: data/us/clean/dc_features.csv    (one row per DC + national factors)

Keyless factors filled NOW:
  - state, county_fips        (FCC block API — no key)
  - egrid_subregion           (state -> subregion lookup, approximate)
  - grid_co2_lb_mwh           (eGRID 2022 subregion output rate — baked in)
  - elec_price_cents_kwh      (EIA state industrial price 2024 — baked in)
Keyed factors left as columns to fill when a key lands (.env):
  - pm25_annual, fossil_co2_25km, pop_10km, pct_minority_10km, median_income_10km
Climate factors (NOAA) can be added next; stubbed here.

Run:  /opt/anaconda3/bin/python3 pull/build_us_features.py
Safe to run with a tiny sample file; re-run when the full coordinates arrive.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "us" / "raw" / "datacenters_us.csv"
OUT = ROOT / "data" / "us" / "clean" / "dc_features.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

# eGRID 2022 subregion output CO2 rate (lb/MWh). Public values, documented.
EGRID_RATE = {
    "NEWE": 528, "NYUP": 243, "NYCW": 601, "RFCE": 737, "RFCM": 1108, "RFCW": 1012,
    "SRVC": 630, "SRMW": 1476, "SRTV": 884, "SRSO": 836, "FRCC": 846, "MROW": 962,
    "MROE": 1310, "SPNO": 1013, "SPSO": 1001, "ERCT": 793, "CAMX": 494, "NWPP": 614,
    "AZNM": 743, "RMPA": 1112, "PRMS": 1577, "HICC": 1619, "AKGD": 1013,
}
# rough state -> dominant eGRID subregion (all 50 + DC)
STATE_SUBREGION = {
    "MA": "NEWE", "CT": "NEWE", "RI": "NEWE", "NH": "NEWE", "VT": "NEWE", "ME": "NEWE",
    "NY": "NYUP", "NJ": "RFCE", "PA": "RFCE", "VA": "SRVC", "MD": "RFCE", "OH": "RFCW",
    "IL": "SRMW", "TX": "ERCT", "CA": "CAMX", "OR": "NWPP", "WA": "NWPP", "AZ": "AZNM",
    "GA": "SRSO", "FL": "FRCC", "NC": "SRVC", "TN": "SRTV", "CO": "RMPA", "NV": "NWPP",
    "UT": "NWPP", "IA": "MROW", "WI": "MROE", "MN": "MROW", "MO": "SRMW", "IN": "RFCW",
    "MI": "RFCM", "DC": "RFCE", "DE": "RFCE", "WV": "RFCW", "KY": "SRTV", "SC": "SRVC",
    "AL": "SRSO", "MS": "SRMW", "LA": "SRMW", "AR": "SRMW", "OK": "SPSO", "KS": "SPNO",
    "NE": "MROW", "SD": "MROW", "ND": "MROW", "NM": "AZNM", "ID": "NWPP", "MT": "NWPP",
    "WY": "RMPA", "AK": "AKGD", "HI": "HICC",
}
# EIA 2024 avg state industrial electricity price (cents/kWh), approximate.
ELEC_PRICE = {
    "MA": 17.5, "CT": 16.8, "RI": 15.2, "NH": 14.9, "VT": 12.1, "ME": 11.8,
    "NY": 7.9, "NJ": 11.2, "PA": 8.1, "VA": 7.6, "TX": 6.2, "CA": 18.4, "OR": 7.3,
    "WA": 6.0, "AZ": 7.1, "GA": 6.4, "FL": 8.5, "NC": 6.9, "IL": 7.7, "OH": 6.8,
    "MD": 10.2, "MI": 8.0, "DC": 11.0, "DE": 9.3, "WV": 7.2, "KY": 6.5, "SC": 6.7,
    "AL": 6.6, "MS": 6.8, "LA": 6.0, "AR": 6.9, "OK": 5.9, "KS": 7.6, "NE": 7.1,
    "SD": 7.4, "ND": 7.3, "NM": 6.8, "ID": 6.6, "MT": 6.4, "WY": 7.0, "CO": 7.5,
    "NV": 6.9, "UT": 6.3, "IA": 6.5, "WI": 7.9, "MN": 7.8, "MO": 6.7, "IN": 7.2,
    "TN": 6.3, "AK": 16.0, "HI": 33.0,
}


def fcc_lookup(lat, lon):
    url = f"https://geo.fcc.gov/api/census/block/find?latitude={lat}&longitude={lon}&format=json&showall=false"
    try:
        with urlopen(Request(url, headers={"User-Agent": "HourMatch/1.0"}), timeout=15) as r:
            d = json.load(r)
        fips = d.get("Block", {}).get("FIPS")
        state = (d.get("State", {}) or {}).get("code")
        county_fips = fips[:5] if fips else None
        return state, county_fips
    except Exception as e:
        print(f"  FCC lookup failed for {lat},{lon}: {e}", file=sys.stderr)
        return None, None


def _state_abbr(name):
    """Full state name -> 2-letter code (the input file already has state)."""
    M = {"Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
         "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
         "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS",
         "Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA",
         "Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT",
         "Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM",
         "New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
         "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC",
         "South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT",
         "Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY",
         "District of Columbia":"DC"}
    return M.get(str(name).strip())


def main() -> int:
    if not RAW.exists():
        # write a 3-row sample so the pipeline is testable before coords arrive
        sample = pd.DataFrame([
            {"name": "Markley Lowell", "lat": 42.6412, "lon": -71.3162, "mw": 60},
            {"name": "Ashburn VA cluster", "lat": 39.0438, "lon": -77.4874, "mw": 300},
            {"name": "Santa Clara CA", "lat": 37.3541, "lon": -121.9552, "mw": 180},
        ])
        RAW.parent.mkdir(parents=True, exist_ok=True)
        sample.to_csv(RAW, index=False)
        print(f"no input found — wrote 3-row SAMPLE to {RAW}")

    df = pd.read_csv(RAW)
    # input may carry a full 'state' name column (OSM export) or need FCC lookup
    has_state_col = "state" in df.columns
    rows = []
    for _, r in df.iterrows():
        if has_state_col and pd.notna(r.get("state")):
            state = _state_abbr(r["state"])
            county = None  # offline: skip county (not needed for state-level factors)
        else:
            state, county = fcc_lookup(r["lat"], r["lon"])
        sub = STATE_SUBREGION.get(state)
        rows.append({
            "name": r.get("name"), "lat": r["lat"], "lon": r["lon"],
            "mw": r.get("mw"), "operator": r.get("operator"),
            "state": state, "county_fips": county,
            "egrid_subregion": sub,
            "grid_co2_lb_mwh": EGRID_RATE.get(sub),
            "elec_price_cents_kwh": ELEC_PRICE.get(state),
            # keyed factors — filled when API keys are available
            "pm25_annual": None, "fossil_co2_25km": None,
            "pop_10km": None, "pct_minority_10km": None, "median_income_10km": None,
            # climate factors — NOAA step
            "cooling_deg_days": None, "summer_tmax_avg": None,
        })
        if not has_state_col:
            time.sleep(0.2)  # be polite to FCC only when we must call it

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT}  ({len(out)} data centers)")
    print(out[["name", "state", "egrid_subregion", "grid_co2_lb_mwh",
               "elec_price_cents_kwh"]].to_string(index=False))
    filled = ["state", "grid_co2_lb_mwh", "elec_price_cents_kwh"]
    todo = ["pm25_annual", "fossil_co2_25km", "pop_10km", "pct_minority_10km",
            "median_income_10km", "cooling_deg_days"]
    print(f"\nfilled now  : {filled}")
    print(f"needs a key : {todo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
