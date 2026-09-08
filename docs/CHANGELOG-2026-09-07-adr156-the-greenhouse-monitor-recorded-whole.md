# 2026-09-07 — ADR-156: the greenhouse monitor, recorded whole

**Everything the page computes rests on a log, and no task had ever loaded one.
Driven against a frozen clock the worked example is exact — and the exact numbers
found a defect in the average-draw denominator.**

## New

- **`tools/tasks/page-greenhouse-science.json`** — 27 → 58 steps, 122 confirmed
  expectations. Freezes the clock, loads the worked example, and reads the
  environment (mean leaf VPD, range, time outside band by duration, dew point,
  absolute humidity, VPD trend), the integrated DLI, the energy block, a saved
  baseline run, and all three exports against a Python oracle that mirrors the
  page's seeded generator, Buck (1981), the trapezoid integrals, the OLS trend
  and the economics.

## Changed — `docs/greenhouse.html`

- **Average draw divided by the wrong number of days.** It used the cycle length
  a grower typed instead of the days the log spans, so 82.9 kWh over a 7-day log
  read as a 49 W average (8% of a 640 W rated lamp) once a 70-day cycle was
  entered. The average draw is now energy over the log's own span; the cycle
  length stays a fact about the run.

## Changed — the task grammar

- **A leading `$$` is one literal dollar sign** (`tools/harness_tasks.py`), so a
  task can hold `$14.92`. A single `$` still means a step reference. Covered by
  `verify_tasks` and two new `mutate_tasks` mutants.

## Numbers

    greenhouse.html   6 -> 14 of 14 fields entered  (100%)
                      2 unread exports -> 0
    the kit           416 -> 424 of 520 fields      (80% -> 82%)
                      39 -> 37 unread outputs

Every figure in the task comes from the oracle; none was typed by hand.

## Held

- The frozen clock fixes the worked example's timestamps; the file, poll, serial
  and manual sources are still driven only by their availability checks.
- 37 outputs on 14 pages are still unread; 16 buttons still silent.
