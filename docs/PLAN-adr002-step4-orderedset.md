# PLAN: ADR-002 step 4 — `OrderedSet<K>` facade, `TreeContext` as the `Integer` adapter

**Status:** Ready to execute (blocked on step 2 landing green)
**Date:** 2026-06-02
**Owner:** Richmond
**Implements:** ADR-002 Option C, step 4 ("Add an `OrderedSet<K>` facade alongside
`TreeContext`; make `TreeContext` (int) a thin adapter over `OrderedSet<Integer>` so
existing callers/tests keep passing throughout"). Builds on the step-2 generic spine
(`PLAN-adr002-step2-generic-keys.md`, branch `adr002-step2-generics`).
**Prerequisite:** step 2 is green on the host (`RedBlackTree<K>`, `TreeEngine<K>`,
`OrderStatisticsOps<K>`, `TreeStrategy<K>` all exist; `TreeContext`/periphery pinned to
`<Integer>`). Do **not** start step 4 until then — it is purely additive on top of the
generic spine.

> **Why this is a written plan.** Unlike step 2 (a type-system sweep where the compiler is
> the safety net and the build is red until the spine is consistent), step 4 is mostly
> *additive then delegating*: a new generic class, two generified interfaces, one generified
> collaborator, and a re-plumb of `TreeContext` to delegate. Each phase ships green and the
> existing ~295-test int suite is the regression harness throughout. The thinking that needs
> writing down is the **scope boundary** — what moves into `OrderedSet<K>` vs. what stays
> `Integer` on `TreeContext` — because that boundary is what keeps step 4 from sprawling into
> steps 5+ (persistence) and into the still-`Integer` collaborators (intervals, cloning,
> history).

---

## 1. Goal and non-goals

**Goal.** Introduce `core.OrderedSet<K>` — a clean, generic, client-facing ordered-set facade
over the step-2 engine — and reduce `TreeContext` to an `Integer` adapter that delegates its
ordered-set behaviour to an internal `OrderedSet<Integer>` while retaining the genuinely
`Integer`-bound machinery. The `int` `TreeContext` public API and its ~295-test suite keep
passing unchanged throughout.

**In scope — what `OrderedSet<K>` owns (the key-type-agnostic facade):**

- Ordered-set ops: `add(K)` / `remove(K)` / `contains(K)` / `size()` / `inOrder():List<K>` /
  `clear()` / `isEmpty()`, including the dedup guard, size counter, and sliding-window
  eviction currently hand-rolled in `TreeContext`.
- Order statistics (a lazily-built internal `OrderStatisticsOps<K>`): `select(int)` / `rank(K)`
  / `successor(K)` / `predecessor(K)` / `median()` / `percentile(int)` / `minimum()` /
  `maximum()` / `countInRange(K,K)` / `rangeQuery(K,K)`.
- Health-gated strategy morph: `setStrategy(TreeStrategy<K>)` (rebuild-aside → validate →
  publish), carrying per-node tags across the morph.
- Windowing: `setMaxSize(int)` / `getMaxSize()` (FIFO over `K`).
- Metrics: `avgInsertTimeMs()` / `avgDeleteTimeMs()` / rotation count passthrough.
- Augmentation: `setAugmentor(TreeNode1.Augmentor<K>)` + per-insert augmentor stamping.
- Self-repair (`implements SelfHealingTree`) using `StrategyHealthCheck<K>` for validity.
- `comparator()` and an engine accessor (`getEngine()` / `getTree()` → `RedBlackTree<K>`).

**In scope — the supporting changes that unblock the above:**

- Generify the client interfaces: `OrderedCollection<K>`, `AugmentedTree<K>` (decision 2.4).
- Generify the one collaborator `OrderedSet<K>` needs: `StrategyHealthCheck<K>` (decision 2.3).
- Re-plumb `TreeContext` to delegate (decision 2.2).

**Explicitly out of scope (resist starting these here):**

- **Key (de)serialization — step 5.** `FilePersistenceAdapter` stays `int`; `saveSnapshot` /
  `loadSnapshot` stay on `TreeContext` (`Integer`). `TreePersistenceAdapter` is unchanged
  (it still names `TreeContext`).
- **Undo/redo over generic keys.** `TreeHistory` stays `Integer` and stays a `TreeContext`
  feature (`getHistory()`). It already drives through `context.add/remove`, so it keeps
  working against the adapter unchanged. A `TreeHistory<K>` is a later, separable piece.
- **Generic intervals.** `IntervalAugmentor` stays `Integer`; interval helpers stay on
  `TreeContext`. (The generic `Augmentor<K>` already exists; only the interval *implementation*
  is `Integer`-pinned.)
- **Cloning / clone-army.** `TreeCloner` and `deployCloneArmy` stay `Integer`/`TreeContext`-bound.
- **`TreeDiagnostics` generification.** It stays `Integer`/`TreeContext`-bound (it is a rich
  reporting tool used by `TreeContext`, `TreeCloner`, `TreeEcology`). `OrderedSet<K>` does **not**
  use it — it reuses `StrategyHealthCheck<K>`'s validity logic (decision 2.5).
- **Control-plane consolidation** (`StrategyScorer` / `WorkloadMonitor`) and **generifying
  `GenomeDrivenTreeController` / evolution / experimental** — separate ADR-002 action items.
  The controller stays `Integer` by continuing to drive `TreeContext`.
- **Primitive-key specialization / boxing** — documented ADR-002 non-goal.

---

## 2. Pivotal design decisions

### 2.1 `OrderedSet<K>` is a *new* class, not a rename of `TreeContext`

`TreeContext` carries a lot that is genuinely `Integer`-bound today (persistence text format,
interval augmentor, cloner, the experimental relic/clone-army hooks). Renaming it to `<K>`
would drag all of that into the generic world prematurely (it is steps 5+). Instead introduce
`core.OrderedSet<K>` as a **fresh, dependency-light** facade that wraps a `RedBlackTree<K>` and
a lazily-built `OrderStatisticsOps<K>`, and owns only the key-type-agnostic behaviour listed in
§1. `TreeContext` then *holds one* (`OrderedSet<Integer>`) and delegates to it.

This mirrors step 2's discipline: the generic core stays clean; the `Integer`-bound world is
pinned and layered on top.

### 2.2 `TreeContext` becomes a delegating adapter; `add` returns "did it insert"

Today `TreeContext.add(int)` does, in order: dedup-guard (`tree.contains`), `size++`,
`liveOrder.add`, augmentor-stamp, metrics, `history.recordAdd`, `updateMetadata`
(stress tracking), window eviction. After step 4, the **ordered-set part** of that lives in
`OrderedSet<Integer>.add(Integer)`; the **`TreeContext`-only side-effects** (undo history,
legacy stress auto-morph) stay on `TreeContext`.

To keep the side-effects firing *only on a real insert* (today's dedup guard guarantees this),
`OrderedSet<K>.add(K)` **returns `boolean`** (`true` = inserted, `false` = duplicate) — replacing
the current void-plus-`contains`-precheck. Then:

```java
// TreeContext (Integer adapter)
public void add(int value) {
    synchronized (lock) {
        if (!set.add(value)) return;          // dedup + size + window + augment all handled inside
        if (historyRecording) history.recordAdd(value);
        updateMetadata(value);                // legacy stress signal (auto-morph default off)
    }
}
```

`remove(int)` is symmetric (`if (!set.remove(value)) return;`). This is the one behavioural
subtlety in the whole step, and the ~295 tests (which assert size, dedup, undo, and window
semantics) are precisely the guard for it.

### 2.3 `StrategyHealthCheck` is the only collaborator that must be generified

`OrderedSet<K>.setStrategy` and `selfRepair` need to validate a freshly-built candidate. The
existing `StrategyHealthCheck.validate(RedBlackTree<Integer>, TreeStrategy<Integer>,
List<Integer>)` already does exactly the right checks (in-order equality, size, BST ordering,
per-strategy invariant, an order-statistics spot check) — and **every check is already
key-agnostic**: it uses `inOrder()`, `getRoot()`, `compareTo`, `select`/`rank`, none of which
touch a concrete `int`. So generify it to:

```java
public static <K> List<String> validate(RedBlackTree<K> candidate,
                                         TreeStrategy<K> strategy,
                                         List<K> expectedSortedKeys)
```

and its private helpers `isBst`/`isRedBlackValid`/`blackHeight`/`isHeightBalanced` to
`TreeNode1<K>`. This is the only collaborator `OrderedSet<K>` depends on; it is a low-risk,
internal generification. `TreeContext`'s existing call updates to `<Integer>` (inferred).

### 2.4 Generify the client interfaces; `SelfHealingTree` and `TreePersistenceAdapter` are untouched

- `OrderedCollection` → `OrderedCollection<K>` (`add(K)`/`remove(K)`/`contains(K)`/
  `inOrder():List<K>`/`size`/`clear`/`isEmpty`). `OrderedSet<K> implements OrderedCollection<K>`;
  `TreeContext implements OrderedCollection<Integer>` (its `add(int)` etc. satisfy the
  `Integer` instantiation by autoboxing at the boundary — verify the override resolves, mirroring
  the `PersistentTreeEngine` `add(Integer)` lesson from step 2).
- `AugmentedTree` → `AugmentedTree<K>` (`setAugmentor(TreeNode1.Augmentor<K>)`). Only two
  implementers after this: `OrderedSet<K>` and `TreeContext` (`<Integer>`). The step-2 doc
  already flagged this interface as "to revisit in step 4".
- `SelfHealingTree` — **unchanged** (`selfRepair():boolean` is key-agnostic).
- `TreePersistenceAdapter` — **unchanged** (it names `TreeContext` and is `Integer`/step-5).

### 2.5 `OrderedSet<K>` validity reuses `StrategyHealthCheck<K>`, not `TreeDiagnostics`

`TreeContext.selfRepair` currently leans on `TreeDiagnostics(this).isValidRedBlack()`, and
`TreeDiagnostics` is constructed from a `TreeContext` (tight coupling, plus richer reporting:
`emitRelicBeacon`, JSON, etc.). Rather than generify and decouple `TreeDiagnostics` (scope
blow-up), `OrderedSet<K>.selfRepair` validates via `StrategyHealthCheck<K>` (decision 2.3),
which already encapsulates RB-validity/BST/height checks against a `RedBlackTree<K>`.
`TreeDiagnostics` stays exactly as-is, serving `TreeContext` and the experimental package.

### 2.6 Tags carry through morph generically; the legacy stress auto-morph stays on `TreeContext`

Per-node tags (`TreeNode1.getTag/setTag`) are `String` and key-agnostic, so
`OrderedSet<K>.setStrategy` can capture a `Map<K,String>` before the rebuild and restore it
after (re-augmenting), exactly as `TreeContext` does today — fully generic. The **legacy
facade-driven stress auto-morph** (`frequencyMap`/`stressEvents`/`morphIfStressed`, default
**off**) depends on `TreeDiagnostics.hasNoRedRedAt` and is a `TreeContext`-era convenience; it
**stays on `TreeContext`** (`Integer`). The real morph authority — the control plane calling
`setStrategy` directly — is preserved generically in `OrderedSet<K>`.

---

## 3. What becomes `K` vs what stays `int`

**New / becomes `K`:**

| Symbol | Form |
|---|---|
| `core.OrderedSet<K>` (new) | the generic facade: `add/remove/contains(K)`, `inOrder():List<K>`, order-stats, `setStrategy(TreeStrategy<K>)`, `setMaxSize`, `setAugmentor(Augmentor<K>)`, `selfRepair`, `comparator()`, `getEngine():RedBlackTree<K>` |
| `OrderedCollection<K>` | `add/remove/contains(K)`, `inOrder():List<K>` |
| `AugmentedTree<K>` | `setAugmentor(TreeNode1.Augmentor<K>)` |
| `StrategyHealthCheck.validate` | `<K>(RedBlackTree<K>, TreeStrategy<K>, List<K>)` + private helpers on `TreeNode1<K>` |
| `OrderedSet` internal window | `LinkedHashSet<K> liveOrder`, `Map<K,String>` tag capture |

**Stays `int` / `Integer` (do not touch):**

| Symbol | Why |
|---|---|
| `TreeContext` public API (`add(int)`, …) and all its tests | it is the `Integer` adapter; the regression harness |
| `TreeHistory` (undo/redo) | deferred; drives through `context.add/remove`, keeps working |
| `FilePersistenceAdapter`, `saveSnapshot`/`loadSnapshot`, `TreePersistenceAdapter` | step 5 |
| `IntervalAugmentor` + interval helpers | intervals stay `Integer` |
| `TreeCloner`, `deployCloneArmy` | `Integer`/`TreeContext`-bound |
| `TreeDiagnostics` | `Integer`/`TreeContext` reporting tool (decision 2.5) |
| `GenomeDrivenTreeController`, evolution, experimental | drive `TreeContext` (`Integer`) |
| `OrderStatisticsOps.select(int)`/`percentile(int)` | positional, already `int` from step 2 |

---

## 4. Execution order (each phase ships green)

### Phase A — generify `StrategyHealthCheck` (internal, isolated)

1. `StrategyHealthCheck.validate` → `<K>(RedBlackTree<K>, TreeStrategy<K>, List<K>)`; private
   helpers to `TreeNode1<K>`. Update `TreeContext.setStrategy`'s call site (infers `<Integer>`).
   Nothing else references it. **Gate:** full suite green.

### Phase B — add `OrderedSet<K>` (purely additive)

2. Create `core.OrderedSet<K>` wrapping `RedBlackTree<K>` + lazy `OrderStatisticsOps<K>` +
   `StrategyHealthCheck<K>`. Implement the §1 surface. Provide
   `OrderedSet.withNaturalOrder(TreeStrategy<K>)` and a `(TreeStrategy<K>, Comparator<? super K>)`
   constructor, mirroring `RedBlackTree`. `add(K):boolean` / `remove(K):boolean`.
3. Add `OrderedSetTest` exercising **non-`Integer`** keys (e.g. `String`, and a custom
   `Comparator` such as reverse order) across add/remove/contains/inOrder, all order statistics,
   `setMaxSize` eviction, `setStrategy` morph (RB↔AVL↔Splay), and `selfRepair`. Nothing depends
   on `OrderedSet` yet. **Gate:** green (additive).

### Phase C — generify the client interfaces

4. `OrderedCollection<K>`, `AugmentedTree<K>`. `OrderedSet<K>` implements both; `TreeContext`
   implements the `<Integer>` instantiations (confirm `add(int)` satisfies `add(Integer)` —
   the `PersistentTreeEngine` override lesson). **Gate:** green.

### Phase D — reduce `TreeContext` to an adapter (the behaviour-sensitive phase)

5. Replace `TreeContext`'s hand-rolled ordered-set/order-stats/morph/windowing/metrics internals
   with an internal `private final OrderedSet<Integer> set` and delegation:
   - `add(int)`/`remove(int)` per decision 2.2 (fire history + stress only when `set` reports a
     real change);
   - `contains`/`size`/`inOrder`/`clear`/`setMaxSize`/`setAugmentor`/`setStrategy`/order-stats →
     delegate;
   - keep `getTree()` → `set.getEngine()` (many callers/tests + `TreeDiagnostics`/`TreeCloner`/
     `IntervalAugmentor` depend on it);
   - retain unchanged: `history`, `saveSnapshot`/`loadSnapshot`, interval helpers, `cloner`/
     `deployCloneArmy`, `emitRelicBeacon`, the legacy stress auto-morph, `selfRepair` (delegates).
   **Gate:** the ~295-test int suite is authoritative — it asserts dedup, size, undo/redo,
   window order, metrics, morph-preserves-contents, and order-stats. Green → done.

### Phase E — optional follow-through (only if trivially green)

6. Repoint internal callers that should program against `OrderedCollection<Integer>` rather than
   concrete `TreeContext` where it clarifies intent; update `README`/docs. No behaviour change.

---

## 5. Verification and rollback

- **Behaviour-identity argument:** at `K = Integer`, `OrderedSet<Integer>` performs exactly the
  ordered-set/order-stats/morph/window operations `TreeContext` did inline; `TreeContext` keeps
  its public `int` API and its `Integer`-only extras. So a green ~295-suite after Phase D means
  no semantic regression. New `OrderedSet<K>` tests prove the generic path on `String`/custom
  comparators.
- **Gate:** `ant clean test` after each phase. Phases A–C are additive/low-risk; Phase D is the
  one to watch (the delegation re-plumb).
- **Atomicity / rollback:** one branch (`adr002-step4-orderedset`), ideally one commit per phase.
  Phase B/C are independently revertible; Phase D is the only one that touches `TreeContext`
  internals — if it misbehaves, revert that file alone (the new `OrderedSet<K>` + interfaces from
  A–C remain valid and useful even without the adapter swap).
- **Watch-list (the spots a blind edit is most likely to trip):**
  - `add(int)` firing `history.recordAdd` / `updateMetadata` only on a *real* insert
    (rely on `set.add(...)` returning `boolean`, not a pre-`contains`).
  - window eviction order: `OrderedSet` must preserve FIFO `liveOrder` semantics and the
    `resyncLiveOrder` safety net after wholesale rebuilds (morph / loadSnapshot).
  - `loadSnapshot` replaces the engine wholesale — `TreeContext` must rebuild/repoint the
    internal `OrderedSet`'s view (or reconstruct the `OrderedSet` around the loaded engine).
  - `OrderedCollection<Integer>` override resolution for `add(int)` vs `add(Integer)`.

---

## 6. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| `TreeContext` delegation drifts semantics (double-recorded undo, wrong size, window order) | Medium | `add/remove` return-boolean contract (2.2); the ~295 tests assert all of these |
| `loadSnapshot` wholesale engine swap desyncs the internal `OrderedSet` | Medium | Reconstruct the `OrderedSet<Integer>` around the loaded engine; `resyncLiveOrder` |
| `OrderedCollection<Integer>` `add(int)` doesn't override `add(Integer)` | Low–Med | Mirror step-2 `PersistentTreeEngine` fix; verify on first compile |
| `AugmentedTree<K>` ripples beyond its two implementers | Low | Only `OrderedSet`/`TreeContext` implement it; grep confirms |
| Scope creep into history/persistence/intervals/cloning | Medium | §1 non-goals; those are steps 5+/separate |
| `StrategyHealthCheck<K>` generification subtlety | Low | All its checks already key-agnostic (uses `compareTo`/`select`/`rank`) |
| Boxing for `Integer` keys | Low | Documented ADR-002 non-goal |

---

## 7. First-edit checklist (start here, after step 2 is green on the host)

1. `git switch -c adr002-step4-orderedset` (off the merged step-2 work).
2. **Phase A:** generify `StrategyHealthCheck.validate` to `<K>`; fix the one `TreeContext`
   call site; `ant clean test` → green.
3. **Phase B:** write `core.OrderedSet<K>` (wrap `RedBlackTree<K>` + `OrderStatisticsOps<K>`;
   `add/remove` return `boolean`; window + morph + augmentor + self-repair); add
   `OrderedSetTest` with `String` keys + a reverse `Comparator`; `ant clean test` → green.
4. **Phase C:** `OrderedCollection<K>` + `AugmentedTree<K>`; pin `TreeContext` to the `<Integer>`
   instantiations; `ant clean test` → green.
5. **Phase D:** swap `TreeContext`'s internals to delegate to `OrderedSet<Integer>`, preserving
   the public `int` API and the `Integer`-only extras; `ant clean test` (the ~295 suite) → green.
6. Update `ADR-002` action item 4 → done, add `CHANGELOG-2026-…-orderedset.md`. Step 5
   (key serializer) is the next item.
