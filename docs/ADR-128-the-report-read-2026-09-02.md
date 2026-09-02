# ADR-128 — The report, read: every data-entry page entered through the gateway and held to a hand-checked oracle

**Status:** accepted · **Date:** 2026-09-02 · **Gives the harness a reader for a page's report, a picker driven the way a finger drives it, a way for a task to name a control the page's way, and twenty-one science tasks — one per data-entry page of the kit — that enter data and hold the page's arithmetic to numbers computed by hand**

## 1. The gap

The robot (ADR-117, ADR-124) proved every routed page can be operated from
its manifest: every tool driven, nothing broken. The tasks (ADR-125) proved
a goal can be graded. But the one page task that existed typed a value into
"the first text control" and read it back — it never entered a collection,
never opened the analysis, never asked whether Chao1 was 6.5. The kit's
science suites (`verify_cs_science`, `verify_rv`, `verify_ss`, the benches)
do ask, with Playwright reaching straight into the DOM: `pg.click("#cAdd")`,
`querySelectorAll('#anBox .tile')`. A model or a robot at the gateway had no
such reach. It could press every button and could not check a single figure.

Three things were missing, and none of them was a page's fault.

- **No reader.** `read-control` reads one control; `read-page` reads the
  page's health. Nothing read the *report* — the tiles, the verdict boxes,
  the lists, the tables — that a data-entry page renders from what was
  entered. Without it a task could enter everything and grade nothing.
- **No picker.** A FEK picker (the genus on the collection sheet, the
  species on the relevé, the individual on the selection log) is a filter
  box plus an option list. Typing into the filter enters nothing; the page
  records the option that is *clicked*. `set-text` on the search was a
  driven that drove nothing.
- **No names.** A task's arguments are literal. A selector is `text_in:7`
  — positional within a kind on a page whose widgets rebuild — so a task
  that wrote one down was coupled to a snapshot it had never seen, and a
  dial's option (`4`, under `#rCov`) had no address at all.

## 2. The decision

### `read-report` (SENSITIVE_READ, no arguments) — the page plugin

One call returns the page's report as it stands:

- **`figures`** — every element that shows a `.v` value beside a `.l`
  label, keyed by the label: the kit's `.tile`, the selection log's
  `.stat .st`, the benches' `.stat .k`, the greenhouse's `.gh-stat` —
  *the pair is the convention, the class is not* (the first draft named
  four classes and read nothing on the selection log). The first label
  wins in the flat map; a second carries ` #2`. A `<small>` unit inside
  a value is spaced off (`38.9 mol/m²/d`, not `38.9mol/m²/d`).
- **`by`** — the same figures by the box they sit in (the nearest
  identified ancestor), because a label is a fact of its box: the relevé's
  pack shows `families 23` and its analysis `families 2`; `grOut` shows
  `doubling time` twice, in hours and in minutes.
- **`boxes`** — the text of every element whose id follows the kit's
  naming: `an*`, `*Out`, `*Box`, `*Stats`, `*Plan`, `*Matrix`, `*Verdict`,
  `*Note`, `*Warn`, `*Tell`, `*Advice`, `*Refuse`, `*Table`, `*Chart`,
  `*List`, `*Grid`, `*Export`, `*Lint`, `*Cmd`, `*Meas`, `*Help`, `*Card`,
  `*Legend`, any case, hyphens allowed (`eco-out`), and the plain names
  `coherence`, `report`, `results`, `outputs`, `toast`, `journal`. Read
  **whether or not the box's pane is open** — the first draft filtered by
  visibility and read nothing at rest on a page whose analysis lives
  behind a closed tab. Which boxes a reader could see right now is
  reported beside them as **`shown`**, not used to drop them.
- **`tables`** — every `<table>`'s cells, row by row, by its host: the
  recipe card's ingredient/quantity pairs, the trial's entry means, the
  season's quadrat table — a blob of text loses which quantity belongs to
  which row.
- **`rows`** — the count of `.row2` children per list.

Everything is capped: 200 figures, 64 boxes of 1,500 characters, 16
tables of 40 rows of 8 cells, whitespace normalised.

### `pick` (DRAFT, `selector`, `value`) — the page plugin

Drives a FEK picker the way a finger does: types the value into the
filter, then clicks the option whose **label** (its text without the
`<small>` sub-line) matches **exactly**, else the option it **prefixes**,
else — when the filter left **exactly one** option — that one (`Tarnok`
inside `S. leucophylla 'Tarnok' × S. flava var. ornata`). Two or more left
is a guess and is refused as `ambiguous: N options match`; none left is
`no option matches`. The snapshot publishes each picker's option labels as
an argument-set pool `pick` — `[{selector, value}]`, sub-lines stripped —
because the first walk of every page left `pick` undriven on five pages
whose pickers offer no genus; the manifest's examples are only examples. The genus tell, the
guild badge and the host list render from the picker's `onchange` — a
hidden write-through would have skipped them (`verify_cs_science` learned
that the hard way; the gateway now enters data the way the page expects).

### `@control:<name>` — the task grammar

A task names a control the page's way, resolved to the moment's selector
from the latest snapshot any step so far has carried: the element's **id**
(`cName`), then its **label** (a stepper's `area searched`; a picker's
search carries `<label> filter`), then the id of the nearest identified
ancestor, its **host** (`genEntry`). `@control:<host>/<label>` scopes a
label every dial shares to one dial (`rCov/4`); a trailing `#n` is the nth
match in document order (`iList/died#2`); `season #` is a label. Nothing
found is the task's DEFECT, never the page's refusal. A task never writes a
selector down; `verify_tasks` pins that no science task does.

For that the snapshot now carries, per control, **`id`**, **`host`**, and
a **label a finger reads**: the aria-label, a `.nm` child, or the text with
`<small>` and `<kbd>` removed — a dial option is `4`, not `425–50%`; a
behaviour key is `forage`, not `forageFf0`.

### Twenty-one science tasks — `tools/tasks/page-*.json`

One per data-entry page of the kit. Each enters data through the gateway
by the page's own names, reads the report, and holds figures, table cells
or row counts — never prose alone — to an oracle **computed by hand and by
tool, not read off the page**: the collection sheet's Chao1 6.5 from
`5 + 3·2/(2·(1+1))`, Shannon H′ 1.359 from p = .1 .1 .1 .2 .5; the
relevé's H′ 0.53 on cover shares 62.5 : 15 : 0.5; the stand sheet's
QMD 29.7 and SDI 132 on four Douglas-fir; Cohen's κ 0.722 from two
ten-sample records; the selection log's i = 0.586 from S 1.000 over the
population SD; the pheno tracker's S = +1.44 and χ² 0.00; the deployment
log's 11.61 GB (`14 d × 86400 s × 0.1 × 96 kB/s`), GSD 8.33 cm/px, 12,960
readings; the cell bench's slope 0.0406, r² 0.9999, 2.83×10⁻⁴ M; the micro
bench's µ = ln 2 = 0.6931 h⁻¹; the cp bench's 43 of 84 cold days from the
demo series; the soil bench's blended C:N 42.9:1 from ΣC/ΣN; the breeding
bench's Nₑ 36.0, i 1.755, LSD 0.82 kg; the survey design's 15 Humboldt rows
and one absence refused without a scope; the ordination's 190 pairs and
the four-site boundary; the food web's 12/81 = 0.148; the recipe card's
`6.3–12.5 lb` and `1.5 tsp` from the page's own rounding rules, ported;
the field notebook's Morisita 2.24 and Lincoln–Petersen 10; the field
season's **whole seeded meadow** — 29 marked, 33 caught, 8 marks, 108
plants in five quadrats, 90/100 — from an independent Python port of its
mulberry32 generator; the experiment guide's `17.9 ms · 9× the floor` and
its exact `.eco` text; the greenhouse's DLI 38.9 and the demo runs' z with
self excluded. Each ends by finding the page intact (no junk, no errors).
Where a plan's hand figure disagreed with the page, the tool decided:
breeding's ΔF at K = 10 is 5.00 %, not 2.50; the assay's unknown reads
11.3873 from the unrounded slope; the 32 GB card lasts 39 days.

A **page canary** (`page-collection-sheet-canary`, `must: FAIL`) enters
one collection and claims the sheet counts two; it is refuted and held —
the grader can say no to a page's figure, not only to the fixture's.

### Verification

- **`tools/verify/verify_report.py`** (**30 checks**), in process on a
  fixture page whose report is known plus the collection sheet: every
  clause of `read-report`, `pick` and the naming above.
- **`tools/mutate_report.py`** — **22 mutants** of the page plugin against
  it: figures only `.tile` again, a second label overwriting the first,
  figures not kept by box, the unit glued, the old five prefixes, every id a
  box, a closed pane's box dropped, every box shown, tables and lists
  unread, pick taking the first option, never the sole one, matching the
  sub-line, no prefix, one refusal for two reasons, no id, host = pane, a
  dial labelled by its whole text, a key by its whole text, the picker pool
  unpublished, the pool carrying sub-lines. **22 killed.**
- **`verify_tasks`** (**133 checks**, +63; 102 in the mutant runner's quick mode): the `@control` grammar in
  section A; two canaries; every real task held per its `must`; section G,
  the science: every data-entry page has a task and every science task is
  on one, each enters data, holds a figure or a table cell or a row count
  or a box's whole text, names its controls the page's way, states its
  numbers in its goal, and is in the ledger with at least twenty confirmed
  expectations. **`mutate_tasks`: 24 mutants**, +8 on `find_control`
  (`@control` not a reference, label over id, host ignored, `#n` ignored,
  `#n` unparsed, None instead of DEFECT, no snapshot searched, the first
  snapshot instead of the latest). **24 killed.**
- **`verify_walk`**: 17 page tools (was 15), `pick` and `read-report`
  driven on the collection sheet; ledgers regenerated for `csrbt-page`,
  `csrbt-page@mcp` and all 41 routed pages.

### Two findings on the kit, from the robot, once it could pick

Driving pickers for real changed what the page walk saw:

- **Fifteen pages: a record row pushed a phone's page 4 px sideways** once
  a host was recorded on the collection sheet — `.rowlist { display:grid }`
  with the implicit `auto` column, whose floor is the widest row's
  min-content, and a `.row2` whose guild badge, count and remove button do
  not shrink. Fixed in the shared row CSS on every page that carries it:
  `grid-template-columns: minmax(0, 1fr)`, and the row wraps below 220 px
  of name so the badge, the count and the button take the next line
  together. The science tasks now end on `overflow == 0`, and `verify_tasks`
  pins that they do.
- **The experiment guide read a photograph as a protocol.** A JPEG dropped
  on the import card was read as text; its bytes became "extra lines" in
  the lint, one wide enough to spill 30 px. Now refused by name — by MIME
  type, and by its bytes when the type is blank — with nothing imported;
  lint rows wrap long tokens. `verify_experiment_guide` +4 (86), the
  science task +3. The guide's panes had never been opened by the robot at
  all: its tabs name their pane by `aria-controls`, not `data-pane`, so
  `show-pane` refused every one and the pane pool was luck; `_open_pane`
  now honours both.

`CSRBT_WALK_VERBOSE=1` prints every command a walk makes, which is how the
second finding was traced to its drop; `--page a.html,b.html` re-walks a
few pages into their own ledger entries.

## 3. First reading

    23 page tasks held (21 science, the read-back, the canary)
    1,316 expectations confirmed on the page, 1 refuted on purpose
    every one of the 21 data-entry pages entered and read through the gateway
    41 / 41 routed pages walked at 17 tools; kit 76 / 76 jobs, 5,389 / 5,389 checks
    16 pages republished and stamped current (the row-wrap and the guide's import)

## 4. Held

- **Characters, suites, explorers.** `plant-characters`, `fungal-characters`
  and `cp-characters` are keys (pick states, read matches); `soil-suite`,
  `cp-suite`, `breeding-suite`, `tree-visualizer`, `douglas-explorer` and
  `ecology-lab` are simulators and explorers. They are walked (ADR-124) but
  have no science task yet. Next slice.
- **Wall clocks and dialogs.** The ethogram's time budget, the ordination's
  `Date.now()`-seeded NMDS starts, the greenhouse's demo log read with a
  real clock, `confirm()` on Clear buttons: not driven, on purpose. The
  tasks hold what is deterministic (κ, the bands, the boundary fixtures,
  the demo runs) and say so in their goals.
- **`excludes`.** The grammar has no "does not contain". A task that wants
  to say a sentence is absent says what replaced it. Added when a task
  needs it, with its mutant.
- **Charts.** SVG text and geometry are outside `read-report`; the suites
  that check them keep doing so with Playwright.
