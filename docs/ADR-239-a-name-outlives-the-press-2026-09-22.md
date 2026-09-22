# ADR-239 — A name outlives the press

**Date:** 2026-09-22 · **Status:** accepted · **Chain:** ADR-238 → this ·
**Protocol:** 1.11 (unchanged)

## Why

ADR-188 gave every control an **address**: the page's own name for it
(`@forage`, `@rCov/4`, `#tAdd`). Indexes renumber the moment a page rebuilds,
and four blind operators had spent their trials counting buttons. Each address
is checked, when it is published, to resolve back to its control. Nothing
checked it a moment later.

The field notebook's filed defect (eighth trial) is exactly that moment. Its
tally cards read `species-a0`. One tap made the card `species-a1`, so the name
the door had just published lasted one press. That was on the page's primary
data-entry control. The notebook's own task had given up on names and pressed
`@control:specGrid#0` six times, counting cards by position like the operators
before ADR-188.

## Decision

**A new audit, `tools/audit_addresses.py`.** It presses every control that
has an address, on every page, through the door (`PagePlugin.execute`). It
then reads the old address back through the door's own resolver. Each press
gets one of four verdicts:

| verdict | meaning |
|---|---|
| **HELD** | The old name resolves to the pressed control, or to its rebuilt successor under the same id, or under the same host and name. |
| **GONE** | The control left the page: a delete, or a key moving to its next couplet. There is nothing left to name. |
| **RENAMED** | The control is still there and its name is not. The label carried a value the press changed. |
| **SHADOWED** | The old name now resolves to a *different* control while the pressed one is still on the page. A caller acting on it presses the wrong thing and is told ok. |

"Still there" is decided by the node itself when the page kept it (the audit
marks it before the press). When the page re-rendered, it is decided by a
control under the same host whose label differs from the old one **only in its
digits**, which is the shape of a label that carries a count. A list rebuilt
into other words is GONE, not RENAMED. The bias is toward not crying wolf.

Controls a press brings into being join the walk, such as a quadrat's steppers
after *+ Add quadrat*. The gate is zero RENAMED and zero SHADOWED. The audit
runs in `run_all` and writes `tools/address_ledger.json`.

## What it found

**1. The door itself.** The audit's first reading on all 41 pages flagged
about 700 presses. Most were not the pages' fault. `data-h`, the stamp a name
resolves through, is written by DISCOVER, and DISCOVER ran only at the last
observe. A press that rebuilt a list left the rebuilt controls unstamped. The
list could be a picker collapsing to its pick or a tally board re-rendering.
After that, the very name the door had just published answered *"no control
answers to @isoPick/pepper"* until the client observed again.

Not needing that re-observe is the whole point of a name. `_resolve` now runs
DISCOVER before it reads a name, so it reads the page as it stands. A stamped
index is compared against the numbering as it is now, which is the only
numbering it can honestly be compared against.

**2. Two pages whose tally cards were named by their count.**

- **Field notebook:** ethogram and species boards, 7 cards (`forage0`,
  `species-a0`, …).
- **Farm scout:** pollinator board, 4 cards (`honeybee0`, …).

Each card's name div is now the `.nm` the reader takes as a name, a rule since
ADR-128. The card reads `species-a` and stays `species-a`.

**3. Steppers that said nothing but `−` and `+`.** The field notebook's
quadrat and mark–recapture steppers could only be named by counting to the
eighth button of the grid. Now each one says what it counts: *add one to Q4*,
*take one from Q1*, *add one to Marked (M)*.

After the fixes, the audit reads **1,632 presses on 41 pages: 1,615 held, 17
gone, 0 renamed, 0 shadowed.** That also meant 34 separate pages were clear on
the first honest reading.

The phenology tracker's `#pNext` is rebuilt reading the next plant's number
(`#5 →`, then `#6 →`). It is held by its id. An id is the page saying "this is
the same control".

## Held by

- **The two tasks now press by name.** In `page-field-notebook-science`, 39
  steps move from `specGrid#0` / `quadGrid#7` / `p-more#1` to
  `specGrid/species-a` / `add one to Q4` / `add one to Marked (M)`. In
  `page-farm-scout-science`, 11 steps move from `poGrid#n` to
  `poGrid/honeybee` … `poGrid/mason`. The tasks are unchanged otherwise: 95
  and 120 confirmed.
- **New suite `verify_addresses`, 36 checks.** It covers:
  - the rule, on readings stated in the suite, one per verdict and per edge;
  - a scratch page with a control of every shape, walked by the audit itself;
  - the door: a name from before a rebuild resolves after it, with no observe
    in between;
  - the real kit from the ledger: every page walked, none renamed, none
    shadowed;
  - the two found pages, walked live;
  - the notebook's names for its steppers;
  - both tasks: no index left.
- **New runner `tools/mutate_addresses.py`, 12 mutants.** The first run killed
  11 of 12. The survivor was "a shadowed page is not a problem". The suite's
  check used the fixture, which is a problem for its renamed cards anyway, so
  a rule that ignored shadowing still flagged it. The check now holds a
  shadowed-only reading and a renamed-only one separately. **12/12 killed.**

## Numbers

| | before | after |
|---|---|---|
| presses whose name outlived them | not measured | **1,615 of 1,632** (17 gone, 0 renamed, 0 shadowed) |
| field-notebook task steps pressing by index | 39 | **0** |
| farm-scout task steps pressing by index | 11 | **0** |
| task steps kit-wide pressing `host#n` | 164 | **114** |
| verify_addresses | — | **36** |
| mutate_addresses | — | **12**, all killed |

## Held

- **The other 114 index-addressed task steps.** They are on the pheno tracker
  (44), farm scout (43 outside the tallies), collection sheet (8), selection
  log (7) and five more pages. Their names are stable now. The tasks still
  count. Trigger: a task step that presses the wrong control after a page
  change. Price: a pass per task, oracle first.
- **The field notebook's other filed defect,** the report's
  duplicate-name suffix (`Shannon H′ #2`), is already closed by the task's
  per-box reads (`output.by.specResults…`). Nothing is left to fix there.
- **The remaining pages' filed defects:** ethogram, relevé, pheno tracker,
  stand sheet and ecology lab.

## Lessons

- An address checked only when it is published is a promise checked at the
  one moment it is certain to hold. The measurement that matters is one press
  later.
- The first reading was mostly the door's own fault, not the pages'. An audit
  that goes through the door finds the door before it finds anything else.
