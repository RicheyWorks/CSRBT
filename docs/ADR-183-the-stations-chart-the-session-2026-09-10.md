# ADR-183 — The stations chart the session: ten of the lab's station charts are held, bar by bar and step by step, to the shipped session they draw

**Status:** accepted · **Date:** 2026-09-10 · **`verify_engine_sessions` binds the lab's inline `SESSION` to `docs/ecology-lab-session.json` and, since ADR-139, that file to the engine that emitted it; ADR-182 gave the reader a path's box. What was never bound was the drawing to the data: a station chart that plotted the wrong phase, the wrong ceiling or a survivorship curve one class short looked exactly like the right one. The chart primitives — `frame`, `barPath`/`barChart`, `lineChart` with its `yMax`, `xTicks` and `step` options — are ported to `tools/verify/_lab_charts.py`, fed from the session file, and the ten station charts under the reader's sixteen-chart cap are held three ways: the live page's paths, ticks and marks to the port; the lab task's `boot` literals to the port; the task's literals to the page by the runner. `page-ecology-lab-science` 211 → 263, `verify_eco` 143 → 165.**

## The unbound link

    engine  →  ecology-lab-session.json  →  inline SESSION  →  prose tiles  (verify_engine_sessions, ADR-052)
                                                            →  the charts    (nothing)

The meadow's two rank-abundance bar charts, its rarefaction curves, the
demography station's survivorship steps and logistic fit, the archipelago's
occupancy steps, the fossils' inherited-fraction bars, the grid's quadrat and
leaf bars — ten `<svg>`s that the task's first `read-report` has returned
since ADR-140 and no expectation named. ADR-182's `spans` made a bar's height
readable; this slice says what the height must be.

## The port

`tools/verify/_lab_charts.py` is not a suite (no `verify_` prefix; nothing
runs it) and is imported by `verify_eco`. It states the page's arithmetic:
margins 42 / 10 / 12 / 34; `barChart` with `yMax = 1.05 × max`, bars of
`iw/n − 2` at `x = 42 + i·iw/n + 1`, no bar for a zero; `lineChart` with
`yMax` given or `1.08 × max`, `X` linear over the first series' x range,
`Y = 12 + ih − ih·min(v, yMax)/yMax`, a step line as `1 + 2(n − 1)` points;
ticks `fmt(yMax·i/4)` under the page's decimals rule (2 below 2, 1 below 10,
else 0) with `toLocaleString`'s half-up rounding and thousands separator;
x ticks as `fmt(v, 0)`. `station_charts(session)` walks the session the way
`render()` does — phases in order, rarefaction only for phases that have one,
the growth fit from the session's own `r`, `K`, `n0` with the `n0 ≤ 0` guard,
the archipelago to a ceiling of 1.0 with a tick per survey, the survivorship
to 1.05 with every other class ticked, `clustered` before `spread` with each
one's leaves after it — and keys the result as `read-report` keys it
(`station-meadow`, `station-meadow #2`, …).

Two of the port's numbers are the *reader's*, not the page's, and are said
so in the file: a hit-rect's centre is `x` and `width` rounded to two places
*before* halving, because `num()` rounds each attribute as it reads it (the
grid's 44 leaf bars are 9.7272… wide and the difference is a hundredth); and
every rounding is `Math.round(v·100)/100` in the same doubles, not a decimal
half-up, because `80.91 + 4.865` is `85.775` only in decimal.

## What is held

**The page.** `verify_eco` renders the session, collects every `svg` under a
`station-*` host in document order, parses each path's `d` with its own box
routine, and holds — per chart — the boxes to the port's `spans`, the y tick
labels (the texts at `x = 36`), the x tick row (the texts at the tick line,
when there are three or more), and the counts of circles, rects, paths and
lines. Twenty checks. The session comes from the *file*: a value moved in the
file with the page's inline copy unchanged fails the fossils chart here and
fails `verify_engine_sessions` on the copy, two instruments disagreeing with
one lie.

**The task.** At `boot`, for each of the ten charts: `marks`, `longest`,
`aligned.col`, `aligned.row` where the chart has one, `spans` whole (forty of
the leaf chart's forty-four bars, the reader's cap on paths), and `at.0`.
Sixty-two expectations at that step, 211 → 263 confirmed; every literal
written by the port from the session file, none read from the page. The
suite holds the task's literals to the port, and holds that the task names
exactly the ten charts under the cap — the port sees an eleventh, the spread
leaves, and the task must not claim it.

**Moving a thing.** A `longest` changed by one in the task fails the
task-literal check; a session value changed in the file fails the page check
and the task check together.

## What moved

    page-ecology-lab-science      211 → 263
    verify_eco                    143 → 165
    tools/verify/_lab_charts.py   new (imported, not run)

One port, one suite, one task. No page was edited.

## Held

- The terrarium's two charts are drawn from a seeded stream in the page's
  own JavaScript and are not in the session; the port cannot feed them. They
  stay unheld and are said so.
- The eleventh station chart (the spread leaves) and everything past
  `station-grid` at boot are beyond the reader's cap. Raising the cap would
  move nothing held but is a reader change and a separate decision. The
  theory bench's curve is under the cap and unheld: its port is the model.
- The rarefaction curves are held by extent and point count, not by shape:
  `spans` is a box. A curve with the right endpoints and the wrong middle
  would pass, as ADR-140 said of paths and ADR-182 said of boxes.
- ADR-182's workbench checks now read the same module; the inline copy of
  the port in `verify_eco` is gone.
- Still unasserted (ADR-181's list): the visualizer's tree, the character
  keys' figures, the cp-bench dormancy chart, the greenhouse's second chart.
