# ADR-164 — The micro bench, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The microbiology bench computed a CFU/mL and a dilution plan, but six of its eighteen fields were never entered: the plated volume that the count divides by, the transfer and diluent volumes that set the dilution factor, and the medium and organism a zone reading is meaningless without. Now 18 of 18, every pane driven and the count and plan held against an oracle.**

## The bench whose volumes were assumed, not entered

`micro-bench.html` is a microbiology bench: turn colony counts into a **CFU/mL**
(`colonies ÷ (volume plated × dilution)`), plan a **serial dilution** so a plate
lands in the countable 30–300 window, fit a **growth curve**, and read a
**zone of inhibition** against CLSI breakpoints. Its task counted plates to
1.48×10⁸, planned a dilution and interpreted a zone — but **six of its eighteen
fields were never entered**, and every one is a volume or a label the result
silently depends on: the **plated volume** (0.1 mL) that the CFU divides by, the
**transfer and diluent volumes** (1 mL into 9) that make the 1:10 per step, and
the **medium and organism** without which a zone diameter interprets to nothing.

The page's own method note makes the point: "the plated volume, the transfer and
diluent volumes are *settings* — you choose them" — and the task had chosen none
of them, running entirely on their defaults.

## Entered whole, the count and plan checked

The existing scenario is kept verbatim — the plate counts still mean to
9.90×10⁷ CFU/mL across the countable plates, the dilution still steps 1:10 at
1.00 log₁₀, the growth curve and the zone interpretation all hold — and the six
untouched fields are set to the values those results already assumed: 0.1 mL
plated, 1 mL transferred into 9 mL of diluent, Mueller-Hinton medium and an
*E. coli* ATCC control strain. The count and the dilution plan are then re-read
and held against the oracle, now that the volumes behind them have actually been
entered rather than left at a default.

## What moved

    micro-bench     12 → 18 of 18 fields entered    (the largest remaining gap
                                                    among data-entry pages closed)
    micro-bench     74 → 86 confirmed expectations    0 refuted
    the kit        496 → 502 of 521 fields            (96%), 21 of 27 pages whole

## Held

The "mean of countable" CFU is 9.90×10⁷, not the 1.48×10⁸ of the single best
plate — the box averages the plates inside the 30–300 window, and the confirming
read holds that average, not a single plate. Setting each volume to the value
the calculation already used leaves every figure exactly where it was; the point
is that the settings are now driven, not that a number moved. No page was
edited: a task-only slice, the fourteenth page driven end to end.
