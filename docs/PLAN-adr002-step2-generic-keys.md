# PLAN: ADR-002 step 2 — generify the tree against `<K>`

**Status:** Ready to execute (not yet started)
**Date:** 2026-06-01
**Owner:** Richmond
**Implements:** ADR-002 Option C, steps 2–3 (the generic-key portion). Builds directly on the
step-1 comparator seam (`CHANGELOG-2026-05-31-comparator-seam.md`, committed `ab75f2d`).
**Prerequisite met:** every key comparison already routes through `TreeNode1.compareTo` /
`compareKeyTo` and the `KEY_ORDER` authority; subtree size is already an intrinsic field
(`augmentedValue` overloading resolved). So this step changes *one* ordering authority and
threads a type parameter — it does not re-sweep comparison sites.

> **Why this is a written plan, not a code sweep.** This is a type-system refactor, not a
> behaviour-preserving one. The compiler is the safety net, and the build is red until the
> whole spine is internally consistent. The prep sandbox is JRE-only (no `javac`), so the
> sweep must be executed on a JDK host with **iterative compilation between sub-steps**. This
> document is the executable order of operations + the design decisions that make it tractable.

---

## 1. Goal and non-goals

**Goal.** Make the engine spine generic over the key type `K`, ordered by a pluggable
`Comparator<? super K>`, defaulting to natural order for `Comparable` keys. The existing
`int` `TreeContext` facade and its ~295-test regression suite keep passing throughout
(it becomes a thin `RedBlackTree<Integer>` user).

**In scope (the generic spine):** `TreeNode1<K>`, `MutableTree<K>`, `TreeStrategy<K>` + the
four strategies, `RedBlackTree<K>`, `TreeEngine<K>`, `OrderStatisticsOps<K>`.

**Explicitly out of scope (later ADR-002 steps — do NOT start here):**

- The `OrderedSet<K>` client facade and reducing `TreeContext` to an `Integer` adapter — **step 4**.
- A pluggable key (de)serializer for snapshots — **step 5**. `FilePersistenceAdapter` stays `int`.
- Generic *intervals* (typed high endpoint / typed max-hi). `IntervalAugmentor` stays
  integer-interval and gets **pinned to `Integer`**, not generified.
- A second type parameter for the augment payload (`<K, A>`). See decision 3 — **we keep one type
  parameter and leave `augmentedValue` as `int`.** This is the single biggest scope-limiter.
- Primitive-key specialization to avoid `Integer` boxing — a documented non-goal (ADR-002).

---

## 2. Pivotal design decisions

These five decisions are what turn a "wall of generics errors" into a bounded, ordered sweep.
Each is grounded in a specific fact found in the code.

### 2.1 Where the comparator lives: on the per-tree **sentinel**, read by nodes via `nilSentinel`

Today `KEY_ORDER` is `static final Comparator<Integer>` on `TreeNode1` (line 36). A generic class
**cannot** have a `static` field of type `Comparator<K>`, so the authority must become per-instance.

Every node already holds a reference to its per-tree `nilSentinel` (set in the constructor), and
the sentinel is created once per engine (`RedBlackTree.NIL = TreeNode1.createNil()`, line 23).
**Put the `Comparator<? super K> keyOrder` on the sentinel, and have `compareTo` / `compareKeyTo`
read `this.nilSentinel.keyOrder`.**

```java
// TreeNode1<K>
private final Comparator<? super K> keyOrder;   // set on the sentinel; real nodes copy the ref from nil at construction

public int compareTo(TreeNode1<K> other) { return keyOrder.compare(this.data, other.data); }
public int compareKeyTo(K otherKey)      { return keyOrder.compare(this.data, otherKey);   }
```

**Why this is the low-churn path:** it keeps step 1's chokepoint exactly where it is (on the
node), so none of the ~26 comparison call-sites move, and it keeps `createNode(data, nil)` at
**two args** — a new node copies the comparator reference from the `nil` sentinel it already
receives (`this.keyOrder = nil.keyOrder`), so no call-site passes a comparator. The sentinel is
the source of truth (set once via `createNil(Comparator)`); the per-node cost is a single
reference field, which is negligible against the already-accepted `Integer` boxing. The only new
plumbing is `createNil(Comparator)` and one extra constructor arg on the engine.

**Considered alternative:** move comparisons off the node onto the engine (`tree.compare(a,b)`).
Rejected for this step — it would relocate every comparison site into the strategies/order-stats
and undo step 1's deliberate placement, for no functional gain.

### 2.2 `K` is unbounded; natural order is a convenience factory

Declare `class TreeNode1<K>` (no `extends Comparable` bound). Ordering is supplied by the
comparator, which is the whole point — it must support keys that aren't `Comparable`. Provide
natural-order convenience constructors that add the bound only where used:

```java
public static <K extends Comparable<? super K>> RedBlackTree<K> withNaturalOrder(TreeStrategy<K> s) {
    return new RedBlackTree<>(s, Comparator.naturalOrder());
}
```

`TreeContext` (Integer) calls `new RedBlackTree<>(strategy, Comparator.naturalOrder())`.

### 2.3 `augmentedValue` stays `int` — one type parameter, not two

Both current augmentors write an `int`: the default writes a node count, `IntervalAugmentor`
writes an `int` max-hi (parsed from a string tag). Neither touches `K`. So **keep
`augmentedValue` as `int`** and keep a single type parameter `<K>`. `Augmentor<K>` takes
`TreeNode1<K>` but its body remains `int`-valued.

This is the decision that prevents the `<K, A>` explosion (which would thread a second parameter
through node, engine, strategies, and order-stats). A typed augment payload is a separate, later
piece of work; nothing in this step needs it.

### 2.4 Static `NIL` and `defaultAugmentor`: one deletion, one shared-instance factory

- **`public static final TreeNode1 NIL` (line 46): delete it.** A generic class can't hold a
  `static TreeNode1<K>`. The codebase already mandates per-instance sentinels (the field's own
  Javadoc says *"Engines should NOT use this directly"*). The **only** external consumer is
  `RegressionFixesTest` (lines 378, 379, 389: `createNode(5, TreeNode1.NIL)`); that test moves to a
  locally-created sentinel. Removing the shared static is strictly in the direction the design
  already points.

- **`defaultAugmentor` (line 15): keep ONE shared instance behind a generic factory.** It is
  referenced *by identity* (`augmentor != TreeNode1.defaultAugmentor`) in seven places
  (`TreeContext` ×4 — lines 52, 135, 240, 332; `TreeCloner` ×2 — lines 70, 163; `TreeHistory` ×1 —
  line 293). A naive `static <K> Augmentor<K> defaultAugmentor()` that builds a *new* lambda each
  call would silently break every one of those `!=` checks. Instead keep a single shared instance
  and hand it out cast:

  ```java
  private static final Augmentor<?> DEFAULT_AUGMENTOR = node -> { /* same body, writes int augmentedValue */ };
  @SuppressWarnings("unchecked")
  public static <K> Augmentor<K> defaultAugmentor() { return (Augmentor<K>) DEFAULT_AUGMENTOR; }
  ```

  The body never touches `K`, so sharing one instance across all `K` is type-safe, and identity
  holds because the cast returns the same object. Call-sites change from the field reference
  `TreeNode1.defaultAugmentor` to the method call `TreeNode1.defaultAugmentor()`.

### 2.5 The two key-arithmetic breakers leave the generic node

These are the only spots in `core` that do *arithmetic* on a key, which is undefined for generic
`K`. Both are "experimental theatrics" (the codebase's own term, `TreeContext` line 370):

- **`TreeNode1.alienSpawn(...)` (line 508):** `this.data ± rng.nextInt(...)`. **Dead** — its only
  callers are its own recursion; `experimental.TreeAgent` has an independent
  `alienSpawnIterative`. **Delete it from `TreeNode1`.**
- **`TreeNode1.mutateAugmentorByDepth(int)` (line 530):** `node.getData() * 2`, `getData() *
  getData()`. **One caller:** `TreeCloner.mutantClone()` (line 138). **Relocate** it to a static
  `int`-specialised helper (in `TreeCloner` or an experimental util) operating on
  `TreeNode1<Integer>`; with `K = Integer`, `getData()` unboxes and the arithmetic compiles.
  `mutantClone` calls the helper instead of the node method.

After this, the generic `TreeNode1<K>` contains **no key arithmetic** — only ordering (via the
comparator) and structural/`int` metadata.

---

## 3. What becomes `K` vs what stays `int`

**Becomes `K`** (key-typed):

| Symbol | Today | After |
|---|---|---|
| `TreeNode1.data` / `getData()` | `int` | `K` |
| `TreeNode1.compareKeyTo(int)` | `int` arg | `K` arg |
| `TreeNode1` constructors / `createNode` / `createNodeWithAugment` | `int data` | `K data` |
| `TreeEngine.add/remove/contains` | `int` | `K` |
| `TreeEngine.inOrder()` | `List<Integer>` | `List<K>` |
| `MutableTree` (root/NIL/rotate node params) | `TreeNode1` | `TreeNode1<K>` |
| `TreeStrategy.insert/fixInsert/delete` node param | `TreeNode1` | `TreeNode1<K>` |
| `TreeStrategy.search(MutableTree, int)` | `int value` | `K value` |
| `HybridStrategy.recordAccess(int)` | `int` | `K` |
| `RedBlackTree.add/remove/contains`, fields `root`/`NIL`/`strategy` | `int` / raw | `K` / `<K>` |
| `OrderStatisticsOps.rank / successor / predecessor` | `int value` | `K value` |
| `OrderStatisticsOps.countInRange(int,int)` / `rangeQuery(int,int)` | `int` / `List<Integer>` | `K` / `List<K>` |
| `OrderStatisticsOps.findNode / rankCeiling / rankFloor` (private) | `int` | `K` |

**Stays `int`** (genuinely positional / structural — do **not** touch):

| Symbol | Why |
|---|---|
| `OrderStatisticsOps.select(int rank)` | rank is a 1-indexed position, not a key |
| `OrderStatisticsOps.percentile(int pct)` | 0–100 percentile, not a key |
| `TreeNode1.augmentedValue`, `size`, `height`, `blackHeight`, `depth()` | structural metadata (decision 2.3) |
| `RedBlackTree.size()` | a count |
| `TreeContext` public API (`add(int)`, `Map<Integer,…>`, `LinkedHashSet<Integer>`, metrics) | it is the `Integer` adapter for this step |
| `FilePersistenceAdapter` text format | `int` until step 5 |
| `IntervalAugmentor` lo/hi/max-hi | pinned to `Integer` this step |

---

## 4. Execution order

Do this **on a branch** (`adr002-step2-generics`) and land the whole thing as **one atomic
green commit** — the same lesson the fax-trident half-finished multi-module restructure taught:
a type refactor that spans the module is either green or it isn't; there is no useful partial.
Use `ant compile` (fast) between sub-steps to shrink the error surface; use `ant clean test`
only as the final gate.

### Phase A — the generic spine (one compile unit; chase the compiler outward)

Adding `<K>` to `TreeNode1` breaks everything that references it at once; that's expected. Work
in this order and treat each compile run's error list as the worklist for the next file:

1. **`TreeNode1` → `TreeNode1<K>`.** This is the bulk of the thinking; everything else is
   mechanical once it's right. Concretely:
   - `class TreeNode1<K> implements Comparable<TreeNode1<K>>, Cloneable`
   - `data` / `getData()` → `K`; constructors take `K data`.
   - Replace `static KEY_ORDER` with a sentinel-held `Comparator<? super K> keyOrder`
     (decision 2.1). Add `createNil(Comparator<? super K>)`; keep `createNode(K, TreeNode1<K>)`
     two-arg (inherits the comparator via the sentinel).
   - `compareTo(TreeNode1<K>)` / `compareKeyTo(K)` read `nilSentinel.keyOrder`.
   - `Augmentor` → `Augmentor<K>`; `defaultAugmentor` → shared-instance factory (decision 2.4).
   - **Delete** static `NIL` and `alienSpawn`; **relocate** `mutateAugmentorByDepth`
     (decision 2.5).
   - `augmentedValue`/`size`/`height`/`blackHeight` stay `int` (decision 2.3).
2. **`MutableTree` → `MutableTree<K>`** — every `TreeNode1` becomes `TreeNode1<K>`. Trivial.
3. **`TreeStrategy<K>`** + **`RedBlackStrategy` / `AVLStrategy` / `SplayStrategy` /
   `HybridStrategy`.** All four are purely structural except `search(MutableTree<K>, K value)`
   and `HybridStrategy.recordAccess(K)`. The default `rotateLeft/rotateRight` use only
   `setLeftLocal/…/setParent` — they generify by changing `TreeNode1`→`TreeNode1<K>` only.
   *(Verified: no strategy does key arithmetic; the step-1 seam already removed the
   `value - getData()` subtraction.)*
4. **`TreeEngine<K>`** (`add(K)`, `remove(K)`, `contains(K)`, `List<K> inOrder()`).
5. **`RedBlackTree<K> implements TreeEngine<K>, MutableTree<K>`** — fields `TreeNode1<K> root`,
   `TreeNode1<K> NIL`, `TreeStrategy<K> strategy`; constructor gains
   `Comparator<? super K>`; add the `withNaturalOrder` factory (decision 2.2). `inOrder()`
   collects `List<K>`.
6. **`OrderStatisticsOps<K>`** — holds `RedBlackTree<K>`; `rank/successor/predecessor/
   countInRange/rangeQuery/findNode/rankCeiling/rankFloor` go `K`; **`select`/`percentile`/
   `subtreeSize` stay `int`** (decision: §3). `rangeQuery` returns `List<K>`.

At the end of Phase A the spine compiles in isolation, but the **periphery** (Phase B) is now
red — that red set is the proof Phase A is internally consistent, and it is exactly the file
list below.

### Phase B — pin the `int` world to `<Integer>` (restores green against the existing suite)

None of these become generic; they each name `Integer` so the existing behaviour and tests are
unchanged.

7. **`TreeContext`** — `RedBlackTree<Integer>`, `TreeStrategy<Integer>`,
   `TreeNode1.Augmentor<Integer>`, internal `TreeNode1<Integer>` locals; construct via
   `new RedBlackTree<>(strategy, Comparator.naturalOrder())`; switch the seven
   `defaultAugmentor` references to `defaultAugmentor()` (decision 2.4). Public `add(int)` etc.
   stay `int` (autobox at the boundary).
8. **`IntervalAugmentor implements TreeNode1.Augmentor<Integer>`**; static methods operate on
   `TreeNode1<Integer>` / `TreeContext`. Hi/max-hi stay `int` (string-tag-parsed). Add a one-line
   note that typed intervals are deferred.
9. **Utils:** `TreeCloner`, `TreeDiagnostics`, `TreeHistory`, `StrategyHealthCheck` →
   `TreeNode1<Integer>` / `RedBlackTree<Integer>`. `TreeCloner.mutantClone` calls the relocated
   `mutateAugmentorByDepth` helper (decision 2.5).
10. **Construction hub + second engine:**
    - `TreeEngineRegistry` builds `Integer` engines: `Supplier<TreeEngine<Integer>>`,
      `new RedBlackTree<Integer>(s.get(), Comparator.naturalOrder())`,
      `create(...) : TreeEngine<Integer>`.
    - **`PersistentTreeEngine implements TreeEngine<Integer>`** — it is a *second* `TreeEngine`
      implementer with its own int-keyed `Node`. Its `add/remove/contains` params must become
      `Integer` to satisfy `TreeEngine<Integer>` (an `add(int)` does **not** override
      `add(Integer)`). Small but mandatory.
11. **Evolution** (`GenomeDrivenTreeController`, `StrategyBattleRunner`) — change `TreeStrategy`
    → `TreeStrategy<Integer>` in the `Supplier`/`buildStrategy` signatures. The genome's own
    arithmetic is on `double` traits (`TreeGenome.mutateTrait`), **not** keys — evolution is
    otherwise insulated.
12. **Experimental** (`TreeAgent`, `TreeEcology`) — `TreeNode1<Integer>`; `TreeAgent`'s own
    `getData() ± rng.nextInt(...)` unboxes under `Integer`.
13. **Persistence** (`FilePersistenceAdapter`) — `TreeNode1<Integer>`; `createNode(data, nil)`
    where `data` is the parsed `int` (autoboxes).

### Phase C — tests (the green gate)

The ~295-test suite is the behaviour gate; a chunk of it touches internals directly
(`StrategyInvariantTest` ~43 refs, `RegressionFixesTest` ~28, `TreeContextTester` ~27, …).

14. **`RegressionFixesTest`** — the only hard breaker: replace `TreeNode1.NIL` with a locally
    created sentinel (`TreeNode1.createNil(Comparator.naturalOrder())` or a
    `RedBlackTree<>(…).getNIL()`).
15. Parameterise direct-internal usages to `<Integer>` (`TreeNode1<Integer>`,
    `RedBlackTree<Integer>`, `OrderStatisticsOps<Integer>`). Most are mechanical; raw usages will
    compile with unchecked warnings if you want to defer cosmetics. `select(int)`/`percentile(int)`
    call-sites are unaffected.
16. **`ant clean test`** on the JDK host. Green → commit. Red → fix before committing.

---

## 5. Verification and rollback

- **Behaviour identity argument:** with `K = Integer` and `Comparator.naturalOrder()`, every
  comparison is exactly the old natural-int order (this is what step 1 already proved
  site-by-site). So a green suite means **no semantic regression** — the generic refactor is
  type-only at `K = Integer`.
- **Gate:** `ant clean test` is authoritative. Do not commit on a red suite (or a red compile).
- **Incremental signal:** run `ant compile` after each Phase-A file; the shrinking error count is
  your progress bar. If errors *grow* in unrelated files, you've changed a signature the periphery
  depends on in a way that needs an `<Integer>` pin — note it for Phase B rather than chasing it
  mid-spine.
- **Atomicity / rollback:** one branch, one commit when green. If the generics get away from you,
  `git checkout -- src/main/java/core/TreeNode1.java` (and the spine files) resets cleanly; nothing
  else has been committed.
- **Suggested commit message:** `Generify the tree engine against <K> behind a pluggable
  Comparator (ADR-002 #2/#3)`. Update ADR-002 action items 2–3 and add a
  `CHANGELOG-2026-…-generic-keys.md`.

---

## 6. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| "Wall of generics errors" mid-spine | High (inherent) | Phase A ordering + `ant compile` between files; the periphery red set is *expected*, not a regression |
| `defaultAugmentor` identity checks silently broken | Medium | Decision 2.4 — one shared instance behind the factory; grep the 7 `!= defaultAugmentor` sites after editing |
| `PersistentTreeEngine` won't compile against `TreeEngine<Integer>` | Medium | It needs `Integer` params (overriding `add(Integer)`, not `add(int)`) — called out as step 10 |
| Test compile breaks on static `NIL` | Certain (1 file) | Step 14 — `RegressionFixesTest` moves to a local sentinel |
| Raw-type / unchecked warnings flood the build | Low–Med | Acceptable interim; pin to `<Integer>` to clear them. Not a correctness issue |
| Test `assertEquals(5, os.select(1).getData())` resolution changes (`getData()` was `int`, now `Integer`/`K`) | Low | **Verified non-issue** — resolves via unboxing to the primitive `assertEquals` (pinned `<Integer>`) or via `equals` (raw); compiles and behaves identically either way |
| Scope creep into `OrderedSet<K>` / generic intervals / persistence | Medium | §1 non-goals — those are steps 4–5; resist starting them here |
| `Integer` boxing cost | Low | Documented, accepted non-goal (ADR-002); revisit only if profiling demands |

---

## 7. First-edit checklist (start here)

The whole sweep unblocks from `TreeNode1`. Concretely, the first editing session is:

1. `git switch -c adr002-step2-generics`
2. In `TreeNode1.java`: declare `<K>`; `data`/`getData()` → `K`; sentinel-held
   `Comparator<? super K> keyOrder` + `createNil(Comparator)`; `compareTo`/`compareKeyTo(K)` via
   `nilSentinel.keyOrder`; `Augmentor<K>` + shared-instance `defaultAugmentor()`; **delete** static
   `NIL` and `alienSpawn`; **move** `mutateAugmentorByDepth` to an `int` helper; leave
   `augmentedValue`/`size`/`height`/`blackHeight` as `int`.
3. `ant compile` → read the error list → fix `MutableTree`, then the four strategies, then
   `RedBlackTree`/`TreeEngine`, then `OrderStatisticsOps` (Phase A order).
4. When the spine compiles, pin the periphery (Phase B), then the tests (Phase C).
5. `ant clean test` → green → commit.
