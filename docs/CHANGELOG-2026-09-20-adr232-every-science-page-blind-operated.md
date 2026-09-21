# 2026-09-20 — ADR-232: every science page blind-operated, and a picker says what it holds

## Changed

- **`read-control` on a picker** carries `picker.selected` (the row marked as
  picked among those the filter shows) and `picker.selectedNote` (why a null:
  nothing picked, filtered out of view, or no rows shown).
- **The tenth blind trial** — the ecology lab alone, the kit's longest task:
  39 / 55 outcomes, 234 / 263 claims, 132 calls, 61 of 61 values entered;
  19 guards from the trace (18 report, 1 snapshot), **0 refused**. Every one
  of the 21 science tasks now has a blind trace. Under `tools/traces/blind10/`.
- **The ecology lab's goal sentence** named four figures the page does not
  show (Bray-Curtis 0.35/0.29, Newick depth 5/3); the task held 0.31/0.25 and
  6/4 all along. Corrected; the task re-run.
- `docs/OPERATOR.md`: a message written into a box moves the report stamp;
  stamps are digests, not histories; the picker's selected row.

## Checked

verify_report 276 → 281, verify_tasks 466 → 479; mutate_report 162 → 165,
all killed.

## Filed

Unkeyed chart numbering shifts past a chartless station (`charts/station-grid
#4` gained in a diff); a theory model resets its parameters when chosen; the
sites verdict at Bray–Curtis 0.17.
