# ADR-004: Lock-free multi-reader reads — retiring the torn-read caveat

**Status:** Accepted (2026-06-09 — R1 + R2 landed, see CHANGELOG-2026-06-09-adr004-r1.md /
-r2.md; R3 deliberately held as the horizon)
**Date:** 2026-06-09
**Deciders:** Richmond
**Builds on:** the landed ensemble (ADR-003, E1–E6) — exact mirrors, the single writer lock, the
`volatile` primary swap — and the design doc's concurrency goal
(`DESIGN-adaptive-engine.md` §4: "single writer lock; readers on the `volatile` engine ref…
full lock-free is explicitly deferred").
**Goal:** make concurrent reads *safe* (no torn state, ever) and, where the ensemble is in play,
*lock-free* — un-deferring the design doc's deferred item without chasing a lock-free tree.

---

## 1. Context

Every engine in CSRBT mutates **in place**: rotations re-link `TreeNode1` pointers, recolors flip
fields, and deletes splice nodes — all under the single writer lock. Readers take **no lock**:
`contains`, `inOrder`, and the order statistics walk the live structure while a writer may be
mid-rotation. The README documents this honestly ("a read concurrent with a write may observe the
primary mid-mutation"), but documentation is not a fix. Three forces sharpen the problem now:

- **The ensemble made concurrent callers normal.** ADR-003's facade serializes *writers* and is
  marketed as a drop-in; the natural next assumption a user makes is that reads are safe too.
  Today a reader can chase a stale pointer through a half-applied rotation — transient cycles and
  NPEs are possible, not just stale answers. The `volatile` primary swap gives safe *publication*,
  but what it publishes is a tree that keeps mutating in place after publication, so the JMM
  guarantee evaporates on the first post-swap write.
- **Splay reads are writes.** `SplayStrategy.search` splays the accessed node to the root on every
  hit *and* every miss (move-to-root on absent keys). Any "read-only" path through a splay member
  structurally mutates the tree. No read-side scheme can treat splay reads as pure; this is a
  first-class constraint, not a footnote.
- **The machinery is half-built already.** The ensemble holds K *exact, independent* copies of the
  logical set behind one writer lock with an atomic serving-pointer — which is most of a
  left-right concurrency structure. And `PersistentTreeEngine` already implements path-copying
  immutability (Integer-only, unbalanced, not strategy-pluggable) — a seed for the full
  copy-on-write vision, not a usable engine today.

Non-goals: a lock-free *writer* path (the single external writer stays — ADR-003 §4 chose
linearizability via one lock deliberately), and lock-free reads on a **bare** `OrderedSet`
without an ensemble (single-tree callers get *safe*, not lock-free).

---

## 2. Options considered

### Option A: `StampedLock` per set — optimistic reads, validated

Replace the reader's no-lock walk with `tryOptimisticRead` → traverse → `validate(stamp)`;
fall back to a real read lock on validation failure. Writers take the write stamp inside the
existing mutator lock. Splay reads must take the **write** stamp (they mutate).

| Dimension | Assessment |
|---|---|
| Complexity | Low-Medium |
| Read cost (uncontended) | ~1× + two volatile reads (stamp) |
| Read cost (contended) | retry, then shared lock — blocks only during an in-flight write |
| Writer cost | one stamp acquire inside the existing lock |
| Lock-free? | No (optimistic ≠ lock-free; fallback blocks) |
| Splay | degrades fully: every splay read is a writer |

**Pros:** small, local, fixes *every* caller including bare `OrderedSet`; no memory overhead; no
new invariants. **Cons:** an optimistic traversal of an in-place tree can transiently chase a
cycle a rotation creates from the reader's viewpoint — the walk must be **step-bounded**
(bail to the locked path after ~2·log₂(n)+slack steps); splay members effectively serialize
reads against writes; not lock-free, so the design-doc goal is only half-met.

### Option B: Seqlock (version counter) with retry traversal

Writer bumps a version to odd before mutating, even after; readers snapshot the version, walk,
re-check, retry on change.

| Dimension | Assessment |
|---|---|
| Complexity | Medium (deceptively) |
| Read cost | 1× + retries under write pressure |
| Lock-free? | Readers never block but can starve under sustained writes |
| Splay | same degradation as A |

**Pros:** no reader locks at all. **Cons:** identical torn-traversal hazard as A (must
step-bound), reader starvation under write bursts, and it is strictly dominated by A
(`StampedLock` *is* a seqlock with a curated API and a fallback). Rejected.

### Option C: Left-right over ensemble mirrors — epoch reads ("READ_REPLICA" mode)

Use two exact members as the left/right instances of the classic left-right pattern. Readers
enter an epoch (increment the serving side's reader counter, `volatile`-read the serving member,
walk a tree **no writer touches during that epoch**, decrement). The writer, under the existing
lock: applies the op to the *non-serving* member, flips the serving pointer, **waits for the old
side's readers to drain** (the grace period), then applies the op to the other member. Fan-out to
additional members (K>2) proceeds as today.

| Dimension | Assessment |
|---|---|
| Complexity | High (grace periods, two-phase apply) |
| Read cost | 1× + two counter ops — **wait-free**, never blocks, never retries |
| Writer cost | 2× sequential apply + a bounded wait for stale readers |
| Memory | none beyond the 2× the ensemble already pays |
| Splay | the serving side must **not** splay on read — see §3 |

**Pros:** genuinely lock-free (wait-free) readers with *strong* answers (each read sees a fully
consistent tree, not a best-effort walk); reuses ADR-003's mirrors, writer lock, and volatile
swap; zero added memory. **Cons:** writer latency now includes a reader-drain wait; promotion/
failover/health interplay must respect epochs; splay's read-adaptivity is lost on the serving
side; only ensembles benefit.

### Option D: Balanced persistent engine — copy-on-write root swap

The full vision: immutable nodes, path-copying updates (O(height) fresh nodes per write), readers
`volatile`-read the root and walk a snapshot that can never change. `PersistentTreeEngine` is the
seed; it would need balancing (persistent RB or weight-balanced), generic keys, augments, and
strategy-seam integration — effectively a second engine family.

| Dimension | Assessment |
|---|---|
| Complexity | Very High (a new engine family + strategy rework) |
| Read cost | 1×, wait-free, snapshot-consistent — the ideal |
| Writer cost | O(log n) allocation per write + GC pressure |
| Splay | persistent splay is awkward: read-splay either abandoned or turns reads into writes again |

**Pros:** the cleanest end state; snapshots, iteration, and morph/promote all become free
reference handoffs. **Cons:** the largest build on the table for a benefit C already delivers
where it matters; in-place strategies (the project's core asset) don't carry over — they would be
reimplemented, not reused. Held as future work, exactly as the design doc holds it.

---

## 3. The splay constraint (applies to every option)

`SplayStrategy.search` mutates on hit and miss. Decisions:

- **Concurrent-read modes must not splay on read.** Add a read-path entry that searches without
  splaying (`SplayStrategy` gains a pure BST lookup used when the engine is serving concurrent
  reads). The tree keeps splaying on *writes*, so it still adapts — more slowly, and its amortized
  bound now leans on write traffic. This is the honest cost of making splay reads shareable.
- Under Option A, a splay member that *does* splay on read simply takes the write stamp — correct
  but serializing. The no-splay-on-read entry is what keeps splay members useful under A too.
- The ensemble already has the right vocabulary: a member whose strategy cannot serve shared reads
  cheaply is simply a less attractive **primary** — the controller's meters will see its read
  latency and prefer promoting RB/AVL/Hybrid under read-heavy concurrency anyway.

---

## 4. Trade-off analysis

- **Safe vs lock-free are different deliverables.** A fixes *correctness* everywhere for pennies;
  C buys *progress guarantees* (wait-free reads) where the ensemble's 2× memory is already being
  paid. D buys elegance at the price of a second engine family. B is A without A's escape hatch.
- **The grace period is the real cost of C.** The writer's drain-wait is bounded by the longest
  in-flight read (a walk + possibly an `inOrder` copy). Order statistics are O(log n); `inOrder`
  on a large set is the outlier — it should snapshot *inside* its epoch and copy out, never hold
  the epoch while post-processing.
- **Where they compose:** A is not throwaway — it is the fallback path C needs for bare
  `OrderedSet` callers and for QUARANTINED-member healing reads, and the step-bounded walk it
  introduces is reusable. Ship A, then C; D stays a documented horizon.

---

## 5. Decision

**Phase R1 — safety everywhere (Option A).** `StampedLock` inside `OrderedSet`: optimistic,
step-bounded reads with locked fallback; mutators take the write stamp inside the existing
monitor. `SplayStrategy` gains the no-splay-on-read lookup, used whenever the optimistic path is
active. Bare `OrderedSet` and every ensemble member become torn-read-free. The README's caveat
paragraph is retired.

**Phase R2 — lock-free reads on the ensemble (Option C).** A new `EnsembleMode.READ_REPLICA`
(MIRROR semantics + left-right serving): wait-free epoch readers over the serving member, writer
applies non-serving-first with a reader drain at the flip. Promotion, failover, quarantine, and
VERIFIED voting acquire epoch-awareness (a member may not be healed or retired while readers
drain on it). The E5 benchmark grows a read-throughput row: k readers × 1 writer, READ_REPLICA vs
R1-locked vs today's unsafe baseline.

**Phase R3 — horizon (Option D).** Balanced persistent engine stays future work; revisit when a
workload demands snapshot iteration or wait-free reads without an ensemble.

---

## 6. Consequences

**Easier:** concurrent callers stop being a documented hazard; the ensemble's drop-in claim
becomes true under multi-threaded read load; the controller can weigh read-concurrency in
promotion decisions; `getEngine()`'s "live structure" leak can finally be deprecated in favor of
epoch-scoped reads.

**Harder:** the writer path grows phases (R2's two-step apply + drain); splay loses read-side
adaptivity in shared-read modes; `inOrder`/range queries need epoch discipline to keep grace
periods short; test surface grows real multi-threaded tests (the suite gains its first
genuinely concurrent assertions beyond E5's linearizability check).

**Revisit:** whether R1's step bound needs tuning for deep (healed-splay) trees; whether R2's
drain should time-box and fall back to the locked path; D when persistent-structure demand
appears.

---

## 7. Risks & open questions

| Risk | Mitigation |
|---|---|
| Optimistic walk loops on a transient cycle | step bound ≈ 2·log₂(n) + 32, then locked retry; never trust an unvalidated answer |
| Reader starvation of the writer (R2 drain) | epochs are entered/exited in O(1); `inOrder` copies inside the epoch; drain time-box + locked fallback is the escape hatch |
| Epoch leaks (reader dies mid-epoch) | try/finally on the read path; counters are per-side `LongAdder`s, leak shows as a stuck drain → log + fallback |
| Splay no-read-splay changes its complexity story | document: amortized bounds now write-driven; controller meters already observe realized latency, not theory |
| `getEngine()` bypasses everything | unchanged-by-contract (diagnostics seam); deprecate for application reads once R2 lands |

---

## 8. Action items

1. [x] **R1a** — no-splay-on-read lookup on the facade read path; existing suite stays green
   (single-threaded behavior unchanged by default). _(Done 2026-06-09 -- realized as a
   strategy-independent descend in OrderedSet rather than a SplayStrategy entry point;
   OrderStatisticsOps was already pure. See CHANGELOG-2026-06-09-adr004-r1.md.)_
2. [x] **R1b** — `StampedLock` optimistic reads in `OrderedSet` (step-bounded walk, locked
   fallback); torn-read stress test: hammer reads during writes, assert no NPE/cycle/wrong-size,
   on every strategy. _(Done 2026-06-09 -- ConcurrentReadStressTest; rollback constant
   OPTIMISTIC_READS. See CHANGELOG-2026-06-09-adr004-r1.md.)_
3. [x] **R2a** — epoch infrastructure (per-side reader counters, drain) behind
   `EnsembleMode.READ_REPLICA`; single-writer/multi-reader stress: k reader threads see only
   fully consistent states (size parity, sorted `inOrder`, monotone rank). _(Done 2026-06-09 --
   enter/verify/exit epoch readers + two-phase left-right writes; EnsembleReplicaTest. See
   CHANGELOG-2026-06-09-adr004-r2.md.)_
4. [x] **R2b** — epoch-aware promotion/failover/quarantine + the benchmark's read-throughput row.
   _(Done 2026-06-09 -- promote drains the deposed side, heal drains before rebuild, loud
   degradation below two exact members; printed MIRROR-vs-READ_REPLICA throughput reference.)_
5. [ ] **R3** — (held) balanced persistent engine ADR when demanded.

---

## 9. Verification & rollback

Each phase is additive and flag-gated: R1's optimistic path can fall back to today's behavior by
constant (`OPTIMISTIC_READS = false` → exactly the current no-lock walk); R2 is a new mode, so
not selecting `READ_REPLICA` is the rollback. Every phase ships green through host
`ant clean test` per `CLAUDE.md`, with the new concurrent tests bounded (fixed thread counts,
deterministic seeds, generous-but-finite timeouts) so the suite stays CI-stable.
