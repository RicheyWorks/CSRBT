# ADR-181 — The charts, read (2): the compost log, the splay chart, the 2-3-4 view and the trap count are held to their own scales

**Status:** accepted · **Date:** 2026-09-10 · **ADR-140 gave `read-report` a `charts` channel and held four of the kit's fourteen-odd drawings, naming the rest — the tree proofs, cp-bench, soil-bench and the visualizer draw "and are not yet asserted." Four more are held now, three of them to a Python recomputation of the page's own projection: the soil bench's compost chart (eighteen dots, two threshold lines, five turning ticks, every position from the scale the page states), the tree proofs' splay chart (twenty bars under one amortized line, the last bar's centre recomputed from the ticks and the cost the task already holds) and its red-black 2-3-4 view (held to what a 2-3-4 tree is), and the cp-bench's trap-count chart (held to the task's own entries). Two suite pages that advertise counts moved with their suites and were republished.**

## The drawings ADR-140 left

ADR-140's channel reads a chart in the svg's own units — every `<text>` with
the x and y the page gave it, every mark counted by tag, the longest series,
the aligned row and column, every mark centre in document order — so that an
oracle can recompute what the page computed. It held four charts and said
plainly which it had not: *"The tree visualizer, tree proofs, cp-bench,
soil-bench and the character keys draw and are not yet asserted."* Those tasks
have run every slice since with `charts` in every `read-report` and nothing
holding it. A compost chart that put its 55 °C line at the wrong height, a
splay chart whose bars did not match the costs the task holds two lines
above, a 2-3-4 view with a leaf out of order — each would have passed.

## What is held now

**Soil bench — `cChart`, to a port.** The worked example logs eighteen
readings (32, 48, 58, 62, 64, 61, … 54, 49) with five turnings while hot. The
chart's scale is its own prose and geometry: x from the left pad to the right
edge less 16, evenly by reading; y from a floor of 20 (or four below the
coldest) to a ceiling of 70 (or four above the hottest); the 55 and 66 degree
lines at those temperatures; one tick per turning, under its reading.
`verify_soil` states the eighteen readings and the five turnings, ports
`cx(i)` and `cy(t)`, and holds the page's circles to the port one for one,
the two threshold lines and the five ticks to their y and x, and the peak (64,
the fifth reading) as the highest dot. The task holds the marks — 18 circles,
7 lines, 1 rect, 1 path — the longest series 18, the two threshold labels
seven units above their lines at x = pad + 6, the first, peak and last
dot's centre, and `points` empty; the suite recomputes each from the port and holds the task's
literal to it. The suite goes red when the last dot's y is moved by a tenth.

**Tree proofs — `spChart` and `rbSvg`.** The splay chart draws twenty seeded
accesses as twenty bars under one amortized polyline, bars of width
min(22, (W − 2·pad)/n − 3) spaced evenly, y linear to a ceiling maxV with
ticks at its quarters. The task holds the ticks the page printed (15, 11, 8,
4, 0), the marks (20 rects, 5 lines, 1 polyline), the legend texts and the
last bar's centre; `verify_proofs` takes maxV from the held ticks (which must
be quarters of one ceiling, read top to bottom), the last access's actual cost
from `figures.last actual` the task already held, recomputes the last bar's
centre from those two figures and holds the task's literal to it — a literal
transcribed from the page cannot pass a scale it does not fit. The 2-3-4 view
is held to what a 2-3-4 tree *is*: the task holds the root text (8 · 20 · 36)
and the leaf row (2 · 5 · 6, 11 · 15 · 18, 26 · 28, 38 · 39 · 40); the suite
holds every group sorted, the root's keys separating the leaves in order, and
13 to 15 keys in all — the page's own 13 + press mod 3. Moving the centre by a
hundredth fails the suite.

**CP bench — `pOut`, to the task's own entries.** The plants pane draws a
trap-count chart the task never looked at: it types three counts for
*S. flava 'Claret'* and then reads the end pane, where the chart is hidden.
The task now shows the plants pane and reads it before leaving — one path,
three points, captioned *S. flava 'Claret' — trap count across 3 observations*,
viewBox 0 0 560 170 — and `verify_cp` holds the caption and the point count
to the task's own `pnm` and `Count` steps, so a task that typed a fourth
count without moving the chart is caught.

## What moved

    charts held (ADR-140's channel)   4 → 8
    page-soil-bench-science           78 → 86      verify_soil     75 → 80
    page-tree-proofs-science         186 → 195     verify_proofs  137 → 143
    page-cp-bench-science            104 → 109     verify_cp       87 → 88
    soil-suite.html                   75/75 → 80/80 verified, republished
    cp-suite.html                     87/87 → 88/88 verified, republished

Three tasks, three suites, two suite pages. No instrument page was edited.

## Held

- The compost port is stated from the example's numbers, not read back: the
  suite carries the readings and the turnings as literals and the chart's
  scale as arithmetic, so a page that moved its floor or its right margin
  fails against the dots, and a task that pasted a position fails against the
  port.
- The splay chart's scale is not ported whole — its ceiling is
  ceil(1.15 × the largest cost), and the largest cost is not held. The suite
  takes the ceiling from the held ticks instead and holds the ticks to be
  quarters of it; that is a weaker pin than the compost chart's, and the
  ledger of what each chart is held to should say so.
- `points` on the compost chart is empty by ADR-140's 30-unit rule (the
  labels sit above the lines, not beside the dots); the task holds that empty,
  and the dots are held by `at`, which is the claim that does not depend on a
  label.
- Not done here: the visualizer's tree drawing, the character keys' trap and
  pitcher figures, the ecology lab's nine station charts, the cp-bench
  dormancy chart and the greenhouse's second chart still draw and are not
  asserted. The two soft edges of ADR-180 stand; the lab importer's band
  lists and the undocumented `dwc:` stand from ADR-179.
