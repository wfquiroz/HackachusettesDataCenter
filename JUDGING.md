# HourMatch — Judging Write-up

**"Massachusetts wrote the rule. We built the meter."**
Repo: https://github.com/wfquiroz/HackachusettesDataCenter · Demo: *(YouTube link)*

---

## 1. Potential Value

**Problem 1 — growth with nowhere to point it.** Boston is racing to become an AI
hub; a coalition is courting that growth and companies (AWS, hyperscalers, AI
startups) want to expand into Massachusetts. Data centers are the physical floor of
that economy. But the state has no shared instrument to answer the first question
every project raises — *where should it go?* Siting is guesswork and politics, so
projects stall in fights or land in the wrong place. Growth without a map produces
bans, not build-out.

**Problem 2 (secondary) — the clean-energy rule has an hourly hole.** Executive
Order 658 (Sept 8, 2026) makes a data center match a *year* of energy with clean
power, but the grid runs *hourly*. "100% clean annually" can be ~20% clean at 2am
in January, and no one in the approval chain can see the gap.

**Who benefits, and how the journey fits their need.**
- *The state / a town planning board* drops a proposed site and gets a recommended
  location — the map Massachusetts is missing. Their need is "where do we steer
  growth so it actually gets built," and we answer it with data, not politics.
- *A company like AWS* runs its own site to validate, with cited public data, that
  it chose a low-impact location — a public-image and permitting asset a greenwashed
  annual claim can't buy.
- *A resident in an environmental-justice block group* is made visible: impact is
  weighted by who already carries the most pollution, so equity is in the model.

**Scalable and realistic.** Not MA-specific. The hourly model needs only a regional
grid feed (ISO-NE today; CAISO/PJM/ERCOT are the same shape); the placement model
needs population + a state boundary. Any state chasing AI growth — or writing a
matching rule — is a drop-in. It's a thin app over real public data, not a toy.

**Market.** Carbon-accounting dashboards (Watershed, Persefoni) do *corporate
annual* reporting; grid-carbon APIs (WattTime, Electricity Maps) sell the raw
signal. **Nobody** combines hourly matching + environmental-justice exposure + a
validated siting optimizer aimed at the *decision* — the state steering growth and
the company proving good faith. That civic, place-based angle is open market.

**Why it's credible: it's validated on real data.** The recommendation engine is a
model trained on **1,839 real US data center sites**, cross-validated at **R²
0.975**, with a **passing placebo test (R² −0.048)** that proves the signal is real
and not overfit — shown on screen. Every map number traces to a cited public source
(ISO-NE, MassGIS, EJ block groups, a hand-cited 13-town ban dataset). The siting
advice is defensible, not an opinion.

**Accessibility & adoption.** Runs in a browser, no login, light map, plain-English
numbers in units a non-engineer knows (homes-worth of power, gallons/day,
decibels). Measured data is solid, modeled is dashed — the user always knows what's
real. Adoption path: a town hands it to its planning board for one meeting; a state
agency embeds it in the EO-658 review workflow.

---

## 2. Implementation — how Kiro was used

We treated Kiro not as autocomplete but as a **team of agents under house rules**,
which is what let a small team move fast without stepping on each other.

**Tools used — Crew, CLI, and IDE, each for what it's best at.**
- **Kiro Crew (the core of our strategy)** — a conductor/PM pattern: a lead agent
  coordinated parallel worker agents, each owning its own files and its own feature
  branch, reconciling through pull requests. This is why multiple features (US ML
  model, placement optimizer, map features, data pulls) could progress at once
  without merge chaos.
- **Kiro CLI** — the heavy lifting: clone, branch, push, run the model tests,
  reproduce the notebook. Fast, scriptable, close to git.
- **Kiro IDE** — human hand-edits and close reading of agent diffs.

**Spec-driven development vs vibe coding.** Before building, we committed a spec
set to the repo — `docs/MODEL_SPEC.md` (exactly what `model.py` computes),
`docs/DATA_SOURCES.md` (every dataset + pull method), `docs/BUILD_PLAN.md`
(hour-by-hour checklist + ownership), `docs/MAP_ENGINEER.md` (the map handoff). One
source of truth every teammate and every agent pulled from. The payoff over vibe
coding was concrete: when we split work across agents, each read the same spec, so
their outputs *composed* instead of conflicting. A vibe-coded version would have
had each agent inventing its own units and column names.
*(Honest note: these are plain-markdown specs committed to the repo, not Kiro's
native spec-folder generator — we used the discipline, in our own format.)*

**Steering — our single biggest lever.** `.kiro/steering/project-rules.md` is an
`inclusion: always` doc every agent loads on every turn. It encodes three things:
1. A **non-negotiable design system** — exact palette, IBM Plex type, lucide 1px
   icons, 4px corners, no shadows, dot+small-caps status, *measured = solid /
   modeled = dashed*. This is why a UI built by several agents across many sessions
   looks like one designed product, not an AI patchwork.
2. **Git topology** — no `main`; push to feature branches; trunk merges are a human
   decision. This kept agents from force-pushing shared history.
3. **File ownership for parallel work** — two agents never edit the same file.
   This rule, enforced by steering, is what made the Crew parallelism safe.
Steering was the difference between "fast and chaotic" and "fast and coherent."

**Automation — a 30-minute git-upkeep cron.** Because this was fast-paced hacking
with teammates pushing constantly, a teammate set up a **Kiro Crew scheduled job
that runs every ~30 minutes to keep git in sync** — fetch all branches, report what
changed, and keep the shared branch current — so no one built on a stale tree and
divergences surfaced in minutes instead of at merge time. This is Crew's scheduling
(cron) standing in for a CI janitor, and in a multi-person sprint it quietly
prevented the single most common hackathon failure: a giant end-of-night merge.

**MCP.** We configured the **Lovable MCP server** (`/.kiro/settings/mcp.json`) to
extend Kiro toward rapid UI generation — wiring an external design/codegen service
into the agent's toolset rather than hand-rolling every component.

**Invariant / property-style testing.** `tests/test_model.py` doesn't just check
fixed outputs — it asserts *properties that must hold for any input*:
- hourly match can **never exceed** annual match,
- adding a battery can **never lower** the hourly match,
- an all-solar supply **always** has uncovered (red) night hours.
These invariant checks caught logic we'd have missed with single-value asserts —
e.g. a storage path that could inflate the match above annual. (We used pytest with
hand-written invariants rather than the `hypothesis` library, but the *strategy* is
property-based: test the law, not the example.)

---

## 3. Quality & Design

**Creativity / originality.** The signature idea is the **"go vs should"
contrast**: a validated ML model (1,839 real US sites, CV R² 0.975, passing placebo
test) learns where data centers *actually* get built — then we invert its logic
into a placement optimizer for where one *should* go in Massachusetts. Showing the
industry's revealed preference *and* a better civic choice, on the same map, is a
genuinely original framing.

**Unique public data, combined in a surprising way.** ISO-NE hourly generation,
MassGIS boundary + hydrology, environmental-justice block groups, a hand-built
sourced CSV of **13 MA towns' real data-center bans/moratoriums**, and 1,839
US sites for the ML model. The town-ban dataset in particular is current,
hand-cited civic data that doesn't exist pre-packaged anywhere — and it ties the
model straight to live political reality (drop a center in Holyoke → "this town
bans data centers," with the source).

**Intuitive, intentional UI.** One headline number, toggleable impact surfaces,
drop-and-play buildout with motion cues (pulse ring, breathing surface, threshold
flash on the exact year/factor that crosses into harm), real units, and a
"Find best site" button that recommends five spaced, in-state options. The design
system from steering makes it read as a polished product. The playback turns a
static map into a tool you *operate*.

---

## Submission requirements checklist

- **Text description** — `SUBMISSION.md` (features + problem/solution + gov vs
  private value).
- **Public GitHub repo** — above, with source, data in `data/clean/`, and run
  instructions.
- **`.kiro/` committed** — steering doc + settings are in the repo and *not*
  gitignored.
- **Demo video (< 3 min, public)** — link to add on the form.
