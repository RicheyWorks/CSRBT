# The sixth blind trial — provenance (ADR-228)

Four operators, **four science pages that had never been operated blind** —
greenhouse, soil bench, survey design, tree visualizer — through the door that
ADR-188 through 227 built. The first five trials ran the same four pages
(stand sheet, collection sheet, pheno tracker, breeding bench) over and over
to measure the door as it changed; this one turns the loop outward and starts
paying down the forty science tasks that no blind operator had ever touched.

What is new in the door since the fifth trial is ADR-228: `blind_console` lets
a `call` carry `if_stamp` and `expires_at` — the two things ADR-222 gave the
gateway and no operator could send. This trial is the first that could use
them, and all four did.

Run **2026-09-18**. Traces are gzipped; `gunzip -c <file>` is the trace exactly
as the server wrote it.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind6/CSRBT` — a copy of the repository with `tools/tasks/`,
`tools/traces/`, `tools/delivery/`, `tools/push/`, every ledger, the board and
its renderer, every `mutate_*.py`, the whole of `tools/verify/` except
`_kit.py` (which the door imports), and every `*.md` **removed from the
filesystem**. As in ADR-136, "the operator did not see the task" is a fact
about the disk. Each was handed its blind brief (ADR-193), an `OPERATOR.md`
that now documents `if_stamp` and `expires_at`, and
`blind_console.py --session <name> --rungs SENSITIVE_READ,DRAFT,MUTATE,DESTRUCTIVE`
— every one of these four tasks declares the fourth rung, because every one
ends in an irreversible act.

## What it measured

| task | reached | of | claims | of | calls | attempts |
|---|---|---|---|---|---|---|
| page-greenhouse-science | **18** | 24 | **96** | 107 | 43 | 1 |
| page-soil-bench-science | **11** | 17 | **41** | 53 | 40 | 1 |
| page-survey-design-science | **15** | 22 | **40** | 54 | 35 | 1 |
| page-tree-visualizer-science | **11** | 15 | **62** | 71 | 53 | 1 |
| **total** | **55** | 78 | **239** | 285 | **171** | **4 in 4** |

Every operator finished in one attempt, took the snapshot once and worked from
the diff, and reached its DESTRUCTIVE step: the greenhouse's *Clear all runs*
(runChart removed from the report), the soil bench's *Undo*, the survey's
stratum *remove* and scope clear, the tree's *Clear*.

## What it measured about ADR-222's two fields

This is the trial's real subject, and it is measured, not asserted. Every one
of the four **guarded its irreversible act with `if_stamp`**, and the trace
carries the proof in the door's own words:

- **A stale `if_stamp` refused the act, on all four.** Each operator first read
  a stamp, let (or made) the page move, and pressed with the old stamp; the
  door answered `stale`, naming the stamp it was bound to and the stamp the
  target had, and *nothing ran*. The recorded `activate` shows the refusal —
  e.g. greenhouse: *"csrbt-page has moved since the snapshot stamped
  s36d33023c4f8 (it is s0eb7855db728 now) and nothing was run"*.
- **A past `expires_at` refused the act.** The tree operator set a 2020
  deadline on a Clear and the door answered *"this command expired at
  2020-01-01T00:00:00+00:00 and was not run"*, then ran the same act with a
  fresh stamp and a future deadline.

An operator who had just read a figure could, for the first time, say "clear
the runs only if the page is still the one I read" — and be refused when it was
not, instead of clearing a page that had changed under the plan.

## What every operator found in the door (recurred, filed)

**The report stamp and the snapshot stamp cannot be told apart, and `if_stamp`
guards only the snapshot one.** All four, independently, first passed a
`read-report` inner stamp to `if_stamp` and were (correctly) refused `stale`,
then switched to the snapshot/observe baseline stamp and succeeded. The fifth
trial filed the same confusion for `read-report`'s `since`; ADR-228 gives the
operator a second place to make it. Both are `s` + twelve hex digits and
nothing on the wire says which series a stamp belongs to. It never caused a
wrong answer — the door failed toward refusal — but it cost every operator a
guarded retry. This is the clearest candidate for the next slice.

## What they found in the pages (filed, not fixed)

- **tree visualizer** — the task holds `24 nodes after 15 seeded random
  draws` (`msg: "inserted 24"`), and the page produces **28**. The operator
  reproduced the draw *sequence* exactly (60 first, 19 eleventh) but every one
  of the 15 presses answered `inserted` — the page's random button draws until
  it finds a key not already present, so 13 boot keys + 15 new = 28, and the
  task's 24 would require four collisions the page never allows. The seeded
  outcome is the one this trial missed on that page; the miss is this
  divergence, not the operator.
- **survey design** — the copied occurrence CSV carries an `occurrenceID`
  column of random UUIDs; the task excludes the per-row UUID from grading, so
  this is a grader-side exclusion working as intended, noted only so the next
  reader does not re-find it as a defect.
- **greenhouse** — the brief's "against the clones band" (78% of time outside)
  is read under a growth-stage the 13 listed values do not name; the operator
  set the clones/seedlings stage to reach it. Not a defect; a value the brief
  implies in prose but does not tabulate.

## Why these numbers are floors

No blind operator had touched these four pages, so there was nothing to beat —
`verify_tasks` section F6 holds this run's reached/claims as the floor a later
door or a widened goal may not fall below, exactly as F3–F5 hold the first four
pages. Graded as a ROUTE (the script, in order) all four are FAIL, as in every trial
before this one: an operator reaches the outcomes without walking the steps.
