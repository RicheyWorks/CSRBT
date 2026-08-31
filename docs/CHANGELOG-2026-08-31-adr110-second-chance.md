# Changelog — 2026-08-31 — ADR-110: a control judged on an empty page

Ten of twelve "dead" controls were working; the harness had pressed them with no
data. Full suite **68 of 68 jobs, 4,591 of 4,591 checks**; Java **1,127 tests**.

## Fixed — the harness only ever tested the empty state

- **Second chance.** Anything still dead at the end of a walk is pressed once
  more against state built by the page's own controls. Pane-scoped, and it
  **rebuilds** the state rather than inheriting it — on field-notebook the walk
  both builds the tally history and drains it, so a retry in the leftover state
  is the same wrong test twice.
- **dead: 12 → 2.** Revived controls are recorded as having "needed prior state".
- A bug in the implementation was caught by the accounting identity mid-write:
  the per-pane loop extended every bucket and then overwrote `res["dead"]`,
  losing two affordances. The run printed `UNACCOUNTED`.

## Fixed — a real product defect, surfaced and repaired

- `docs/tree-proofs.html` **"New random tree" built the identical tree every
  press.** The shuffle was a pure function of the loop index, and `take` read
  `RB.rot` from a tree created one line earlier, always 0. Probed: four presses,
  no change to text, SVG or DOM. Now a counter advances per press and seeds an
  xorshift mixer — press N always yields tree N, reproducible and different from
  press N−1. Verified across reloads.

## Fixed — a finding's identity has to survive the next run

- Generated row ids (`harness-373:plot:01`) leaked into signatures, minting new
  ones every run and reading as regressions. They collapse to `#` now, and the
  normalisation applies to labels parsed out of error strings too — it previously
  applied only to records, which is why every spill kept its row id.
- **Counts are no longer compared.** The second-chance retry moved a signature
  from 7 occurrences to 9 with no page change, because the retry builds more rows.
  How many rows a walk builds is a property of the walk. A ratchet that fires on
  its own maintenance gets ignored.
- Accepted debt: **32 distinct → 17**, across 4 pages instead of 8, nothing
  forgiven. `survey-design` has one row-spill defect, not twenty-three.

## New — tester coverage for the new clause

- `verify_harness_matrix` section J (5 checks), including `j_drained`, which puts
  the drain in a second pane so the walk ends empty and only a real rebuild can
  revive the control. **62 checks total.**
- Three new mutants. The catalogue found a genuine survivor (the rebuild clause
  was unasserted) and a self-reference (a mutant "killed" by the anchor check,
  which proves nothing) — the runner now marks mutation runs so section I stands
  aside. **13 mutants, 13 killed, 0 survived.**
