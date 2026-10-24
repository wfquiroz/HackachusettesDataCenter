"""
test_model.py — sanity checks from Section 5 of the brief, on a tiny synthetic
year plus the real ISNE 2024 table.

Run:  /opt/anaconda3/bin/python3 -m pytest tests/ -q
   or just: /opt/anaconda3/bin/python3 tests/test_model.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model  # noqa: E402

CFG = model.load_config()


def _synthetic_year(days=10):
    """A tiny year: flat demand, a clean diurnal solar bump (zero at night)."""
    n = days * 24
    ts = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    hour = ts.hour.to_numpy()
    solar = np.clip(np.sin((hour - 6) / 12 * np.pi), 0, None) * 100  # daytime only
    df = pd.DataFrame(index=ts)
    df.index.name = "ts_utc"
    df["demand_mw"] = 1000.0
    for c in model.FUEL_COLS:
        df[c] = 0.0
    df["gen_solar"] = solar
    df["gen_ng"] = 500.0
    df["gen_nuc"] = 400.0
    return df


def test_annual_match_equals_ratio_without_storage():
    df = _synthetic_year()
    r = model.hourly_match(100, 1, 0, 0, df, CFG, procurement_ratio=1.0)
    assert abs(r.annual_match_pct - 100.0) < 1e-6


def test_hourly_never_exceeds_annual():
    df = _synthetic_year()
    r = model.hourly_match(100, 1, 0, 0, df, CFG)
    assert r.hourly_match_pct <= r.annual_match_pct + 1e-9


def test_all_solar_has_red_night_hours():
    df = _synthetic_year()
    r = model.hourly_match(100, 1, 0, 0, df, CFG)
    hm = model.heatmap_matrix(r)
    assert (hm == 2).sum() > 0  # night hours uncovered by solar


def test_battery_raises_hourly_match():
    df = _synthetic_year()
    base = model.hourly_match(100, 1, 0, 0, df, CFG)
    withbatt = model.hourly_match(100, 1, 0, 0, df, CFG,
                                  battery_mw=100, battery_mwh=400)
    assert withbatt.hourly_match_pct >= base.hourly_match_pct


def test_real_westfield_headline():
    """The demo number holds: annual 100, hourly in a sane low range for all-solar."""
    df = model.load_grid()
    r = model.hourly_match(274, 1, 0, 0, df, CFG)
    assert abs(r.annual_match_pct - 100) < 0.5
    assert 10 < r.hourly_match_pct < 40      # all-solar in New England
    assert r.hidden_co2_t > 0


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL  {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
