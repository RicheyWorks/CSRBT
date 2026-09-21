# ADR-232 — every science page blind-operated, and a picker says what it holds

**Date:** 2026-09-20 · **Status:** accepted · **Chain:** ADR-231 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The standing goal is that the harness operates every science page and proves
data entry and every report. Since ADR-187 the proof has been the blind
trial: an operator who has never seen the task, a stripped checkout, the
door, and a graded trace. After the ninth trial 20 of the 21 science tasks
had one. The ecology lab — the kit's longest task, 337 steps, 61 values,
nine stations — did not, because every trial ran four pages and it was
always the one that would not fit.

And the ninth trial's cp-bench operator filed the one reader gap it hit:
`read-control` on a picker lists the rows the filter shows and never says
which one is picked, so a pick could be confirmed only by reading whatever
verdict it fed.

## Decision

**`read-control` on a picker says which row is picked.** `picker.selected`
is the text of the row marked as picked among those the filter shows, and
`picker.selectedNote` says, when it is null, which of three things is true:
nothing is picked, the pick is filtered out of view, or the filter shows no
rows. The list holds only the rows the filter shows (that is how the kit's
picker works), so a null is honest only with the reason beside it. Held by
`verify_report` D on the collection sheet through all four states; three
mutants (never finds the row, calls the first shown row the picked one, calls
an empty filter "nothing picked"), all killed.

**The tenth blind trial: the ecology lab, alone.** One operator, one attempt,
the rewritten manual (ADR-231's `docs/OPERATOR.md`), and the first door that
records the guard a call carried, so the guard is measured from the trace:

| | |
|---|---|
| outcomes | **39** of 55 |
| claims | **234** of 263 |
| calls | 132 |
| values entered | 61 of 61 |
| guards sent | **19** — 18 report stamps, 1 snapshot stamp |
| refused `stale` | **0** |

Every guard was the stamp from the read before it; the runs of presses went
unguarded, as the manual now says. The ninth trial's farm scout, under the old
manual, was refused 127 times. `verify_tasks` F10 holds the floors, the guard
count by series, the zero refusals, and the closed set: **every one of the 21
science tasks has a blind trace.**

## What the trial found

**The goal was wrong and the task was right.** The brief the operator was
handed said *Bray-Curtis 0.35 … 0.29* and *a Newick string of seven taxa is
depth 5 and (A,(B,(C,D))) is four and three*. The page shows 0.31, 0.25, 6 and
4; the task's expectations hold exactly those and have passed since the task
was written; the Python recomputation from the seeded sites gives 0.311 and
0.253, and the page counts depth as levels from the root to the deepest leaf,
both included. The goal sentence carried figures its author computed by a
different convention. ADR-193 kept every goal sentence unrewritten on purpose
— the brief is `says` + `gives` + `holds`, and only the last two are derived
— so a wrong `says` is exactly the thing nothing checked. Corrected in the
task (re-run, ledger refreshed); the copy under `tools/traces/blind10/tasks/`
is the one the operator saw, and F10 holds both. A general check that every
figure a goal names is a figure the task holds was tried and does not hold:
goals also name seeded inputs, counts and prose numbers. Held on that
measurement.

**Filed on the reader and the page:**

- A message the page writes into a box (the run record's *"Copied 21
  line(s)."*) moves the report stamp; the toast does not. True, and now in the
  manual.
- A workbench station with no chart shifts the numbering of the unkeyed
  charts after it, so a `since` diff reports `charts/station-grid #4` as
  gained. Chart re-indexing, not a page change; the reader keys charts by id
  and numbers the rest by host.
- Choosing a theory model resets its parameters; the sites verdict says
  "nearly identical communities" at Bray–Curtis 0.17 sharing 3 of 7 kinds.

## Numbers

| | before | after |
|---|---|---|
| verify_report | 276 | **281** (D: the picked row, four states) |
| verify_tasks | 466 | **479** (F10) |
| mutate_report | 162 | **165**, all killed |
| science tasks with a blind trace | 20 | **21 of 21** |

## Held

- Unkeyed chart numbering by host: a chartless station in between renumbers
  the rest. Trigger: an operator misled by it (the tenth's noticed and was
  not).
- A check that a goal's figures are the task's figures. Trigger: a way to tell
  a figure from a seeded input in prose.
- The picker's `selected` cannot see a pick the filter hides — the DOM does
  not hold it. Trigger: FEK exposing the picker's value to the reader.

## Lessons

- The brief's prose is the one part of a trial nothing derives, and the
  tenth trial is the first to catch it lying. Every trial from here reads the
  goal's figures against the trace's.
- A suite check that reads a possibly-null field with `.get(k, "")` crashes
  the suite under the mutant that nulls it — a crashed suite cannot kill;
  write `(… or "")`.
