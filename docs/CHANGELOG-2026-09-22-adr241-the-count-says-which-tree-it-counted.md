# 2026-09-22 — ADR-241: the count says which tree it counted

Ported from the FlowersForever harness (`scripts/verify_harness.py`,
`config/harness-test-floors.json`).

## Added

- `tools/evidence.py`: a SHA-256 over the subject (pages, prose, tools,
  tasks, suites, CI, engine sources; never the ledgers, counts, floors, board,
  published state, manifests or push scripts), a sha12 per file, and
  `status()` saying whether `counts.json` is about the tree as it stands and
  which files differ. `--check`, `--raise-floors`.
- `tools/verify/floors.json`: the fewest checks each suite may count. A green
  suite below its floor is red for the run and fails it. Never seen → floored
  at its count. Rises only by `--raise-floors`.
- `run_all`: takes the tree before the jobs (`CSRBT_RUN_TREE` to every job),
  writes it with every count, applies the floors, takes the tree again and
  fails a run the tree moved under. `--only NAME` runs one job and records it.
- The board: two gates, *the counts are about this tree* and *no suite counts
  fewer than its floor*; the header names the tree and, when it has changed,
  the files.
- `verify_evidence` (28), `verify_board` section 10 (+9), `tools/mutate_evidence.py`
  (13/13, copies the whole subject and restamps the copy's counts).
