# HourMatch — the short version (for Mike)

## What we are building

A tool that checks if a data center is **really** clean.

The rule in Massachusetts says: match a **year** of your power with clean power.
The grid works by the **hour**. Those are not the same.

A data center can buy a year of solar and still burn gas every winter night.
Our tool shows that gap. In one number.

## The one number

> **Annual: 100% clean. Hourly: X%.**

The first number is what the rule counts. The second is what the air counts.
The gap between them is the whole point.

## Why it matters

- Massachusetts got ~2 GW of data-center requests. That is a lot of power.
- Towns now say yes or no to each project. They have no tool to judge them.
- One site (Lowell) already fought over diesel generators next to homes.

We are not against data centers. We help the good ones prove they are good.

## What we show on screen

1. A map of Massachusetts. Data centers, power lines, who lives nearby.
2. A report card for each site: the one number, hidden CO₂, neighbors affected.
3. A year-long grid. Green means clean, red means fossil. Sliders to play with.
4. A plain memo a town can read, written by AI, with sources shown.

## Who is doing what

| Person | Owns |
|---|---|
| Felipe (me + AI partner) | The model, the data pulls, the Streamlit app, the AI memo |
| Map engineer | The map screen — see `docs/MAP_ENGINEER.md` |
| Mike | TBD — pick from the build plan |

## Where we are

Repo is set up. Planning docs written. Next step: pull the grid data and get the
headline number for Westfield on all-solar. That number is the demo.

## The closing line

> "Massachusetts wrote the rule. We built the meter."
