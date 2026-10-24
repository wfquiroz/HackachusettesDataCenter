# Map engineer — handoff

You own the **Map** screen. Self-contained. You do not need the model to start.

---

## Goal

A map of Massachusetts with clickable data centers. Click a site → the rest of the app opens its report card.

## Layers (in draw order, bottom to top)

| Layer | Source | Geometry | Note |
|---|---|---|---|
| Base map | pydeck / deck.gl | — | light or dark, your call |
| Transmission lines | HIFLD (below) | lines | color by voltage if easy |
| EJ block groups | MassGIS EJ2020 | polygons | shade by % minority or income |
| Landfill solar | MA DEP | points | size by operating MW |
| Fossil plants | EPA CAMPD | points | lat/lon in the facility data |
| Data centers | `data/clean/datacenters.csv` | points | **the clickable layer** |

## The one contract you must keep

Read data centers from **`data/clean/datacenters.csv`**. Columns:

```
name, town, lat, lon, status, peak_mw_low, peak_mw_high, utility, source_url
```

On click, emit the site `name`. That is the only handshake with the rest of the app.
In Streamlit + pydeck: use a selection callback / tooltip; pass the clicked `name` back via session state.

## Data endpoints (copy-paste ready)

**EJ block groups (polygons, 4326, geojson):**
```
https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/EJ2020/MapServer/0/query?where=EJ%3D%27Yes%27&outFields=MUNICIPALITY,TOTAL_POP,PCT_MINORITY,LIMENGHHPCT,BG_MHHI,EJ,EJ_CRIT_DESC&returnGeometry=true&outSR=4326&f=geojson
```
Paginate with `resultOffset` / `resultRecordCount` if capped.

**Transmission lines (HIFLD, lines, ~1,228 features — paginate):**
```
https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0/query?geometry=-73.5081%2C41.1870%2C-69.9284%2C42.8868&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=OWNER,VOLTAGE,VOLT_CLASS,TYPE,STATUS&returnGeometry=true&outSR=4326&f=geojson
```

**Landfill solar (points):**
```
https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/DEP/RenewablesAtMaLandfills/MapServer/0/query?where=1%3D1&outFields=MUNICIPALITY,FACILITY,TYPE_,MW_PERMITTED,MW_OPERATING,STATUS_1,OPERATING_SINCE&returnGeometry=false&f=json
```
These have no geometry — geocode by municipality, or use as a chart not a map layer.

**Fossil plants:** EPA CAMPD bulk/API ([campd.epa.gov](https://campd.epa.gov)), facility list has lat/lon. Filter states MA/CT/RI/NH/VT/ME.

## Rules (shared with the whole team)

- **Cite every layer on screen** — a small source label per layer.
- **No street addresses.** Town-level points only.
- Save raw pulls to `data/raw/`, record URL + pull date in `data/SOURCES.md`.

## Suggested files for your lane

```
pull/pull_kit.py     # fetch EJ + transmission + landfill → data/raw/ then data/clean/
map_view.py          # the pydeck map, imported by app.py (or a standalone Streamlit page)
```

## Start without blocking

`data/clean/datacenters.csv` may not exist yet. Seed your own 2-row stub now (Lowell, Westfield) so you can build the clickable layer immediately; the real file will match these columns.
