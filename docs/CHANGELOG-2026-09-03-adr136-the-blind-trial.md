# Changelog — 2026-09-03 — ADR-136: the blind trial

## Harness — `tools/`

- `blind_console.py` **(new)**: the operator's side of the door. Spawns
  `harness_mcp.py` as a child, speaks JSON-RPC over the pipe, and offers
  `tools/list`, `resources/list`, a call and a read — and nothing else. It
  never reads `tools/tasks/`. `--moves <json>`, `--trace <file>`.
- `harness_tasks.py`:
  - `grade_trace` — **an observation rides every response**: an `observe` step
    is met by any call whose response carries a `snapshot`. The licence is
    `observe`'s alone; a response with no snapshot observes nothing.
  - `load_task` — **a claim may not rest on a probe**: a required step that
    reads an `"optional": true` step's response is a task DEFECT at load. The
    rule is one-way.
  - `--grade-trace all` now reaches `tools/traces/blind/` too, filing each
    blind grade in the ledger as `<id>@blind` beside the sighted `<id>@trace`,
    and marking the line it prints.

## Tasks — `tools/tasks/`

- `page-enter-and-read-back`: `read` expects `$type.output.value`, not the
  literal the task happens to type; `still` also requires `output.filled > 0`.
- `organism-crash-road`: `look` and `settle` are probes; the steps are ordered
  `arm, crash, wedged, look, clean, settle, count, wire, fold`; `count` claims
  `>= 3`, the goal's claim rather than the author's batch size; `fold` also
  requires `output.gapped: false`.
- `organism-replica-behind`: `w2`, `w3`, `w4` are probes — one write is the
  claim, four were the author's route.

## Traces — `tools/traces/blind/`

- Six blind traces and `PROVENANCE.md`: the conditions, verbatim goals, the
  deleted directories, both gradings, and the one run that was mis-conducted
  with a paraphrased goal and re-run.

## Audits — `tools/`

- `audit_states.py`: the walk **settles once more at the end**, and if the page
  grew a control after the last stamp, stamps and measures it in a final
  `settled` state. A control mounted after the last stamp had carried no stamp
  at all, and `coverage()` reported it — correctly by its own rule, falsely in
  fact — as a control no state exposed. deployment-log produced that fault on
  one kit run and not the next two, and it named nothing.

- `harness_board.py`: the Tasks and traces table gains a **blind trace**
  column, and the headline counts the blind grades among the traces — twelve,
  not six. `verify_board` requires both (45, +2).
- `verify/run_all.py`: a failing job whose output has no line beginning `FAIL`
  — every audit, which reports a fault table and a total — printed its name and
  nothing else. It now falls back to the last twelve lines the job printed.

## Verification

`verify_tasks` 234 (+25; 180 in QUICK) — the observe rule three ways, the
probe rule both directions, and **section F2**: the six blind traces graded
PASS and held, every required step met, the observe rule exercised by the
evidence, probes demonstrably skipped, the provenance on the record, and the
ledger carrying every `@blind` grade.

`mutate_tasks` 55 killed, 0 survived (+11). The runner now mutates **task
files** as well as the harness: four mutants put the author's constants back,
and only the blind operators refuse them.

`verify_audit_states` 55 (+3); `mutate_audit_states` 37 killed, 0 survived (+3).

A committed task that will not load is now a failing check, not a traceback.

Kit: **77 / 77 jobs, 5,615 / 5,615 checks**.

## Docs

`docs/ADR-136-the-blind-trial-2026-09-03.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
