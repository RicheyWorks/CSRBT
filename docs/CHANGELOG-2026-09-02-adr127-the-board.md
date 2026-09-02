# Changelog — 2026-09-02 — ADR-127: the board

## New — `tools/mutant_ledger.py`, `tools/mutant_ledger.json`

Every mutant runner records its run (mutants, killed, survived,
inconclusive, equivalents, a row per mutant), merged per runner. All six
runners wired. First reading: 104 mutants, 104 killed.

## New — `tools/harness_board.py`, `tools/harness_board.html`

The Harness Board, rendered whole from `counts.json`, `walk_ledger.json`,
`task_ledger.json`, `mutant_ledger.json`, `ecosystem_ledger.json` and
`routes.json`; `--check` for drift. Published as an artifact.

## New — `tools/verify/verify_board.py` (**37 checks**)

The file is the render; the arithmetic is the ledgers'; every runner on the
board and in the ledger with its own catalogue; every page and task on the
page; no leaks; both themes; deterministic.

## Docs

`docs/ADR-127-the-board-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
