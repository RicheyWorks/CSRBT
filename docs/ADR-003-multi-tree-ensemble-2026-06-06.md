# ADR-003: Multi-tree ensemble — parallel strategies with measured promotion and N-version voting

**Status:** Accepted (2026-06-09 — E1–E6 landed; see the `CHANGELOG-2026-06-09-ensemble-*.md` series)
**Date:** 2026-06-06
**Deciders:** Richmond
**Builds on:** the landed control plane (ADR-002 step 6, Phase D) — `WorkloadMonitor` →
`StrategyScorer` → `MorphPolicy` → `MorphController` — and the health-gated `setStrategy`
executor (`StrategyHealthCheck`, `StrategyMorphTarget`).
**Goal (from elicitation):** a **production-usable, drop-in** ensemble — robust API, real
fault tolerance — designed in depth (not a research toy).

---

## 1. Context

Today CSRBT backs a logical ordered set with **one** tree. The control plane decides *when*
and *to what* to morph, but the act of morphing is an **O(n) rebuild**: `OrderedSet.setStrategy`
builds the candidate aside, validates it through `StrategyHealthCheck`, and swaps it in. Two
limitations follow:

- **Adaptation is expensive and bursty.** Every regime change pays O(n) to rebuild. Under a
  workload that shifts often, the anti-thrash `MorphPolicy` must hold morphs back precisely
  *because* each one is costly — so the structure adapts slower than the workload moves.
- **The decision is predicted, not measured.** `CostModelStrategyScorer` ranks strategies from
  a cost *model* over `WorkloadFeatures` (read/write mix, hot-key skew). It never observes how a
  given strategy would *actually* shape this data.
- **One tree is a single point of failure.** A latent bug in one strategy, or in-memory
  corruption, has no cross-check — the health gate runs only at morph time, on the candidate.

A multi-tree **ensemble** keeps several strategy-backed members live over the same key set at
once. That reframes adaptation as **routing** (which member serves) instead of **rebuilding**,
and it makes redundancy — failover and cross-validation — a first-class property. The cost is
steady-state overhead: K members means K× memory and K× write work.

This ADR commits to the ensemble direction and designs it in depth. The non-goal is replacing
the single-tree path — `OrderedSet`/`TreeContext` stay as the lightweight default; the ensemble
is an opt-in facade for workloads that shift often or need redundancy.

### What "voting" means here (stated precisely)

For a deterministic ordered set, every correct member returns the *same* answer to `contains` /
`select` / `rank` — so members do not "vote" to compute results. "Voting" has two distinct,
useful meanings, and this design supports both as separate, configurable mechanisms:

1. **Promotion vote (performance).** The controller chooses the *serving* member from
   per-member evidence over a window, gated by the existing `MorphPolicy`
   (cooldown / stability / margin). Switching the winner is an **O(1) atomic swap**, not a rebuild.
2. **Correctness vote (N-version, opt-in).** In `VERIFIED` mode, reads fan out to ≥3 exact
   members; the **majority** answer is served and a dissenting member is quarantined as faulty
   and healed. This is N-version programming applied to a data structure — it catches a
   strategy-implementation bug or memory corruption that a single tree cannot.

---

## 2. Decision

Introduce `core.ensemble.EnsembleOrderedSet<K>`: a drop-in facade (same contract as
`OrderedSet<K>`) backing the logical set with **K independent members**, each a full
strategy-backed engine over an *exact copy* of the key set. Generalize the control plane from
"morph one tree" to "promote among warm members":

- **Members stay in sync** by fanning every effective `add`/`remove` out to all active members.
- **Reads serve from a `primary`** member (`volatile` reference); promotion is an atomic swap.
- **An `EnsembleController`** (the `MorphController` generalized) collects per-member evidence,
  runs `MorphPolicy`, and promotes — emitting the existing one-line-per-eval observability.
- **Health/quarantine/heal** runs per member; a failed member is dropped from serving, rebuilt
  from the primary, or retired. If the *primary* fails, a healthy member is promoted instantly
  (the failover win).
- **`VERIFIED` mode** adds read-quorum correctness voting on top.

Reuse, unchanged: `WorkloadMonitor`/`RollingWorkloadMonitor`, `WorkloadFeatures`, `MorphPolicy`,
`MorphHistory`, `StrategyHealthCheck`, the per-op timers `avgInsertTimeMs`/`avgDeleteTimeMs`, and
`FilePersistenceAdapter`/`KeySerializer<K>`.

---

## 3. Options considered

The direction (ensemble) is chosen; the real decision is **how members stay in sync**, which
sets the cost/capability envelope. Option 0 is the status-quo baseline for comparison.

### Option 0: Single-tree morph (baseline / do-nothing)
| Dimension | Assessment |
|---|---|
| Complexity | Low (already shipped) |
| Memory | 1× |
| Write cost | 1× |
| Read cost | 1× |
| Adaptation | **O(n) rebuild** per morph |
| Fault tolerance | None (no cross-check) |

**Pros:** simplest; minimal memory; already correct and tested.
**Cons:** bursty O(n) adaptation; model-only decisions; single point of failure.

### Option A: Synchronous mirrored ensemble (CHOSEN default)
All members are exact copies; writes fan out to all; reads serve from the primary.
| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Memory | K× |
| Write cost | K× (parallelizable — members are independent) |
| Read cost | 1× (NORMAL) / quorum× (VERIFIED) |
| Adaptation | **O(1) atomic promotion** (candidate already warm) |
| Fault tolerance | Instant failover; correctness voting available |

**Pros:** turns adaptation into a pointer swap; enables failover and N-version voting; promotion
is grounded in each member's *real* structure, not only a model. **Cons:** K× memory and writes;
needs an executor to keep fan-out cheap.

### Option B: Primary + sampled shadows
Shadow members receive only a sampled fraction *p* of ops, so they only *estimate* cost.
| Dimension | Assessment |
|---|---|
| Complexity | Medium-High |
| Memory | ~1 + p·(K−1) × |
| Write cost | ~1 + p·(K−1) × |
| Read cost | 1× |
| Adaptation | promotion needs a **build + catch-up** step (not O(1)) |
| Fault tolerance | None (shadows aren't exact → can't serve or vote) |

**Pros:** cheap standing cost; good for memory-constrained hosts. **Cons:** statistical/noisy
signal; a sampled shadow cannot serve, fail over, or vote — promoting it costs a sync step.

### Option C: Primary + periodic-rebuild shadows
Shadows are rebuilt from a primary snapshot every N ops, then measured on the live stream until
the next rebuild.
| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Memory | K× (transient during rebuild) |
| Write cost | 1× (+ amortized O(n) rebuild every N ops) |
| Read cost | 1× |
| Adaptation | promotion = the warm just-rebuilt shadow |
| Fault tolerance | Weak (shadow only fresh just after a rebuild) |

**Pros:** cheap steady-state writes; the rebuilt shadow is a ready promotion target.
**Cons:** the signal lags the workload by up to N ops; no continuous redundancy.

**Choice:** ship **Option A (synchronous mirror)** as the default and the headline capability
(O(1) adaptation + redundancy), with **Option B (sampled shadows)** offered as a memory-lean
mode behind the same facade. Option C is held as a future optimization.

---

## 4. Trade-off analysis

- **The crux: pre-pay vs pay-on-switch.** Single-tree morph pays O(n) *at the moment it adapts*;
  the mirrored ensemble pays K× *all the time* but adapts in O(1). The ensemble wins when the
  workload shifts often enough that morph cost (and the anti-thrash hold-off it forces) dominates,
  or when redundancy is required. The single tree wins when morphs are rare and memory is tight.
  This is a deliberate, configurable trade — not a strict upgrade.

- **What "measured" actually buys (and its honest limit).** In NORMAL mode only the primary
  serves reads, so non-primary members never see real queries — you cannot measure their *read
  latency* without sending them reads (read amplification). What you *can* measure cheaply, per
  member, is **structure and write cost**: tree height / mean depth (its actual shape), rotations
  per write, and the existing `avgInsertTimeMs`/`avgDeleteTimeMs`. Promotion therefore combines
  the **shared** `WorkloadFeatures` (the workload, from the one `WorkloadMonitor`) with
  **per-member measured structure** — strictly more grounded than the single tree's pure model.
  True per-member read-latency is available only by opting into **probe-reads** (replay a sample
  of recent read keys against members — a sampling cost) or **VERIFIED** mode (which sends reads
  to a quorum anyway). The design is explicit about this so "promote on measured cost" is not
  oversold.

- **Sync vs sample.** Exact mirrors cost K× writes but are the *only* configuration that supports
  failover and correctness voting (a member must be exact to stand in or to vote). Sampled
  shadows are cheap but can only *estimate* — they are an optimization, not the robust default.

- **Concurrency.** Members share no mutable state, so write fan-out is **embarrassingly
  parallel**. But the current engine is single-threaded and the existing `OrderedSet` serializes
  writers on one lock. The ensemble keeps a **single external writer** (linearizable logical set)
  and parallelizes the *internal* fan-out across members via a small executor; per member, only
  one thread touches it at a time, so no member needs to become thread-safe internally. Promotion
  is a `volatile`/`AtomicReference` swap of `primary` — this is exactly the "single-writer /
  multi-reader via atomic root swap" the design doc defers, realized at member granularity.

- **Drop-in compatibility.** `EnsembleOrderedSet<K>` implements `OrderedCollection<K>` and mirrors
  `OrderedSet`'s order-statistics surface, so existing call sites swap the type and keep working.
  An int adapter parallel to `TreeContext` preserves the `int` API.

---

## 5. Architecture (in depth)

**Package:** `core.ensemble` (new), depending on `core`, `core.control`, `core.strategy`,
`core.util` — never the reverse.

**Components.**
- `EnsembleMember<K>` — wraps one `OrderedSet<K>` (the backing engine), plus its measured meters
  (height, rotations/write, `avgInsertTimeMs`/`avgDeleteTimeMs`) and a health state
  (`ACTIVE` / `QUARANTINED` / `RETIRED`).
- `EnsembleOrderedSet<K>` — the facade. Holds the active members, a `volatile EnsembleMember<K> primary`,
  the shared `WorkloadMonitor`, the `EnsembleController`, and the `MemberExecutor`. Implements
  `OrderedCollection<K>` + order-stats.
- `EnsembleController<K>` — the generalized `MorphController`: each evaluation reads the shared
  `WorkloadFeatures` + per-member measured structure, asks `MorphPolicy` whether the best
  non-primary member beats the primary by the margin for the stability window past cooldown, and
  if so promotes (atomic swap). Emits one `event=morph_eval decision=PROMOTE from=… to=…` line
  (same schema as today).
- `MemberExecutor` — fans writes out to members (sequential in E1; parallel in E5).

**Consistency model.**
- *Logical set* = the keys applied through the facade. Each `ACTIVE` member holds an exact copy.
- *Write path:* acquire the single writer lock → fan `add`/`remove` to all `ACTIVE` members on the
  **effective-mutation** boolean (so duplicates/absent removes don't drift members) → feed the one
  `WorkloadMonitor` once → return. Members being independent, a member that throws is quarantined
  and the write still commits to the rest (the logical set follows the primary/majority).
- *Read path (NORMAL):* serve from `primary` only — 1× read cost, same lock-free read caveat as
  `OrderedSet` today. Order statistics serve from the primary's subtree-size augment (all members
  carry it).
- *Read path (VERIFIED):* fan the read to a quorum (≥3), compare, serve the majority, quarantine
  any dissenter.

**Promotion (the O(1) win).** A non-primary `ACTIVE` member that is already in sync can become
`primary` by swapping one reference. `MorphPolicy` gates it exactly as it gates morphs today, and
`MorphHistory` tracks the cooldown/streak — so anti-thrash behavior is inherited, not re-invented.
No rebuild, no revalidation at swap time (the member was validated when it joined and is
health-checked on cadence).

**Membership lifecycle.** A new member is built **once** from `primary.inOrder()` (O(n)), then
registered for fan-out; it is `WARM` and promotable thereafter. Retiring a member frees its
memory. Ensemble size K is configurable (default 2).

**Failure & self-healing.**
- Per-member `StrategyHealthCheck` on a cadence (and on demand). Failure → quarantine (drop from
  serving + voting) → heal by rebuilding from `primary.inOrder()` (the existing `selfRepair` /
  `resyncFromEngine` pattern) → re-`ACTIVE` on a clean check, else `RETIRED`.
- If the **primary** fails its check, promote a healthy member immediately, then heal the failed
  one in the background — queries are never served from a known-bad tree.
- Invariant: **always keep ≥1 known-good member.** If all members fail (should be impossible
  without a shared cause), fall back to rebuilding one from the last durable snapshot.

**Persistence.** Snapshot the **primary** through the existing `FilePersistenceAdapter` /
`KeySerializer<K>` (no new format). On load, restore the primary and rebuild the other members
from it. Versioned/time-travel snapshots are out of scope here (that is the separate
"persistent + versioned" direction).

---

## 6. API sketch (drop-in)

```java
// Drop-in: same contract clients already use.
EnsembleOrderedSet<String> set = EnsembleOrderedSet.builder(Comparator.naturalOrder())
    .member(RedBlackStrategy::new)     // member 0 — initial primary
    .member(SplayStrategy::new)        // warm standby / promotion candidate
    .mode(EnsembleMode.MIRROR)         // MIRROR (default) | VERIFIED | SAMPLED_SHADOW
    .promotionPolicy(MorphPolicy.defaults())
    .healthEvery(4096)                 // ops between per-member health checks
    .build();

set.add("pear"); set.add("apple");    // fans out to all ACTIVE members
set.contains("apple");                 // served by the primary
set.select(1);                          // order stats from the primary's augment
// …workload shifts read-heavy + skewed → controller promotes the Splay member (O(1) swap).
```

- `EnsembleOrderedSet<K> implements OrderedCollection<K>` plus the order-stat methods mirrored
  from `OrderedSet` (`select`/`rank`/`successor`/`predecessor`/`min`/`max`/`median`/`percentile`/
  `countInRange`/`rangeQuery`), so it is a true drop-in.
- A `core.ensemble` int adapter (parallel to `TreeContext`) preserves the `int` API for existing
  callers.
- Observability: one structured line per controller evaluation, same `event=morph_eval` schema
  (with `decision=PROMOTE|HOLD`, `from`/`to` members), so existing log tooling keeps working.

---

## 7. Cost model (production reference)

| Mode | Memory | Write | Read | Adaptation | Fault tolerance |
|---|---|---|---|---|---|
| Single-tree morph (today) | 1× | 1× | 1× | O(n) per morph | none |
| MIRROR, k=2 (default) | 2× | 2× (∥) | 1× | **O(1) promote** | instant failover |
| VERIFIED, k=3 quorum | 3× | 3× (∥) | 3× + compare | O(1) promote | failover + corruption detection |
| SAMPLED_SHADOW, p=0.1 | ~1.2× | ~1.2× | 1× | O(n) sync-on-promote | none |

"(∥)" = parallelizable across members (E5). Defaults stay conservative (k=2, MIRROR) so the
out-of-the-box overhead is 2×, buying O(1) adaptation and failover.

---

## 8. Consequences

**Easier:**
- Adaptation becomes a pointer swap — the structure can track a fast-shifting workload without
  paying O(n) each time, and `MorphPolicy` can be less conservative because switching is cheap.
- Real fault tolerance: failover on member failure, and (VERIFIED) detection of a buggy strategy
  or corruption that a single tree cannot catch.
- The design doc's atomic-swap concurrency goal lands naturally at member granularity.

**Harder:**
- K× memory and write work; an executor and a membership/quarantine state machine to maintain.
- Persistence snapshots only the primary (members rebuilt on load) — acceptable, but a behavior to
  document.
- "Measured promotion" must be scoped honestly to structure/write-cost (not read latency) unless
  probe-reads/VERIFIED are enabled.

**Revisit:**
- Memory ceilings — cap K and offer SAMPLED_SHADOW when constrained.
- Whether VERIFIED's read amplification is acceptable for the target deployment.
- The single external-writer lock as a throughput ceiling (future: lock-free multi-reader on the
  primary via the atomic swap already in place).

---

## 9. Risks & open questions

| Risk / question | Disposition |
|---|---|
| K× write amplification dominates a write-heavy workload | parallel fan-out (E5); default k=2; recommend single-tree for write-bound + stable workloads |
| Non-primary read cost is not directly observed | promote on structure + write-cost by default; probe-reads / VERIFIED for true read measurement (documented limit) |
| Promotion thrash | reuse `MorphPolicy` gates + `MorphHistory`; same proven anti-thrash as morphs |
| A correlated bug corrupts all members identically | VERIFIED only catches *divergent* faults; diversity across strategies (RB vs AVL vs Splay) makes identical corruption unlikely but not impossible |
| Memory blow-up on large n | cap K; SAMPLED_SHADOW; expose live memory metrics |
| Concurrency bugs in fan-out | E1 sequential first; parallelism (E5) added only behind the oracle + failover tests |
| Sandbox is JRE-only | every step verified by `ant clean test` on the host, per `CLAUDE.md` |

---

## 10. Action items (phased strangler, mirroring Phase D's style)

1. [x] **E1 — facade + mirror, sequential.** `EnsembleMember<K>`, `EnsembleOrderedSet<K>`
   (MIRROR, k configurable) implementing `OrderedCollection<K>` + order stats; fan-out writes
   (sequential), primary serves reads. **Test:** all `ACTIVE` members agree with a `TreeSet`
   oracle and with each other across randomized mixed ops.
2. [x] **E2 — measured promotion.** Per-member meters (height, rotations/write,
   `avgInsert/DeleteTimeMs`) → `EnsembleController` → `MorphPolicy` → **O(1) atomic primary swap**;
   one `event=morph_eval decision=PROMOTE` line per eval. **Test:** a skewed read stream promotes
   the Splay member in ≤1 promotion with **no rebuild** (assert promotion count + that contents
   were never rebuilt).
3. [x] **E3 — health / quarantine / heal + failover.** Per-member cadence health check; corrupt a
   member → quarantined and healed from the primary, queries uninterrupted; corrupt the primary →
   instant failover to a healthy member. _(Done 2026-06-09 -- quarantine/heal/retire on EnsembleOrderedSet + EnsembleController.checkHealth; see CHANGELOG-2026-06-09-ensemble-e3.md.)_
4. [x] **E4 — VERIFIED mode.** Read quorum + majority serve + dissenter quarantine. **Test:** inject
   a deliberately buggy strategy as one member → it is outvoted and quarantined; results stay
   correct. _(Done 2026-06-09 -- EnsembleMode.VERIFIED + quorum vote in EnsembleOrderedSet; see CHANGELOG-2026-06-09-ensemble-e4.md.)_
5. [x] **E5 — parallel fan-out + SAMPLED_SHADOW + benchmarks.** Member executor for parallel writes;
   memory-lean sampled mode; a `StrategyBattleRunner`-style benchmark of adaptation latency and
   steady-state overhead vs single-tree morph. _(Done 2026-06-09 in three slices: the benchmark -- EnsembleBenchmarkTest; the parallel fan-out -- MemberExecutor/ParallelMemberExecutor + EnsembleFanOutTest; SAMPLED_SHADOW -- EnsembleMode.SAMPLED_SHADOW + EnsembleMember.isExact + sync-on-promote, EnsembleShadowTest. See the three CHANGELOG-2026-06-09-ensemble-e5-*.md entries.)_
6. [x] **E6 — persistence + docs.** Snapshot primary / rebuild members on load; README "Ensemble"
   section; `CHANGELOG-…-ensemble.md`; flip this ADR to **Accepted**. _(Done 2026-06-09 --
   FilePersistenceAdapter.saveSnapshot(ensemble)/loadEnsemble + EnsemblePersistenceTest; README
   ensemble coverage; status flipped. See CHANGELOG-2026-06-09-ensemble-e6.md.)_

---

## 11. Verification & rollback
- The ensemble is an **additive, opt-in facade** — `OrderedSet`/`TreeContext` are untouched, so
  the existing suite stays the regression floor. Each E-step ships green via host `ant clean test`
  (the dev sandbox is JRE-only). "Rollback" is simply not constructing an `EnsembleOrderedSet`; no
  existing call site changes until a client opts in.
