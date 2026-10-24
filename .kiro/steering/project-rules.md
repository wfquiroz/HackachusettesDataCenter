---
title: HourMatch project rules
description: House rules every Kiro agent and human follows when working on this repo.
inclusion: always
---

# HourMatch — project rules

These are standing rules. Follow them in every change, every agent, every session.

## Design system (non-negotiable)

This is a polished product UI, not an AI-ish dashboard. Use ONLY these tokens.

### Palette
- Background: `#0A0C0F`
- Panel: `#12161B`
- Border: `#1F262E`
- Text: `#E6EDF3`
- Text dim: `#7D8A99`
- Clean / teal: `#2EF2C4`
- Warn / amber: `#FFB020`
- Bad / red: `#FF4D3D`

Never use purple, pink, or default blue. Always set a surface's background together with its text color — never half a pair.

### Type
- Body text: IBM Plex Sans.
- All numbers: IBM Plex Mono, `font-variant-numeric: tabular-nums`.

### Visual rules
- Icons: lucide, 1px line weight. No emoji.
- Corners: 4px max.
- Borders: 1px. No shadows.
- Status: a dot plus small-caps label, not a filled pill.
- Data lines: measured = solid, modeled = dashed.
- Controls (toggles, sliders): teal.
- Legend: one single teal → amber → red gradient.
- Data-center markers pulse.

### Map
- Basemap: the LIGHT OpenStreetMap tiles. NOT CARTO Dark Matter.
- Layer changes: smooth, Apple-Maps-style translucent transitions.

## Git topology

- There is **no `main` branch**. `origin/HEAD` defaults to `docs/planning`.
- `docs/planning` is Felipe + Kiro's working build.
- Push to a **feature branch**, named explicitly: `git push origin <feature-branch>`.
- Never push to a protected branch. Never force-push. Never `reset --hard` shared history.
- Merges into the trunk are a human decision, reviewed first — not an automatic agent action.

## File ownership (parallel work)

- Each agent owns its OWN files and its OWN branch.
- Two agents must never edit the same file at the same time — that corrupts work.
- Before starting parallel work, split files so ownership is clear.
- A worker on one feature does not touch another feature's files.

## Data vs model

- Measured data is real, from the 2604 polygons / source CSVs.
- Modeled values (decay, phased buildout, impact rings) are computed, shown dashed.
- Keep the two visually distinct. Never present a modeled number as measured.
