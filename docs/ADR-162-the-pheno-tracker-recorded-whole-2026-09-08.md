# ADR-162 — The pheno tracker, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The breeder's phenotype-selection bench scored a run and computed a selection differential, but nine of its sixteen fields were never entered: the run's own name/observer/date, the plant note, the mother and cross controls, the trait weight, and the segregation trait. Now 16 of 16, every pane driven and both exports held against an oracle.**

## The selection bench that never named its run

`pheno-tracker.html` is where a plant breeder turns a bench of seedlings into a
decision: score every plant on weighted trait dials, star the keepers, and read
the **selection differential S** — how far the keepers sit above the run mean,
the quantitative-genetics number that (times heritability) predicts the
response. It also plans **mothers and crosses**, and tests a **segregation**
count against the Mendelian ratios by χ².

Its task scored a run of eight, starred three keepers and read S = +1.44 — but
**nine of its sixteen fields were never entered**: the run's name, observer and
date; the per-plant note; the 🌿 mother promotion and the two cross-parent
pickers; the trait weight; and the segregation trait name. The bench computed
the number a breeder lives by and never recorded whose run it was.

## Entered whole, both exports checked

The existing scenario is kept verbatim — the eight scores, the three keepers,
the run mean 2.41, keeper mean 3.85, differential +1.44, and the three
segregation χ² tests all hold — and the nine untouched fields are driven around
it: the run is named and stamped, a standout gets a note, a plant is promoted to
mother, a cross is planned between two keepers, the trait weight and the
segregation trait are set. Then both files the bench exports are read and held
against an oracle:

    field-day report   the header and stamp, each plant's weighted score
                       (#1  4.18 KEEP — with its note), the keeper line with
                       S = +1.44, and the 60:20 segregation cross
    CSV                the header row with every weighted trait, and #1's row
                       5,4,4,4 → 4.18 keep, verbatim

Every plant's weighted mean, the differential and the ratios are computed the
page's way — the four dial weights (vigor×1, structure×1, aroma×2,
resistance×1.5) over the scores — so both sides of every claim come from the
same arithmetic.

## What moved

    pheno-tracker    7 → 16 of 16 fields entered    (the largest remaining gap
                                                    among data-entry pages closed)
    pheno-tracker   77 → 102 confirmed expectations   0 refuted
    its exports      0 → 2 read and held against an oracle
    the kit        481 → 490 of 521 fields            (94%), 19 of 27 pages whole

## Held

The mother is promoted on a non-keeper and the cross planned between keepers so
that neither disturbs the asserted keeper line or the asserted plant row. The
trait name and weight are entered without adding a trait — adding one would put
an unscored dial on every plant, a new field that could only be closed by
scoring it, which would move the very totals the run is trusted for. No page was
edited: a task-only slice, the twelfth page driven end to end.
