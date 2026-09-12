# 2026-09-12 — ADR-193: the brief

**A goal stops being a sentence and becomes a brief: what it says, every value
it gives, and every reading it holds. The sixth of the seven slices of
`docs/PLAN-operator-api-2026-09-11.md`, and the one that makes the fourth blind
trial a fair one.**

## The measurement this fixes

Across the 21 science tasks: **547 values entered, 281 of them appearing
nowhere in the goal handed to the operator** — 51%. ADR-187's four operators
were graded on figures computed from data nobody had given them.

## Added — `tools/harness_tasks.py`

- `gives_of(task)` — every value the task supplies, in order, with the control
  that takes it, the argument it rides on, and whether it is `bulk` (over 60
  characters: a CSV block, an import, a paragraph of notes).
- `holds_of(task)` — every reading the task holds, with its claims (ADR-187's
  outcomes, in the shape a brief hands over).
- `goal_of(task)` — `{says, gives, holds, needs, counts}`.
- `brief_of(task, claims=True)` — the brief as an operator reads it;
  `claims=False` withholds what the task holds, for a blind trial.
- `brief_counts(task)` — what a ledger row says about a brief, used by both the
  run's row and the could-not-stand-up's.
- CLI: `--goal TASK` (JSON), `--brief TASK`, `--blind`; `TASK` may be `all`.
- `GIVING` now covers `set-text`, `type-text`, `pick`, `choose-option`,
  `set-slider`, `set-checkbox`, `press-step`, `attach-file`, `drop-files`,
  `set-clock`, `set-seed`, `set-dialog`, `answer-dialog`.

## Added — suites

- `tools/verify/verify_brief.py` (31) and `tools/mutate_brief.py` (14 / 14).
  Its own suite because it opens nothing and runs in 0.3 seconds: a mutant
  runner over `verify_tasks` would be twelve hours and therefore never run.

## Changed

- `tools/task_ledger.json`: every row carries `gives`, `holds` and `claims`
  (all 55 tasks re-run; no task file was edited).
- `tools/harness_board.py`: a `values handed over` tile — 642, with 632
  readings and 1 956 claims held — and `verify_brief` / `mutate_brief` in the
  suite and runner tables.

## Held

- `gives` and `holds` are computed from the steps; no task file carries a brief
  of its own, and a step added to a task is in its brief at once.
- What a brief holds is exactly what `grade_outcomes` scores, step for step and
  claim for claim, for all 55 tasks — and re-graded against ADR-187's four real
  traces.
- A blind brief hands over every value and withholds the claims; the default is
  the full brief, so an organiser who forgets the flag notices.
- No transport and no plugin imports `harness_tasks`: a door that served a
  client its own task would end the blind trial that made the brief necessary.
