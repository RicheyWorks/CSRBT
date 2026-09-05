# Changelog — 2026-09-05 — ADR-142: the rungs a task declares

ADR-141 let a supervised session press a button. This one asks whether the
tasks can actually be *run* that way — because the runner had been opening all
four rungs for every task since ADR-114, so every "the harness can enter this
data" in this kit was measured with the wipe-the-store rung held throughout.

## The robot — `tools/harness_walk.py`

- `WALK_RUNGS` (all four) and `SUPERVISED_RUNGS` (`SENSITIVE_READ`, `DRAFT`,
  `MUTATE`), named.
- `_spawn(..., allow=)` — and it now **clears every inherited
  `CSRBT_HARNESS_ALLOW_*`** before setting what it was given. A rung open in the
  parent's environment is a rung nobody in this process decided to open.
- `Wire` and `McpWire` take `allow=`; with none, a wire is a walk and holds
  everything.

## The tasks — `tools/harness_tasks.py`, `tools/tasks/`

- A task runs **supervised** unless its file says otherwise. `"policy":
  {"allow": [...], "needs": [step ids], "why": "..."}`; `DESTRUCTIVE` requires
  both a non-empty reason and step ids that exist in the task.
- The ledger records `rungs` and `rungsWhy` per task — including on the
  early-exit DEFECT path, because an entry that does not say what it was
  allowed to do cannot be compared with one that does.
- **12 of 54 tasks declare `DESTRUCTIVE`**, each naming its step: the
  greenhouse's *Clear all runs*, the food web's / soil bench's / stand sheet's
  *Undo*, three character keys' *Start over*, the breeding bench's *Clear
  trial*, the tree visualizer's *Clear*, the survey design's row remove, tree
  proofs' *Reset*, the experiment guide's *Start over*.
- **42 of 54 enter their data with no destructive rung at all.**

## The classifier's first false positive — `tools/harness_plugin_page.py`

`page-field-notebook-science` failed supervised on its **tally chip**, which is
one button reading `<span class="x" data-x>✕</span><div class=name>clover</div>
<div class=count>3</div>`: clicking the button increments the tally, clicking
the ✕ inside it deletes the row. ADR-141's label took the whole button, saw a
removal mark, and raised a data-entry page's primary control to `DESTRUCTIVE`.

`LABEL_FN` now strips `[data-x]` and `.x` children — the same rule already
applied to `<small>` and `<kbd>`: the name of a control is not the name of a
smaller control inside it.

Re-measured over all 41 routed pages: raised **110 → 99** of 1,453 activatable
controls, distinct raised labels **34 → 23**. The eleven that left were tally
chips on the three pages using that pattern; every remaining one names a
removal.

## The board — `tools/harness_board.py`

- A new tile: **entered supervised**, `42 / 54`. Entries written before this ADR
  carry no rungs and are counted neither way.

## Verification

- `verify_tasks` **282** (+48): the supervised default; a declaration granted
  exactly and in ladder order; five refusals on fixtures (no reason, no
  `needs`, a `needs` naming nothing, a rung outside the ladder, an empty allow
  list); the ledger's per-task record. And the one that runs something: **a task
  that never declared the fourth rung and reaches for it is refused by the
  door** — without which a runner that read the declaration and ignored it would
  pass everything else.
- `verify_walk` **126** (+5): the named sets, a supervised wire, the parent
  environment that does not leak into it, the withheld tool, the refusal.
- `mutate_tasks` **62** (+7), 62 killed, 0 survived — including "the runner
  opens every rung again" and "a task's declaration is read and then ignored".
- `verify_report` 79, `mutate_report` 50 killed: the label change is covered by
  the chip already in that fixture.

## Docs

`docs/ADR-142-the-rungs-a-task-declares-2026-09-05.md`; `docs/AI_HARNESS.md`,
`docs/AUTOMATION-HARNESS.md`.
