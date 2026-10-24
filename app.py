#!/usr/bin/env python3
"""
app.py — HourMatch. MAP FIRST.

A full-bleed map of Massachusetts is the product. You toggle layers of impact,
click a data center (or drop a pin anywhere) and a panel shows the hourly meter
and the predicted impact for THAT place.

Run:  /opt/anaconda3/bin/python3 -m streamlit run app.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk

import model

ROOT = Path(__file__).resolve().parent
KIT = ROOT / "data" / "raw" / "kit"
GEO = ROOT / "data" / "clean" / "geo"

st.set_page_config(page_title="HourMatch", page_icon="⚡", layout="wide")

# strip Streamlit chrome so the map reads as a product, not a notebook
st.markdown("""
<style>
#MainMenu, header, footer {visibility:hidden;}
.block-container {padding:0.4rem 0.8rem; max-width:100%;}
[data-testid="stSidebar"] {background:#0e1116;}
h1,h2,h3 {color:#e8eaed;}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_everything():
    cfg = model.load_config()
    grid = model.load_grid()
    dcs = pd.read_csv(ROOT / "data" / "clean" / "datacenters.csv")
    land = pd.read_csv(KIT / "landfills" / "data.csv")
    berdo = pd.read_csv(KIT / "berdo" / "data.csv")
    ej = json.loads((GEO / "ej_blockgroups.geojson").read_text()) if (GEO / "ej_blockgroups.geojson").exists() else None
    tx = json.loads((GEO / "transmission_lines.geojson").read_text()) if (GEO / "transmission_lines.geojson").exists() else None
    return cfg, grid, dcs, land, berdo, ej, tx


cfg, grid, dcs, land, berdo, ej, tx = load_everything()

# town centroids for landfill solar points (no geometry in kit) — rough geocode
MA_TOWNS = {
    "Brookfield": (42.21, -72.10), "Westfield": (42.13, -72.75), "Lowell": (42.64, -71.32),
    "Boston": (42.36, -71.06), "Worcester": (42.26, -71.80), "Springfield": (42.10, -72.59),
    "Fall River": (41.70, -71.15), "New Bedford": (41.64, -70.93), "Barnstable": (41.70, -70.30),
}


def ej_color(feat):
    p = feat.get("properties", {})
    m = p.get("PCT_MINORITY") or 0
    try:
        m = float(m)
    except Exception:
        m = 0
    # red intensity rises with minority %
    r = int(120 + min(m, 100) * 1.3)
    return [min(r, 255), 60, 60, 110]


# ---- sidebar: layers + inputs --------------------------------------------- #
with st.sidebar:
    st.markdown("## ⚡ HourMatch")
    st.caption("Massachusetts wrote the rule. We built the meter.")
    st.markdown("### Map layers")
    L_ej = st.checkbox("People — EJ communities", True)
    L_tx = st.checkbox("Energy — transmission lines", True)
    L_solar = st.checkbox("Clean supply — landfill solar", True)
    L_dc = st.checkbox("Data centers", True)

    st.markdown("### Selected site")
    names = list(dcs["name"]) + ["📍 Drop a pin (predict anywhere)"]
    pick = st.selectbox("Click target", names)
    if pick.startswith("📍"):
        lat = st.number_input("lat", value=42.30, format="%.4f")
        lon = st.number_input("lon", value=-72.00, format="%.4f")
        peak_lo = peak_hi = st.slider("Peak MW", 10, 400, 100, 5)
        sel_name, sel_town = "Pinned site", "(custom)"
    else:
        row = dcs[dcs["name"] == pick].iloc[0]
        lat, lon = row.lat, row.lon
        peak_lo, peak_hi = int(row.peak_mw_low), int(row.peak_mw_high)
        sel_name, sel_town = row["name"], row["town"]

    st.markdown("### Scenario")
    peak_mw = st.slider("Peak demand (MW)", 10, 400, peak_hi, 1)
    w_solar = st.slider("Solar %", 0, 100, 100, 5)
    w_off = st.slider("Offshore wind %", 0, 100, 0, 5)
    w_on = max(0, 100 - w_solar - w_off)
    battery_mw = st.slider("Battery MW", 0, 400, 0, 10)
    battery_mwh = st.slider("Battery MWh", 0, 2000, 0, 50)

# ---- run the model for the selected place --------------------------------- #
res = model.hourly_match(peak_mw=peak_mw, w_solar=w_solar/100, w_onshore=w_on/100,
                         w_offshore=w_off/100, df=grid, cfg=cfg,
                         battery_mw=battery_mw, battery_mwh=battery_mwh)
imp = model.impact_estimate(res, cfg)
berdo_n = model.berdo_equivalent(res.hidden_co2_t, berdo)

# ---- build map layers ------------------------------------------------------ #
layers = []
if L_ej and ej:
    for f in ej["features"]:
        f.setdefault("properties", {})["__fill"] = ej_color(f)
    layers.append(pdk.Layer("GeoJsonLayer", ej, stroked=False, filled=True,
                            get_fill_color="properties.__fill", pickable=True))
if L_tx and tx:
    layers.append(pdk.Layer("GeoJsonLayer", tx, stroked=True, filled=False,
                            get_line_color=[120, 170, 255, 140], line_width_min_pixels=1))
if L_solar:
    pts = []
    for _, r in land.iterrows():
        c = MA_TOWNS.get(str(r["municipality"]))
        if c and str(r.get("status", "")).lower().startswith("oper"):
            pts.append({"lat": c[0], "lon": c[1], "mw": float(r.get("mw_operating") or 0),
                        "name": r["facility"]})
    if pts:
        layers.append(pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"],
                                get_radius="mw*600+400", get_fill_color=[47, 158, 68, 180],
                                pickable=True))
if L_dc:
    dd = dcs.assign(radius=4000)
    layers.append(pdk.Layer("ScatterplotLayer", dd, get_position=["lon", "lat"],
                            get_radius="radius", get_fill_color=[224, 49, 49, 220],
                            get_line_color=[255, 255, 255], line_width_min_pixels=2,
                            stroked=True, pickable=True))
# selected marker
layers.append(pdk.Layer("ScatterplotLayer", [{"lat": lat, "lon": lon}],
                        get_position=["lon", "lat"], get_radius=2500,
                        get_fill_color=[255, 209, 102, 255]))

view = pdk.ViewState(latitude=42.2, longitude=-71.8, zoom=7.3, pitch=0)
deck = pdk.Deck(layers=layers, initial_view_state=view,
                map_style="mapbox://styles/mapbox/dark-v10",
                tooltip={"text": "{name}{MUNICIPALITY} {EJ_CRIT_DESC}"})

# ---- layout: map left, impact card right ---------------------------------- #
left, right = st.columns([2.2, 1])
with left:
    st.pydeck_chart(deck, use_container_width=True, height=620)
    st.caption("Red = data centers · green = landfill solar (size = MW) · "
               "red shading = environmental-justice communities · blue = transmission lines. "
               "Sources: EIA-930, MassGIS EJ2020, HIFLD, MA DEP.")

with right:
    st.markdown(f"### {sel_name}")
    st.caption(f"{sel_town} · {peak_mw} MW scenario")
    st.markdown(f"## Annual **{res.annual_match_pct:.0f}%** → Hourly **{res.hourly_match_pct:.0f}%**")
    st.progress(min(1.0, res.hourly_match_pct/100))
    a, b = st.columns(2)
    a.metric("Hidden CO₂ (est.)", f"{res.hidden_co2_t:,.0f} t/yr")
    b.metric("Peak MW added", f"{imp['peak_contrib_mw']:,.0f}")
    c, d = st.columns(2)
    c.metric("Cooling water (est.)", f"{imp['water_gal_per_year_est']/1e6:,.1f}M gal")
    d.metric("Noise radius (est.)", f"{imp['noise_radius_m_est']:,.0f} m")
    st.caption(f"≈ {berdo_n:,.0f} Boston BERDO buildings of hidden CO₂")
    st.divider()
    st.caption("Energy & CO₂: real ISO-NE 2024. Water/noise: benchmarked estimates — "
               "shown so a town knows what to ask.")
