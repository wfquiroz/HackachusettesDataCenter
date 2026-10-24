#!/usr/bin/env python3
"""
model.py — HourMatch core model.

Three layers, all pure functions, all driven by data/clean/isne_hourly_2024.csv
and config.yaml:

  1. hourly_match()      — Section 5 of the brief. The meter.
  2. impact_estimate()   — energy/CO2 (real) + water/noise/diesel (benchmarked).
  3. placement_score()   — rank a candidate site/town for a new data center.

Nothing here reads the network. The app and tests import these functions.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
HOURLY_CSV = CLEAN / "isne_hourly_2024.csv"
CONFIG = ROOT / "config.yaml"

FUEL_COLS = ["gen_coal", "gen_ng", "gen_nuc", "gen_oil",
             "gen_hydro", "gen_solar", "gen_wind", "gen_other"]


# ----------------------------------------------------------------------------- #
# Loading / shared grid data
# ----------------------------------------------------------------------------- #
def load_config(path: Path = CONFIG) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def load_grid(path: Path = HOURLY_CSV) -> pd.DataFrame:
    """The ISNE 2024 hourly table, indexed by UTC timestamp."""
    df = pd.read_csv(path, parse_dates=["ts_utc"]).set_index("ts_utc")
    return df


def grid_intensity(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """EF[h] = tonnes CO2 per MWh of total ISNE generation, each hour.

    Average intensity (NOT marginal). sum(fuel*factor) / sum(fuel).
    """
    ef = cfg["emission_factors_t_per_mwh"]
    gen = df[FUEL_COLS]
    total = gen.sum(axis=1).replace(0, np.nan)
    co2 = sum(gen[c] * ef[c] for c in FUEL_COLS)
    return (co2 / total).fillna(0.0)


def normalized_shape(series: pd.Series) -> np.ndarray:
    """Normalize an hourly series so it sums to 1 over the year."""
    v = np.nan_to_num(series.to_numpy(dtype=float), nan=0.0)
    s = v.sum()
    return v / s if s > 0 else v


# ----------------------------------------------------------------------------- #
# 1. The hourly meter — Section 5
# ----------------------------------------------------------------------------- #
@dataclass
class MatchResult:
    annual_match_pct: float
    hourly_match_pct: float
    energy_mwh: float
    covered_mwh: float
    uncovered_mwh: float
    hidden_co2_t: float
    hidden_co2_t_peaker_proxy: float
    peak_contrib_mw: float
    load: np.ndarray = field(repr=False)
    clean: np.ndarray = field(repr=False)
    served_clean: np.ndarray = field(repr=False)  # after battery+flex
    uncovered: np.ndarray = field(repr=False)


def _battery_dispatch(load, clean, p_mw, e_mwh, eff):
    """Greedy battery: store surplus clean, discharge into deficit."""
    if p_mw <= 0 or e_mwh <= 0:
        return clean.copy()
    served = clean.copy()
    soc = 0.0
    sqrt_eff = eff ** 0.5
    for h in range(len(load)):
        surplus = clean[h] - load[h]
        if surplus > 0:  # charge
            room = e_mwh - soc
            charge = min(surplus, p_mw, room / sqrt_eff)
            soc += charge * sqrt_eff
        else:            # discharge
            need = load[h] - clean[h]
            dis = min(need, p_mw, soc * sqrt_eff)
            served[h] += dis
            soc -= dis / sqrt_eff
    return served


def _flex_shift(load, clean, flex_share):
    """Move up to flex_share*load from deficit to surplus hours within each UTC day."""
    if flex_share <= 0:
        return load.copy()
    L = load.copy()
    n_days = len(L) // 24
    for d in range(n_days):
        sl = slice(d * 24, d * 24 + 24)
        day_load = L[sl]
        day_clean = clean[sl]
        deficit = np.maximum(day_load - day_clean, 0)
        surplus = np.maximum(day_clean - day_load, 0)
        movable = np.minimum(deficit, flex_share * day_load)
        total_move = movable.sum()
        headroom = surplus.sum()
        move = min(total_move, headroom)
        if move <= 0:
            continue
        # shave deficit hours proportionally, add to surplus hours proportionally
        if movable.sum() > 0:
            day_load -= movable * (move / movable.sum())
        if surplus.sum() > 0:
            day_load += surplus * (move / surplus.sum())
        L[sl] = day_load
    return L


def hourly_match(peak_mw, w_solar, w_onshore, w_offshore, df, cfg,
                 load_factor=None, procurement_ratio=None,
                 battery_mw=0.0, battery_mwh=0.0, flex_share=0.0,
                 onshore_shape=None, offshore_shape=None) -> MatchResult:
    """Section 5. Solar shape = normalized ISNE hourly solar generation.

    Wind shapes default to normalized ISNE wind if weights are nonzero and no
    explicit shape is given (the brief's fallback).
    """
    d = cfg["defaults"]
    load_factor = d["load_factor"] if load_factor is None else load_factor
    procurement_ratio = d["procurement_ratio"] if procurement_ratio is None else procurement_ratio
    eff = d["battery_roundtrip_eff"]

    n = len(df)
    # 1. load
    load = np.full(n, peak_mw * load_factor, dtype=float)
    E = load.sum()

    # 2. clean supply from normalized shapes
    solar_shape = normalized_shape(df["gen_solar"])
    wind_shape = normalized_shape(df["gen_wind"])
    s_on = wind_shape if onshore_shape is None else onshore_shape
    s_off = offshore_shape if offshore_shape is not None else wind_shape
    weights = np.array([w_solar, w_onshore, w_offshore], dtype=float)
    if weights.sum() > 0:
        weights = weights / weights.sum()
    mix = weights[0] * solar_shape + weights[1] * s_on + weights[2] * s_off
    clean = procurement_ratio * E * mix

    # 3 + 4. battery then flex (flex adjusts load, battery adjusts served clean)
    load_flexed = _flex_shift(load, clean, flex_share)
    served_clean = _battery_dispatch(load_flexed, clean, battery_mw, battery_mwh, eff)

    # 5. metrics
    covered = np.minimum(load_flexed, served_clean)
    uncovered = np.maximum(load_flexed - served_clean, 0.0)

    ef = grid_intensity(df, cfg).to_numpy()
    hidden_co2 = float((uncovered * ef).sum())

    # peaker proxy on the top-5% demand hours
    thr = np.quantile(df["demand_mw"].to_numpy(), d["peaker_percentile"])
    peak_mask = df["demand_mw"].to_numpy() >= thr
    pf = cfg["peaker_factor_t_per_mwh"]
    ef_proxy = np.where(peak_mask, pf, ef)
    hidden_co2_proxy = float((uncovered * ef_proxy).sum())

    # peak contribution: DC MW during ISNE top-N demand hours
    topn = int(d["peak_hours_window"])
    top_idx = np.argsort(df["demand_mw"].to_numpy())[-topn:]
    peak_contrib = float(load_flexed[top_idx].mean())

    annual = clean.sum() / load.sum()
    hourly = covered.sum() / load.sum()

    return MatchResult(
        annual_match_pct=100 * annual,
        hourly_match_pct=100 * hourly,
        energy_mwh=float(E),
        covered_mwh=float(covered.sum()),
        uncovered_mwh=float(uncovered.sum()),
        hidden_co2_t=hidden_co2,
        hidden_co2_t_peaker_proxy=hidden_co2_proxy,
        peak_contrib_mw=peak_contrib,
        load=load_flexed, clean=clean, served_clean=served_clean, uncovered=uncovered,
    )


def heatmap_matrix(res: MatchResult) -> np.ndarray:
    """365/366 x 24 status matrix. 0=clean(green) 1=battery(amber) 2=grid(red)."""
    n = len(res.load)
    days = n // 24
    L = res.load[:days * 24].reshape(days, 24)
    C = res.clean[:days * 24].reshape(days, 24)
    S = res.served_clean[:days * 24].reshape(days, 24)
    status = np.full((days, 24), 2, dtype=int)         # default red = grid
    status[S + 1e-6 >= L] = 1                            # battery/clean covered it
    status[C + 1e-6 >= L] = 0                            # direct clean (no battery need)
    return status


# ----------------------------------------------------------------------------- #
# 2. Impact estimate — energy real, water/noise/diesel benchmarked
# ----------------------------------------------------------------------------- #
def impact_estimate(res: MatchResult, cfg: dict, aircooled=False) -> dict:
    b = cfg["impact_benchmarks"]
    mwh = res.energy_mwh
    water_rate = b["water_gal_per_mwh_aircooled"] if aircooled else b["water_gal_per_mwh"]
    peak_mw = res.load.max()
    diesel_mwh_if_tested = peak_mw * b["backup_diesel_share_of_peak"]  # per test hour
    return {
        "hidden_co2_t": res.hidden_co2_t,                       # REAL (est. avg intensity)
        "water_gal_per_year_est": mwh * water_rate,             # ESTIMATE
        "noise_radius_m_est": b["noise_audible_radius_m_per_100mw"] * peak_mw / 100.0,
        "diesel_co2_t_per_test_hour_est": diesel_mwh_if_tested * b["diesel_ef_t_per_mwh"],
        "peak_contrib_mw": res.peak_contrib_mw,
    }

def four_factor_impact(res: MatchResult, cfg: dict, peak_mw: float,
                       local_grid_mw: float = 2000.0,
                       town_water_mgd: float = 10.0) -> dict:
    """Air / Energy / Water / Noise, each with its CORRECT scaling shape.

    Per factor: absolute value, a % impact, and the scaling law used — so the UI
    shows 'not just +X carbon'. Coefficients are benchmarks (modeled); the
    SHAPES (log, sqrt, super-linear, %-of-grid) are real physics/engineering.
    """
    import math
    b = cfg["impact_benchmarks"]
    mwh = res.energy_mwh

    # AIR: real hourly CO2; super-linear because peak hours burn dirtier peakers
    co2 = res.hidden_co2_t
    co2_proxy = res.hidden_co2_t_peaker_proxy
    superlinear = (co2_proxy - co2) / co2 * 100 if co2 > 0 else 0

    # ENERGY: % of the LOCAL grid node (what actually strains a grid), not MW
    energy_pct = 100.0 * peak_mw / max(local_grid_mw, 1)

    # WATER: ~linear with energy, shown as % of town supply
    water_gal_yr = mwh * b["water_gal_per_mwh"]
    town_gal_yr = town_water_mgd * 1e6 * 365
    water_pct = 100.0 * water_gal_yr / max(town_gal_yr, 1)

    # NOISE: logarithmic dB, audible radius grows ~sqrt(MW)
    noise_db = 55.0 + 10.0 * math.log10(max(peak_mw, 1) / 10.0)
    noise_radius_m = b["noise_audible_radius_m_per_100mw"] * math.sqrt(peak_mw / 100.0) * 10

    return {
        "air": {"value": round(co2), "unit": "t CO\u2082/yr", "pct": 100,
                "scaling": "super-linear (peak hours dirtier)",
                "note": f"+{round(superlinear)}% worse at peak vs average"},
        "energy": {"value": round(energy_pct, 1), "unit": "% of local grid",
                   "pct": round(energy_pct, 1), "scaling": "% of local capacity",
                   "note": f"{peak_mw:.0f} MW on a ~{local_grid_mw:.0f} MW node"},
        "water": {"value": round(water_gal_yr / 1e6, 1), "unit": "M gal/yr",
                  "pct": round(water_pct, 1), "scaling": "linear with energy",
                  "note": f"{round(water_pct,1)}% of a {town_water_mgd:.0f} MGD town supply"},
        "noise": {"value": round(noise_db), "unit": "dB at source",
                  "pct": round(noise_radius_m), "scaling": "logarithmic dB, radius \u221d \u221aMW",
                  "note": f"~{round(noise_radius_m)} m audible radius"},
    }



def berdo_equivalent(hidden_co2_t: float, berdo_df: pd.DataFrame) -> float:
    """= N Boston BERDO buildings, by median building annual CO2."""
    col = "GHG_Emissions_MTCO2e"
    med = pd.to_numeric(berdo_df[col], errors="coerce").replace(0, np.nan).median()
    return hidden_co2_t / med if med and med > 0 else float("nan")


def landfill_solar_total_mw(landfill_df: pd.DataFrame) -> float:
    return pd.to_numeric(landfill_df["mw_operating"], errors="coerce").fillna(0).sum()


# ----------------------------------------------------------------------------- #
# 3. Placement score — OPTIMIZE where a new center should go
# ----------------------------------------------------------------------------- #
def placement_score(grid_clean_01, people_01, headroom_01, water_01, cfg) -> dict:
    """Combine four 0..1 sub-scores into a weighted placement score (0..100).

    Each input is already normalized so that HIGHER = BETTER place to build.
    """
    w = cfg["placement_weights"]
    parts = {
        "grid_cleanliness": grid_clean_01 * w["grid_cleanliness"],
        "people_distance":  people_01 * w["people_distance"],
        "grid_headroom":    headroom_01 * w["grid_headroom"],
        "water_stress":     water_01 * w["water_stress"],
    }
    total = sum(parts.values()) / sum(w.values())
    return {"score": 100 * total, "parts": parts}


if __name__ == "__main__":
    # smoke run: Westfield 274 MW, 100% solar
    cfg = load_config()
    df = load_grid()
    res = hourly_match(peak_mw=274, w_solar=1.0, w_onshore=0.0, w_offshore=0.0,
                       df=df, cfg=cfg)
    print(f"Annual: {res.annual_match_pct:.0f}% clean.  Hourly: {res.hourly_match_pct:.0f}%.")
    print(f"Hidden CO2: {res.hidden_co2_t:,.0f} t/yr  (peaker proxy {res.hidden_co2_t_peaker_proxy:,.0f} t/yr)")
    print(f"Uncovered energy: {res.uncovered_mwh:,.0f} MWh of {res.energy_mwh:,.0f} MWh")
