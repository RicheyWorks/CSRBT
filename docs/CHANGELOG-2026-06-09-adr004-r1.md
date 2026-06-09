# CHANGELOG 2026-06-09 -- ADR-004 R1: torn-read-free concurrent reads

First phase of ADR-004 (`ADR-004-lock-free-reads-2026-06-09.md`): every public read on
`OrderedSet<K>` is now safe under concurrency -- no torn structure, no transient-cycle hangs, no
mid-rotation NPEs -- on every strategy, including Splay. This is the *safety* deliverable (R1);
the *lock-free* deliverable (R2, left-right epoch reads over ensemble mirrors) is still open.

## What changed

- **R1a -- public reads never splay.** `OrderedSet.contains` no longer routes through
  `strategy.search` (which, for Splay, moves the accessed node to the root on every hit and
  miss -- a structural mutation on the "read" path). The facade read path now uses a
  strategy-independent BST descend; `OrderStatisticsOps` was already pure. Splay keeps its
  move-to-root adaptivity on the write path (the add/remove prechecks still go through the
  engine's `contains` under the writer monitor), so its amortized story is now write-driven.
  The engine-level `RedBlackTree.contains` is untouched -- `StrategyInvariantTest`'s
  splay-to-root assertions still exercise the real thing.
- **R1b -- `StampedLock` read guard.** Mutators acquire the write stamp inside the existing
  monitor (whole-body for add/remove/clear/eviction/augmentor/resync; publish-only for
  `setStrategy`/`selfRepair`, whose candidates are built aside, so readers keep reading the
  untouched incumbent during the O(n) rebuild). Readers:
  - `contains` / `inOrder` -- optimistic (`tryOptimisticRead` -> walk -> `validate`), with the
    walk **step-bounded** (~2·log2 n + 32 steps; ~4n + 64 links for `inOrder`) because a reader
    overlapping a rotation can transiently chase a cycle. Any suspicion (bound trip, NPE, torn
    comparator data) diverts to the shared-lock retry, where the tree is consistent by
    construction. A legitimately deep tree (degenerate splay chain) trips the bound too and
    simply always takes the locked path -- correct, just not optimistic.
  - order statistics (`select`/`rank`/`successor`/.../`rangeQuery`) -- shared read lock; the
    walks are pure but not step-bounded, so they only ever run on a consistent tree.
  - `size`/`isEmpty` -- unchanged plain reads of an `int` (atomic; can be momentarily stale,
    never torn).
- **Rollback constant.** `OrderedSet.OPTIMISTIC_READS = false` restores the pre-R1 unguarded
  read walk verbatim (including engine-level `contains`), per the ADR's verification plan.
- **Deliberately out of scope:** `getEngine()` still exposes live structure and bypasses the
  guard (diagnostics seam, unchanged by contract); reads are torn-read-free but not lock-free --
  that is R2.

## Reentrancy & deadlock notes (audited)

`StampedLock` is not reentrant, so no mutator may call a public reader while holding the write
stamp. Audit: all mutator internals (`evictOldest`, `resyncLiveOrder`, `reapplyAugmentor`,
`captureKeyTags`, `restoreTags`, health validation) use engine-level calls, never the public
read API. Lock order is monitor -> write stamp for writers; readers touch only the stamp.
The ensemble's paths hold its own write lock first and member locks second, consistently.

## Tests

- `ConcurrentReadStressTest`:
  - *redBlack / avl / splay / hybrid* -- 1 writer churning adds/removes vs 3 readers hammering
    `contains`, validated `inOrder` snapshots (every snapshot must be strictly ascending), and
    racing order statistics (out-of-range `select` / absent-key `rank` are tolerated as
    consistent outcomes). Fails on any stray exception or a wedged walk; asserts quiescent
    agreement of size, traversal, and order afterward. Time-boxed and seeded for CI stability.
  - *splayReadsDoNotSplay* -- facade `contains` and `rank` leave the splay root untouched; a
    duplicate `add`'s precheck still splays (adaptivity demonstrably lives on the write path).

## Still open in ADR-004

- **R2** -- `EnsembleMode.READ_REPLICA`: wait-free left-right epoch readers over ensemble
  mirrors, epoch-aware promotion/failover/quarantine, and the read-throughput benchmark row.
- **R3** -- (held) balanced persistent engine.
