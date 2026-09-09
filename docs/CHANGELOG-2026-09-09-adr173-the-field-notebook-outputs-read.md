# 2026-09-09 — ADR-173: the field notebook's outputs, read — and the notebook gets a suite

**Three exports the notebook hands over and nothing read — the .eco lines, the
CSV, the print — are pressed and held by the task, byte for byte; and the one
data-entry page without a suite gets one. Unread outputs 18 → 15.**

## Changed — `tools/tasks/page-field-notebook-science.json`

63 → 70 steps, 80 → 95 confirmed. After ADR-165's scenario, verbatim:
`ecoCopy` (clipboard, the seven .eco lines whole), `csvCopy` (clipboard,
fifteen rows under `section,item,count`, the comma-bearing site quoted),
`Print / save PDF` (one print payload), then the counters and the .eco box
read once more.

## Added — `tools/verify/verify_fn.py`

21 checks. Shannon, Pielou, Hill N1, variance/mean, Morisita, Lincoln–Petersen
(and its R = 0 "undefined" in words) from independently stated formulas; the
.eco from the grammar and the CSV from RFC 4180 on the clipboard; the print
counted once; and the task's literals held to the same texts and figures.

## Changed — `tools/outputs_ledger.json`

field-notebook: 3 held, ceiling 3 → 0.

## Numbers

    field-notebook     0 → 3 of 3 outputs held
    the kit           18 → 15 unread of 66
    suites            75 → 76

## Held

- Both exports are deterministic (the task enters the date) and held whole.
- No page was edited.
