# US Data-Center Impact Dataset — plan

Goal: one row per US data center, with the location factors we measure, so an
ML model learns `location traits + size -> impact` and we can predict for any
Massachusetts site.

## Input (from teammate)
`data/us/raw/datacenters_us.csv` — at minimum:
```
name, lat, lon
```
Nice-to-have if they have it: `mw`, `sqft`, `status`, `operator`, `year`, `cooling_type`.

## Output (we build)
`data/us/clean/dc_features.csv` — one row per DC, these columns:

### Location identity
- `name, lat, lon, state, county_fips`

### MEASURABLE factors (real national data — the model's targets + predictors)
| column | meaning | source | key? |
|---|---|---|---|
| `grid_co2_lb_mwh` | grid carbon intensity of its eGRID subregion | EPA eGRID | no |
| `pm25_annual` | nearest EPA PM2.5 monitor annual mean | EPA AQS / AirData | free key |
| `fossil_co2_25km` | sum of power-plant CO2 within 25 km | EPA CAMPD / eGRID plants | free key |
| `pop_10km` | population within 10 km | US Census ACS / grid | free key |
| `pct_minority_10km` | EJ: % minority within 10 km | Census / EJScreen | no (bulk) |
| `median_income_10km` | income within 10 km | Census ACS | free key |
| `water_stress_idx` | basin water stress | WRI Aqueduct | no (bulk) |
| `cooling_deg_days` | climate — cooling load proxy | NOAA normals | no |
| `summer_tmax_avg` | avg summer high (cooling water driver) | NOAA normals | no |
| `elec_price_cents_kwh` | state industrial electricity price | EIA | free key |

### DERIVED / MODELED (from model.py, same benchmarks as the MA app)
- `est_water_gal_yr`, `est_noise_radius_m`, `hourly_match_pct` (if MW known)

## ML model (`us_model/train.py`)
- **Target options** (pick per question):
  1. Predict `fossil_co2_25km` or `pm25_annual` from location traits + size
     — "what pollution context does a DC of this size sit in?"
  2. Predict `grid_co2_lb_mwh` — "how dirty is the power it will pull?"
- **Features:** everything measurable above except the target.
- **Model:** gradient-boosted trees (sklearn) — small data, tabular, interpretable.
- **Output:** feature importances (what drives impact) + a predict(lat,lon,mw)
  function the MA app can call for any candidate site.

## Honesty
- We do NOT claim to measure a DC's own noise/water — no such national dataset.
- We model the LOCATION's measurable factors and the DC's size-scaled estimates.
- Every factor cites its source; prediction intervals shown, not point claims.
