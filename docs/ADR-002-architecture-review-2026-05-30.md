# ADR-002: CSRBT architecture review — path to the adaptive end goal

**Status:** Proposed
**Date:** 2026-05-30
**Deciders:** project owner (Richmond)
**Supersedes/extends:** ADR-001; companion to `DESIGN-adaptive-engine.md`

## Context

After a session of audit-driven work, the **core is correct and well-tested**
(~295 tests): four balancing strategies (RB/AVL/Splay/Hybrid) with verified
invariants, exact O(log n) order statistics, interval augmentation, persistence,
undo/redo, **health-gated morphing** with a single morph authority and an
anti-thrash policy, a **sliding-window** mode, and structured morph observability.
The experimental surface (`TreeAgent`/`TreeEcology`) is isolated in its own
package; `PersistentTreeEngine` is stack-safe.

The layering is sound and is the project's main strength:

```
 client → TreeContext (facade: metrics, history, persistence, morph, windowing)
            └→ RedBlackTree (engine, implements MutableTree + TreeEngine)
                 └→ TreeStrategy (RB | AVL | Splay | Hybrid) via MutableTree seam
 control plane → GenomeDrivenTreeController → MorphPolicy → setStrategy (health gate)
 experimental → TreeAgent, TreeEcology (depend on core, never the reverse)
```

The `MutableTree` seam (getRoot/setRoot/getNIL/rotate) cleanly decouples
strategies from the engine, and the registry keeps `StructureType` honest. These
are good bones.

**Two architectural gaps remain between the code and the stated end goal**
(`DESIGN-adaptive-engine.md`):

1. **Keys are `int`-only.** The design calls generic `<K>` + `Comparator` "a
   prerequisite for real workloads" (strings, timestamps, prices, IP ranges).
   This is the largest untouched item (C5) and touches every class.
2. **Two adaptation models coexist.** The live path uses the `TreeGenome` /
   `GenomeDrivenTreeController` "self-interpreting fitness" model; the design
   specifies replacing it with four small, individually testable control-plane
   units (`WorkloadMonitor` → `StrategyScorer` → `MorphPolicy` → `MorphController`)
   fed by an O(1)-per-op event stream. Today there is no live `WorkloadMonitor`;
   morph signals are derived ad hoc (stress/entropy/fragmentation) rather than
   from a rolling workload feature vector.

This ADR decides **how to close those two gaps** without destabilizing the core.

## Decision

1. **Adopt generic `<K> implements ordered-set` keys via a *phased* refactor
   (Option C below), behind a new `OrderedSet<K>` facade**, keeping the current
   `int` facade working until the migration completes.
2. **Consolidate adaptation onto the design's control-plane units incrementally**,
   extracting the genome's *scoring kernel* into a pure `StrategyScorer` and adding
   a real `WorkloadMonitor`, while reusing the already-built `MorphPolicy` and the
   health-gated `setStrategy` as the `MorphController`'s executor.

Both are sequenced so each step ships green; neither is a big-bang rewrite.

## Options Considered (primary decision: the key model)

### Option A: Keep `int`-only
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (no change) |
| Cost | None now, blocks real workloads forever |
| Scalability | Fine algorithmically; useless for string/timestamp/price keys |
| Team familiarity | High |

**Pros:** zero risk; primitives avoid boxing.
**Cons:** permanently blocks the motivating applications (streaming percentiles
over real keys, order books, interval/IP indexing). The design explicitly calls
this a prerequisite. Non-starter for the end goal.

### Option B: Generic `<K>` — big-bang refactor
| Dimension | Assessment |
|-----------|------------|
| Complexity | High |
| Cost | One large, all-at-once change across every class + test |
| Scalability | Achieves the goal |
| Team familiarity | Medium |

**Pros:** done in one conceptual move; no dual-API period.
**Cons:** every file changes simultaneously; the build is red until the whole
thing compiles — exactly the failure mode seen this session when changing a single
method signature without a clean rebuild. High chance of latent errors; hard to
review; no intermediate safe point. Order statistics and the `augmentedValue`
overloading (size vs interval max-hi) complicate a blind sweep.

### Option C: Generic `<K>` — phased, behind a new facade (CHOSEN)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium, spread over steps |
| Cost | Several reviewable PRs; each ends green |
| Scalability | Achieves the goal |
| Team familiarity | High (incremental) |

Sequence:
1. Introduce `Node<K>` payload + `Comparator<K>` in `TreeNode1`/engine, defaulting
   to natural ordering for `Comparable`; keep all comparisons routed through the
   comparator. Internal only.
2. Generify `TreeStrategy`, rotations, and the engine against `<K>`; the
   `MutableTree` seam already isolates this.
3. Generify `OrderStatisticsOps` and the augmentor. Resolve the `augmentedValue`
   overloading by giving augmentors a typed payload slot rather than reusing one
   `int` field for both subtree-size and interval max-hi.
4. Add an `OrderedSet<K>` facade alongside `TreeContext`; make `TreeContext`
   (int) a thin adapter over `OrderedSet<Integer>` so existing callers/tests keep
   passing throughout.
5. Pluggable key (de)serializer for persistence (the text format currently assumes
   `int`).

**Pros:** every step is independently testable and ends with a green build; the
existing int API and its ~295 tests act as a regression harness during migration;
reviewable in slices.
**Cons:** a temporary dual-API period; boxing cost for `Integer` keys (revisit with
specialized primitives only if profiling shows it matters — a documented non-goal
for now).

## Trade-off Analysis

The decisive factor is **risk management on a now-stable core**, not end-state
shape (B and C reach the same place). This session demonstrated that even a
one-method signature change required a clean rebuild to surface breakage; a
big-bang generic refactor (B) multiplies that risk across the whole tree with no
safe intermediate. Option C trades a short-lived dual API for continuous
green-ness and reviewability — worth it.

For adaptation, the genome model and the four-unit control plane are
*functionally the same idea*; the design's units win on **testability and
explainability** (each is a pure function over an immutable feature vector). The
pragmatic path is not to delete the genome wholesale but to **extract its scoring
kernel** into `StrategyScorer` and feed it a real `WorkloadMonitor` — preserving
the working `MorphPolicy` + health-gated executor already in place.

## Consequences

**Easier:** real-world key types unlock the motivating apps; the control plane
becomes unit-testable with hand-built feature vectors; decisions stay auditable via
the existing `event=morph_eval` line.

**Harder (temporarily):** a dual `OrderedSet<K>` / `TreeContext` surface during
migration; the augmentor payload change ripples through order-statistics and
interval code; persistence needs a key serializer.

**To revisit:** boxing cost for primitive keys; whether the genome's
breeding/lineage machinery survives once `StrategyScorer` exists (likely demoted
to `experimental`); incremental/background morph for very large `n`.

## Action Items
1. [x] Land Option C step 1 (comparator-routed comparisons, internal) behind the
       existing int API; full suite stays green.
       — **DONE 2026-05-31**: introduced `TreeNode1.KEY_ORDER` (a
         `Comparator<Integer>` = natural order) as the single key-ordering
         authority; `compareTo` / new `compareKeyTo(int)` consult it, and every
         comparison site across the 4 strategies, order statistics, interval,
         diagnostics and the BST health-check now routes through them. No site
         compares `getData()` directly. Behaviour-identical by construction
         (natural int order); step 2 swaps `KEY_ORDER` for a pluggable
         `Comparator<K>` in one place. See `CHANGELOG-2026-05-31-comparator-seam.md`.
2. [~] Steps 2–3: generify strategies + order statistics; fix the `augmentedValue`
       overloading with a typed augmentor payload.
       — `augmentedValue` overloading **RESOLVED 2026-05-31**: subtree size promoted
         to an intrinsic `TreeNode1` field (sibling of height/black-height), order
         statistics repointed to it, so order-stats + interval now coexist on one
         tree. See `CHANGELOG-2026-05-31.md` and `AugmentorCoexistenceTest`.
         The generify-against-`<K>` portion of steps 2–3 is still pending.
3. [ ] Step 4: `OrderedSet<K>` facade; reduce `TreeContext` to an `Integer` adapter.
4. [ ] Step 5: pluggable key serializer for snapshots.
5. [ ] Extract `StrategyScorer` from `TreeGenome`; add `WorkloadMonitor` (O(1)/op
       rolling features); wire controller to feed it and drive the existing
       `MorphPolicy` + health-gated `setStrategy`.
6. [ ] Do C5 in a session with iterative compilation (clean rebuild between steps).
