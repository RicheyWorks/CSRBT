# Changelog — 2026-09-03 — ADR-131: audits, after entry

## Audits — `tools/`

- `audit_states.py`: `enter()` replays a page's own science task in process on
  the audit's browser, then `entered` and `entered/pane:<id>` are walked;
  `task_for()` picks the science task and never a reference task, a canary or
  another page's; `entry_fault()` makes an entry that drove nothing a fault
  while an expected refusal is not; `_settle()` waits out running animations;
  stamps come from a window counter so a control built by the entry cannot
  take an existing stamp.
- `audit_focus.py`: presses and releases a key before every probe, so the
  browser is in its keyboard mood whatever the entry did; a never-reached
  entered state is a counted fault.
- `audit_targets.py`, `audit_contrast.py`: count an unreached entry, and print
  the entry's task and how far it got on every row.

## Pages — `docs/`

- 42 controls under 44 px that only exist once data is entered:
  survey-design's hierarchy-node buttons (32), stand-sheet's per-stem remove
  (4), experiment-guide's chip close and chip height (3), relevé's C-value box
  (2).
- relevé's C-value inputs gain `aria-label="C-value for <taxon>"`.

## Verification

`verify_audit_states` 52 (+19, section F); `mutate_audit_states` 34 (+14).

## Docs

`docs/ADR-131-audits-after-entry-2026-09-03.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
