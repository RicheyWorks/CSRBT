# ADR-008: The Phase-4 large-n engine — a page-structured B+tree, structure before disk

**Status:** Accepted (2026-06-09 — D1 landed, see CHANGELOG-2026-06-09-adr008-bplus-engine.md;
D2/D3 held)
**Date:** 2026-06-09
**Deciders:** Richmond
**Builds on:** `DESIGN-adaptive-engine.md` Phase 4 ("add a large-n engine — B-tree /
cache-oblivious — once the loop is proven on the existing three"; the loop is proven:
ADR-001–007 all Accepted), ADR-005 P3's `RankedSet` seam (engines join ensembles without the
strategy machinery), ADR-002's `KeySerializer` (the disk format's key tokens, when D2 comes).
**Goal:** the engine family's answer for n too large for pointer-chasing BSTs — cache-line
friendly today, disk-page ready tomorrow — without touching the genome/evolution layer until
the engine has earned its registry slot.

---

## 1. Context

Every current engine is a pointer-per-key structure: ~96 bytes and a cache miss per node on
the RB family, ~56 on the persistent engine. At large n the constant factors invert the
complexity story — a million-key RB tree walks ~20 cache misses per lookup. The DESIGN doc
deferred the fix ("larger-than-memory scale — a future disk/B-tree engine") until the
adaptive loop was proven. It now is, and two seams built since make the engine cheap to land:
`RankedSet` (ADR-005 P3) gives it full ensemble citizenship — fan-out, voting, healing,
explicit promotion — with no registry or strategy involvement, and `KeySerializer` (ADR-002)
already defines how keys become bytes when pages move to disk.

The honest scoping question is what "disk engine" means as a first slice. A real paged store
needs a page cache, eviction, a free list, crash semantics — none of which is worth building
before the *page-structured data structure itself* is proven against this codebase's
contracts (order statistics, `OrderedSet`-parity voting semantics, the mechanical-invariant
test discipline). Structure first, disk second.

---

## 2. Options considered

### Option A: B+tree (fanout-paged; keys in leaves; leaf chain)

| Dimension | Assessment |
|---|---|
| Complexity | Medium — split/borrow/merge are classic and mechanically checkable |
| Reads | O(log_F n) node visits, each a sorted array scan — cache-line friendly |
| Order statistics | per-child subtree counts in internal nodes fund select/rank/countInRange — same trick as ADR-005 |
| Range scans | leaf chain: O(log_F n + result) with sequential locality |
| Disk readiness | the canonical on-disk layout; leaf/internal nodes *are* pages |

**Pros:** every key lives in a leaf (internal nodes are pure routing — exactly what pages
want); range queries walk the chain; the standard structure for D2's file backing.
**Cons:** separator bookkeeping; delete rebalancing is the fiddly part (mitigated by the
invariant checker + oracle tests at a small fanout to force splits/merges constantly).

### Option B: Classic B-tree (keys in internal nodes)

**Pros:** marginally fewer node visits on hit.
**Cons:** keys at every level complicate paging (interior pages mix routing and data),
range scans need parent re-ascent, deletion is harder still. Strictly worse disk story.

### Option C: Cache-oblivious (vEB-layout) search tree

**Pros:** asymptotically optimal across every cache level without tuning.
**Cons:** static layouts want amortized rebuild machinery for updates; research-grade
complexity for a codebase that values mechanical checkability; no natural disk page story.

### Option D: LSM tree

**Pros:** the write-optimized disk answer.
**Cons:** wrong contract — order statistics over merging runs are expensive; reads are
multi-run; compaction is a background-thread commitment this project has deliberately avoided
(ADR-006 rejected async machinery for less).

---

## 3. Decision

**Adopt Option A, sliced:**

**D1 (this slice) — the structure, in memory.** `BPlusTreeEngine<K>` implementing
`RankedSet<K>` directly: configurable fanout (default 32, floor 4 — tests run at the floor to
force structural churn), per-child subtree counts funding the full order-statistics surface,
leaf chain for `inOrder`/`rangeQuery`, `OrderedSet`-parity semantics on every method (the
VERIFIED voting requirement), realized write meters, `validateStructure()` as the mechanical
checker (sorted keys, occupancy floors, uniform leaf depth, separator = subtree-min, counts,
chain order). Ensemble membership via a new generalized `Builder.engineMember(supplier,
label)` — which `persistentMember()` now delegates to. **No registry / genome integration:**
the evolution layer's switches stay untouched until the engine earns promotion-by-fitness
semantics (D3).

**D2 (held) — pages to disk.** Serialize leaves/internals as fixed-size pages via
`KeySerializer`; read path first (frozen snapshot → paged file → point/range queries against
a page cache), write path after. Demanded by a working set that misses RAM, not before.

**D3 (held) — registry + genome.** `StructureType.B_PLUS_TREE`, capability note, fitness
model — only once D2 exists, because "recommend the disk engine" is meaningless while it is
an in-memory structure with worse constants than RB below ~10⁵ keys.

---

## 4. Consequences

**Easier:** large-n workloads get a cache-friendly engine that is already a first-class
ensemble member (vote it, heal it, promote it explicitly); D2 becomes a serialization
exercise over an already-proven page layout; `engineMember()` opens the ensemble to any
future `RankedSet` without further seam work.

**Harder:** three engine families now (strategy BSTs, persistent, paged) — the docs must keep
their roles straight; delete rebalancing is the largest single method in the engine family
(accepted: it is the price of Option A, fenced by the checker).

**Revisit:** fanout default if profiling disagrees with 32; bulk-loading (build from sorted
input without per-key splits) when D2's snapshot-load path wants it.

---

## 5. Action items

1. [x] **D1** — `BPlusTreeEngine<K>` + `engineMember()` seam + `BPlusTreeEngineTest`
   (oracle parity under churn at fanout floor, sorted/reverse/organ-pipe inputs, order-stats
   parity, OrderedSet-semantics edges, invariant checker throughout) + ensemble smoke
   (VERIFIED voting beside strategy members — unanimity is the parity proof).
   _(Done 2026-06-09.)_
2. [ ] **D2** — (held) paged file backing via `KeySerializer`; read path first.
3. [ ] **D3** — (held) `StructureType.B_PLUS_TREE` + capability + fitness, after D2.

---

## 6. Verification & rollback

D1 is purely additive (one new class, one builder method, tests); rollback is deleting it.
The invariant checker runs inside the oracle test every few hundred ops, mirroring ADR-005's
discipline. Ships green through host `ant clean test` per `CLAUDE.md`.
