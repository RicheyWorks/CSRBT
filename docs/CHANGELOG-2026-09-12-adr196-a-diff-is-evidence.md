# 2026-09-12 — ADR-196: a diff is evidence

**The fifth blind trial measured ADR-195 and found the defect in this kit's
own grader: it held every claim against what a call answered with, and those
calls answered with diffs.**

## What the trial measured

| | 4th | 5th |
|---|---|---|
| `read-report` calls | 71 | **75** |
| report bytes served | 1,214,815 | **332,828** |
| outcomes reached | 82 / 112 | **80 / 112** |
| claims confirmed | 213 / 260 | **208 / 260** |

More reads for a quarter of the bytes, at level scores. Scored the old way the
fifth trial reads 63 / 172 — a fall proportional, page by page, to how much
each operator used the feature.

## Added

- `harness_contract.apply_diff(before, diff, spec)` — the inverse of
  `diff_of`, returning `approximate` (the target's own words, fewer of them)
  and `unrestored` (no value carried at all) as different things.
- `harness_contract._segments` — a flattened path split back by asking the
  document, because a key may contain the separator (`pollen / seed parents`).
- `harness_tasks.fold_diffs(trace)` — the document each call stood for,
  rebuilt; unrestored paths deleted, approximate ones kept.
- `grade_outcomes(..., fold=True)`, with `fold=False` kept as the measurement.
- `tools/traces/blind5/` — four traces and their provenance.
- `verify_contract` 148 → 161, `verify_tasks` 329 → 358.
- `mutate_contract` 65 → 74 / 74, `mutate_tasks` 73 → 80 / 80.

## Changed

- A moved value's two sides are **windowed on the first character they differ
  about** instead of cut from the start. The bench operator was told a box had
  moved and handed two identical strings.
- `diff_of` carries a `trimmed` register naming every path it shortened.
- `grade`: a claim whose value cannot be hashed is false, not a `TypeError`.

## Filed, not fixed

The snapshot's stamp and the report's stamp are the same shape and cannot be
told apart; three of four operators mixed them up at least once. Seven page
defects, two of them found for the third time.
