# Changelog — 2026-09-02 — ADR-130: audits, everywhere

## Audits — `tools/`

- `audit_states.py` (new): walks a page through its states — `rest` with
  every `<details>` open, each `.tab[data-pane]` and `[aria-controls]`
  pane, the page-specific reveals in `STATE_BUTTONS` (a button, or a
  `<select>` value that grows a dependent field, its tab pressed first),
  and a revealed surface's own tabs — with programmatic clicks, and keeps
  the accounting: `coverage()` names every control no state exposed.
- `audit_targets.py`, `audit_contrast.py`, `audit_focus.py`: measure per
  state, merge findings by key, print states and `measured/exist`, and
  count a never-exposed control as a fault. `CSRBT_DOCS_DIR` and
  `CSRBT_AUDIT_STATES` are the suite's fixture hooks.

- `audit_frontend.py`: reconciles every rule a page's `<style>` declares
  against the rules the CSSOM kept, and names any the browser dropped
  (`css-rule-dropped`); `::-moz-`/`::-ms-` rules are exempt.

## Pages — `docs/`

- Ten controls under 44 px behind tabs (cell-bench `.bgrid .bb`,
  farm-scout `.bed .x`, pheno-tracker `.kbtn`, deployment-log `time`) and
  twenty-five field borders at 1.35:1 (experiment-guide, cp-bench,
  pheno-tracker's note) fixed; the audits are clean in every state.
- An orphaned declaration block on deployment-log, ordination and relevé
  was eating the `.tiles` rule after it; removed, and `.tiles` is live
  again on all three.

## Verification

`verify_audit_states` 33 (new); `mutate_audit_states` 20/20 (new);
`verify_audit_frontend` 23 (+3); `audit_frontend` 369/369, 0 dead rules.
The board lists both new runners.

## Docs

`docs/ADR-130-audits-everywhere-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
