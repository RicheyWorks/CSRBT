# 2026-09-10 — ADR-180: the figures beside the controls

**The readable audit skipped any element holding a control, so a figure
written beside a button was never measured. It now reads such a host by what
remains once its controls, the entry kit's widgets and its links are
subtracted, on both sides. 42 more elements measured, 6 blind, 0 after: the
survey's event tree becomes a box the task holds byte for byte; five are
declared furniture.**

## Changed — `tools/audit_readable.py`

- `TEXT_JS`: an element holding a widget (`[data-h]`, button, input, select,
  textarea, label, `a[href]`, `.fek-row/-step/-dial/-pick/-field/-slide/
  -chip/-chips/-lab/-help`) is read from a clone with those removed; the same
  subtraction on the baseline. `"whole"` reads unsubtracted (a mutant, not a
  mode the audit uses).

## Changed — `tools/harness_plugin_page.py`

- `BOX` names `tree` as a whole-id box, beside `journal` and `toast`.

## Changed — suites, runners, task, ledger

- `verify_readable` 33 → 37: `rankHost` (a row with a button: written,
  unreadable), `scoreBoard` (the same in a `*Board`: readable), `fekHost` (a
  kit stepper with label and help: not written), `linkHost` (static prose
  with a link: not written); fixture2's host gains a `.kopt` option, so the
  stamp-first rule is tested by a control that is not a button.
- `mutate_readable` 30 → 33 / 33: read whole, skipped whole, furniture as a
  figure, baseline read whole; the True/False flag recorded equivalent.
- `verify_report` 114 → 115; `mutate_report` 68 → 69 / 69 (`tree` is a box;
  the regex anchor widened).
- `page-survey-design-science` 73 → 74: `boxes.tree` byte for byte, fifteen
  rows. `verify_sd` 70 → 73: `demo_tree()` port of the example's ID scheme;
  the page's rows and the task's literal held to it.
- `readable_ledger.json`: furniture `pRg` (collection-sheet), `fkq`
  (fungal-characters), `scorePanel`, `traitChips` (pheno-tracker), `wEditor`
  (releve), each with a reason; every ceiling 0.

## Numbers

    written 270 → 312    blind 0 → 6 → 0    ceilings 0

No page was edited.
