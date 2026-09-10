# 2026-09-10 — ADR-185: the charts, read (3)

**The cp-bench dormancy chart and the greenhouse leaf-VPD chart — the last
two instrument charts no task held — are held to Python ports of the pages'
own chart arithmetic; the greenhouse port reproduces the worked example's
337 generated rows byte for byte.**

## Changed — tasks

- `page-cp-bench-science` 109 → 116: `season` holds `charts.sChart` —
  viewBox, marks {circle 58, rect 1, path 1, line 1}, longest 58, the path's
  box, `at.0`, `at.39`, the two texts.
- `page-greenhouse-science` 122 → 128: `g155-readout` holds
  `charts.envChart` — viewBox, marks {rect 1, line 2, path 1}, longest 337,
  the path's box, `at.0`, the four texts.

## Changed — suites

- `verify_cp` 88 → 93: `season_chart()` port; the page's dots, rect, line
  and label held to it, dots blue exactly at or below the target; the task's
  chart literals and season tiles held to the port fed from the target and
  weeks it typed.
- `verify_gh` 141 → 147: `demo_rows()` reproduces the seeded generator row
  for row; `env_chart()` port with the band, the `toFixed` ties and the r²
  gate for the trend line; the page's path, rect, band lines, texts and
  absent trend held to it; the task's chart literals and readout figures
  held to the port fed from its own clock, band and offset.

## Changed — page

- `cp-suite.html` 88/88 → 93/93 verified; republished and measured.

## Numbers

    instrument charts unheld  2 → 0

No instrument page was edited.
