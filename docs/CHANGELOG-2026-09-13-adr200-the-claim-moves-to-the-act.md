# 2026-09-13 — ADR-200: the claim moves to the act

**ADR-199 gave every act `said` and closed by saying it had not made the six
steps polling `boxes.toast` correct, only unnecessary. This is that slice — and
it found the task grammar could not state the claim at all, and that the kit has
two message conventions rather than one.**

## Added

- `any-contains` and `none-contains` in the task grammar: *some element of this
  list of strings holds this text*, and its mirror. `said` is a list, and the
  claim about a refusal is almost never the whole string — `contains` on a list
  is exact membership of one element, which is left unchanged, because a table
  row is a list of cells and widening it would loosen every list claim in the
  kit. Both directions are false on a path that is not a list, and a missing
  path proves nothing in either direction.
- `verify_tasks` (371 → 380) and `verify_report` section N (237 → 242).
- `mutate_tasks` (80 → 87) and `mutate_report` (141 → 145).

## Fixed

- **greenhouse** — `#runMsg` and `#srcMsg`, and **tree visualizer** — `#msg`:
  a dedicated `msg(text, bad)` writes a sentence into these and colours it red
  when the news is bad, and none of them was a live region. The greenhouse's
  *"Load a source first — there is nothing to save."* is the entire outcome of
  that press and it reached neither a screen reader nor the door. All three now
  declare `role="status" aria-live="polite"`. The tree visualizer is a page
  this kit's `.toast` convention never touched.

## Changed

- Six steps in three tasks. Each `read-report` of `boxes.toast` — a whole
  report taken inside a 1.7-second window against a box holding whatever the
  last message was — is replaced by a claim on the act that raised it, and four
  of those read-reports existed only for the race and are gone. The protocol
  library's copy also claims `produced == 1`; the two refusals claim
  `produced == 0`; and the experiment guide's accepted model claims
  `none-contains "needs 4 parameters"` — the assertion that the refusal did not
  come back, which the old grammar could not write. A check scans every task
  file and fails if any of them reads the toast box again.
