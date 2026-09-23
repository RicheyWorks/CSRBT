# ADR-241 — The count says which tree it counted

**Date:** 2026-09-22 · **Status:** accepted · **Chain:** ADR-240 → this ·
**Protocol:** 1.11 (unchanged) · **Ported from:** the FlowersForever harness
(`scripts/verify_harness.py`, `config/harness-test-floors.json`)

## Why

A review of the FlowersForever harness, which had itself ported three CSRBT
ideas the day before (its `HARNESS_ECOSYSTEM.md`: replay before freshness,
per-class floors, a derived verdict), found two things it does that this kit
did not.

**Its evidence is bound to the tree it was taken on.** `verify_harness.py`
hashes every build input, writes the digest with the passing result, and
`--check` refuses evidence taken on any other tree. A source edit made *during*
verification invalidates it.

This kit's `counts.json` bound each count to the SHA of its *suite source*
(ADR-052). That says the count is about this suite. It says nothing about what
the suite was pointed at. Edit a page, a task, a tool, and every count that
measured them still reads green, still renders green on the board, and the
board is published with a number about a tree that no longer exists. The
ADR-238 close met this: `verify_board` read 218/219 until the board was
re-rendered, and the fix was to hand-edit a `counts.json` entry. A count that
can be hand-edited into green is a count nothing binds.

**Every test class has a committed floor.** A growing class cannot hide a
deleted one. Here, a suite that lost a section printed a smaller `n/n`, stayed
green, and the board's total absorbed the loss without a word.

## Decision

- **`tools/evidence.py`.** The *subject* is every file the suites and audits
  read: pages and prose under `docs/`, tools, tasks, suites, CI, the engines'
  sources. The *evidence* is what a run writes: ledgers, `counts.json`,
  `floors.json`, the board, `published.json`, routes, delivery manifests, push
  scripts. `digest()` is one SHA-256 over the subject with a sha12 per file, so
  the difference between two trees can be named file by file. 1,094 files, 0.7
  s.
- **`run_all` takes the tree before the jobs** and writes it with every count
  (`tree` on each suite entry, the file map on the ledger). It hands the digest
  to every job as `CSRBT_RUN_TREE`. It takes the tree again after: a tree that
  moved during the run fails the run and names the files.
- **`tools/verify/floors.json`.** A green suite that counted fewer checks than
  its floor is red for that run, says so, and fails the run. A suite never seen
  is floored at what it counted. Floors rise only by `--raise-floors`, and
  never fall.
- **The board gains two gates:** *the counts are about this tree* and *no
  suite counts fewer than its floor*. The header says which tree the counts
  were measured on and how many files it has; when the tree has changed since,
  it names the changed, added and removed files, any count from another tree,
  and any count carrying none.
- **`run_all --only NAME`** runs one job and records it the way the run
  records it. The post-sweep bootstrap of `verify_publish_reach` is now a
  measurement, not an edit.

## Held by

- **`verify_evidence`, 28 checks**: the subject and the evidence on a scratch
  kit (a ledger, the counts and the board change and the digest does not; a
  changed byte, an added file and a removed file each move it and are named);
  `status()` in every state; the floors (below goes red, never seen is
  floored, raise never lowers, a non-integer is not a floor); `run_all`'s
  wiring; and the real kit, which inside a run holds the tree to the one
  `run_all` began on, and outside a run holds `counts.json` to the tree as it
  stands.
- **`verify_board`** gains section 10: the tree gate met and named, not met
  with the files named, a tree moved during the run, an unstamped count, a
  suite below its floor on the tile.
- **`tools/mutate_evidence.py`**, 13 mutants across `evidence.py`, `run_all`
  and the board. The runner copies the whole subject and restamps the copy's
  counts as if a run had taken them on the mutated tree, because the mutation
  itself moves the digest.

## What the first run found

The first `run_all` under the new rules was red twice, and both were the
slice's own doing. `verify_anchors` found two of `mutate_board`'s anchors
stale: the board patch had reworded the two lines they landed on, which is
ADR-235's finding arriving on schedule. And the floor rule fired on two suites
that were already red (`80/81 counted but the floor is 81`), which is the
floor saying the same thing twice; it now applies to suites that *pass* with
fewer checks than they had, which is the defect it exists to catch. Both
fixes were edits after the run, so the tree gate refused the run's counts and
the run was made again.

## Held

- **The FlowersForever action journal** (`PENDING` / `COMPLETED` /
  `action-status`) and `expected-context` tokens have no counterpart need
  here: the kit's pages act synchronously, and ADR-191/229's stamps bind
  actions to snapshots.
- **An MCP doctor** (`--mcp-doctor`: `ready`, the exact missing settings,
  exit 2) would help a reader connecting an AI to the kit. Trigger: the first
  such reader.
- **Paged reads** with `offset`/`limit`/`hasMore` on long boxes and tables.
  The reader truncates with a flag today. Trigger: a task that needs the part
  beyond the cap.
