# ADR-234 — a goal's figures are bound to the claims that hold them

**Date:** 2026-09-21 · **Status:** accepted · **Chain:** ADR-233 → this ·
**Protocol:** 1.11 (unchanged)

## Why

ADR-193 split a goal into a brief: `says` (the prose, kept as written),
`gives` and `holds` (both derived from the steps). Only the derived parts can
be trusted to stay true. The prose is the one part of a brief nothing checks.
ADR-232 held a general check back, one that would compare every figure in the
prose with the task, because prose also names seeded inputs, counts and years.
Its trigger was *"a way to tell a figure from a seeded input in prose"*.

Since then, three blind trials have found prose stating figures the page never
shows, while the task's expectations held the right ones:

| task | the goal said | the page shows, and the task holds |
|---|---|---|
| ecology lab (10th trial) | Bray-Curtis 0.35 … 0.29; depths 5 and 4 | 0.31, 0.25; depths 6 and 4 (fixed in ADR-232) |
| tree visualizer (6th) | *"draws 60 first and 19 eleventh, and the tree is 24 nodes after 15 draws"* | after Clear, 11 draws, 11 nodes, and the last message *inserted 24* |
| tree proofs (7th) | *"accessing key 1 costs 6 rotations+1 = 6"*; *"key 63 costs 7 / 13.0"* | 5 rotations + 1 = 6; key 63 costs 7 only after key 1 has been splayed to the root (6 on a fresh tree) |

The tree visualizer's goal took `inserted 24`, a message naming the last key
drawn, and read it as a node count. The blind operator there did exactly what
the prose said, 15 presses on the boot tree, got 28 nodes and missed the
outcome. The prose had set up a trial the operator could not pass.

The same trial also filed a page defect. The tree proofs' worst-case note said
the 63 keys were *"inserted in ascending order"*, but the loop inserts them in
descending order, and the page's own comment says the ascending build would put
key 1 at the root, which defeats the demonstration. The task held only
`contains "Built as a path"`, so nothing could see it.

## Decision

**The author says which figures are claims.** A task may carry
`figures: [{says, step, claim}]`. `says` is a phrase of the goal, and `claim`
is an expectation of a required step. The value that expectation holds (bare,
`==` or `contains`) must appear in the phrase as a whole token: `11` does not
match inside `110`, `0.3` does not match inside `0.31`, and `4` does not match
the digit in `-4`. `load_task` refuses a task that breaks any part of this. If
the expectation is edited and the prose is not, or the other way round, the
task does not load. A figure cannot rest on a probe, because an operator may
skip one (ADR-136). A bound, a membership test or an approximation states no
single figure a sentence could repeat, so none of them can be bound.
`figures_of(task)` lists them, and the brief counts them.

This meets the trigger ADR-232 set: the prose cannot mark which of its figures
are claims, and now the author marks them.

**Bound now: 18 figures on the three tasks whose prose was caught.** Ten on
the tree proofs, four on the tree visualizer and four on the ecology lab. Each
goal was corrected first:

- The tree visualizer's goal now says that after Clear, one press of + Random
  and one of + 10 random draw eleven keys with none repeated. The first press
  reads *inserted 60*, the last *inserted 24*, and the tree is 11 nodes after
  11 draws.
- The tree proofs' goal now says key 1 costs *5 rotations + 1 = 6*, and that
  key 63 costs 7 / 13.0 *"one level deeper now that key 1 is the root (on the
  fresh balanced tree it would cost 6, like key 1)"*. The amortized figure is
  now `-77.4`, with the same ASCII hyphen as the claim.

**The tree proofs' note is read off the tree.** The order comes from the
root: in a tree built without rebalancing, the first key inserted stays the
root. The depth of key 1 is found by walking down to it. The note now says
*"63 keys inserted in descending order (63 first) … key 1 sits 62 edges
down"*, and the task holds that exact sentence rather than `contains "Built as
a path"`.

## Held by

- `verify_brief` 31 → **46**. It checks every bound figure against the task
  files using its own token reading, not the subject's. The wrong sentences
  must be gone from the goals, and the brief must count the figures. Nine
  ways a figure can drift must each be refused with the right reason: the
  prose moved, the claim moved, a phrase the goal lacks, a probe, a missing
  claim, a bound, a missing step, an empty list, and `0.3` inside `0.31`.
  The task as committed must still load. A crash inside `load_task` counts as
  a failure, not as a refusal.
- `verify_proofs` 143 → **149**. It adds an independent Python port of the
  page's splay core, with its own BST and its own rotations. The worst-case
  note must match the port's root and depth. A counterfactual rebuilds the
  path ascending through the same button, and the note must then say
  ascending, 1 first, 0 edges. Accessing (63) and (1, 1, 63) on the page must
  give the same results as the port: 6, then 7.
- `verify_tv` 115 → **118**: mulberry32 seeded 42 and ported in Python, with
  the page's redraw-on-repeat rule and both buttons. The draws must be the
  port's, from *inserted 60* to *inserted 24*, eleven draws for eleven nodes.
- `mutate_brief` 14 → **24**, all killed. The ten new mutants loosen each
  refusal, drop the token boundary, misreport `figures_of` and stop the count.
- **New runner `tools/mutate_proofs.py`**, 8/8 killed. It covers the order
  typed as ascending, typed as descending, the depth typed as n-1, the first
  key typed as n, a depth walk that goes the wrong way, the loop turned
  round, the missing +1, and a zig-zig in the wrong order.

## What the slice found in its own instruments

**Two of `mutate_brief`'s anchors no longer landed.** One had been stale
since ADR-196, which added a comment inside `holds_of` (the arguments guard)
and split the two-line anchor of *"what a brief holds is a sample of what it
holds"*. `mutate_brief` had not been run since. The
other broke while this slice was being written, because adding `figures` to
the counts dict changed the line the *"claims as readings"* mutant anchors on.
The ledger still showed 14/14 killed from its last run, so the board was
reporting kills against code that no longer existed. Both anchors were fixed,
and the full run is 24/24. The same scan across all 32 runners found no other
stale anchor among 1,173. A static check that every recorded runner's anchors
still land is **filed as the next slice**. Until then, a stale anchor shows
up only when its runner is run again.

**The carried-figures audit is read with the clock running.** The full
`run_all` for this slice went red on `audit_declared`, because the relevé's
declaration for *taxa in pack* read IDLE: the audit had found 49 carried.
`audit_carried` matches a figure by any number in any export, and the
relevé's exports carry the time they were made. When the minute or second
happens to be 49, the pack's size of 49 counts as carried. Run alone, the page
reads it as not carried, and a second full run reads it as not carried again.
Nothing in this slice touched the relevé. The instability comes from where
the audit reads, not from the page. **Filed**, together with the obvious fix:
the audit should freeze the clock (`set-clock`, which the plugin already has)
so that the same page gives the same reading every time.

## Numbers

| | before | after |
|---|---|---|
| verify_brief | 31 | **46** |
| verify_proofs | 143 | **149** |
| verify_tv | 115 | **118** |
| mutate_brief | 14 | **24**, all killed |
| mutate_proofs | — | **8**, all killed |
| goal figures bound | 0 | **18** on 3 tasks |

## Held

- **Binding every science goal's figures.** 18 on 3 tasks is the start, not
  the floor. Trigger: the next trial that catches a goal's prose. Price:
  roughly one slice per four tasks, since each goal has to be read against
  its task.
- **Stale anchors in any runner, checked statically.** The next slice.
- **`audit_carried` under a frozen clock.** Trigger: the next IDLE reading
  on a declaration nobody changed. This slice's was one.
- **The other pages' filed defects** (memory list): ordination, selection
  log, field notebook, ethogram, relevé, pheno tracker, stand sheet, ecology
  lab. One page per slice, oracle first.

## Lessons

- A goal sentence that describes a message (*inserted 24*) is one misreading
  away from stating a figure (*24 nodes*). Bind the claim, and the misreading
  cannot load.
- `contains "Built as a path"` held the part of the sentence that could not
  be wrong and left out the part that was. A claim should hold the part of a
  sentence that states a figure.
- A mutant ledger records kills against the code as it was at the last run,
  and says nothing about the code as it is now.
