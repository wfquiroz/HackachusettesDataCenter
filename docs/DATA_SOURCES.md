# Data sources

Save raw to `data/raw/`, cleaned to `data/clean/`. Record source URL + pull date in `data/SOURCES.md` for **every** dataset.

---

## 4A. Core — the 8,760-hour model (must have)

### 1. EIA Hourly Electric Grid Monitor (EIA-930), ISO New England (`ISNE`), 2024
Hourly net generation by fuel + hourly demand.
- **Option A (no key):** six-month bulk CSVs from the [Grid Monitor download page](https://www.eia.gov/electricity/gridmonitor/) → "Download data" → `EIA930_BALANCE_2024_Jan_Jun.csv`, `..._Jul_Dec.csv`. Filter `Balancing Authority == ISNE`.
- **Option B (free API key, [opendata](https://www.eia.gov/opendata/)):**
  `https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/?api_key=KEY&frequency=hourly&data[0]=value&facets[respondent][]=ISNE&start=2024-01-01T00&end=2024-12-31T23&offset=0&length=5000`
  Max 5,000 rows/call → paginate with `offset` (~70k rows total).
- **Output:** `data/clean/isne_hourly_2024.csv` — `ts_utc, demand_mw, gen_ng, gen_nuc, gen_oil, gen_coal, gen_hydro, gen_solar, gen_wind, gen_other`.
- **Gotchas:** timestamps are UTC; some hours missing or negative → forward-fill small gaps, **log it**.

### 2. Clean-supply hourly shapes (what the data center "buys")
- Easiest: [renewables.ninja](https://www.renewables.ninja) (free account) → hourly 2024 capacity factors:
  - Solar PV at Westfield (~42.13, −72.75) and Lowell (~42.64, −71.32).
  - Offshore wind near Southern New England lease areas (~41.0, −70.6), 12–15 MW turbine, hub ~140 m.
- Fallback for wind: ISNE `gen_wind` / `gen_solar` from file #1, normalized to a shape.
- Bonus: [NOAA buoy wind](https://www.ndbc.noaa.gov/) (station 44020 or 44008), 2024 — sanity-check that offshore wind blows on winter evenings.

### 3. Emission factors (CO₂ per MWh by fuel)
- [EPA eGRID](https://www.epa.gov/egrid) latest, New England `NEWE` average — sanity check.
- Per-fuel direct-combustion factors → `config.yaml` as named constants. **Shown on methodology screen.**

---

## 4B. Who is affected (strongly recommended)

### 4. EPA CAMPD — hourly emissions per power plant
[campd.epa.gov](https://campd.epa.gov) → bulk files or API (free api.data.gov key). Hourly emissions 2024, states MA/CT/RI/NH/VT/ME. Includes facility lat/lon.
Use: find which fossil plants run in the hours the data center is **not** covered, and where. Stretch: hourly regional CO₂ ÷ hourly generation = measured hourly intensity.

### 5. Hackathon kit datasets (MassGIS / HIFLD / Boston)
- **EJ block groups (MassGIS EJ2020):**
  `https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/EJ2020/MapServer/0/query?where=EJ%3D%27Yes%27&outFields=MUNICIPALITY,TOTAL_POP,PCT_MINORITY,LIMENGHHPCT,BG_MHHI,EJ,EJ_CRIT_DESC&returnGeometry=true&outSR=4326&f=geojson`
- **Electric utility by town:**
  `https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/ElectricityProviders/MapServer/0/query?where=1%3D1&outFields=TOWN,ELEC,ELEC_LABEL&returnGeometry=false&f=json`
- **Renewables at MA landfills** (real clean supply to "procure"):
  `https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/DEP/RenewablesAtMaLandfills/MapServer/0/query?where=1%3D1&outFields=MUNICIPALITY,FACILITY,TYPE_,MW_PERMITTED,MW_OPERATING,STATUS_1,OPERATING_SINCE&returnGeometry=false&f=json`
  → total **operating landfill MW** for the opening-slide chart vs ~2 GW requests.
- **Transmission lines (HIFLD):**
  `https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0/query?geometry=-73.5081%2C41.1870%2C-69.9284%2C42.8868&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=OWNER,VOLTAGE,VOLT_CLASS,TYPE,STATUS&returnGeometry=true&outSR=4326&f=geojson`
  (paginate; ~1,228 lines)
- **Boston BERDO 2021** (benchmark buildings):
  `https://data.boston.gov/api/3/action/datastore_search?resource_id=43e4abc9-1fae-40d9-a02e-ff950bd0e732&limit=5000`

---

## 4C. Context / benchmarks (cite, don't model)
- LBNL *2024 US Data Center Energy Usage Report* — national growth.
- Virginia JLARC *Data Centers in Virginia* (2024) — ratepayer impacts.
- PJM capacity auction analyses (Monitoring Analytics).
- ISO-NE CELT report (latest) — official load forecast.
- ISO Express (ISO-NE) — live demand / fuel mix for the "today" view.
- MA EO 658 text + Data Center Framework (mass.gov); DPU interconnection directive.
- Lowell/Markley: CLF + Yale EJ clinic releases; WBUR / GBH (Aug 2026).
- Westfield: Boston Globe (Sept 8 2026), Bisnow.

---

## 4D. Hand-made file — `data/clean/datacenters.csv`
Columns: `name, town, lat, lon, status, peak_mw_low, peak_mw_high, utility, source_url`.
Seed with Lowell (Markley) and Westfield. Coordinates **approximate / town-level**. No street addresses.
