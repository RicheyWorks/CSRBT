# ADR-135 — The stations, named: the lab's thirteen cards and the session they chart

**Status:** accepted · **Date:** 2026-09-03 · **Every station on the interactive lab now carries the session key the engine uses for it, so its figures are read under that name instead of colliding under `#main`. The kit's own shipped session is dropped onto the page through the gateway, and four stations' figures are held to the engine's own — 33 expectations where there were none.**

## 1. What ADR-129 held

> The lab's session station cards have no ids, so their tiles collide under
> `#main`; the task reads the workbench and the terrarium, not the stations.

Thirteen stations — the meadow, the drift, the census, the archipelago, the
fossil record, the survey grid, the theory bench, the greenhouse, the entered
data, the notebook, the trees, the hypotheses, the island — were all anonymous
`<section class="card">`. They reuse the same tile labels (*effective species*,
*Chao1 est.*, *evenness J′*), so `read-report`'s by-box map folded nine
stations' figures into one, where a duplicate label became `#2`, `#3` and
nobody could say which station it came from.

The part of the page a student actually walks through was unheld.

## 2. The decision

### The id is the engine's own key

`card()` takes a slug and sets `id="station-<key>"`, where the key is the
session's own — `meadow`, `drift`, `demography`, `models`, `crosses`,
`entered`, `notes`, `trees`, `hypotheses`, and the four the page adds
(`archipelago`, `fossils`, `grid`, `island`). A figure read off the page is
read under the same name the engine reports it under. `read-report`'s box
pattern accepts `station-*`.

### The drop the harness could never make

The page says *"drop a session anywhere to reload"* — and it means anywhere:
the listener is on the **window**. The swarm stamps `data-h-drop` on any
element that registers a `drop` listener, and a window is not an element, so
the lab published no drop zone and the harness had never dropped anything on
it through four ADRs. A `drop` listener on the window or the document now
stamps the page's `<body>`, because the surface a reader drops onto is then
the page itself.

`FIXTURES["session"]` is the kit's shipped
`docs/ecology-experiment-session.json`, read from `docs/` rather than pasted
into the plugin as base64: a copy in the plugin would be a second session that
drifts from the one the engine writes, and a page that charts it must chart
**the** session.

### A control the page never named

The lab's drop zone is the page's own `<body>`: no id, no host, and a "label"
that is the whole navigation bar. It is perfectly identifiable by *what it is*
— the one drop zone on the page — and a task that cannot say that has to
invent an id for the page's sake, which is the page changing to suit the
harness. `@control:kind=drop_zone` names a control by its kind, `#n` picks
among several, and naming by id still wins.

### What is held

`two-targets-stations`: run `sample-experiment` through the lab engine, drop
the session the engine wrote onto the page, and hold four stations to it —

- **the meadow**, all three phases: `J′`, effective species and Chao1 for
  graze, bloom and seasons, and the curve shapes (`geometric`,
  `broken stick`);
- **the census**: 676 completed lives, mean age 820 ops;
- **the theory bench**, six models: the logistic and island equilibria, the
  Hardy–Weinberg *p* and χ², Euler–Lotka's R₀ and exact *r*, and both
  mark–recapture estimators;
- **the entered data**, all three datasets: kinds, Shannon, evenness, Chao1.

33 expectations, every one a page figure held to the engine's own number
through `~=` at the precision the page prints. The page charts what the engine
computed; if a station disagrees with the session it is charting, one of them
is wrong.

## 3. Verification

`verify_tasks` **209** (+6): `kind=` names a control the page never named, `#n`
picks among them, naming by id is unchanged, and a kind nothing matches is the
task's DEFECT.

`mutate_tasks` **44** (+3): `kind=` removed, matching on the label instead of
the kind, and swallowing a plain id.

`verify_report` 50 at the widened box pattern.

    verify_tasks 209 / 209 · mutate_tasks 44 killed, 0 survived
    54 tasks, 54 held · kit  77 / 77 jobs, 5,585 / 5,585 checks

## 4. Held

- Nine of the thirteen stations are charted but not held: the drift, the
  archipelago, the fossil record, the survey grid, the greenhouse's Punnett
  squares, the notebook, the trees, the hypotheses and the island. The session
  carries figures for some and not others; the four held here are the ones the
  engine reports numbers for that the page prints as tiles.
- The stations' **charts** — bars, rarefaction lines, the Shepard plot — are
  SVG, and still outside `read-report` (ADR-128's hold).
