# ADR-005: Balanced persistent engine — cashing in ADR-004's R3 horizon

**Status:** Accepted (2026-06-09 — P1 + P2 landed, see
CHANGELOG-2026-06-09-adr005-persistent-engine.md; P3 deliberately held)
**Date:** 2026-06-09
**Deciders:** Richmond
**Builds on:** ADR-004 (R3 held as horizon: "balanced persistent engine ADR when demanded"),
the `PersistentTreeEngine` seed (Integer-only, unbalanced, auto-history), ADR-002's generic-key
migration (`Comparator` seam, `OrderedSet<K>` facade), and the `TreeEngine<K>` contract.
**Goal:** wait-free, snapshot-consistent reads *without* an ensemble — a single balanced
persistent structure whose readers can never observe a torn state, plus O(1) immutable
snapshots — while keeping the engine a well-behaved `TreeEngine` citizen.

---

## 1. Context

ADR-004 delivered torn-read-free reads everywhere (R1) and wait-free reads where an ensemble's
2× memory is already being paid (R2), and deliberately held R3 — the persistent engine — until
demanded. It is now demanded, and the demand clarifies the shape:

- **The seed is real but not usable.** `PersistentTreeEngine` already implements iterative
  path-copying insert/delete with structural sharing and subtree counts. But it is
  `TreeEngine<Integer>` (the rest of the codebase generified a week ago), **unbalanced**
  (sorted input → O(n) operations, the javadoc admits it), and it retains **every version
  forever** in an `ArrayList` — memory grows with write count, unconditionally.
- **R1's reads are safe, not wait-free; R2's are wait-free, not free-standing.** A bare set
  under R1 still pays optimistic-retry/locked-fallback costs, and order statistics always take
  the shared lock. A persistent root makes every read — including `select`/`rank`/`inOrder` —
  a `volatile` read plus a walk of nodes that can never change. No stamps, no step bounds, no
  epochs, no fallback paths.
- **Snapshots are the new capability, not just a faster read.** ADR-003 E6's snapshot
  persistence serializes the primary's in-order keys under the writer lock; `TreeHistory` undo
  is a copy. A persistent engine makes "the set as of now" an O(1) pointer grab — iteration,
  diffing, and audit reads stop contending with writers entirely.

Non-goals, restated from ADR-004 §2D so they stay decided: the in-place `TreeStrategy` family
(the project's core asset) does **not** carry over — RB/AVL/Splay/Hybrid rotations mutate
shared nodes and have no meaning over immutable ones. This engine joins the registry's ENGINE
tier beside that family; it does not replace it, back `OrderedSet<K>` (hard-wired to
`RedBlackTree<K>` by design), or grow a persistent splay (a contradiction — splay reads are
writes, ADR-004 §3).

---

## 2. Options considered

### Option A: Weight-balanced tree (Adams / BB[α], the Haskell `Data.Set` lineage)

Balance invariant on subtree *sizes* (the formulation Haskell's `containers` has shipped since
its 2010 balance bug was fixed): past trivial sizes, neither child's subtree size may exceed
`Δ`× the other's. Restore by single/double rotation on the copied path, choosing by the inner
child's size against ratio `Γ`. Use the proven parameter pair **Δ=3, Γ=2** (Hirai & Yamamoto's
verified region) in exactly the battle-tested formulation, not a re-derivation.

| Dimension | Assessment |
|---|---|
| Complexity | Medium — one invariant, two rotations, all on the already-copied path |
| Balance bound | height ≤ ~2·log₂(n); O(log n) worst-case ops |
| Extra per-node state | **none** — the seed's `count` field *is* the balance information |
| Order statistics | free — `select`/`rank`/`countInRange` read the same `count` field |
| Persistent delete | clean — same rebalance as insert, applied up the copied path |

**Pros:** the size field does triple duty (size, balance, order stats); deletion is not a
special case; deterministic; the invariant is mechanically checkable in tests. **Cons:** less
famous than red-black; parameter choice matters (hence pinning the verified Δ=3, Γ=2).

### Option B: Persistent red-black (Okasaki insert + Germane–Might delete)

| Dimension | Assessment |
|---|---|
| Complexity | Insert low (Okasaki's four-case balance); **delete high** (double-black bubbling or the Kahrs encoding) |
| Extra per-node state | a color bit, *plus* `count` anyway for order statistics |
| Order statistics | needs the same `count` field Option A gets balance from |

**Pros:** matches the project's red-black heritage; Okasaki insert is beautiful. **Cons:**
persistent deletion is notoriously fiddly and adds no capability over A; we would carry color
*and* count per node where A carries count alone. The heritage argument is hollow — the
in-place RB strategy stays regardless. Rejected.

### Option C: Treap (randomized heap priorities, persistent join/split)

**Pros:** simple join/split vocabulary. **Cons:** expected — not worst-case — O(log n); a
priority field per node; seeded-determinism care in every test; the suite's invariant checks
become statistical. Rejected — this codebase asserts structural invariants mechanically
(`StrategyHealthCheck`, `StrategyInvariantTest`), and "balanced in expectation" is a worse fit
than "balanced by checkable invariant".

### Option D: Keep the seed unbalanced, document harder

Rejected outright: ADR-004 already documented the caveat; R3 exists to retire it. Sorted input
is not adversarial exotica — it is replay-on-load (E6) and morph rebuilds, both of which feed
ascending keys.

---

## 3. The version-model decision

The seed auto-appends every structural change to a version list — unbounded memory, no opt-out,
and the *engine* decides what is worth remembering. Decision: **explicit snapshots**.

- `snapshot()` returns an immutable, O(1) `Snapshot<K>` handle (root + size capture) offering
  `contains` / `inOrder` / `size` / `select` / `rank` / `countInRange` / `rangeQuery` over a
  tree that can never change. Nothing is retained unless a caller holds a handle; GC reclaims
  unshared structure when handles drop.
- `versionCount()` / `inOrderOfVersion(int)` are **removed**, not deprecated — the seed is
  pre-release internal machinery with two test classes as its only callers; both migrate to
  snapshot handles and assert the same persistence property (an old handle is unchanged by
  later mutations).
- Auto-history as a bounded ring stays available as a *caller* pattern (keep your last k
  handles); the engine does not grow a policy for it.

---

## 4. Concurrency contract

Single writer / wait-free readers, by construction rather than by guard:

- The root is `volatile`. Mutators (`add`/`remove`/`clear`) synchronize on an internal monitor
  (matching `OrderedSet`'s one-writer discipline), build the new path off to the side, and
  publish with one `volatile` store. A half-built path is unreachable until published.
- Every read — membership, traversal, order statistics, snapshots — does one `volatile` read
  of the root and walks immutable nodes. **Wait-free, no retry, no lock, no step bound**, even
  for `inOrder` on a huge set, even for a bare engine with no ensemble. This is exactly the
  guarantee R1 could not give (its optimistic walks validate-or-retry) and R2 gives only over
  mirrors (epoch counters, drain waits).
- The JMM does the rest: all fields of the immutable nodes are `final`, so publication via the
  volatile root is safe publication; readers can never see a partially constructed node.

Cost honesty: every write allocates O(log n) fresh nodes and retires O(log n) old ones — GC
pressure scales with write rate. That is the structural price of wait-free readers; the
benchmark row (P2) makes it visible rather than asserted away.

---

## 5. Decision

**Adopt Option A** (weight-balanced, Δ=3, Γ=2) **with explicit snapshots**, evolving
`PersistentTreeEngine` in place rather than minting a second persistent class:

**Phase P1 — the engine.** Generify to `PersistentTreeEngine<K>` (`Comparator` constructor +
`withNaturalOrder()` factory, matching `OrderedSet`/`RedBlackTree` post-ADR-002 conventions).
Add weight-balanced rebalancing to the iterative path-copying insert and delete. Replace the
version list with `snapshot()`/`Snapshot<K>`. Add count-field order statistics
(`select`/`rank`/`countInRange`/`rangeQuery`) on both the live engine and snapshots. Migrate
the registry (`PERSISTENT_TREE` note + factory) and the two test classes; add balance-invariant
and sorted-input (no-degeneracy) tests.

**Phase P2 — the concurrency proof.** `volatile` root + synchronized mutators (P1 ships the
fields; P2 ships the *tests*): a k-readers × 1-writer stress asserting every read sees a fully
consistent tree (sorted `inOrder`, `size()` consistent with contents, `select`/`rank`
mutually consistent), and a benchmark row beside E5's: persistent snapshot reads vs R1
optimistic vs R2 `READ_REPLICA`, so the GC-for-wait-freedom trade is a printed number.

**Phase P3 — horizon (not scheduled).** Ensemble membership for the persistent engine (an
ENGINE-tier member needs the `EnsembleMember` seam to accept non-`RedBlackTree` engines) and
key-serializer persistence of snapshots. Revisit when a workload demands a persistent ensemble
member, not before.

---

## 6. Consequences

**Easier:** bare-set callers get wait-free snapshot-consistent reads with zero coordination;
"the set as of now" becomes an O(1) handle (audit reads, diffing, undo all stop copying);
sorted/replay input loses its O(n²) cliff; the genome's `PERSISTENT_TREE` recommendation stops
pointing at a structure with a documented degeneracy.

**Harder:** writes allocate O(log n) nodes (GC pressure is now a tuning surface); the engine's
API diverges further from the strategy family (order statistics live on the engine, not an
`OrderStatisticsOps` wrapper — immutable nodes cannot host the augmentor machinery);
removing `versionCount()`/`inOrderOfVersion` is a (pre-release) breaking change.

**Revisit:** Δ/Γ if profiling shows rotation churn on realistic workloads (only within the
verified parameter region); bulk operations (persistent union/split via join) if set-algebra
demand appears; P3 when a persistent ensemble member is demanded.

---

## 7. Risks & open questions

| Risk | Mitigation |
|---|---|
| Rebalance bug in a rarely-hit rotation case | mechanical invariant check (every node: weights within Δ, count = 1+l+r, BST order) run inside the oracle test every few hundred ops, plus a dedicated sorted/reverse/organ-pipe input test |
| Snapshot handles retained forever → memory | documented as the caller's ledger (a handle pins O(distinct structure) memory); no engine-side registry of handles, so dropping the handle is dropping the memory |
| `final`-field publication subtlety (a non-final field sneaks into Node) | Node fields are all `final` by construction; test can't check the JMM, so this is a review-time invariant — flagged here for every future edit |
| Generic keys + nulls | nulls rejected at the facade boundary like `OrderedSet` (comparator NPE is not a contract) |
| Registry factory signature drift | `PERSISTENT_TREE` builds `PersistentTreeEngine.<Integer>withNaturalOrder()`; the `Supplier<TreeEngine<Integer>>` seam is unchanged |

---

## 8. Action items

1. [x] **P1a** — weight-balanced generic engine: `PersistentTreeEngine<K>`, Δ=3/Γ=2 rebalance
   on iterative path-copying insert/delete, `volatile` root + monitor-serialized mutators,
   null rejection. _(Done 2026-06-09 — the `containers` size-based formulation verbatim;
   see CHANGELOG-2026-06-09-adr005-persistent-engine.md.)_
2. [x] **P1b** — explicit snapshots: `snapshot()` → `Snapshot<K>` (contains / inOrder / size /
   select / rank / countInRange / rangeQuery); version-list API removed. _(Done 2026-06-09.)_
3. [x] **P1c** — order statistics on the live engine (same code path as snapshots); registry
   note + factory migration; `PersistentTreeEngineTest` + `TreeContextTester.Persistent`
   migrated and extended (balance invariant, sorted-input no-degeneracy, snapshot persistence).
   _(Done 2026-06-09 — plus `validateInvariants()` as the mechanical checker.)_
4. [x] **P2** — k-readers × 1-writer wait-free stress test; benchmark row: persistent snapshot
   reads vs R1 optimistic vs R2 READ_REPLICA. _(Done 2026-06-09 —
   `PersistentEngineConcurrencyTest`; sandbox reference: ~3.1M persistent reads / 250ms vs
   ~0.38M R1 vs ~1.8M READ_REPLICA under identical churn.)_
5. [ ] **P3** — (held) ensemble membership + snapshot persistence via `KeySerializer`.

---

## 9. Verification & rollback

P1 is a rewrite of a leaf engine with exactly three dependents (registry + two test classes) —
rollback is `git revert` of the slice; no flag is warranted for pre-release internal machinery
with no external callers. P2 is additive tests + a benchmark row. Every phase ships green
through host `ant clean test` per `CLAUDE.md`, with the new concurrent test bounded (fixed
thread counts, deterministic seeds, finite timeouts) like its R1/R2 siblings.
