# 2026-09-10 — ADR-182: a path is placed by its box

**The chart reader placed marks by `cx` and `x + width/2` and counted a path's
points as its `M`s and `L`s, so the ecology lab's bars — rounded paths — had
no height in any report and its step line was one point. `read-report` now
reports each path's box, counts every command that ends somewhere, rounds a
rect's centre and leaves an unplaced mark out of `at`. The lab's two
workbench charts are held to a port of `barChart`.**

## Changed — `tools/harness_plugin_page.py` (read-report `charts`)

- `spans`: per `<path>` (≤ 40), `[x0, y0, x1, y1]` over every point a
  command ends at — `M L H V C S Q T A Z`, absolute and relative, implicit
  pairs after `M` — rounded to two places; control points not counted.
- `longest`: a path's points are every command that ends somewhere, not only
  `M` and `L`.
- `at`: a rect's centre is rounded like every other number; a circle or
  ellipse with no position is counted in `marks` and not placed.

## Changed — suites, runners, task

- `verify_report` 115 → 120: fixture `theBars` — an absolute rounded bar, the
  same bar relative, a step line, a rect at `0.1 + 0.2`, an unplaced circle.
- `mutate_report` 69 → 75 / 75: box not read, relative read as absolute, `H`
  not followed, points `M`/`L` only, unplaced mark placed at nothing, centre
  not rounded; two anchors moved with the lines they anchor.
- `page-ecology-lab-science` 202 → 211: `field-back` holds `wb-field-out`
  (five boxes, ticks 36/27/18/9/0, marks, longest 6, `at.0`); `quad-twelve`
  holds `wb-quad-out` (seven boxes for twelve quadrats, ticks to 63, marks,
  `at.11`).
- `verify_eco` 138 → 143: `bar_chart()` port (margins, `1.05 × max`, ticks
  with the page's decimals rule and half-up rounding, bar width and x); the
  live page's paths parsed and held to it; the task's literals and typed
  inputs held to it.

## Numbers

    every page task 44 / 44 held under the new reader

No page was edited.
