# The tenth blind trial — provenance (ADR-232)

One operator, **the last science page no blind operator had ever driven**:
the ecology lab, whose task is the kit's longest (337 steps, 61 values, nine
stations) — through the door with ADR-231 and ADR-232 in it, and with the
manual (`docs/OPERATOR.md`) rewritten after the ninth trial: guard the act that
DEPENDS on the figures, not a run of presses. This is the first trial whose
door **records the guard a call carried** (`guard` on the trace row,
ADR-231), so guards are counted from the trace rather than from the
operator's own report.

Run **2026-09-20**. The trace is gzipped; `gunzip -c <file>` is the trace
exactly as the server wrote it. `tasks/` holds the task file as of the run
(BEFORE the goal-prose correction below); `OPERATOR.md` is the manual the
operator was handed.

## The conditions

One general-purpose subagent, fresh context, working in `/tmp/blind10/CSRBT`
— a copy of the repository with `tools/tasks/`, `tools/traces/`,
`tools/delivery/`, `tools/push/`, every ledger, the board and its renderer,
every `mutate_*.py`, the whole of `tools/verify/` except `_kit.py`, and every
`*.md` **removed from the filesystem** (ADR-136). The goal names no
irreversible act, so it ran with the supervised three rungs. One attempt, with
a stated budget of about 150 console calls.

## What it measured

| task | reached | of | claims | of | calls | attempts |
|---|---|---|---|---|---|---|
| page-ecology-lab-science | **39** | 55 | **234** | 263 | 132 | 1 |

Every one of the 61 values was entered; the misses are outcomes whose claims
name chart geometry the operator did not read back (rank bars, curve extents)
and a `read-control` on the eco field.

## What it measured about the guard, from the trace

| guards sent | report stamps (`r…`) | snapshot stamps (`s…`) | refused `stale` |
|---|---|---|---|
| **19** | 18 | 1 | **0** |

Eighteen acts bound to the report as last read, one (the drill's start
button) bound to the snapshot, and not one refusal: every guard was the stamp
from the read immediately before it, and the operator wrote that the runs of
presses were left unguarded, as the manual now says. Against the ninth trial's
farm scout — 127 refusals from one stamp over 36 presses — this is the manual
correction measured. The screen chrome and pane switches, noise since ADR-231,
did not refuse a guard once.

## What it found — in the brief

The goal sentence the operator was handed named four figures the page does
not show and the task never held: *Bray-Curtis 0.35 … 0.29* (the page and
the task say **0.31** and **0.25**; recomputed from the seeded sites in
Python, 0.311 and 0.253) and *a Newick string of seven taxa is depth 5 and
(A,(B,(C,D))) is four and three* (the page counts the levels from the root to
the deepest leaf, both included: **6** and **4**, and the task holds those).
ADR-193 kept every goal sentence unrewritten on purpose; this one carried
figures its author computed by a different convention than the page, and the
task's expectations — the oracle — were right all along. The goal is corrected
in the task; the copy under `tasks/` is the one the operator saw.

## What it found — in the door and the page (filed)

- The page's copy confirmation (*"Copied 21 line(s)."*) is written into the
  `station-record` box, not the toast, so it moves the report stamp; the
  manual's "a toast does not move the report" is true of the toast and not
  of a box the page chooses to write a message into.
- A workbench box that has no chart (a refused quadrat list, a bad Newick, K =
  0) shifts the numbering of the unkeyed charts after it, and a `since` diff
  reports `charts/station-grid #4` as gained — chart re-indexing, not a page
  change. The reader keys charts by id and numbers the rest by host; a
  chartless station in between moves the numbers.
- Choosing a theory model resets its parameters; the sites verdict said
  "nearly identical communities" at Bray–Curtis 0.17 sharing 3 of 7 kinds.
- Report stamps are content hashes: reverting a value returns the earlier
  stamp, and `since` that stamp answers "nothing changed" although acts ran
  in between. By design (ADR-191: the stamp is a version of the observation),
  and worth a sentence in the manual.

## Why these numbers are floors

No blind operator had touched this page; `verify_tasks` section F10 holds this
run's reached/claims as the floor and holds the guard count and the zero
refusals from the trace. Graded as a ROUTE it is FAIL, as always. **Every one
of the 21 science tasks now has a blind trace.**
