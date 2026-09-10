# ADR-185 — The charts, read (3): the dormancy season and the leaf-VPD week are held to ports of the pages that draw them

**Status:** accepted · **Date:** 2026-09-10 · **Two instrument charts remained from ADR-140's list of drawings no task held: the cp-bench's dormancy chart, which the task read past because the season pane's readout was the thing it checked, and the greenhouse's leaf-VPD chart, which sat behind the env pane while the task held the readout beside it. Both are held now — the page's drawing to a Python port of its own scale, the task's literals to the same port, the task to the page by the runner. The greenhouse port reproduces the worked example itself: the seeded generator, row for row, 337 rows, so the chart is held to the data the page *made*, not to the data it happened to hold. `page-cp-bench-science` 109 → 116, `page-greenhouse-science` 122 → 128, `verify_cp` 88 → 93, `verify_gh` 141 → 147; cp-suite advertises 93/93 and was republished.**

## The two left

After ADR-181 to ADR-183, the instrument charts not yet held were the
cp-bench's `sChart` (fifty-eight daily temperatures against a dormancy
target, drawn when the worked example is loaded) and the greenhouse's
`envChart` (leaf VPD over the worked week, against the stage's band). Both
tasks already drove the state that draws them — the cp task presses the
worked example and reads the season tiles; the greenhouse task fixes the
clock, loads the worked example, picks the clones band and a 1.5 °C leaf
offset, and reads the readout — and neither looked at the chart beside the
figures it held.

## What is held

**cp-bench — `sChart`.** The page's `seasonChart()` is ported: width 620,
height 210, pad 38; x by reading index to the right edge less 16; y from
two below the coldest of the readings and the target to two above the
hottest; the band rect from the target line down to the baseline; one dot
per reading, blue when at or below the target; the label seven above the
line. `verify_cp` already carried the worked example's fifty-eight readings
(ADR-052's summary checks); it now holds the page's fifty-eight dots, the
rect, the line and the label to the port, and that a dot is blue exactly
when its reading is at or below the target. The task holds, at `season`,
the marks, `longest` 58, the path's box, the first and fortieth mark, the
two texts and the viewBox — and the suite holds those literals to the port
fed from the target the task typed, and the season tiles the task holds
(43 / 84, a run of 15, 58 readings, 51 %, 41 short) to the same readings
counted against that target.

**greenhouse — `envChart`.** `verify_gh`'s docstring said "no trust in the
demo generator" and meant it: no check derived a constant from the demo.
None reproduced it either. It is a seeded LCG — `seed = 1664525·seed +
1013904223 mod 2³²` — over a week of half-hour rows with `Math.sin` of the
hour and `toFixed` rounding, and the port reproduces all 337 rows byte for
byte from the clock the task fixes (`2026-09-07T09:00:00Z`). On top of it,
`envChart()` is ported: width 680, height 260, pad 46; x by time to the
right edge less 18; y from 0.15 below the lower of the band floor and the
lowest VPD to 0.15 above the higher of the ceiling and the highest; the band
rect and its two lines; the trend line only when the least-squares r² reaches
0.3 — the worked week's is 0.00004, so two lines, not three, and the caption
says "time". The suite holds the page's path string (337 points to the
tenth), the rect, the two band lines, the four texts and the absent trend to
the port on the default band; the task holds, at `g155-readout`, the marks,
`longest` 337, the path's box, the rect's centre, the four texts and the
viewBox on the clones band with the 1.5 offset, and the suite holds those
literals — and the readout's VPD range, mean and count — to the port fed from
the task's own clock, band and offset.

**Two rounding rules, said once.** Every coordinate these pages write goes
through `toFixed(1)`, whose ties go to the larger digit: 0.25 is "0.3". The
axis label at the bottom of the greenhouse chart is exactly that case
(0.4 − 0.15), and Python's `%.1f` prints "0.2". The ports use the exact
binary value with half-up rounding, as `Number.prototype.toFixed` does, and
the reader's `Math.round(v·100)/100` in the same doubles.

## What moved

    page-cp-bench-science        109 → 116     verify_cp    88 → 93
    page-greenhouse-science      122 → 128     verify_gh   141 → 147
    cp-suite.html                88/88 → 93/93 verified, republished
    instrument charts unheld     2 → 0

Two tasks, two suites, one suite page. No instrument page was edited.

## Held

- The ports are of the *chart*, fed from data the suites already own: the
  cp readings are a literal the page also carries (a change to either fails
  the dots), and the greenhouse rows are regenerated, so a page that changed
  its seed, its noise or its rounding fails the row-for-row check before
  the chart is reached.
- `points` on both charts is not held: the cp label sits within thirty
  units of one dot and is paired with it, which is ADR-140's approximate
  pairing and not a claim about the data; the greenhouse label pairs with
  nothing.
- The trend line is held absent. A worked example with a trend would draw
  a third line, and the port says when; the task would then hold three.
- What still draws unasserted: the tree visualizer's tree, the character
  keys' figures (static drawings, not data), the terrarium's seeded stream,
  the theory bench's model curve, and the lab's charts past the reader's
  cap.
