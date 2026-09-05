# ADR-140 — The charts, read: what a page draws is now something a task can hold

**Status:** accepted · **Date:** 2026-09-04 · **ADR-128 held that SVG text and geometry were outside `read-report`, so every page that draws published numbers no task could check — and a chart that plots the wrong series looks exactly like one that plots the right series. `read-report` now returns a `charts` section per visible `<svg>`: its texts with their positions, every mark counted by what it is, the longest drawn series, the text that lines up, and where each mark was placed. Four charts are held to oracles, two of them to a Python recomputation of the page's own projection**

## 1. The last thing the reader could not read

`read-report` finds figures, boxes, tables, rows and headings. It has never
found a chart. So the ordination's NMDS, the food web, the greenhouse's run
series and the selection log's fitness gradient published numbers to a reader
that no task in this kit could hold — and a wrong chart is not a *visibly*
wrong chart. It is the same picture with different coordinates.

## 2. `charts`, per visible `<svg>`

Keyed by the svg's own id (or its nearest identified ancestor's), capped at 16
charts × 40 texts × 60 marks:

| field | what it is |
|---|---|
| `viewBox` | the space the page drew in |
| `texts` | up to 40 `<text>` nodes, each with the `x`/`y` the page gave it |
| `n` | how many texts |
| `marks` | a count per tag — `circle`, `rect`, `path`, `line`, `polyline`, `polygon`, `ellipse` |
| `longest` | the most points any one polyline or path carries |
| `aligned.row` / `.col` | the longest row of text sharing a y, read left to right; the longest column sharing an x, read top to bottom |
| `points` | each text paired with the nearest mark within 30 units, by label |
| `at` | every mark centre, in document order, labelled or not |

Three choices worth naming.

**In the svg's own units, not in rendered pixels.** A rendered position depends
on the viewport; the page's arithmetic does not. Reading the attributes the page
computed is what lets an oracle recompute them.

**`aligned`, not `ticks`.** The plan asked for "each axis's tick labels in
order", and a reader cannot know an axis unless the page declares one. What it
*can* know is which texts line up. On a chart with axes that lowest row is the x
tick sequence; on the food web it is the trophic level headings and the species
names. Calling it `ticks` would have been the reader deciding what a drawing
means, which is the page's business.

**`points` and `at` are two different claims.** `points` is the pairing the
*page* made by putting a label beside a mark. `at` is where the marks are,
whether or not anything named them. A chart whose dots carry no labels still
plots them somewhere, and where is the claim.

## 3. Four charts, held

| page | chart | what is now held |
|---|---|---|
| greenhouse | `runChart` | viewBox, 5 dots, a 5-point path, and **the x of every dot** |
| ordination | `ordPlot` | viewBox, 4 circles, 4 axis lines, and all four sites present by name |
| food-web | `webSvg` | viewBox, 10 nodes, 13 links, 20 texts, and the species column in trophic order |
| selection-log | `gradBox` | viewBox, 6 circles, 3 lines, and **the x of the first, second and last dot** |

The two bold rows are the recomputation. The greenhouse's chart maps run *i* to

    X(i) = P + i/(n-1) · (W − P − 24)      W=680, H=250, P=52, n=5

and the labels to `Y(hi)+12` and `H−P`. A Python oracle of that formula gives
**52, 203, 354, 505, 656** and label rows at **36** and **198**, and those are
what the task asserts — the page's own projection, recomputed independently and
compared to what the page drew. The selection log's six dots come out at
**44, 144.4, 244.8, 345.2, 445.6, 546**; the task pins the first, second and
last. Neither number was typed from a reading.

The ordination's coordinates are deliberately *not* held. Its NMDS takes a seed
this task does not pin (ADR-134 recorded that the 5-site solution is
degenerate), so the arrangement is not reproducible and asserting a position
would be asserting a coincidence. The count, the axes and the four names are.

And the negative claim, which is the one that catches a chart drawn from stale
state: after the greenhouse's runs are wiped, `output.charts` **excludes**
`runChart`. There is no chart, and saying so is a fact about the page.

## 4. Verification

`verify_report` **60** (+11). The fixture gained two charts — one with axes, a
legend row, a 4-point polyline, a 6-point path, three labelled dots and one mark
with nothing beside it; one with a 7-point polyline — plus a chart inside a
`display:none` block that must not be read. The checks: a visible svg is a chart
and a hidden one is not; the viewBox and text count; every mark counted by what
it is; the longest series taken from the path in one chart and the polyline in
the other; the **lowest** aligned row taken rather than the first found (the
legend three rows above it is just as aligned); the leftmost column top to
bottom; the labelled pairs; every centre in `at` including a rect by its middle;
and a mark with no text near it placed but not named.

`mutate_report` **47** (+12): charts not read at all, a hidden chart read, marks
counted as one kind, a series' length taken as its mark count, a path's points
not counted, aligned text left unordered, the first aligned row taken instead of
the lowest, a text paired with any mark however far, a centre recorded only when
labelled, text positions dropped, a rect placed by its corner, and the viewBox
dropped. **47 killed, 0 survived.**

**A stale anchor, found by running it.** `mutate_report`'s BOX-regex mutant had
not matched since ADR-135 widened that regex for the lab's stations, so it had
been a `BAD MUTANT` — a mutation that never applied, reported as inconclusive —
in every run since, and the last recorded ledger row predated the change. Fixed
and re-run. The lesson is the same one ADR-130 learned about a discovery regex:
a runner that cannot see its own subject is not a runner.

Every page task was re-run: `charts` is new output on every `read-report`, and
all **54 tasks hold** with both canaries still refuted, plus **12 traces** PASS.

## 4a. Two things measuring the board turned up

ADR-138 made the Harness Board a measured artifact, and this slice's close is the
first time the board's own published copy has been read twice in a row. Two
findings, neither of them about charts:

**A read has two shapes, and only one is dated.** A large artifact comes back
from a read as a file, wrapped by the publisher and carrying
`<base href="/_f/<epoch>-…">` — the version marker `publish_state` dates every
measurement by. A small one comes back as its own HTML in a bare skeleton, with
no marker anywhere. ADR-056's rule then refuses it, correctly: *a copy that
cannot be dated cannot be ordered against the publish it would be evidence
about* — and one artifact could therefore never be measured at all.

`--taken <epoch|now>` is the third dating source: **the fetching reader stating
when it fetched**. It ranks below the marker (which is about the version) and
above mtime (which is about neither), it never overrides a marker when one is
present, and the ledger records what it is — *"about the fetch, not about the
version"*. A date whose provenance is unstated is how ADR-078's nine bad entries
got written; this one states it.

**The published board was holding first paint on a font request.** Every page of
this kit asks for its webfont stylesheet with `media="print"` and promotes it on
load (ADR-031). The board asked for it with `media="all"`, and the only place
that was ever visible is a measurement of the published copy — which is what
ADR-138's checker prints when it verifies one. Fixed in `harness_board.py`:
print, a `<noscript>` fallback, and the promoter. The board is a page of this
kit and is now held to the kit's rule.

`verify_publish_reach` **81** (+3) and `mutate_publish` **17** (+2) cover the new
dating source both ways: it dates a copy that has nothing else, and it never
passes itself off as the version.

## 4b. And a third: one last look

`audit_focus` failed the closing run with one *"never exposed, so never
measured"* and passed three solo runs, twice. ADR-136 fixed one member of this
family — a control mounted *after* the last stamp — and this is the other: a
control that HAS a box a moment after the probe that measured it. Every state
stamps and measures exposure at the instant it probes; under `run_all -j 2` a
probe can run before the browser has finished laying that state out, and if that
was the last state to show the control, coverage reports it as one no state
exposed. (ADR-134 widened `_settle` for the same reason and did not close it.)

Two fixes, because the first was not enough. `coverage()` now settles once and
measures exposure once more before counting — not a new state and not a second
chance: **the end of the walk is still the last state**, so finishing the
measurement its probe began is the same measurement. The next run then produced
the same fault in `audit_contrast`, on a page whose control is hidden again by
the end, which the end-of-walk look cannot reach.

So the walk now waits for **two animation frames** before it measures, in every
state. `_settle` answers *"is anything still moving?"* and cannot answer *"has
the browser laid this state out yet?"* — a page that reveals a control from its
own `requestAnimationFrame`, or a browser competing for the CPU with the other
half of `run_all -j 2`, has run the click handler and not yet produced a frame.
The first frame schedules; the second is delivered only after the first has been
painted, which is the browser's own answer to the question.

`verify_audit_states` **58** (+3): a control that never has a box is still
named, one whose box arrives after the last probe is counted, and one the page
reveals asynchronously is measured. `mutate_audit_states` **39 killed, 0
survived**, with the frame wait recorded as **2 known equivalents** and why:
`_click` already waits 150 ms, under which a page's own `requestAnimationFrame`
always lands, so no deterministic fixture can tell the two apart — the frame
wait is defence against *contention*, and contention is not reproducible. Kept
for the reason ADR-134 widened `_settle` from one second to two: an instrument
whose answer depends on what else is running is not an instrument. Recorded as
equivalent rather than asserted by a check that could not fail.

Measured after both fixes: `audit_contrast` and `audit_focus` run side by side,
both clean, where each had produced one phantom fault.

## 5. Held

- **`aligned` finds a row or column, not an axis.** On a page whose tick labels
  are fewer than three, or staggered, it finds nothing and reports an empty
  list. That is an honest empty, not a failure, and a page that wants its ticks
  held should give them a shared coordinate.
- **`points` is a 30-unit rule.** Two marks closer than that to one label take
  the nearer, and a label between two marks names one of them. It is the page's
  pairing read approximately; a page that wants it exact should mark it up.
- **Nothing reads a `<path>`'s shape**, only how many segments it has. A curve
  with the right number of points and the wrong ones would pass.
- **Four charts of the kit's fourteen-odd drawings are held.** The tree
  visualizer, tree proofs, cp-bench, soil-bench and the character keys draw and
  are not yet asserted.
- Transformed text (a rotated y-axis label) reports the attributes it was given,
  not where it ended up.

## 6. First reading

    read-report   charts on every page, 16 × 40 texts × 60 marks
    tasks         54 / 54 held, both canaries refuted; 12 / 12 traces PASS
    verify_report 60 / 60  ·  mutate_report 47 killed, 0 survived
    verify_publish_reach 81 / 81  ·  mutate_publish 17 killed, 0 survived
    verify_audit_states  58 / 58  ·  mutate_audit_states 39 killed, 0 survived, 2 equivalent
    kit   77 / 77 jobs, 5,747 / 5,747 checks
    board 5,337 checks, 272 / 272 mutants  ·  publish reach 42 / 42 measured
