# HourMatch — Hackachusetts 2026 Submission

**"Massachusetts wrote the rule. We built the meter."**

Public repo: https://github.com/wfquiroz/HackachusettesDataCenter
Demo video: *(add YouTube/Vimeo link here before you submit)*

---

## What it is

Massachusetts Executive Order 658 (Sept 8, 2026) says big data centers must buy
enough new clean power to match a **year** of their use. But the grid runs **hour
by hour**. A data center can buy a year of solar and still pull gas on winter
nights, when the sun is down and New England peaks. Towns now approve these
projects — and they have no tool to see the real hourly impact, or who breathes it.

HourMatch is that tool. It turns an annual "100% clean" claim into an honest
hourly number, maps who lives nearby, scores where a data center *should* go in
Massachusetts, and flags which towns have already banned or restricted them.

---

## Features

**1. Hourly clean-energy meter**
One headline that cuts through the paperwork: *"Annual: 100% clean. Hourly: X%."*
A 274 MW data center that reads 100% clean over a year reads ~23% clean by the
hour. 5/5 model tests pass on a synthetic year.

**2. Interactive Massachusetts map**
- Impact surfaces you can toggle: air (fossil CO₂), energy demand, water stress,
  noise, and environmental-justice population burden.
- **Drop a data center** anywhere in MA, set its size, and see its predicted
  footprint. Placement is clipped to the real state boundary (ray-cast
  point-in-polygon against the MassGIS outline) — you can't place one outside MA.
- **Reservoir layer** (MassGIS Hydro) so you can see the water bodies a site sits near.
- Light OpenStreetMap basemap with smooth layer transitions.

**3. Year-by-year buildout playback**
Press play and watch the impact bloom grow across a 5-year phased buildout. Each
year gives a visual cue — an expanding pulse ring, a "breathing" surface repaint,
and a year-badge tick — so the change reads as motion, not a snap. When a factor
crosses a severity threshold (clean → watch → bad), that factor's card flashes an
outline in the new color with a "→ Medium / → High" chip, so the eye lands on the
exact factor and year that tipped over.

**4. Four-factor impact card in real units**
Not percentages — the units a town official or utility engineer recognizes:
- **Air:** tonnes CO₂ / year (scales with the local grid-carbon surface)
- **Energy:** GWh / year, anchored to "≈ N homes' worth of power"
- **Water:** million gallons / day (scales with local water stress)
- **Noise:** dB at source
The same machine produces different air and water magnitudes depending on *where*
it lands — dirtier local grid → more hidden CO₂.

**5. Placement optimizer — "go vs should"**
- A **"Find best site"** button recommends the top 5 locations in MA, each ≥30
  miles apart (best spot, then exclude a radius, then pick the next), clipped to
  the state. It scores on honest "who absorbs the harm" terms: people nearby
  (45%), existing dirty air, grid strain, water, grid carbon.
- The contrast is the story: the **US ML model** shows where data centers
  *actually* go (chasing cheap power near no one); the **placement optimizer**
  shows where they *should* go in MA (away from dense, already-burdened communities).

**6. US machine-learning model, validated**
Trained on 1,839 real US data center sites. The Model tab shows the real
evidence on screen: CV R² = 0.975, a placebo test at R² = −0.048 (the signal is
real, not overfitting), feature importances (price 46%, climate 34%, …), and a
stated methodology. A Jupyter notebook (`us_model/analysis.ipynb`) reproduces it.

**7. Real Massachusetts ban/moratorium data**
A sourced CSV of 13 MA towns and their actual data-center rules — full bans
(Holyoke, Shutesbury, Taunton), near-total zoning limits (Mansfield),
moratoriums (Westfield, Plymouth), and towns weighing bans. Drop a center in one
of these towns and the impact card shows, at the bottom, *"⚠ This town bans data
centers"* with the detail and news source. Informative, not prescriptive — you
can still model the site.

**8. Honesty by design**
Measured data is solid; modeled values are drawn dashed. Hourly emissions are
labeled estimates. Coordinates are town-level where exact parcels aren't public,
and the CSV flags confidence per row. Every dataset is cited on screen. No street
addresses.

---

## How Kiro was used

- **Steering** (`/.kiro/steering/project-rules.md`) — house rules every agent and
  teammate followed: the exact design system (palette, type, icon weight, corners,
  measured-vs-modeled convention), the git topology (no `main`; push to feature
  branches; trunk merges are a human decision), and file-ownership rules for
  parallel work so two agents never edit the same file.
- **Spec-driven planning** (`docs/`) — one set of planning docs (MODEL_SPEC,
  DATA_SOURCES, BUILD_PLAN, MAP_ENGINEER) committed to GitHub as the single source
  of truth every teammate and agent pulled from.
- **Kiro Crew agent orchestration** — a conductor/PM pattern coordinating parallel
  workers, each on its own branch and files, pushing to feature branches and
  reconciling through PRs — never auto-merging into the trunk.
- **Kiro CLI + dashboard** — heavy clone/branch/push/test work in the CLI, live
  hand-edits and status checks from the dashboard.
- **MCP** — Lovable MCP server configured in `/.kiro/settings/mcp.json`.

---

## Repo layout

```
HackachusettesDataCenter/
  .kiro/
    steering/project-rules.md   # house rules (design system, git, ownership)
    settings/                   # Kiro CLI + MCP config
  data/clean/                   # cleaned CSVs the app reads (incl. ban/rule CSV)
  data/SOURCES.md               # source URL + pull date for every dataset
  pull/                         # one script per data source + rings.py (impact)
  us_model/                     # US ML model + analysis.ipynb
  model.py                      # the 8,760-hour hourly model
  serve.py                      # API server (surfaces, bestsite, townrules, model)
  web/public/                   # the map app (index.html, app.js, style.css)
  tests/                        # model sanity tests
  docs/                         # planning / spec docs
```

---

## Run it

```bash
# 1. serve the API + static app
python serve.py          # serves the map app and the /api/* endpoints

# 2. open the app
#    http://localhost:5173

# run the model tests
python -m pytest tests/ -q

# reproduce the US model
jupyter notebook us_model/analysis.ipynb
```

All data needed to run is in `data/clean/`. The `.kiro/` directory is committed so
Kiro usage is visible for judging.
