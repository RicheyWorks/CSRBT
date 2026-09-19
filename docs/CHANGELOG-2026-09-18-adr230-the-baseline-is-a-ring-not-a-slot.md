# 2026-09-18 — ADR-230: the baseline is a ring, not a slot (protocol 1.10)

## Changed

- **`since` takes any of the last 8 stamps a door served**, snapshot and
  report alike; an older stamp is unknown and the reason names the depth; a
  stamp served again moves to newest. Manifest `session.baselines: 8`;
  `stamps.report` names `output.stamp`.
- **The eighth blind trial** — micro bench, ordination, field notebook,
  selection log, one attempt each: 35 / 63 outcomes, 116 / 175 claims, 311
  calls. Non-latest `since` asks answered "unknown": 10 of 10 in the seventh
  trial, 5 of 32 here. Traces, tasks, the operators' manual and provenance
  under `tools/traces/blind8/`.

## Checked

verify_contract 230 → 241, verify_report 249 → 252, verify_tasks 429 → 446,
mutate_contract 111 → 116, mutate_report 151 → 153.

## Filed

Micro bench zone outputs drop medium/organism; selection-log dials toggle off
on re-press; ordination's stale toast; the snapshot stamp is controls-only and
operators keep reading `changed: false` as "nothing happened".
