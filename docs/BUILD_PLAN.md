# Build plan

One day. Build the headline number first. Keep every estimate labeled.

---

## Who owns what

| Owner | Scope | Key files |
|---|---|---|
| **Felipe + AI** | Model, data pulls, Streamlit app, AI memo | `model.py`, `pull/`, `app.py`, `memo.py`, `config.yaml` |
| **Map engineer** | The whole map screen + its data layers | see `docs/MAP_ENGINEER.md` |
| **Mike** | Pick one lane below | — |

### Mike — pick a lane
- **Demo + story.** Own the 3-minute script, the opening slide (landfill solar MW vs 2 GW), rehearse.
- **Data wrangling.** Own `pull/pull_eia.py` + `pull/pull_campd.py`, deliver clean CSVs the model reads.
- **AI memo.** Own `memo.py` — the plain-language town brief with the 5 developer questions.

---

## The clean seam

Everyone agrees on **two files**. Nobody blocks anyone else.

1. `data/clean/isne_hourly_2024.csv` — the grid, one row per hour.
2. `data/clean/datacenters.csv` — the sites, one row per data center.

The model reads #1 and #2. The map reads #2 and its own geo layers. Build to these and merge clean.

---

## Hour-by-hour

| Hours | Task | Owner |
|---|---|---|
| 0–1 | Pull EIA-930 ISNE 2024 + renewables.ninja shapes → `isne_hourly_2024.csv` | Felipe / Mike |
| 1–2 | `model.py` + sanity checks. **Get the Westfield all-solar headline number. Screenshot it.** | Felipe |
| 2–3 | Heatmap + sliders in Streamlit | Felipe |
| 3–4 | Map layers (EJ, transmission, landfill solar, data centers, CAMPD plants) | Map engineer |
| 4–5 | AI town memo + methodology page | Mike / Felipe |
| 5+ | Polish, opening-slide chart, rehearse demo | Mike |

---

## Definition of done (for the demo)

1. A real headline number on screen: *"Annual 100%, Hourly X%"* for Westfield all-solar.
2. The heatmap glows **red on winter evenings** for all-solar.
3. Sliders live: swap to offshore wind + add batteries → red shrinks on screen.
4. A map with data centers and the people nearby.
5. One AI memo generated, with a "verify sources" label.
6. A methodology page listing every source and assumption.

---

## Stack

- Model: Python + pandas.
- UI: **Streamlit** + Plotly (heatmap) + pydeck (map) for speed.
- Upgrade path if time: Next.js + deck.gl + FastAPI around `model.py`.
- AI memo: Claude API or Bedrock (AWS is a sponsor).

## Environment setup needed

- No EIA API key is set yet. Either use Option A (no-key bulk CSVs) or add a free key to `.env`.
- Streamlit / pandas / plotly / pydeck are **not installed**. Run:
  `pip3 install streamlit pandas plotly pydeck requests pyyaml`
