# Changelog — 2026-09-02 — ADR-128: the report, read

## Page plugin — `tools/harness_plugin_page.py`

- **`read-report`** (SENSITIVE_READ): every `.l`/`.v` figure, flat and by
  box; every box by the kit's id conventions, read behind closed panes with
  `shown` beside; every table's cells; every `.row2` list's count.
- **`pick`** (DRAFT): a FEK picker driven through its filter and option
  list — exact label, else prefix, else the sole option left, else refused
  as ambiguous or no match.
- The snapshot's controls carry `id`, `host` and a label a finger reads
  (`<small>`/`<kbd>` stripped, `.nm` honoured).

## Tasks — `tools/harness_tasks.py`, `tools/tasks/`

- **`@control:<name>`** in arguments: id, then label, then host;
  `host/label`; `#n`; resolved from the latest snapshot; DEFECT when none.
- **21 science tasks**, one per data-entry page, each holding the page's
  report to a hand-checked oracle; **1 page canary** (`must: FAIL`).
  `task_ledger.json` regenerated: 23 page tasks held, 1,316 confirmed.
- 16 published pages republished and stamped current (`tools/published.json`).
- Kit: 76 / 76 jobs, 5,389 / 5,389 checks; the board re-rendered.

## Kit — two findings from the robot

- `.rowlist` on 15 pages: `grid-template-columns:minmax(0,1fr)` and `.row2`
  wraps below 220 px of name — a record row no longer pushes a phone's page
  sideways once a host is recorded.
- `docs/experiment-guide.html`: a non-text file dropped on the import card
  is refused by name and imports nothing; lint rows wrap long tokens.
  `verify_experiment_guide` 86 checks (+4).
- Page plugin: `show-pane` honours `aria-controls` tabs (the guide's).
- Robot: `CSRBT_WALK_VERBOSE=1` prints every command; `--page a,b` re-walks
  a few pages into their own entries.

## New — `tools/verify/verify_report.py` (**30 checks**), `tools/mutate_report.py` (**22 mutants, 22 killed**)

## Verification

`verify_tasks` 133 checks (+63: the `@control` grammar, two canaries,
section G the science); `mutate_tasks` 24 mutants, 24 killed; `verify_walk`
17 page tools; `walk_ledger.json` regenerated for the page target over both
transports and every routed page; the board lists the new suite and runner.

## Docs

`docs/ADR-128-the-report-read-2026-09-02.md`; `docs/AUTOMATION-HARNESS.md`,
`docs/AI_HARNESS.md`.
