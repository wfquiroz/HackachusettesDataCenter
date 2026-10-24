#!/usr/bin/env python3
"""
pull_eia.py  --  Step 1 of the HourMatch build.

Reads the two EIA-930 six-month BALANCE CSVs, keeps only Balancing Authority
ISNE (ISO New England), combines them into one hourly 2024 table with demand
and generation by fuel, fills small gaps, and writes data/clean/isne_hourly_2024.csv.

Column source: we use the EIA "(Adjusted)" series where present (EIA's own
cleaned numbers), falling back to the base column when a row has no adjusted value.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
CLEAN = Path(__file__).resolve().parent.parent / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

FILES = ["EIA930_BALANCE_2024_Jan_Jun.csv", "EIA930_BALANCE_2024_Jul_Dec.csv"]
BA = "ISNE"

# output column  ->  (adjusted name, base name)
FUELS = {
    "gen_coal":   ("Net Generation (MW) from Coal (Adjusted)",
                   "Net Generation (MW) from Coal"),
    "gen_ng":     ("Net Generation (MW) from Natural Gas (Adjusted)",
                   "Net Generation (MW) from Natural Gas"),
    "gen_nuc":    ("Net Generation (MW) from Nuclear (Adjusted)",
                   "Net Generation (MW) from Nuclear"),
    "gen_oil":    ("Net Generation (MW) from All Petroleum Products (Adjusted)",
                   "Net Generation (MW) from All Petroleum Products"),
    "gen_hydro":  ("Net Generation (MW) from Hydropower and Pumped Storage (Adjusted)",
                   "Net Generation (MW) from Hydropower and Pumped Storage"),
    "gen_solar":  ("Net Generation (MW) from Solar (Adjusted)",
                   "Net Generation (MW) from Solar"),
    "gen_wind":   ("Net Generation (MW) from Wind (Adjusted)",
                   "Net Generation (MW) from Wind"),
    "gen_other":  ("Net Generation (MW) from Other Fuel Sources (Adjusted)",
                   "Net Generation (MW) from Other Fuel Sources"),
}
DEMAND = ("Demand (MW) (Adjusted)", "Demand (MW)")
TS = "UTC Time at End of Hour"


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Return a numeric Series for `name`, or an all-NaN Series if absent."""
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(float("nan"), index=df.index, dtype="float64")


def _coalesce(df: pd.DataFrame, adjusted: str, base: str) -> pd.Series:
    return _col(df, adjusted).fillna(_col(df, base))


def load_one(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df[df["Balancing Authority"] == BA].copy()
    out = pd.DataFrame()
    out["ts_utc"] = pd.to_datetime(df[TS], utc=True, errors="coerce")
    out["demand_mw"] = _coalesce(df, *DEMAND)
    for col, (adj, base) in FUELS.items():
        out[col] = _coalesce(df, adj, base)
    return out


def main() -> int:
    frames = []
    for f in FILES:
        p = RAW / f
        if not p.exists():
            print(f"MISSING: {p}", file=sys.stderr)
            return 1
        frames.append(load_one(p))
        print(f"loaded {f}: {len(frames[-1]):,} ISNE rows")

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["ts_utc"]).drop_duplicates("ts_utc").sort_values("ts_utc")
    df = df.set_index("ts_utc")

    # Build the complete 2024 hourly index (UTC) and find gaps.
    full = pd.date_range("2024-01-01 00:00", "2024-12-31 23:00", freq="h", tz="UTC")
    missing_before = full.difference(df.index)
    df = df.reindex(full)

    # Forward-fill small gaps (<=3 h); back-fill a leading gap at the series start.
    df = df.ffill(limit=3).bfill(limit=6)
    still = df["demand_mw"].isna().sum()

    # Negative generation -> clamp to 0 (small sensor noise); demand left as-is.
    gen_cols = list(FUELS.keys())
    neg = (df[gen_cols] < 0).sum().sum()
    df[gen_cols] = df[gen_cols].clip(lower=0)
    # Remaining fuel NaN = EIA reported no generation for that fuel that hour = 0.
    fuel_nan = int(df[gen_cols].isna().sum().sum())
    df[gen_cols] = df[gen_cols].fillna(0.0)

    df.index.name = "ts_utc"
    out_path = CLEAN / "isne_hourly_2024.csv"
    df.round(2).to_csv(out_path)

    print("\n=== SUMMARY ===")
    print(f"rows written          : {len(df):,}  (expected 8784 — 2024 is a leap year)")
    print(f"hours missing in raw  : {len(missing_before):,}")
    print(f"still-NaN after ffill : {still}")
    print(f"negative gen clamped  : {int(neg)} cells")
    print(f"fuel NaN -> 0 filled  : {fuel_nan} cells")
    if len(missing_before):
        print("first missing hours   :", [str(t) for t in missing_before[:5]])
    print(f"written to            : {out_path}")
    print("\n=== FIRST ROWS ===")
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(df.head(5).round(1).to_string())
    print("\n=== DEMAND / SOLAR SANITY ===")
    print(f"demand  min/mean/max : {df.demand_mw.min():.0f} / {df.demand_mw.mean():.0f} / {df.demand_mw.max():.0f} MW")
    print(f"solar   min/mean/max : {df.gen_solar.min():.0f} / {df.gen_solar.mean():.0f} / {df.gen_solar.max():.0f} MW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
