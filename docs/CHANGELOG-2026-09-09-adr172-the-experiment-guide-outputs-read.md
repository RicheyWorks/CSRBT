# 2026-09-09 — ADR-172: the experiment guide's outputs, read

**Five exports the guide hands over and nothing read — the .eco copied and
downloaded, the pre-registration, the JUnit skeleton, the printed checklist —
are pressed and held by the task, the .eco byte for byte. Unread outputs 23 → 18.**

## Changed — `tools/tasks/page-experiment-guide-design.json`

165 → 179 steps, 220 → 251 confirmed. After the existing scenario, verbatim:
`eco-copy` (clipboard, the whole protocol), `eco-download` (download named
`clashing-study.eco`, same bytes), `eng-copy` (the two measured rows, header,
workload/seed/passes, fired verdict), `eng-skel` (the whole skeleton),
`cl-print` (one print payload). Each collect-output holds that no second
payload exists.

## Changed — `tools/verify/verify_experiment_guide.py`

86 → 92. Builds the expected `.eco` from the grammar and the pre-registration
rows from the guide's arithmetic, and holds the task's literals to them —
`keys: 201` in the task fails two checks.

## Changed — `tools/outputs_ledger.json`

experiment-guide: 5 held, ceiling 5 → 0.

## Numbers

    experiment-guide    0 → 5 of 5 outputs held
    the kit            23 → 18 unread of 66

## Held

- The prereg's date is not pinned; every computed line is.
- No page was edited.
