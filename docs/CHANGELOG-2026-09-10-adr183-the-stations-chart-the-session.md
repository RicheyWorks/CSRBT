# 2026-09-10 — ADR-183: the stations chart the session

**The lab's inline session was bound to the shipped file and the file to the
engine; the drawing was bound to nothing. The chart primitives are ported to
`tools/verify/_lab_charts.py`, fed from `docs/ecology-lab-session.json`, and
the ten station charts under the reader's cap are held — page to port, task
to port, task to page.**

## Added — `tools/verify/_lab_charts.py`

- `bar_chart`, `line_chart` (with `yMax`, `xTicks`, `step`), `fmt`, `r2`
  (the reader's `Math.round(v·100)/100` in the same doubles), and
  `station_charts(session)` walking the session as `render()` does and keying
  charts as `read-report` keys them. Imported, not run.

## Changed — suites, task

- `verify_eco` 143 → 165: renders the session, reads every `station-*` svg's
  paths, tick labels, x ticks and mark counts, and holds them to the port fed
  from the session file (20 checks); holds that the task names exactly the
  ten charts under the cap; holds the task's `boot` literals to the port.
  ADR-182's inline port replaced by the module.
- `page-ecology-lab-science` 211 → 263: `boot` holds, per station chart,
  `marks`, `longest`, `aligned.col`, `aligned.row` where present, `spans`
  whole and `at.0` — every number from the port.

## Numbers

    station charts held   0 → 10 of 11 (the eleventh is past the reader's cap)

No page was edited.
