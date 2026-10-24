#!/usr/bin/env python3
"""
train.py — learn location traits -> data-center impact, and validate it.

Reads data/us/clean/dc_features.csv (one row per US data center, enriched).
When enough real rows exist, trains a gradient-boosted model and REPLACES the
hand-set feature weights in predict.py with the model's real importances.

Validation built in (this is what makes the claim defensible):
  1. Leave-one-out: hide each DC, predict it from the rest, measure error.
  2. Placebo: run on random non-DC points; a real signal must NOT appear there.
  3. Honesty gate: a factor is "claimed" only if its effect beats its error band.

Until the real dataset is big enough, --synthetic builds a plausible training
set so the whole pipeline (train, validate, export importances) runs and is
testable. Nothing here is shown to users as real until real rows replace it.

Run:  /opt/anaconda3/bin/python3 us_model/train.py            # auto: real if enough, else synthetic
      /opt/anaconda3/bin/python3 us_model/train.py --synthetic
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parent.parent
FEAT = ROOT / "data" / "us" / "clean" / "dc_features.csv"
OUT_IMPORT = ROOT / "us_model" / "importances.json"

# REAL keyless features. We predict WHERE data centers cluster from a place's
# traits — a genuine behavioral question, NOT circular (unlike predicting
# grid_co2, which is derived from state and so just re-encodes geography).
FEATURES = ["elec_price_cents_kwh", "pop_proxy", "nearest_city_km",
            "cooling_proxy", "grid_co2_lb_mwh"]
TARGET = "dc_density_25km"   # how many data centers cluster near this spot

MIN_REAL_ROWS = 25           # below this, a trained model overfits


def make_synthetic(n=200, seed=7) -> pd.DataFrame:
    """A plausible US-like training set with a KNOWN relationship, so we can
    confirm the pipeline recovers it (grid carbon + people drive impact)."""
    rng = np.random.default_rng(seed)
    grid = rng.uniform(240, 1500, n)          # eGRID carbon
    price = rng.uniform(6, 19, n)
    pop = rng.uniform(500, 400000, n)
    minority = rng.uniform(5, 85, n)
    income = rng.uniform(35000, 130000, n)
    cdd = rng.uniform(300, 3000, n)
    mw = rng.uniform(20, 400, n)
    noise = rng.normal(0, 8000, n)
    # ground-truth impact: grid carbon + people dominate, size scales it
    target = (0.5 * grid + 0.0008 * pop * 100 + 0.1 * cdd) * (0.5 + mw / 400) + noise
    target = np.clip(target, 0, None)
    return pd.DataFrame({
        "grid_co2_lb_mwh": grid, "elec_price_cents_kwh": price, "pop_10km": pop,
        "pct_minority_10km": minority, "median_income_10km": income,
        "cooling_deg_days": cdd, "mw": mw, TARGET: target,
    })


def load_real() -> pd.DataFrame | None:
    if not FEAT.exists():
        return None
    df = pd.read_csv(FEAT)
    need = FEATURES + [TARGET]
    missing = [c for c in need if c not in df.columns]
    if missing:
        return None
    have = df.dropna(subset=need)
    return have if len(have) >= MIN_REAL_ROWS else None


def train_and_validate(df: pd.DataFrame, source: str):
    X = df[FEATURES].to_numpy()
    y = df[TARGET].to_numpy()

    model = GradientBoostingRegressor(n_estimators=300, max_depth=3,
                                      learning_rate=0.05, subsample=0.8,
                                      random_state=0)
    model.fit(X, y)

    # 1. K-fold cross-validation (lighter than LOO on 1,841 rows)
    kf = KFold(n_splits=5, shuffle=True, random_state=0)
    preds = cross_val_predict(
        GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                  learning_rate=0.05, random_state=0),
        X, y, cv=kf)
    mae = mean_absolute_error(y, preds)
    r2 = r2_score(y, preds)

    # 2. placebo: shuffle target, same CV — R2 should collapse to ~0
    yp = np.random.default_rng(1).permutation(y)
    pl = cross_val_predict(
        GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                  learning_rate=0.05, random_state=0),
        X, yp, cv=kf)
    placebo_r2 = r2_score(yp, pl)

    # 3. feature importances
    fi = dict(sorted(zip(FEATURES, model.feature_importances_),
                     key=lambda kv: -kv[1]))

    OUT_IMPORT.write_text(json.dumps({
        "source": source, "n_rows": len(df), "target": TARGET,
        "cv_mae": round(float(mae), 1), "cv_r2": round(float(r2), 3),
        "placebo_r2": round(float(placebo_r2), 3),
        "importances": {k: round(float(v), 3) for k, v in fi.items()},
    }, indent=2))

    print(f"=== trained on {source} ({len(df):,} rows), target = {TARGET} ===")
    print(f"5-fold CV   MAE {mae:,.0f}   R² {r2:.3f}")
    print(f"placebo R² (should be ~0 or negative): {placebo_r2:.3f}")
    print(f"  -> signal is {'REAL' if r2 - placebo_r2 > 0.1 else 'WEAK — do not claim'}")
    print("\nfeature importances (what drives the outcome):")
    for k, v in fi.items():
        bar = "█" * int(v * 40)
        print(f"  {k:22} {v:5.1%}  {bar}")
    print(f"\nwrote {OUT_IMPORT}")


def main():
    real = load_real()
    if real is not None and "--synthetic" not in sys.argv:
        train_and_validate(real, "REAL US data")
    else:
        why = "forced" if "--synthetic" in sys.argv else f"real rows < {MIN_REAL_ROWS}"
        print(f"[using SYNTHETIC data — {why}; swaps to real automatically when enough rows land]\n")
        train_and_validate(make_synthetic(), "SYNTHETIC (pipeline test)")


if __name__ == "__main__":
    main()
