# 2026-09-10 — ADR-186: the charts, read (4)

**The lab's terrarium (two charts from a seeded stream) and theory bench
(the model's curve) are held to Python ports of the page's own arithmetic —
the stream over `tools/mulberry32.py`, the model as the page states it; the
terrarium's tiles, transcribed when the task was written, are written by the
port now.**

## Changed — tasks

- `page-ecology-lab-science` 263 → 337: `boot` holds `charts.t-meadow-chart`
  (viewBox, marks {rect 40, path 40, line 6}, longest 6, ticks, forty boxes,
  `at.0`–`at.1`) and `charts.t-island-chart` (ten boxes, `at.0`–`at.9`);
  `uneven` and `even` hold the meadow at 95% and at a hot set of 20; `island`
  holds the island at 32; the tiles at those steps (mean residence and
  residents/capacity added) come from the port. `logistic-again`,
  `competition` and `still` hold `charts.wb-theory-out` — viewBox, marks,
  longest 31 / 81 / 61, ticks to 324 / 270 / 129, the curves' boxes, `at.0`
  — and the box must contain the effective r and K (or K₁ and K₂) the page
  prints before the habitat chip.

## Changed — suites

- `verify_eco` 165 → 194: `tools/verify/_lab_models.py` (new; imported) ports
  `runMeadow`, `runIsland`, Shannon, Chao1, the evenness sentence, `runTheory`
  for all six models and the reading above the chart. The page's tiles,
  readings and both terrarium charts held at 60%/5/12, 95%, 20 and 32; the
  theory chart and reading held for seven model/habitat cases; the task's
  terrarium literals at four steps and theory literals at three held to the
  ports.

## Numbers

    lab drawings under the cap unheld  3 → 0

No page was edited.
