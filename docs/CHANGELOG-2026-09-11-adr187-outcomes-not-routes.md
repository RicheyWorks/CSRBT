# 2026-09-11 — ADR-187: outcomes, not routes

**The third blind trial: four operators, four science pages, the goal sentence
and nothing else — every figure reached, and every trace UNMET as a route. The
grader gained a second question, and the answer is four floors.**

## Changed — the runner

- `tools/harness_tasks.py`: `outcomes_of(task)` (the reading steps that claim
  something beyond `ok`), `grade_outcomes(task, trace)` (order-free, partial
  credit per claim, `$step` references counted unreachable, nothing written),
  `--grade-trace <file|dir> --outcomes`, and `load_trace` now reads `.gz`.

## Changed — suites

- `verify_tasks` 293 → 308: block F3. The four traces exist and name real
  tasks; the provenance states the conditions, the rungs and the attempt
  counts; the grader's behaviour held on a fixture (entry steps are not
  outcomes, order-free matching, partial credit, an unreachable `$step`
  claim, an empty trace is FAIL); each trace at or above the floor it
  measured, and UNMET as a route short of a quarter of its script; the CLI
  grades a directory, exits non-zero, and leaves the ledger byte-identical.
- `mutate_tasks` 67 → 73 / 73: an entry step counted as an outcome, order-only
  matching, partial credit dropped, an empty trace passing, the grade written
  to the ledger, a gzipped trace read as empty.

## Added

- `tools/traces/blind3/` — four gzipped traces (the last attempt of each
  operator) and `PROVENANCE.md`.
- `docs/PLAN-operator-api-2026-09-11.md` — the outline Richmond asked for:
  what an operator API needs to be driven correctly, and the seven slices
  (ADR-188 … ADR-194) that build and measure it.

## Numbers

    outcomes reached, blind    30/57, 10/22, 8/12, 5/21   (floors)
    science tasks blind-tried  6 → 10 of 54

No page and no task was edited. Two page defects the operators found are
filed in the ADR, not fixed.
