# The second blind trial — provenance (ADR-141)

The six traces in `tools/traces/blind/` were the first blind trial (ADR-136).
They put six tasks to operators that could not see the answers, and every miss
turned out to be a defect in the *instrument* — the grader, the task shapes.

These five are the second trial, run **2026-09-04**, and they were pointed at
the science pages: the data-entry pages this harness exists for. The five files
here are gzipped because each response carries a full page snapshot and the raw
set is 8.6 MB; `gunzip -c <file>` is the trace exactly as it was written.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind2/CSRBT` — a copy of the repo with `tools/tasks/`, `tools/traces/`,
`tools/task_ledger.json`, every `docs/ADR-*.md`, every `CHANGELOG-*`,
`AI_HARNESS.md`, `AUTOMATION-HARNESS.md` and `PLAN-*.md` **removed from the
filesystem**. Each was given one task's `goal` sentence verbatim, and
`tools/blind_console.py` with `SENSITIVE_READ`, `DRAFT` and `MUTATE` allowed
and `DESTRUCTIVE` withheld — a supervised operator.

Five traces for four operators: `page-breeding-bench-science` has a second
file, `.elevated`, because that operator's first run could not finish and it
re-ran with `CSRBT_HARNESS_ALLOW_DESTRUCTIVE=true` inherited. Both are kept.
The difference between them is the finding.

## Why these are not graded

`harness_tasks.py --grade-trace all` reads `tools/traces/` and
`tools/traces/blind/`. It does not read this directory, deliberately.

These five record a door that no longer exists. They were taken against the
contract as it stood at protocol 1.4, where `activate` was `DESTRUCTIVE` for
every button on every page; ADR-141 changed that, and changed the refusals, the
snapshot's pools and the console's own output with it. Grading them now would be
grading the fix against the trial that produced it, and a re-run under the new
door would be a different trial, not a regrade of this one. They are kept as
what they are: the record of what four operators actually met.

## What they found

Converging across four operators who could not see each other's work:

1. **The door as specified cannot press a button.** Every control on these pages
   is pressed through `activate`, `activate` was `DESTRUCTIVE`, and a supervised
   session does not hold `DESTRUCTIVE`. The `page-pheno-tracker-science`
   operator refused to escalate and reached only the segregation figures it
   could read; the other three finished only by inheriting the wipe-the-store
   rung in order to press *Add stem*.
2. **The snapshot advertises what the door then denies** — `activate.selector`
   pools, 65 of them on one page, for a tool the session does not list.
3. **A gated tool refuses as `not_found`**, indistinguishable from a typo:
   *"no tool 'csrbt_page__activate' is listed for this session"* tells a blind
   operator the tool does not exist, not that a rung is withheld.
4. **Positional selectors renumber silently.** A stale `action_btn:45`
   **deleted a tallied stem** and answered `ok: true`.
5. **`read-control` returns no id and no label**, so a control read one at a
   time cannot be matched to the control a task names.
6. **The console truncated every response to 4000 characters**, silently. The
   snapshot is the documented discovery path and is 40 KB on these pages, so it
   arrived as JSON that would not parse; two of the four operators abandoned
   `blind_console.py` and wrote their own JSON-RPC client, which means the trial
   was partly measuring the console rather than the door.

All six are fixed in ADR-141. The vocabulary the risk classifier uses came from
an inventory taken across all 41 routed pages: **956 distinct labels over 1,453
activatable controls**, of which the classifier raises **110** — 34 distinct
labels, and every one of them names a removal: the bare ✕ (39), ↩ Undo (19),
Clear (8), "Forget this device's copy" (8), Start over (4), Reset (3), Clear
mix (2), and one each of Clear trial, Clear form, Clear ticks, Clear the log,
Clear all runs, Clear whole run, Clear pile, Clear the list, Undo last, remove
last, Delete, and eleven ✕-prefixed chip removers.
