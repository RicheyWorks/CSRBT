# Changelog — 2026-09-02 — ADR-125: tasks

## New — `tools/harness_tasks.py`, `tools/tasks/*.json`, `tools/task_ledger.json`

Goal-shaped tasks: steps with arguments, references to earlier responses
(`$step.path`, escaped dots), expectations graded CONFIRMED / REFUTED with
nine operators, verdicts PASS / FAIL / DEFECT, a `must: FAIL` canary. Run
through the real transport (`--transport stdio | mcp`), each task on its
own target, kept in a merged ledger. Eight tasks over the organism (4), the
lab, the page and the fixture (2); 8 of 8 held over both transports.

## New — `tools/verify/verify_tasks.py` (**48 checks**), `tools/mutate_tasks.py` (**10 killed** / 0 / 0)

The grammar, the files, the grader on the fixture (canary refuted and held;
a bad reference a DEFECT; an unexpected failure ends the task; a dead
target a DEFECT; MCP the same verdicts), every real target's tasks through
the gateway, the ledger. `CSRBT_TASKS_QUICK=1` for the runner.

## Docs

`docs/ADR-125-tasks-what-an-operator-is-for-2026-09-02.md`;
`docs/AUTOMATION-HARNESS.md`, `docs/AI_HARNESS.md`.
