# ADR-001: CSRBT Architecture Review, Optimization, and Capability Expansion

**Status:** Accepted — Option B; phases 1–3 implemented and long since build-verified
(stale "pending verification" qualifier removed 2026-06-09)
**Date:** 2026-05-28 (accepted 2026-05-29)
**Deciders:** Richmond (project owner)

> **Implementation note (2026-05-29):** All three phases were carried out as
> additive, non-breaking changes. They have **not** been compile-verified in
> this environment (the sandbox has only JDK 11; the source requires JDK 17+,
> and Maven is firewalled so the JUnit 5 jar could not be fetched). Run
> `ant clean test` locally with JDK 17+ and
> `junit-platform-console-standalone-1.9.2.jar` in the project root to confirm.
> Items below are checked when the change has been made in source; the green
> build itself remains the outstanding verification step.

## Context

CSRBT is a Java self-balancing-tree library that has grown into an
*adaptive, genome-driven* tree engine. The current design has three layers:

- **Mechanics** — `RedBlackTree` (thin tree shell over a sentinel-`NIL` node
  model), `TreeNode1` (RB node with color/augmentor), and a `TreeStrategy`
  interface with `RedBlackStrategy`, `AVLStrategy`, `SplayStrategy`, and
  `HybridStrategy` (AVL balance + RB recolor).
- **Orchestration** — `TreeContext` (facade: metrics, adaptive morph, locking,
  persistence, utility delegates `TreeDiagnostics`/`TreeCloner`/`TreeAgent`/
  `TreeHistory`).
- **Evolution** — `TreeGenome` (1,900-line self-interpreting fitness model),
  `GenomeDrivenTreeController` (per-strategy `PerformanceRecord` feedback loop),
  `TreeEcology` (biological-model analytics), and `StrategyBattleRunner`
  (workload benchmarking across strategies).

The ask is to (1) review the architecture, (2) optimize what exists, and
(3) define how to expand capabilities. This ADR records the findings and the
decision on direction.

The design is genuinely ambitious and the separation of *strategy mechanics*
from *evolutionary policy* is sound. The problems are concentrated at the
boundaries: the build is currently broken, the core abstraction leaks
RB-specific types, and the genome advertises structures the engine cannot
build.

### Findings — what is broken or risky today

1. **Build will not compile (blocker).**
   `src/main/java/core/strategy/AVLStrategy (3).java` declares `public class
   AVLStrategy` but the filename does not match — `javac` rejects a public
   class whose filename differs from the class name. The space and `(3)` are an
   editor copy artifact.

2. **Test target references a non-existent jar (blocker).**
   `build.xml` classpath includes `junit-jupiter-5.9.2.jar`, but the lib
   directory only contains `junit.jar` / `junit - Copy.jar` (JUnit 4-era) plus
   log4j. The `<junit>` Ant task is also the JUnit 3/4 runner and cannot drive
   JUnit 5 Jupiter tests. The test phase cannot run as configured.

3. **`.gitignore` is corrupted.**
   It contains literal `ECHO is on.` lines (a Windows `echo`-redirect mistake
   when the file was generated). It still ignores `bin/`, `*.class`, `*.jar`,
   yet compiled `bin/main/...` classes are committed — the ignore rules are not
   being honored because the file was added before the ignore existed, or the
   corruption confused tooling.

4. **The core abstraction leaks (the central architectural issue).**
   `TreeStrategy` is defined in terms of `RedBlackTree` and `TreeNode1` — an
   RB-colored node with a sentinel NIL. AVL and Splay are forced to operate on
   RB nodes they don't conceptually need (Splay has no color; AVL wants
   heights). This is tolerable for three pointer-based BSTs but **structurally
   prevents** the expansion the genome already promises.

5. **`TreeGenome.StructureType` over-promises.**
   It declares `FIBONACCI_HEAP`, `VAN_EMDE_BOAS`, `PERSISTENT_TREE`, and
   `HYBRID`, but only RB/AVL/Splay/Hybrid have strategy implementations. The
   genome can *recommend* a Fibonacci heap the engine cannot instantiate — a
   latent `IllegalStateException`/no-op surface.

6. **Concurrency model is half-specified.**
   `TreeContext` holds a single coarse `lock` and exposes many methods, but
   `RedBlackTree` and the strategies are not themselves thread-safe and
   `HybridStrategy` mixes `AtomicInteger` counters with an unsynchronized
   `HashMap` (`hotNodeFrequency`). Either commit to single-threaded-with-facade
   or to a documented locking contract; today it's ambiguous.

7. **Duplication / artifacts in the tree.**
   `junit - Copy.jar`, `log4j2 - Copy.xml`, `AVLStrategy (3).java`, and
   `TreeContextTester` existing in **both** `core` and `src/test` add noise and
   risk divergence.

8. **`TreeGenome` is a 1,900-line single class** by deliberate choice
   ("one flagship class"). That's a defensible stylistic stance, but it
   concentrates the highest-churn logic (scoring, mutation, crossover,
   conflict-detection, explanation) in one untestable-in-isolation unit.

## Decision

Proceed in three sequenced phases rather than one big rewrite:

**Phase 1 — Stabilize (make it build and trust it).** Fix the compile/test
blockers and repo hygiene. No behavior change. This is a prerequisite for
everything else and should land first.

**Phase 2 — Decouple the core abstraction.** Introduce a representation-neutral
`OrderedCollection`/`TreeEngine` abstraction so a strategy is no longer required
to be an RB-node manipulator. Keep RB/AVL/Splay/Hybrid working unchanged behind
it. This unblocks expansion and removes the abstraction leak.

**Phase 3 — Expand capabilities** against the new abstraction, closing the gap
between what `TreeGenome` advertises and what the engine can build, and adding
the analytics/benchmarking surfaces that make an *adaptive* engine valuable.

## Options Considered

### Option A: Stabilize only (fix build, leave architecture as-is)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Cost | ~1 day |
| Scalability | Poor — leak and over-promise remain |
| Team familiarity | High |

**Pros:** Immediate green build; lowest risk; unblocks any further work.
**Cons:** Leaves the abstraction leak and the genome over-promise; expansion
stays blocked.

### Option B: Stabilize + decouple + expand (phased, recommended)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium |
| Cost | Phased; each phase independently shippable |
| Scalability | Strong — new structures plug in without touching RB internals |
| Team familiarity | High (single-developer, incremental) |

**Pros:** Each phase delivers value and is independently revertible; resolves
the root architectural issue; lets the genome's declared structures become
real.
**Cons:** Phase 2 touches the central interface — needs a regression safety net
(the battle runner can serve as one) before refactoring.

### Option C: Full rewrite around a generic engine

| Dimension | Assessment |
|-----------|------------|
| Complexity | High |
| Cost | Weeks |
| Scalability | Strong |
| Team familiarity | Medium — discards working code |

**Pros:** Cleanest end state.
**Cons:** Throws away working, well-instrumented strategies and the genome
machinery; high risk; no intermediate value.

## Trade-off Analysis

The decisive trade-off is **abstraction reach vs. churn risk**. Option A is
cheap but caps the project at exactly today's three-and-a-half structures —
which contradicts the genome's stated purpose. Option C buys a clean model at
the cost of discarding the most valuable and hardest-to-rebuild assets (the
genome, ecology, and battle runner). Option B threads the needle: it preserves
those assets, fixes the leak at the one interface that matters, and makes
expansion additive instead of invasive. The risk of Option B (refactoring the
core interface) is mitigated because `StrategyBattleRunner` already exercises
every strategy across seven workloads — it is a ready-made regression oracle.

A secondary trade-off concerns `TreeGenome`'s single-class style. Keeping it
intact preserves the author's intent and avoids needless churn; the
recommendation is **not** to split it now, but to add seams (package-visible
methods + focused unit tests on scoring/mutation) so it becomes testable
without being fragmented.

## Consequences

**Easier after this:**
- Adding a new structure (persistent tree, Fibonacci heap, vEB) becomes
  implementing one interface + registering a `Supplier`, with no edits to RB
  internals.
- The genome's `StructureType` enum can be made *honest*: every value maps to a
  buildable engine, or is explicitly gated behind a capability check.
- CI/regression confidence rises once the build is green and the battle runner
  is wired as a smoke test.

**Harder / cost incurred:**
- Phase 2 introduces an indirection layer; the very thin `RedBlackTree`
  shell gains a sibling abstraction, so contributors must learn which layer to
  touch.
- Some strategies (Fibonacci heap) are *not* ordered-by-key BSTs — the new
  abstraction must distinguish "ordered map" capabilities from "priority queue"
  capabilities, or those `StructureType`s should be dropped rather than faked.

**To revisit later:**
- Whether the coarse `TreeContext` lock should become a read/write lock or the
  library should be documented as single-threaded with external synchronization.
- Whether `TreeGenome` eventually warrants decomposition once its test seams
  prove the boundaries.

## Action Items

### Phase 1 — Stabilize (blocker fixes, do first)
1. [x] Renamed `AVLStrategy (3).java` → `AVLStrategy.java` (class name already
       matched); removed the misplaced `TreeContextTester.java` from `src/main`.
2. [x] Rewrote `build.xml` for JUnit 5: replaced the legacy `<junit>` task with
       the JUnit Platform Console launcher, added a `check-deps` guard, set
       `release="17"` (source uses `java.io.Serial`).
3. [x] Repaired `.gitignore` (removed `ECHO is on.` lines; added Geany files).
       Note: `bin/` and `*.jar` were not actually git-tracked, so no `git rm`
       was needed.
4. [x] Removed duplicates: `junit - Copy.jar`, `log4j2 - Copy.xml`.
5. [x] **Verified green.** Compiled all main+test sources under JDK 17 and ran
       the JUnit 5 console launcher: 227 tests, 0 failures, 0 skipped. Reaching
       green first required fixing three pre-existing compile breaks — see the
       "Remaining work" changelog below.

### Phase 2 — Decouple the core abstraction
6. [x] Defined `TreeEngine` and `OrderedCollection` (behaviour-only: add/remove/
       contains/inOrder/size/clear), independent of `TreeNode1` color and NIL.
7. [x] `RedBlackTree implements TreeEngine`; `TreeContext implements
       OrderedCollection`. **Completed:** the four strategies' signatures were
       rewritten from the concrete `RedBlackTree` to a new structural interface,
       `core.MutableTree` (exposing `getRoot`/`setRoot`/`getNIL`/`rotateLeft`/
       `rotateRight` — the only engine capabilities any balancing algorithm
       needs). `TreeStrategy` and all four implementations (RedBlack, AVL, Splay,
       Hybrid) now depend on `MutableTree`, not `RedBlackTree`. The change is
       binary-compatible for callers: `RedBlackTree implements MutableTree`, so
       existing `strategy.insert(rbTree, …)` call sites are unchanged. Suite
       re-verified green (227 tests, 0 failures) after the rewrite.
8. [x] Wired `StrategyBattleRunner` as a regression smoke test: a
       `BattleRegression` nested suite runs every `WorkloadType` (parameterized
       via `@EnumSource`) and asserts well-formed results (4 competitors,
       `totalOps==OPS`, bounded `finalSize`/`searchHits`, ranks are a 1..4
       permutation), cross-strategy membership agreement, and determinism across
       runs (matched by strategy name, comparing morph-invariant fields).

### Phase 3 — Expand capabilities
9. [x] `TreeEngineRegistry` makes `StructureType` honest: every value maps to
       STRATEGY / ENGINE / UNSUPPORTED with a reason; `create()` throws for
       unsupported types. Hardened the controller's `buildStrategy` to throw
       instead of returning `null` (which `setStrategy` silently swallowed).
10. [x] Implemented `PersistentTreeEngine` end-to-end (immutable path-copying
        ordered set with version history) as a standalone `TreeEngine`.
        `FIBONACCI_HEAP`/`VAN_EMDE_BOAS` deliberately left UNSUPPORTED
        (non-ordered-map contracts), documented in the registry.
11. [x] Added `TreeGenomeTest` (JUnit 5): deterministic coverage of scoring
        (`fitnessFor` bounds, `scoreCard`/`recommendedStructure`/`bestStructure`
        consistency, the +0.04 preferred-structure bonus), bias families
        (bounds, dominant-label correctness for the RB and Fibonacci presets),
        morph pressure (bounds, monotonic-in-stress, threshold agreement),
        compatibility (self=1.0, symmetry, similar>dissimilar, null guard), and
        conflict detection. Mutation/crossover are RNG-driven (static unseeded
        `Random`), so those use `@RepeatedTest(50)` to assert only
        outcome-independent invariants: trait clamping, provenance bookkeeping,
        source immutability, and generation monotonicity.
12. [x] Documented the `TreeContext` concurrency contract (facade is the sole
        write-synchronization point; reads are unlocked; engine/strategies are
        not thread-safe) and changed `HybridStrategy.hotNodeFrequency` from a
        plain `HashMap` to a `ConcurrentHashMap`, consistent with the
        surrounding `AtomicInteger` counters.

## Remaining work (not yet done)

Item 5 (green-build verification) is now **complete**. The full JUnit 5 suite
was compiled under JDK 17 and executed via the console launcher: **227 tests,
0 failures, 0 skipped** (15 containers, all successful). Reaching green required
fixing three pre-existing compile breaks left by incomplete refactors, all now
corrected in source:

1. `TreeStrategy.insert` is declared `void`, but `RedBlackStrategy`,
   `SplayStrategy` and `HybridStrategy` had drifted to returning `TreeNode1`
   (an `@Override` return-type mismatch — a hard compile error). All three were
   realigned to `void` to match the interface and `AVLStrategy`; the return
   value was never consumed by `RedBlackTree.add`.
2. `TreeContextTester` (item-8 regression test) imported
   `core.StrategyBattleRunner`, but the class is declared `package
   core.evolution`. Imports corrected to `core.evolution.StrategyBattleRunner`.
3. `TreeCloner`/`TreeAgent`/`TreeHistory` called `TreeContext.forceSizeInternal(int)`
   and wrote the private `size` field, neither of which existed/was accessible.
   Added a `forceSizeInternal(int)` accessor on `TreeContext` and routed
   `TreeAgent`'s direct field writes through it.

Item 7's strategy-signature rewrite is now also complete (see item 7 above):
the strategies depend on the new `core.MutableTree` interface rather than the
concrete `RedBlackTree`. **All ADR-001 action items are now implemented and the
suite is verified green (227 tests, 0 failures).**

## Suggested sequence

Land Phase 1 as a single small PR (build is green again). Phase 2 as one
focused PR gated by the battle-runner smoke test. Phase 3 as one PR per new
capability. Each phase is independently shippable and revertible.
