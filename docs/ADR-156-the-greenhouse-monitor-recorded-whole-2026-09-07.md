# ADR-156 — The greenhouse monitor, recorded whole

**Status:** accepted · **Date:** 2026-09-07 · **The environmental dashboard — VPD on Buck, DLI as an integral, kWh as an integral, a repeatability floor — entered whole for the first time: 6 → 14 of 14 fields, 2 unread exports → 0. Driven against a frozen clock so the worked example's 337 readings are exact, and the exact numbers found a defect: the average draw divided energy by the *cycle length* a grower typed, not by the days the log actually covered, turning a 640 W lamp into one averaging 49 W at 8% of rated.**

## The dashboard that ran on data, and had never been given any

`greenhouse.html` is the kit's monitoring page: leaf VPD against a target band
(Buck 1981, with the leaf/air offset stated rather than assumed), DLI both as the
flat `PPFD × hours` formula and as the trapezoid integral of a logged PPFD curve,
energy as the trapezoid integral of logged watts, a cost model, and a run-history
comparison that measures a new cycle against the grower's *own* spread. Its task
drove the lux→PPFD conversion, a DLI, a g/W, and the confirm-dialog path on
"Clear all runs" — 6 of 14 fields, and its "Copy the summary" and "Copy the log
as CSV" were unread.

Everything the page computes rests on a **log**, and no task had ever loaded one.
The worked-example source exists precisely so the charts have something to show —
seven days of plausible readings, deterministic in their noise. But its
timestamps end at `Date.now()`, so its lights-on hours, and therefore every VPD,
every integral, every trend, move with the wall clock. That is exactly what the
harness's clock control is for.

## A log with a date in it is a log that depends on the clock

    set-clock 2026-09-07T09:00:00Z · load the worked example

With the clock frozen the 337 rows are fixed, and the whole readout is an oracle
computed in Python from the same seeded generator, the same Buck equation, the
same trapezoid:

    mean leaf VPD   1.00 kPa   (range 0.59–1.43), against the clone band 0.4–0.8
    time outside    78% by DURATION, not sample count
    dew point       17.4 °C, 9.2 °C of margin · absolute humidity 14.3 g/m³
    DLI (integrated) 50.5 mol/m²/d — from the curve, not the flat formula
    energy          82.9 kWh over the log · $14.92 at 0.180/kWh
    g/kWh 4.82 against g/W 0.67 rated · average draw 493 W (82% of rated)

Every one of those, and the g/kWh mean of the saved run, and the CSV's first and
last rows, is checked against the oracle. **122 confirmed expectations, 0
refuted.**

## The defect the exact numbers found

The energy is integrated across the days the log spans — 7 of them. The *average
draw* is that energy spread over those same days: 82.9 kWh over 7 days is 493 W,
which against a 640 W lamp on an 18/6 photoperiod is about the 75% duty a lamp on
that schedule actually runs.

But the page divided by the **cycle length** instead — the "70 days" a grower
types to say how long the whole grow was. Enter it, and the same 82.9 kWh became
an average of **49 W**, reported as **8% of rated**, with the banner beside it
quoting that 8% as the duty cycle. A dashboard telling a grower their 640 W light
averages 49 W is not a rounding error; it is the difference between a lamp on a
timer and a lamp that is off.

The cycle length is a real fact about the run — it is kept on the run record and
used where a run genuinely spans more than its log. It is not a denominator for a
quantity the log measured across seven days. The average draw is now `kWh over
the log's own span`, and the task holds that entering a 70-day cycle **does not
move it**: 493 W before, 493 W after.

## A dollar figure is not a reference

Holding the cost lines meant asserting `$14.92` and `$0.04`, and the task grammar
read a leading `$` as "the response of the step named `14.92`". A leading `$$` is
now one literal dollar sign — every task written before this one, which uses `$`
for real step references, is unchanged. `verify_tasks` and `mutate_tasks` both
gained a case for it.

## What the page closed

    greenhouse.html   6 -> 14 of 14 fields entered   (100%)
                      2 unread exports -> 0; Copy summary, Copy CSV, Print all held
    the kit           416 -> 424 of 520 fields (80% -> 82%)
                      39 -> 37 unread outputs

Seven pages are now entered whole: collection sheet, stand sheet, ecology lab,
relevé, experiment guide, deployment log, greenhouse.

## Held

- The stepped clock fixes the worked example's timestamps and nothing else. It
  is one synthetic log; the file, poll, serial and manual sources are still
  driven only by their availability checks, which is the honest limit of a page
  that reads real hardware.
- The "average draw over the log's span" is right for a log that covers the run.
  A log that covers only part of a longer run still under-reports the run's total
  energy — the page says so, and the cycle-length field is where a grower
  supplies the rest. What ADR-156 fixes is that the cycle length was silently
  dividing a quantity it had no business dividing.
- 37 outputs on 14 pages are still unread; 16 buttons still silent.
