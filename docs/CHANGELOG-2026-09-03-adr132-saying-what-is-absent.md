# Changelog — 2026-09-03 — ADR-132: saying what is absent

## Task grammar — `tools/harness_tasks.py`

- New ops **`excludes`** (the value is not in the string/list/dict) and
  **`not-in`** (its mirror). Neither is satisfied by a missing path: a typo in
  a path must not read as proof of absence.
- An op the grader does not know raises `TaskDefect` naming the known ops —
  a task's typo is the task's defect, not a finding about the kit.
- One op table (`OPS`), read by the loader and the grader alike; there were two.
- A trailing `#n` on an expectation path (no space before it) labels a second
  claim about the same path. A ` #2` **with** a space stays a real path
  segment, because that is how `read-report` writes a duplicate label.

## Tasks — `tools/tasks/`

Six refusal paths now assert what is absent rather than guessing at a
replacement: the plant key's no-match excludes `3/3 characters`, the fungal
key's Russula excludes `Lactarius`, the cp key's pitchers exclude `Nepenthes`,
the guide's refused import leaves no `IMG_0431` in the protocol, and the
breeding bench's two refusals stop computing (`intensity i`, `MSE`, `CV`).

## Verification

`verify_tasks` 185 (+9); `mutate_tasks` 31/31 (+7); ledger 43 page tasks, 43
held.

## Docs

`docs/ADR-132-saying-what-is-absent-2026-09-03.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
