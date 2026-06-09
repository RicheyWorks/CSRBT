# CHANGELOG 2026-06-09 — ADR-005 P1+P2: the balanced persistent engine (R3 cashed in)

ADR-004 held R3 — the balanced persistent engine — as the horizon. This slice cashes it in:
`PersistentTreeEngine` rebuilt from the unbalanced Integer-only seed into a generic,
weight-balanced, path-copying engine with explicit O(1) snapshots and wait-free readers,
per **ADR-005** (`ADR-005-balanced-persistent-engine-2026-06-09.md`, now Accepted; decisions:
weight-balanced over persistent-RB/treap, explicit snapshots over auto-history).

## P1 — the engine (`core/PersistentTreeEngine.java`, rewritten)

- **Generic keys:** `PersistentTreeEngine<K>` with a `Comparator` constructor and a
  `withNaturalOrder()` factory, matching the post-ADR-002 conventions (`RedBlackTree`,
  `OrderedSet`). Null keys rejected loudly.
- **Weight balance:** Adams / BB[α] with **Δ=3, Γ=2** in the size-based formulation Haskell's
  `containers` has shipped since its 2010 balance fix — adopted verbatim, not re-derived. The
  iterative path-copying insert/delete now run the `balance` repair (single/double rotation,
  built from fresh nodes) at every rebuilt level, including the two-child delete's successor
  splice. Sorted/replay input loses its O(n²) cliff; height is O(log n) for any input.
- **Explicit snapshots (auto-history removed):** `snapshot()` returns an immutable O(1)
  `Snapshot<K>` handle (contains / inOrder / size / select / rank / countInRange /
  rangeQuery over a tree that can never change). `versionCount()` / `inOrderOfVersion()` are
  gone — memory no longer grows unconditionally with write count; a retained handle is the
  caller's explicit ledger.
- **Order statistics, count-funded:** the `count` field that funds the balance invariant also
  funds `select` / `rank` / `countInRange` / `rangeQuery` on the live engine and on snapshots
  (same static walks). `rangeQuery` is a range-pruned in-order walk, O(log n + |result|).
- **Concurrency by construction:** `volatile` root, monitor-serialized mutators, all-`final`
  node fields (safe publication). Every read is one volatile root read + a walk of immutable
  nodes — wait-free, no stamps/retries/step bounds/epochs, ensemble or not.
- **Diagnostics:** `validateInvariants()` — mechanical BST-order + count + Δ-balance check,
  used throughout the new tests.
- **Registry:** `PERSISTENT_TREE` builds `withNaturalOrder()`; capability note updated.

## P2 — the concurrency proof (`PersistentEngineConcurrencyTest`, new)

- **k-readers × 1-writer stress:** 4 readers hammer snapshots and live reads under write churn,
  asserting every observation is fully consistent (strictly ascending `inOrder`, size parity,
  `select`/`rank`/`countInRange` mutually consistent) — failures collected cross-thread; fixed
  seeds/threads/durations per ADR-005 §9. Engine validates clean after churn.
- **Benchmark row** beside E5/R2's: `contains()` throughput under identical 1-writer churn —
  sandbox reference: **persistent ≈ 3.08M reads/250ms** vs R1-optimistic ≈ 0.38M vs
  READ_REPLICA ≈ 1.79M. Wait-free-by-construction beats both guarded paths; the cost moved to
  the writer (O(log n) allocation per mutation).

## Suite repair — `EnsembleVerifiedTest` (pre-existing red, unrelated to this slice)

Both quarantine tests were failing **at HEAD** (verified against a clean checkout): ADR-004 R1
made `OrderedSet` reads strategy-independent, so the test's fault — a strategy whose `search`
lies — became unobservable by construction; all members answered correctly from their (correct)
trees and nobody ever dissented. That fault class is now structurally impossible, which is R1
working as designed; the fault VERIFIED voting exists to catch post-R1 is **divergent content**.
The injection is now `SilentDropStrategy` (silently never inserts one poison key → a valid,
self-consistent tree missing data its siblings hold — invisible to E3's structural health check,
caught by the E4 vote). Test semantics, names, and assertions are otherwise unchanged.
Note: this means the housekeeping commit (`cf6588a`) shipped with a red suite — the "formality"
run was evidently skipped. Worth a host-side green run before anything else lands.

## Test migrations

- `PersistentTreeEngineTest` — rewritten: oracle parity with periodic invariant checks; snapshot
  persistence (old handles survive mutations and `clear()`); adversarial input (ascending,
  descending, organ-pipe insert + alternating delete) stays balanced; order-statistics oracle
  including inverted ranges and snapshot frozenness; generic `String` keys with a composed
  comparator; null rejection.
- `TreeContextTester.Persistent` — `versionsArePersistent` → `snapshotsArePersistent` (same
  property, snapshot handles instead of version indexes).

## Verification

Full suite: **431 tests, 0 failures** (sandbox JDK 17 via the JUnit console jar, exactly the
`build.xml` classpath). Host `ant clean test` should be run before push per `CLAUDE.md`.

## Deliberately open

ADR-005 P3 (ensemble membership for ENGINE-tier members + snapshot persistence via
`KeySerializer`); ADR-003 Option C (periodic-rebuild shadows); memory ceilings / cap-K metrics;
VERIFIED read-amplification tuning; the DESIGN doc's Phase-4 disk engine.
