# CSRBT system design — the adaptive ordered-set engine

Status: proposed. Companion to `code-review-2026-05-29.md` (correctness fixes)
and `PLAN-nil-sentinel-refactor.md`. This document defines what CSRBT should
*become*: an ordered-set engine that continuously adapts its balancing strategy
to the workload actually hitting it, and morphs between strategies only when a
health check says the new shape is both valid and worth it.

## 1. Requirements

### Functional
- Ordered-set / multiset API: `add`, `remove`, `contains`, `inOrder`, `size`, `clear`.
- Order statistics in O(log n): `select(k)`, `rank(key)`, `median`, `percentile`,
  `rangeQuery`, `successor`, `predecessor`.
- **Adaptive strategy selection**: the engine observes the live workload and
  switches between balancing strategies (Red-Black, AVL, Splay, …) to minimize
  expected operation cost.
- **Health-checked morphing**: a strategy switch is committed only after the new
  structure is built and validated; a failed validation rolls back with no data loss.
- Durable snapshots; undo/redo with checkpoints.

### Non-functional
- Correctness first: every public operation preserves the ordered-set contract and
  the active strategy's invariants. No silent corruption, no infinite loops.
- Predictable cost: individual ops stay O(log n); morphs are O(n) and **rare**.
- Observability: the adaptation decisions must be explainable and logged.
- Embeddable: usable as a plain JVM library with no required external services.

### Recommendations on the two open questions
- **Keys → generic `<K>` with a `Comparator<K>`.** `int`-only blocks the most
  natural real uses (strings, timestamps, composite keys). Make the node payload
  a type parameter and route all comparisons through a `Comparator`; default to
  natural ordering for `Comparable`. This is a prerequisite for "real workloads."
- **Concurrency → single-writer / multi-reader via atomic root swap.** Don't chase
  lock-free now. One writer lock serializes mutations; reads follow a `volatile`
  root reference. Morphs build a brand-new tree off to the side and publish it with
  a single reference assignment — so even long O(n) morphs never block or tear
  readers. This model is *also* what makes morphing safe, so it pays double.

## 2. High-level design — two planes

The key architectural move is to split the **data plane** (serves operations) from
the **control plane** (decides and executes adaptation). They communicate only
through a metrics feed and an atomic engine swap — never by sharing mutable tree
state.

```
            ┌──────────────────────── DATA PLANE ────────────────────────┐
 client ──▶ │  OrderedSet<K>  ──▶  Engine (volatile root)  ──▶  Strategy  │
            │     facade            atomic root swap          RB│AVL│Splay │
            └───────────────┬───────────────────────────▲────────────────┘
                            │ op events (cheap)          │ publish new engine
                            ▼                            │
            ┌──────────────────────── CONTROL PLANE ─────┴────────────────┐
            │  WorkloadMonitor ─▶ StrategyScorer ─▶ MorphPolicy ─▶ Health  │
            │  rolling metrics     cost model       hysteresis     gate +  │
            │                                       + cooldown     swap    │
            └─────────────────────────────────────────────────────────────┘
```

- The facade records a tiny event per op (op type, key hash, depth touched) into the
  `WorkloadMonitor`. This is O(1) and must never do tree-wide work (the current
  per-insert full-tree red-red scan and per-insert snapshot are exactly the
  anti-patterns to avoid — both already fixed in the review).
- The control plane runs on a cadence (every N ops or a background tick), reads the
  monitor's summary, scores candidate strategies, and — if the policy and health
  gate agree — builds a new engine and atomically swaps it in.

## 3. Deep dive — the adaptation loop

This is the heart of the system and replaces the `TreeGenome` / `TreeEcology` /
`GenomeDrivenTreeController` machinery with four small, individually testable units.

### 3.1 WorkloadMonitor — what is the data doing?
A fixed-size rolling window (e.g. last 4–16k ops) summarized into a feature vector:

| Feature | How measured | Why it matters |
|---|---|---|
| op mix | counts of add/remove/search, decayed | write-heavy vs read-heavy |
| access skew | hot-key concentration via Count-Min sketch + exponential decay | temporal locality |
| volume / growth | size and Δsize per window | large-n regime, rebuild affordability |
| search depth | running mean of nodes touched per lookup | how good the current shape is |
| rotation rate | rotations per write | structural churn under current strategy |

All counters are O(1) per op and bounded in memory. No tree traversal.

### 3.2 StrategyScorer — which strategy fits?
A transparent cost model, not a black box. Each strategy exposes an estimated
per-op cost given the feature vector:

- **AVL** wins when reads dominate and skew is low — strict balance ⇒ shallowest tree ⇒ fastest lookups.
- **Splay** wins under high access skew / locality — hot keys migrate to the root, turning a skewed workload into near-O(1) effective lookups.
- **Red-Black** wins on balanced or write-heavy mixes — fewer rotations per insert than AVL, solid worst case.
- (future) **B-tree / cache-oblivious** engine for very large n where memory locality dominates pointer-chasing.

Scores are simple weighted formulas over the features, each weight documented and
unit-tested with synthetic workloads. The scorer returns a ranked list with numbers,
so every decision is explainable in a log line.

### 3.3 MorphPolicy — *should* we switch, *now*?
Morphing is O(n); thrashing is the enemy. The policy gates a switch on all of:

- **Minimum improvement**: predicted cost of the candidate must beat the incumbent
  by a margin (e.g. ≥ 20%) — not just be marginally better.
- **Hysteresis + cooldown**: no morph within K ops of the last one; require the
  candidate to win for several consecutive evaluations.
- **Amortization**: projected savings over the expected next-window op count must
  exceed the O(n) rebuild cost. Big trees raise the bar to switch.
- **Stability**: if the workload itself is churning (no strategy stably wins),
  stay put — adapting to noise is worse than holding.

### 3.4 Health gate + MorphExecutor — switch without breaking
This is the "health check for morphing" made concrete and safe:

1. Build the candidate tree in a **fresh engine** from the current key set (its own
   per-tree NIL sentinel — see the NIL refactor — so it shares no state).
2. **Validate** the new engine: ordered traversal equals the source's sorted keys;
   size matches; the strategy's own invariant holds (RB validity for RB, height
   balance for AVL); order-statistics spot-checks (`select`/`rank`) agree.
3. Only on full pass, **atomically publish** the new engine (single `volatile`
   reference assignment). On any failure, **discard** the candidate and keep the
   incumbent — the live tree was never touched, so rollback is free.

Because the candidate is built off to the side and swapped by reference, readers
never see a half-morphed tree, and a buggy strategy can never corrupt live data —
it can only fail its health check and be dropped.

## 4. Scale and reliability

- **Per-op cost**: O(log n) for all operations; O(1) monitor update. No tree-wide
  work on the hot path (the two prior O(n)/O(n²) per-op offenders are removed).
- **Morph cost**: O(n) build + O(n) validate, bounded by the amortization gate so
  it can't dominate. Under a stable workload, morph frequency → 0.
- **Failure handling**: health-gate failure = keep incumbent + log; never throws
  to the caller. Snapshot load validates structure before returning.
- **Concurrency**: single writer lock; readers on the `volatile` engine ref. Morph
  builds off-thread-safe-by-construction (no shared mutable sentinel) and publishes
  atomically. Full lock-free is explicitly deferred. *(Update 2026-06-09: un-deferred
  by ADR-004 — reads are torn-read-free everywhere via stamped optimistic walks (R1),
  and lock-free on the ensemble via `READ_REPLICA` left-right epoch reads (R2).)*
- **Observability**: every evaluation emits one structured line — feature vector,
  per-strategy scores, decision, and (if morphed) validation result and timing.
  This is the difference between "adaptive" and "mysterious."

## 5. Trade-offs (made explicit)

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Adaptation model | transparent weighted cost model | learned/"genome" fitness | explainable, testable, debuggable; no opaque state |
| Morph safety | build-aside + validate + atomic swap | mutate-in-place + repair | rollback is free; live data is never at risk |
| Concurrency | single-writer + atomic root swap | lock-free / striped locks | 90% of the value, a fraction of the complexity |
| Keys | generic `<K>` + Comparator | keep `int` | unlocks real workloads; one-time refactor cost |
| Strategy set | RB / AVL / Splay now | add B-tree, treap, etc. | prove the loop on three before widening |

## 6. What to demote (focused-set decision)

The biological framing (`TreeEcology`, `TreeAgent` alien-seed / clone-army, the
`TreeGenome` self-interpreting fitness model) is conceptually the same adaptation
idea wearing costume. Fold its *useful kernel* — workload scoring and morph
recommendation — into the four control-plane units above, and move the theatrical
surface (alien spawn, relic beacons, clone armies) into an optional `experimental/`
module that depends on the core, not the other way around. The core must not import
anything whimsical.

## 7. Roadmap

**Phase 0 — stabilize (blocking).** Resolve the outstanding infinite-loop surfaced
by the test suite; get `RegressionFixesTest` fully green. No adaptation work lands
on an unstable core. (A per-test timeout is already wired to localize the hang.)

**Phase 1 — clean seams.** Extract `OrderedSet<K>` facade; make the engine root a
`volatile` reference with an atomic `swapEngine`. Generic-key refactor behind the
facade. Single-writer lock with documented guarantees.

**Phase 2 — control plane.** Implement `WorkloadMonitor`, `StrategyScorer`,
`MorphPolicy`, and the health-gated `MorphExecutor` as independent, unit-tested
units. Wire the facade to feed events and the executor to swap.

**Phase 3 — prove it.** Synthetic workload harness (read-heavy, write-heavy,
skewed/locality, uniform, growth bursts) asserting the engine converges to the
expected strategy and that morphs are rare and always health-valid. Replace
`StrategyBattleRunner` with this as the benchmark of record.

**Phase 4 — widen.** Add a large-n engine (B-tree / cache-oblivious) once the loop
is proven on the existing three.

## 8. Revisit as it grows
- If morphs are still too frequent under real traffic, add cost smoothing or a
  longer evaluation window before touching the strategy set.
- If reads must be strictly consistent with writes, graduate from atomic-swap to a
  copy-on-write or MVCC read path.
- If key sets get huge, the O(n) morph rebuild may need to become incremental
  (morph lazily / in background shards) rather than all-at-once.
- Revisit the generic-key boxing cost; consider specialized primitives if profiling
  shows it matters.

## 9. API contracts

Target interfaces for the new seams. Signatures are illustrative Java; the point is
the boundaries, not the exact names. Everything in the control plane is an
interface so each unit is independently testable with hand-built inputs.

### 9.1 Data plane

```java
public interface OrderedSet<K> {
    boolean add(K key);
    boolean remove(K key);
    boolean contains(K key);
    int size();
    List<K> inOrder();
    void clear();

    // Order statistics (O(log n))
    K select(int rank);          // 1-indexed
    int rank(K key);             // throws if absent
    K median();
    K percentile(int pct);
    List<K> rangeQuery(K lo, K hi);
    Optional<K> successor(K key);
    Optional<K> predecessor(K key);
}

/** The swappable engine behind the facade. Strategies operate on this. */
public interface Engine<K> {
    Node<K> root();
    void setRoot(Node<K> r);
    Node<K> nil();                       // per-instance sentinel
    Comparator<K> comparator();
    StrategyId strategy();
    void rotateLeft(Node<K> x);
    void rotateRight(Node<K> y);
}
```

The facade holds the engine in a `volatile` field and serializes writes on one lock:

```java
public final class AdaptiveOrderedSet<K> implements OrderedSet<K> {
    private volatile Engine<K> engine;     // readers follow this reference
    private final Object writeLock = new Object();
    private final WorkloadMonitor monitor;
    private final MorphController<K> controller;
    // add/remove take writeLock, record an event, then maybe trigger evaluate()
}
```

### 9.2 Control plane

```java
/** O(1) per-op ingest; bounded memory; produces an immutable snapshot. */
public interface WorkloadMonitor {
    void recordAdd(int keyHash);
    void recordRemove(int keyHash);
    void recordSearch(int keyHash, int depthTouched);
    WorkloadFeatures snapshot();         // cheap copy of current window summary
}

/** Immutable feature vector — the only thing the scorer is allowed to see. */
public record WorkloadFeatures(
    double readFraction,        // searches / total ops in window
    double writeFraction,
    double accessSkew,          // 0 = uniform, 1 = one hot key (sketch-derived)
    double meanSearchDepth,
    double rotationsPerWrite,
    long   size,
    double growthRate           // Δsize / window
) {}

/** Pure function: features → ranked strategies with explicit costs. */
public interface StrategyScorer {
    List<Score> score(WorkloadFeatures f);     // sorted ascending by estimatedCost
    record Score(StrategyId strategy, double estimatedCost, String rationale) {}
}

/** Decides whether to act on the scorer's recommendation. Stateful (hysteresis). */
public interface MorphPolicy {
    enum Decision { HOLD, MORPH }
    Decision evaluate(StrategyId current, List<StrategyScorer.Score> ranked,
                      WorkloadFeatures f, MorphHistory history);
}

/** Builds + validates + atomically swaps. Never mutates the live engine. */
public interface MorphController<K> {
    MorphResult evaluateAndMaybeMorph();   // called on cadence; returns what happened
    record MorphResult(boolean morphed, StrategyId from, StrategyId to,
                       boolean healthPassed, long buildNanos, String reason) {}
}
```

### 9.3 Health gate contract
`MorphController` must guarantee: build candidate → run `HealthCheck` → publish only
on pass. The check is total (returns a result, never throws into the caller):

```java
public interface HealthCheck<K> {
    record Report(boolean ok, List<String> failures);
    Report validate(Engine<K> candidate, List<K> expectedSortedKeys);
}
```
Required assertions in the default implementation: `inOrder(candidate)` equals
`expectedSortedKeys`; `size` matches; the candidate strategy's structural invariant
holds; and `select`/`rank` agree at a sampled set of ranks.

## 10. Worked decision trace

A concrete example of the loop making one decision, end to end, so the behavior is
unambiguous and directly testable.

```
Window summary (WorkloadFeatures):
  readFraction      = 0.94      ← lookup-dominated
  writeFraction     = 0.06
  accessSkew        = 0.71      ← strongly skewed toward a hot set
  meanSearchDepth   = 14.2      ← deeper than ideal for current RB tree (n≈9k)
  rotationsPerWrite = 0.3
  size              = 9_120
  growthRate        = +12 / window

StrategyScorer.score(features):
  1. Splay   cost 0.41   "high skew + read-heavy → hot keys near root"
  2. AVL     cost 0.55   "read-heavy favors shallowest tree, but skew unused"
  3. RedBlack cost 0.78  "incumbent; depth 14 vs ideal ~13, no locality gain"

MorphPolicy.evaluate(current=RedBlack, ranked, features, history):
  improvement = (0.78 - 0.41) / 0.78 = 47%   ≥ 20% threshold ........ pass
  cooldown    = 6_400 ops since last morph   ≥ K=4_000 ............. pass
  amortize    = est. savings over next window > O(n=9120) rebuild ... pass
  stability   = Splay won last 3 evaluations ....................... pass
  → Decision.MORPH to Splay

MorphController:
  build Splay engine from 9_120 keys ............ 3.1 ms
  HealthCheck: inOrder == sorted ✓  size ✓  splay-reachability ✓
               select/rank sample (32 ranks) ✓ .... ok
  atomic swap engine reference ................... published
  log → {from:RedBlack, to:Splay, improvementPct:47, buildMs:3.1, health:ok}
```

If `HealthCheck` had failed any clause, the candidate is dropped, the RedBlack
engine stays live (untouched throughout), and the log records `health:failed` with
the failing clause — no caller-visible error, no data loss.

## 11. Failure modes and responses

| Failure | Detection | Response |
|---|---|---|
| Candidate fails invariant | HealthCheck clause | discard candidate, keep incumbent, log clause |
| Morph thrashing (A→B→A…) | policy hysteresis + cooldown | suppressed by design; alert if cooldown repeatedly saturated |
| Monitor starvation (too few ops) | window count below min | HOLD; don't score on noise |
| Scorer tie / no clear winner | top-2 within margin | HOLD (stability gate) |
| Build OOM on huge n | catch during candidate build | abort morph, keep incumbent, raise amortization bar |
| Snapshot load corrupt | structural validation on load | return null/empty, log; never publish a bad engine |
| Concurrent read during swap | volatile publish semantics | reader sees old or new engine, never a torn one |

## 12. Observability schema

One structured event per evaluation (HOLD or MORPH), so adaptation is auditable.
Suggested fields:

```
event=morph_eval ts=<iso> n=<size>
  read=<f> write=<f> skew=<f> depth=<f> rotPerWrite=<f> growth=<f>
  scores=[RB:0.78, AVL:0.55, Splay:0.41]
  decision=MORPH from=RedBlack to=Splay improvementPct=47
  health=ok buildMs=3.1
```

Counters worth exporting: morphs/total-evals, health-fail rate, mean build time,
op-cost (mean search depth) before vs after each morph. The before/after depth delta
is the single best signal that adaptation is actually paying off.

## 13. Migration map — current code → target

| Today | Becomes | Notes |
|---|---|---|
| `TreeContext` | `AdaptiveOrderedSet<K>` facade | keep undo/persistence; add volatile engine + monitor hook |
| `RedBlackTree` | `Engine<K>` impl | already implements the rotation seam; generify + per-tree NIL (done) |
| `TreeStrategy` + impls | unchanged role | operate on `Engine<K>`; rotations stay default methods |
| `TreeGenome` | `StrategyScorer` + `WorkloadFeatures` | extract the *scoring* kernel; drop self-interpreting fitness |
| `GenomeDrivenTreeController` | `MorphController` + `MorphPolicy` | split "decide" from "execute"; add health gate |
| `TreeEcology` | (fold useful metrics into `WorkloadMonitor`) | retire biological analytics |
| `TreeAgent` (alien seed, swarm) | `experimental/` module | depends on core; core never imports it |
| `TreeCloner.snapshot` | reused by `MorphController` build-aside | candidate construction = a clean rebuild, not a clone of live state |
| `StrategyBattleRunner` | Phase-3 workload harness | becomes the benchmark of record, asserting convergence |
| `TreeDiagnostics.isValidRedBlack` | `HealthCheck` clause | per-strategy invariant validation, generalized |

The migration is incremental: the facade and engine seams (Phase 1) can land while
the old controller still runs, then the control plane (Phase 2) replaces the genome
machinery behind the same facade without touching call sites.

## 14. Open decisions still needed
- **Multiset vs set**: does `add` of a duplicate count, or is it a no-op? (Today:
  no-op.) Order-statistics semantics depend on this.
- **Comparator nullability / total order**: reject `null` keys, or define an ordering?
- **Eviction**: is there a max size / TTL, or is the set unbounded?
- **Morph cadence**: every N ops, time-based tick, or both? Background thread or
  inline on the writer? (Leaning: inline check, cheap; actual build can be inline
  since reads aren't blocked.)
- **Persistence format under generics**: the text snapshot assumes `int`; needs a
  pluggable key (de)serializer once keys are generic.

## 15. Application-driven design goals

These translate the target applications (live ranking, order books, exact
streaming-percentile monitoring, time-series/interval indexing, self-tuning
indexes) into concrete, testable architecture goals. Each goal names what it
*enables* and the acceptance criterion that proves it. The north-star application
— an **exact streaming-percentile monitor over a diurnal, hot-keyed workload** —
touches every goal below, which is why it's the integration target.

| # | Design goal | Enables | Acceptance criterion |
|---|---|---|---|
| G1 | **Exact order statistics under churn** — `rank/select/median/percentile/rangeCount` stay exact and O(log n) across inserts, deletes, and morphs | exact p50/p95/p99 monitoring, leaderboards, depth-of-book | property test vs a naive sorted-list oracle over random op sequences, including across a forced morph |
| G2 | **Sliding-window / eviction** — bounded set with evict-oldest or max-size, keeping order statistics correct on the survivors | streaming percentiles over "last N", recent-events indexing | O(log n) evict; percentile of window matches oracle as the window slides |
| G3 | **Hot-key adaptivity** — detect access skew and morph toward a locality-favoring strategy | trending feeds, hot price levels, recent-data queries | skewed synthetic workload converges to Splay; mean depth of the hot set drops measurably after morph |
| G4 | **Non-stationary responsiveness with stability** — adapt within a bounded op-count after a regime change, without thrashing | diurnal traffic, open/close bursts, event spikes | regime-change test reaches the expected strategy within K ops using ≤1 morph; steady workload triggers 0 morphs |
| G5 | **Bounded, predictable cost** — O(1) monitor ingest, O(log n) ops, zero tree-wide work on the hot path; morph O(n) but amortization-gated | low-latency serving (order books, SLO dashboards) | a guard/test asserts no per-op full-tree scan or snapshot; p99 op latency flat as n grows |
| G6 | **Safe live reconfiguration** — a morph never blocks readers and can never corrupt live data | always-on production services | concurrent-reader test observes no torn state during swap; a fault-injected invalid strategy is always rejected by the health gate, incumbent retained |
| G7 | **Pluggable strategies and keys** — add a balancing strategy or a key type without touching the facade or control plane | research testbed, domain-specific keys (timestamps, prices, IP ranges) | a new `Strategy` lands in isolation and is auto-eligible for scoring; `<K>` works for a non-int key end to end |
| G8 | **Explainable adaptation** — every evaluation emits features, scores, and decision | auditability, tuning, trust in production | any morph is reconstructable from a single log line (see §12) |
| G9 | **Exact range/interval surface** — `countInRange`, `rangeQuery`, and interval-overlap queries in O(log n + k) | interval/IP-range lookup, geometry, "events in window" | augmented queries match a brute-force oracle; interval augmentor validated under rotations and morphs |

### Non-goals (explicit boundaries)
- **Durability / transactions** — out of scope; pair with a real store if needed.
- **Larger-than-memory scale** — deferred to a future disk/B-tree engine (Phase 4); the in-memory engine assumes the working set fits in RAM.
- **Approximate percentiles** — not competing with t-digest/HDR on cost; the value
  proposition is *exactness* plus rank/range in the same structure.
- **Distributed / sharded operation** — single-node; sharding is an application-level
  concern layered above this engine.

### How the goals map to the build phases
G5–G6 are foundational and land with the engine/facade seams (Phase 1). G1, G7, G9
ride on the existing augmented tree plus the generic-key refactor. G3, G4, G8 are the
control plane (Phase 2) and are what the synthetic workload harness (Phase 3) exists
to verify. G2 (windowing) is the one net-new capability the current code lacks
entirely and should be designed alongside the facade so eviction and order-statistics
maintenance share the same write path.
