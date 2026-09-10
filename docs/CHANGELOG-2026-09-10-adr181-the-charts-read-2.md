# 2026-09-10 — ADR-181: the charts, read (2)

**ADR-140 held four of the kit's drawings and named the rest. Four more are
held: the soil bench's compost chart to a Python port of its scale, the tree
proofs' splay chart to a scale recomputed from the ticks and the cost the task
holds, its 2-3-4 view to what a 2-3-4 tree is, the cp-bench's trap-count chart
to the task's own entries. Two suite pages republished with their new counts.**

## Changed — tasks

- `page-soil-bench-science` 78 → 86: `g168-held` holds `charts.cChart` —
  marks {circle 18, line 7, rect 1, path 1}, longest 18, the two threshold
  labels with their x/y, `at.0`, `at.4` (the peak), `at.17`, `points` empty.
- `page-tree-proofs-science` 186 → 195: `seededAccesses` holds
  `charts.spChart` — marks {rect 20, line 5, polyline 1}, longest 20, the tick
  column 15/11/8/4/0, the legend texts, `at.19` = [675, 160.65] — and
  `charts.rbSvg` — root `8 · 20 · 36`, the leaf row, marks {rect 5, line 4}.
- `page-cp-bench-science` 104 → 109: `g181-plpane` (show-pane p-pl) and
  `g181-chart` (read-report) before the end pane: `charts.pOut` marks
  {path 1}, longest 3, the caption, viewBox 0 0 560 170.

## Changed — suites

- `verify_soil` 75 → 80: `DEMO`, `DEMO_TURN`, `cx()`, `cy()` port; the page's
  circles, threshold lines, turning ticks and peak held to it; the task's
  chart literals held to it.
- `verify_proofs` 137 → 143: section 6 — ticks are quarters of one ceiling;
  the last bar's centre recomputed from maxV and `figures.last actual`; the
  marks; the 2-3-4 view sorted, separated by the root, 13–15 keys.
- `verify_cp` 87 → 88: the trap chart's caption and point count held to the
  task's own `pnm` and `Count` steps.

## Changed — pages

- `soil-suite.html` 75/75 → 80/80 verified; `cp-suite.html` 87/87 → 88/88
  verified. Both republished and measured.

## Numbers

    charts held 4 → 8

No instrument page was edited.
