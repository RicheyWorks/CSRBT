# Changelog — 2026-09-02 — ADR-129: every page, operated

## Page plugin / swarm

- `read-report`: box suffixes `Msg|Check|Read|Desc|Left|Res`; boxes hold
  4,000 characters; `headings` (h1–h3, in order); a bare `.k` label beside
  a `.v` is a figure. `swarm.SWARM_KINDS`: every `input[type=range]` is a
  slider.

## Tasks — `tools/tasks/`

- Six science tasks with independent oracles: `page-plant-characters-key`,
  `page-fungal-characters-key`, `page-cp-characters-key`,
  `page-tree-visualizer-science` (a Python port of RB/AVL/WB/Splay),
  `page-tree-proofs-science` (splay potential, the AVL table, order
  statistics), `page-ecology-lab-science` (mulberry32 terrarium, every
  workbench figure).
- Fourteen `page-*-reference` tasks pinning each reference page's outline.
- Every routed page has exactly one task; `verify_tasks` pins it (125 quick).

## Verification

`verify_report` 33, `mutate_report` 24/24; `verify_tasks` 125 (quick);
`walk_ledger` re-walked for `ecology-lab` (set-slider driven 6/6);
`task_ledger` 44 page tasks held, 1,807 confirmed.

## Docs

`docs/ADR-129-every-page-operated-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
