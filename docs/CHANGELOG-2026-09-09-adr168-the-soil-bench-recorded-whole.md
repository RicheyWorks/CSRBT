# 2026-09-09 — ADR-168: the soil bench, recorded whole

**The composting pane logged its readings on defaults nobody set: the
temperature unit, the squeeze-test moisture and the turn chip were never driven.
Now 10/10. The kit stays at 99%, 25 of 27 pages whole.**

## Changed — `tools/tasks/page-soil-bench-science.json`

42 → 47 steps, 66 → 72 confirmed expectations. The existing scenario is kept
verbatim (the demo windrow log's 14/15 certified days, 5/5 turnings while hot,
peak 64, not yet certified), so its verdict holds, and the three never-touched
composting controls are driven as pending inputs — the Celsius unit chip, the
squeeze-test moisture dial (bone dry), and the turn chip — without adding a
reading, so nothing is logged and the verdict is unchanged.

## Numbers

    soil-bench.html    7 -> 10 of 10 fields entered    (100%)
                      66 -> 72 confirmed, 0 refuted
    the kit          515 -> 518 of 521 fields            (99%), 25/27 whole

## Held

- The three controls feed the log only through the "Add reading" button; setting
  them and not pressing it drives each one while the demo verdict stays put.
- The unit chip's reselection rebuilds the entry controls and recomputes the
  verdict from the same readings, so it is driven first.
- No page was edited — a task-only slice, the eighteenth page entered whole.
