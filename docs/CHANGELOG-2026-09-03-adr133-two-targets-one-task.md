# Changelog — 2026-09-03 — ADR-133: two targets, one task

## Task runner — `tools/harness_tasks.py`

- A step may name its own `target`. The runner opens every target the task
  names once, keeps them for the task's life, and closes them in the reverse
  of the order it opened them; references resolve across targets.
- A step naming a target that does not exist — or one the caller did not open —
  is the task's `DEFECT`, never a refusal.
- New op **`~=`** with a **required** `tolerance`: how close two instruments
  must be is the task's claim, and has no default.
- `held` is `verdict == must` on every path, the one where a target cannot be
  opened included; every ledger entry names its transport.
- Ledger entries name every target a task used, not just the one it declares.

## Tasks — `tools/tasks/`

- `two-targets-lab-and-page`: the shipped protocol through the lab engine, the
  same field data into `ecology-lab.html`'s workbench, and the page's
  `species` / `Shannon H′` / `evenness J′` / `Chao1 est.` held to the engine's.
- `two-targets-isolated`: a write through the organism survives the fixture's
  crash, and the fixture's failure never touches the organism's meters.
- `two-targets-canary`: a step naming a target that does not exist — the first
  canary written to be a `DEFECT`.

## Verification

`verify_tasks` 203 (+18); `mutate_tasks` 41/41 (+10); ledger 53 tasks, 53 held.

## Docs

`docs/ADR-133-two-targets-one-task-2026-09-03.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
