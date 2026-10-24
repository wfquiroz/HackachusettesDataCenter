# HourMatch

**"Massachusetts wrote the rule. We built the meter."**

HourMatch shows whether a data center is *actually* clean hour by hour — not just on paper over a year — and who breathes the difference.

*Hackachusetts 2026 · Energy & Climate x Civic Action · Oct 24, 2026*

---

## The 20-second pitch

Massachusetts just made a rule (Executive Order 658, Sept 8 2026): big data centers must buy enough new clean power to match a **year** of their use. But the grid runs **hour by hour**. A data center can buy a year of solar and still pull gas every winter night, when the sun is down and New England peaks.

Towns now approve these projects. They have no tool to see the real hourly impact. HourMatch is that tool.

---

## What it does

1. **Map** — MA data centers, who lives nearby (environmental-justice block groups), power lines, clean supply.
2. **Report card** — one headline: *"Annual: 100% clean. Hourly: X%."* plus hidden CO₂, peak MW added, neighbors affected.
3. **Year heatmap** — 365 × 24 grid. Green = clean, amber = battery, red = grid/fossil. Live sliders.
4. **Town memo (AI)** — a one-page plain brief with 5 questions to ask the developer.
5. **Methodology** — every assumption, every source, every limit.

---

## Repo layout

```
hourmatch/
  data/raw/       # raw pulled data (gitignored large files)
  data/clean/     # cleaned CSVs the app reads
  data/SOURCES.md # source URL + pull date for every dataset
  pull/           # one script per source: pull_eia.py, pull_kit.py, pull_campd.py
  model.py        # the 8,760-hour model (Section 5 of the brief)
  tests/          # test_model.py — sanity checks on a tiny synthetic year
  app.py          # Streamlit UI
  memo.py         # LLM town memo
  config.yaml     # emission factors, defaults, assumptions
  docs/           # planning docs (see below)
```

## Planning docs

- [`docs/MODEL_SPEC.md`](docs/MODEL_SPEC.md) — exactly what `model.py` computes.
- [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) — every dataset, URL, and how to pull it.
- [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) — hour-by-hour build checklist + who owns what.
- [`docs/MAP_ENGINEER.md`](docs/MAP_ENGINEER.md) — handoff for the map engineer.
- [`docs/SUMMARY_FOR_MIKE.md`](docs/SUMMARY_FOR_MIKE.md) — the short version for Mike.

---

## Honesty rules (judges reward this)

- Hourly emissions are **estimates**. We label them.
- We never claim "the grid can / can't handle it" — we have no interconnection data.
- Westfield's size is reported two ways (150 vs 274 MW) — it is a slider, we show both.
- Neutral tone: the tool helps **good** projects prove themselves. Not anti-data-center.
- Every dataset is cited on screen. No street addresses.
