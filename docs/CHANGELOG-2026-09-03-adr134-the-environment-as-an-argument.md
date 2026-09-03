# Changelog — 2026-09-03 — ADR-134: the environment as an argument

## Contract

- Protocol **1.3 → 1.4**: a target may publish actions that set the environment
  a run happens in. `harness_mcp`'s `serverInfo.version` is now the gateway's
  protocol version instead of a second number.

## Harness — `tools/`

- `harness.DETERMINISM`: an init script installed beside `harness.STUBS` on
  every browser target. It replaces `Date`, `performance.now` and
  `Math.random`, and while `window.__D` says nothing they are the real ones.
- `mulberry32.py` (new): the kit's generator in Python, masking to 32 bits at
  every step. A port, not a wrapper — it lived in a scratch file until now.
- Page plugin: `set-clock`, `set-seed`, `set-dialog` (NAVIGATE) and
  `read-dialogs` (SENSITIVE_READ); each set is re-installed as an init script
  so it survives a reload; the snapshot publishes `environment`.

## Tasks — `tools/tasks/`

- tree-visualizer: seeded random inserts (60 first, 24 eleventh, 11 nodes,
  11 draws). tree-proofs: twenty seeded accesses against an independent splay
  port (131 actual, 152.0 amortized). ethogram: a frozen clock stamps
  2026-03-01. greenhouse: `confirm()` answered no keeps the five runs, yes
  clears them.

## Pages — `docs/`

- survey-design: `.tree .n` wraps and `.id`/`.ty` shrink — a long site id
  pushed the row's buttons 2 px past a phone's edge (found by the robot).

## Verification

`verify_report` 49 (+16); `mutate_report` 35 (+11); `verify_contract` 89 at
1.4; `verify_walk` at 21 page tools; all 41 pages re-walked.

## Docs

`docs/ADR-134-the-environment-as-an-argument-2026-09-03.md`;
`docs/AUTOMATION-HARNESS.md`, `docs/AI_HARNESS.md`.
