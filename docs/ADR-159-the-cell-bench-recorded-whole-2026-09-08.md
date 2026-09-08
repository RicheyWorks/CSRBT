# ADR-159 — The cell bench, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The cell bench — nine calculators for counting, culture, spectrophotometry and mitosis — had every calculator exercised but twelve of its twenty-eight fields never entered: the ones that sit at a sensible default and were left there. Now 28 of 28, every calculator driven with its inputs set explicitly and every figure held against an oracle.**

## The page whose defaults hid its own coverage

`cell-bench.html` is a bench of calculators: a hemocytometer count (concentration,
viability, Poisson CV), a seeding dilution, a doubling-time from two counts, a
passage log that tracks cumulative population doublings, a linear standard curve
with an unknown read off it, a Beer–Lambert concentration, an A260/A280/A230
purity screen, and a mitotic index with per-phase durations. Its task already
touched every one of these — but **twelve of its twenty-eight value-carrying
fields had never been entered**, because they carry a working default and the
task simply used it: the number of squares, the dilution and chamber factors,
the sample and target volumes, the confluency slider, the standard-curve units,
the unknown's dilution, the cuvette path length — and the **entire passage log**,
whose three inputs the task never opened at all.

A field left at its default is entered by nobody. The report can be right about
the number it computed and the harness still has no evidence it can *drive* the
control that fed it — the gap ADR-150's entry-reach ledger exists to make
visible.

## Entered whole, every calculator driven

The existing scenario is kept verbatim — same 120/12 count, same seed, same
curve, same purity ratios — so **all seventy-six of its assertions still hold**,
and the twelve untouched controls are now set explicitly: the four large squares,
the dilution of 2 and the Neubauer chamber chip, the 10 mL sample and target
volumes, a 70% confluency on the slider, the standard-curve units, the unknown's
unit dilution and the 1 cm path length. Setting each to the value the
calculation already assumed leaves every figure unchanged and every existing
claim intact — the point is that the control was driven, not that the number
moved.

The passage log is entered for the first time: two 1:4 splits are logged, and
the page's **cumulative population doublings** — the number a finite cell line's
senescence actually tracks, and the reason passage count alone means nothing —
is held against an oracle:

    log₂(4) + log₂(4) = 4.0 cumulative PD over two passages

The generator computes it the page's way (`log(4)/log(2)`, summed, `toFixed(1)`),
so both sides of the claim come from the same arithmetic.

## What moved

    cell-bench      16 → 28 of 28 fields entered   (the largest remaining gap
                                                    among data-entry pages closed)
    cell-bench      76 → 100 confirmed expectations  0 refuted
    the kit        449 → 461 of 521 fields           (88%), 16 of 27 pages whole

## Held

The confluency slider needed the `set-slider` action, not `set-text`; the
standard-curve units and the passage inputs are raw text inputs with no FEK
label, reachable by their element id (`@control:stU`, `@control:pNo`) rather than
a name — the resolver matches id when a label is absent, which is why no page
edit was needed to drive them. This is a task-only slice, the ninth page driven
end to end; the cell bench exports nothing, so its correctness is held on the
figures it computes rather than a file it hands over.
