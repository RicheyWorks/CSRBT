# Changelog — 2026-09-02 — ADR-126: the first trace

## Changed — `tools/harness_mcp.py`

`--trace FILE` / `CSRBT_HARNESS_TRACE`: every `tools/call` (refusals
included) and every `resources/read` appended as a JSON line with the
gateway's whole response.

## Changed — `tools/harness_tasks.py`

`grade_trace` and `--grade-trace FILE | all`: required steps in order by the
next unused call, probes (`optional: true`) afterwards anywhere, one call
per step, UNMET / SKIPPED, `"$.path"` for a response's own fields, `observe`
as a step action (run and traced), economy (`calls` vs `required`) on the
record; grades kept as `<task>@trace`. Tasks re-shaped to their goals
(`replicaLagMs > 0`, `entries == $.snapshot.size`, an `observe` step for the
crash counter, probes marked optional).

## New — `tools/traces/*.jsonl` (6), `tools/traces/PROVENANCE.md`

The assistant's traces, planning from each goal and `tools/list`; all six
PASS; provenance stated.

## Changed — `tools/verify/verify_tasks.py` (48 → **70**), `tools/mutate_tasks.py` (10 → **16 killed**)

## Docs

`docs/ADR-126-the-first-trace-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
