# HourMatch — Hackachusetts 2026 Submission

**"Massachusetts wrote the rule. We built the meter."**

Public repo: https://github.com/wfquiroz/HackachusettesDataCenter
Demo video: *(add YouTube/Vimeo link here before you submit)*

---

## The problem

Massachusetts just passed Executive Order 658 (Sept 8, 2026). It says a big data
center must buy enough clean power to match a **year** of its use.

But the grid does not run on a year. It runs on an **hour**. A data center can buy
a year of solar and still pull gas on a winter night, when the sun is down and New
England burns the dirtiest fuel it has.

So "100% clean" on paper can be far less clean by the hour. And three groups are
stuck with no way to see it:

- **Town boards** have to approve or deny these projects. They have no tool. They
  vote on a PDF. Some towns panic and ban everything; some wave through the worst
  sites. They cannot tell a good site from a bad one.
- **State and utility planners** know the annual rule has an hourly hole, but they
  have nothing that shows a town what that hole costs.
- **The data center companies** that are actually trying to build responsibly have
  no way to *prove* it. Their honest project looks the same as a greenwashed one.

No one can measure the thing everyone is fighting about.

## The solution

HourMatch is the meter for the rule Massachusetts already wrote. Drop a data
center anywhere in the state, pick its size, and it tells you:

- how clean it really is **by the hour**, not just on paper,
- **who** breathes, hears, and drinks the difference,
- **where in Massachusetts** that same machine would do the least harm,
- and whether the town has **already banned or restricted** data centers.

It does not say yes or no. It gives every side the same honest numbers to argue
over.

---

## What it does — for government

The people who have to decide.

**1. Turns a PDF claim into one honest number.**
A developer's filing says "100% clean, annually." HourMatch shows the hourly
truth beside it: *"Annual 100% · Hourly ~23%."* That one line is what a town board
needs to ask the right question.

**2. Shows who absorbs the impact.**
Drop a site and the map shows the people within range, weighted by
environmental-justice burden — so a board sees whether the harm lands on a
community already carrying more than its share. Impact comes in real units a town
official knows: tonnes CO₂/yr, GWh/yr (≈ N homes' power), million gal/day, dB.

**3. Tells a town if its own site is good or bad — before it panics.**
The placement optimizer grades any MA location and recommends the 5 best sites in
the state, spread ≥30 miles apart and clipped to the real border. Two MA towns
show why this matters: one banned data centers over a site our model grades an
**A**; another's actual site grades a **D**. Both reacted politically, blind.
HourMatch is the tool that would have told them which was which.

**4. Puts the real legal landscape on the table.**
A sourced dataset of 13 MA towns and their actual rules — full bans, moratoriums,
zoning limits. Drop a center in one and the card flags *"this town bans data
centers"* with the news source. A board sees what its neighbors already did.

## What it does — for private / developers

The people who have to build.

**5. Lets a responsible project prove it is responsible.**
A developer can run their own proposed site, see the hourly clean number and the
impact, and bring *that* to the town instead of a glossy annual claim. An honest
hourly score is a credibility asset — it separates a real clean project from a
greenwashed one.

**6. Finds the site that passes.**
"Find best site" steers a developer toward the MA locations that are genuinely
low-impact and far from already-burdened communities — the sites least likely to
trigger a ban and most likely to clear a town vote. It de-risks siting before a
dollar is spent.

**7. Shows the five-year buildout honestly.**
Press play and watch a phased buildout's footprint grow year by year, with the
exact year and factor that crosses from acceptable into harmful flagged on screen.
A developer can phase and site around that crossing instead of discovering it in
a hearing.

---

## The intelligence under it

- **A validated US ML model** trained on 1,839 real data center sites learns where
  the industry *actually* builds (chasing cheap power near no one). The Model tab
  proves it on screen: CV R² 0.975 and a passing placebo test (R² −0.048 — the
  signal is real, not overfit). Reproducible in `us_model/analysis.ipynb`.
- **The placement optimizer** flips that into where a center *should* go in MA,
  scoring on who absorbs the harm (people 45%, dirty air, grid strain, water).
- **"Go vs should"** is the whole thesis: the model shows the pattern, the
  optimizer shows a better choice, and a town can see both.

## Honesty by design

Measured data is drawn solid, modeled values dashed. Hourly emissions are labeled
estimates. Coordinates are town-level where exact parcels aren't public, flagged
per row. Every dataset is cited on screen. No street addresses. The tool is built
to help a *good* project prove itself — it is not anti-data-center.

---

## How Kiro was used

- **Steering** (`/.kiro/steering/project-rules.md`) — house rules every agent and
  teammate followed: the exact design system, the git topology (no `main`; push to
  feature branches; trunk merges are a human decision), and file-ownership rules so
  two agents never edit the same file in parallel.
- **Spec-driven planning** (`docs/`) — one set of planning docs (MODEL_SPEC,
  DATA_SOURCES, BUILD_PLAN, MAP_ENGINEER) committed to GitHub as the single source
  of truth every teammate and agent pulled from.
- **Kiro Crew agent orchestration** — a conductor/PM pattern coordinating parallel
  workers, each on its own branch and files, reconciling through PRs, never
  auto-merging the trunk.
- **Kiro CLI + dashboard** — heavy clone/branch/push/test in the CLI; live
  hand-edits and status from the dashboard.
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

## Run it

```bash
python serve.py          # serves the map app + /api/* endpoints
# open http://localhost:5173

python -m pytest tests/ -q          # model sanity tests
jupyter notebook us_model/analysis.ipynb   # reproduce the US model
```

All data needed to run is in `data/clean/`. The `.kiro/` directory is committed so
Kiro usage is visible for judging.
