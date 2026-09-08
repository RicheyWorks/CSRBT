# 2026-09-08 — ADR-159: the cell bench, recorded whole

**Nine calculators, every one exercised, but twelve of twenty-eight fields left
at their defaults and so entered by nobody. Now 28/28, every figure held.**

## Changed — `tools/tasks/page-cell-bench-science.json`

51 → 71 steps, 76 → 100 confirmed expectations. The existing scenario is kept
verbatim (count 120/12 → 6.00×10⁵, 90.9% viable; seed; doubling time; four-point
standard curve; unknown; Beer–Lambert; A260/A280/A230 purity; mitotic index), so
every prior assertion holds, and the twelve untouched controls are set
explicitly: large squares (4), dilution (2), the Neubauer chamber chip, sample
and target volumes (10 mL), confluency (70%, via `set-slider`), the
standard-curve units, the unknown's dilution (1) and the path length (1 cm) —
each set to the value the calculation already assumed, so no figure moves. The
passage log is driven for the first time: two 1:4 splits, and the cumulative
population doublings held against an oracle — log₂(4)+log₂(4) = 4.0.

## Numbers

    cell-bench.html   16 -> 28 of 28 fields entered   (100%)
                      76 -> 100 confirmed, 0 refuted
    the kit          449 -> 461 of 521 fields          (88%), 16/27 whole

## Held

- The confluency slider takes `set-slider`, not `set-text`.
- The standard-curve units and the passage inputs are raw text inputs with no
  FEK label; they are reached by element id (`@control:stU`, `@control:pNo`) —
  the resolver falls back to id when a label is absent, so no page edit was
  needed.
- The cell bench exports nothing; correctness is held on the figures it
  computes. A task-only slice, the ninth page entered whole.
