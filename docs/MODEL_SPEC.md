# Model spec — `model.py`

All pure functions. Unit-tested on a tiny synthetic year. This is the heart of the project; build it **first**.

---

## Inputs

| Name | Default | Meaning |
|---|---|---|
| `peak_mw` | — | Data center peak demand (MW). Slider. |
| `load_factor` | 0.85 | Share of peak the site runs at. Slider. |
| `w_solar, w_onshore, w_offshore` | — | Procurement mix weights. **Must sum to 1.** |
| `procurement_ratio` | 1.0 | 1.0 = the EO 658 annual match. Slider for over/under-buy. |
| `battery_mw` | 0 | Battery power limit. |
| `battery_mwh` | 0 | Battery energy limit. |
| `flex_share` | 0 | Share of load shiftable within 24 h. |
| `diesel_test_hours` | optional | Diesel generator test hours (scenario only). |

---

## Steps

1. **Load.** `L[h] = peak_mw * load_factor` (flat, optional small diurnal wiggle). `E = sum(L)`.
2. **Clean supply.** For each resource, normalize its hourly shape `s[h]` so `sum(s) = 1`.
   `C[h] = procurement_ratio * E * sum_k( w_k * s_k[h] )`.
3. **Battery (greedy).** Charge from surplus `C − L`, discharge into deficit. Round-trip efficiency **0.88**. Respect MW and MWh limits.
4. **Flex.** Move up to `flex_share * L[h]` from deficit hours to surplus hours **within the same 24 h window**.
5. **Metrics** (after battery + flex, call the adjusted series `L'` and `C'`):
   - **Annual match %** = `sum(C) / sum(L)` — what EO 658 counts.
   - **Hourly match %** = `sum(min(L', C')) / sum(L)` — what physics counts.
   - **Uncovered energy** `G[h] = max(L' − C', 0)`.
   - **Hidden CO₂** = `sum(G[h] * EF[h])`, where `EF[h]` = ISNE hourly average intensity (fuel mix × factors).
     Also a **peak-hour proxy**: a gas/oil peaker factor for the top 5% ISNE-demand hours. **Label it a proxy.**
   - **Peak contribution** = data-center MW during ISNE's top 100 demand hours.
   - **Comparisons** = "= N Boston BERDO buildings" or "= N% of MA operating landfill solar".
6. **Heatmap output** — a 365 × 24 matrix. Green = covered, amber = battery, red = grid/fossil.

---

## Sanity checks (print these in the test)

- Annual match == `procurement_ratio` when there are no storage losses.
- Hourly match **≤** annual match. Always.
- All-solar case shows **red winter evenings**.

---

## Emission factors

Live in `config.yaml` as named constants. Never hardcoded silently. Shown on the methodology screen.
Source: EPA eGRID (latest) New England subregion `NEWE`, plus per-fuel direct-combustion factors.
