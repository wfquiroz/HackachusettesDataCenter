# HourMatch — Hackachusetts 2026 Submission

**"Massachusetts wrote the rule. We built the meter."**

Public repo: https://github.com/wfquiroz/HackachusettesDataCenter
Demo video: *(add YouTube/Vimeo link here before you submit)*

---

## Problem 1 — Massachusetts wants to grow AI, and can't decide where to put it

Boston is racing to grow as an AI hub. A coalition of industry and civic groups is
actively courting that growth, and companies — AWS, hyperscalers, AI startups —
want to expand into Massachusetts. Data centers are the physical floor of all of
it: no compute, no AI economy.

So the goal is *growth*. But the state has no shared way to answer the first
question every one of these projects raises: **where should it go?** Right now
siting is guesswork and politics. A company picks a parcel, a town reacts, and the
project either stalls in a fight or lands in the wrong place. Massachusetts is
trying to *attract* data centers while having no instrument to steer them to the
sites that actually work — enough land, grid headroom, water, and the fewest people
harmed. Growth without a map is how you get bans instead of build-out.

## Problem 2 — the clean-energy rule the state already wrote has an hourly hole

Massachusetts Executive Order 658 (Sept 8, 2026) requires a big data center to
match a **year** of its energy with new clean power. But the grid runs on an
**hour**. A center can buy a year of solar and still pull gas on a winter night,
when the sun is down and New England burns its dirtiest fuel. "100% clean" on paper
can be ~20% clean by the hour — and no one in the approval chain can see that gap.

## The solution — one validated instrument that serves both sides

HourMatch turns both problems into numbers, and every number is grounded in real,
cited public data (see "How validated" below). Drop a data center anywhere in MA,
pick its size, and it shows the hourly-clean truth, who absorbs the impact, **where
the state should steer it instead**, and whether the town already restricts them.

It does not say yes or no. It gives government and industry the *same* honest,
data-backed picture — so growth happens in the right places, not the contested
ones.

---

## What it does — for government

The state and towns deciding where growth goes.

**1. Turns a PDF claim into one honest number.**
A developer's filing says "100% clean, annually." HourMatch shows the hourly
truth beside it: *"Annual 100% · Hourly ~23%."* That one line is what a town board
needs to ask the right question.

**2. Shows who absorbs the impact.**
Drop a site and the map shows the people within range, weighted by
environmental-justice burden — so a board sees whether the harm lands on a
community already carrying more than its share. Impact comes in real units a town
official knows: tonnes CO₂/yr, GWh/yr (≈ N homes' power), million gal/day, dB.

**3. Recommends where the state should steer growth.**
The placement optimizer grades any MA location and recommends the 5 best sites in
the state, spread ≥30 miles apart and clipped to the real border — the sites where
a data center brings the jobs and compute with the least harm. This is the map
Massachusetts is missing: not "should we allow data centers," but "here is where
to put them." Two MA towns show why it matters: one banned data centers over a site
our model grades an **A**; another's actual site grades a **D**. Both reacted
politically, blind. HourMatch is the tool that would have told them which was which.

**4. Puts the real legal landscape on the table.**
A sourced dataset of 13 MA towns and their actual rules — full bans, moratoriums,
zoning limits. Drop a center in one and the card flags *"this town bans data
centers"* with the news source. A board sees what its neighbors already did.

## What it does — for private / companies

The companies — AWS, hyperscalers, AI builders — expanding into Massachusetts.

**5. Validates a company's good-faith siting — for its public image.**
A data center's biggest obstacle isn't engineering, it's trust. A company like AWS
can run its proposed MA site through HourMatch and show, with validated public
data, that it chose a low-impact location and made a genuine effort to minimize
harm to the surrounding community — the hourly-clean score, the people-impact, the
placement grade. That's a credibility asset a glossy annual "100% clean" claim
can't buy: proof of good-faith siting a greenwashed competitor can't fake.

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

## How validated — this is built on real data, not vibes

Every number in HourMatch traces to a real public dataset, and the model behind the
recommendations is statistically validated:

- **Trained on 1,839 real US data center sites.** Not synthetic, not a toy — the
  actual national build-out.
- **Cross-validated accuracy: R² 0.975.** The model genuinely predicts where the
  industry sites data centers.
- **Passing placebo test: R² −0.048.** We shuffled the labels and the model
  learned nothing — proof the 0.975 is real signal, not overfitting. This is the
  check most ML demos skip, and it's shown on screen in the Model tab.
- **Honest feature weights, on screen:** power price 46%, climate 34%, etc. — you
  can see *why* a site scores the way it does.
- **Reproducible.** `us_model/analysis.ipynb` regenerates the whole thing.
- **Real public sources throughout:** ISO-NE hourly grid generation, MassGIS state
  boundary + hydrology, environmental-justice block groups, and a hand-built,
  individually-cited CSV of 13 MA towns' actual data-center rules.

**The "go vs should" thesis rests on that validation:** the validated model learns
where data centers *actually* go (cheap power, few people), and the placement
optimizer inverts it into where one *should* go in MA — scoring on who absorbs the
harm (people 45%, dirty air, grid strain, water). Because the model is validated,
the recommendation is defensible, not an opinion.

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
- **Kiro CLI** — heavy clone/branch/push/test work; **Kiro IDE** — human
  hand-edits and close reading of agent diffs.
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
