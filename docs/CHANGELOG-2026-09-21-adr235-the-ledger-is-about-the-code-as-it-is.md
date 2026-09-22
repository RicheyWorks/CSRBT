# 2026-09-21 — ADR-235: the mutant ledger is about the code as it is

## Added

- **`tools/audit_anchors.py`**: reads every runner's catalogue without running
  it and reports STALE mutants (anchor found nowhere in the tools, pages,
  tasks, CI, Gradle files or the sibling engine; the runners themselves are
  excluded) and DRIFTED runners (catalogue names or count differ from the
  ledger entry). The four catalogue shapes are stated, and any other shape is
  reported. One second.
- **`verify_anchors`** (23; on the board as a harness suite): a scratch kit
  with one runner per shape and per failure, and the real kit as a gate: 33
  runners and 1,185 mutants, 0 stale and 0 drifted, ledger count equal to the
  catalogues'. Console anchors are NOT VERIFIED without the engine checked
  out.
- **`tools/mutate_anchors.py`** (on the board), 12/12 killed.

## Fixed

- **`mutate_entry`** had drifted since ADR-170: two mutants renamed, and one
  expecting a check the suite no longer says. Re-run it read 16 killed and 1
  inconclusive. The expectation now matches the suite's sentence, and the
  re-run is 17/17.

## Found

Run against ADR-233's tree, the audit reports `mutate_brief` 1 stale, which
is exactly what ADR-234 found by hand.
