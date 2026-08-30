# Changelog — 2026-08-30 — ADR-109: a detector with no alarm

The harness had been finding real defects into a green build. It now fails one.
Full suite **68 of 68 jobs, 4,584 of 4,584 checks**; Java **1,127 tests**.

## Fixed — two of the findings were the instrument, not the pages

- **`sequenced`, a sixth accounting bucket.** Ten of twenty-one "dead" controls
  (48%) had vanished because the harness's own setup clicked a sibling first and
  the page re-rendered. Filing that as "wired to nothing" was an accusation
  against working code. Real dead controls: **12, not 21.**
- **`data-junk-ok`.** Both "junk rendered" findings were false: field-notebook
  says *"the estimate is undefined (R must be ≥ 1)"* because Lincoln–Petersen has
  no value at R=0. An element may now declare that it renders the word as prose,
  with a reason. The declaration excuses `undefined` only — a marker wrapped
  around a real `NaN` is still reported, canaried three ways. Invariant breaks:
  **60, not 62.**

## New — the alarm

- **`tools/findings.py`** — signs a finding `page | category | label`, stable
  across the id renumbering that happens whenever a page changes. Duplicates are
  counted, so eight identical spills cannot hide behind one baseline entry.
- **`tools/harness_baseline.json`** — the accepted debt: 32 distinct, 76
  occurrences, 8 pages, each with a reason.
- **`tools/verify/verify_findings.py`** (11 checks) — fails on a NEW finding and
  on a baseline entry that no longer occurs. Canaried in both directions,
  including that a second occurrence of an accepted finding is still a regression.

## New — the harness's own tester

- **`tools/verify/verify_harness_matrix.py`** (56 checks, 9 sections): all 20
  discovery kinds; all 6 buckets; every trace the oracle accepts (text, class,
  form value, localStorage, print, alert); every invariant (NaN, [object Object],
  two panes, spill, console error); hostile pages (empty, throws on load,
  self-removing control, confirm/prompt, slow handler); determinism; unique ids;
  ledger merge arithmetic.
- **`tools/mutate_harness.py`** — breaks the harness ten ways on a copy and
  requires the matrix to notice. **10 killed, 0 survived, 0 inconclusive.**
  - It found a real weak check on its first run: "sequencing folded back into
    dead" survived because the check only asserted the bucket *existed*. It now
    asserts placement both ways, and the mutant dies.
  - It also caught a mis-anchored mutation of mine and reported `BAD MUTANT`
    rather than a pass — a mutation that never applied produces a meaningless green.
- The matrix asserts the catalogue stays live: every anchor must still match the
  harness exactly once.

## Changed

- `verify_harness` — three junk canaries (declared prose excused, undeclared leak
  caught, declaration cannot hide NaN) and the six-bucket identity. 22 → 28.
- `verify_routes` — six-bucket identity.
- `docs/field-notebook.html` — declares its legitimate `undefined`.
- `docs/AI_HARNESS.md` — the sixth bucket, the declaration, the ratchet, the
  mutation catalogue.
