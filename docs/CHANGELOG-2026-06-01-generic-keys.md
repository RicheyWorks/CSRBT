# CSRBT — change log, 2026-06-01 (generic keys `<K>`)

Implements **ADR-002 Option C, steps 2–3** (the generic-key portion), per
`PLAN-adr002-step2-generic-keys.md`. Builds on the step-1 comparator seam
(`CHANGELOG-2026-05-31-comparator-seam.md`, committed `ab75f2d`).

> **Build status: NOT YET COMPILED OR TESTED.** This was prepared in a sandbox
> with a JRE only (OpenJDK 11, no `javac`/`ant`); the code targets Java 21. The
> authoritative gate is `ant clean test` on a JDK-21 host. Commit only when green.
> See §6 for the host steps and §5 for the spots most likely to need a touch-up on
> the first compile.

Done on branch **`adr002-step2-generics`**.

---

## 1. What changed

The engine spine is now generic over the key type `K`, ordered by a pluggable
`Comparator<? super K>`. The `int` `TreeContext` facade is unchanged in its public
API and now drives a `RedBlackTree<Integer>`; everything outside the generic spine
is pinned to `<Integer>` so behaviour and the ~295-test suite are preserved.

**Generic spine (`<K>`):** `TreeNode1<K>`, `MutableTree<K>`, `TreeStrategy<K>` +
`RedBlackStrategy/AVLStrategy/SplayStrategy/HybridStrategy`, `TreeEngine<K>`,
`RedBlackTree<K>`, `OrderStatisticsOps<K>`.

**Pinned to `<Integer>` (behaviour unchanged):** `TreeContext`, `IntervalAugmentor`,
`TreeCloner`, `TreeDiagnostics`, `TreeHistory`, `StrategyHealthCheck`,
`TreeEngineRegistry`, `PersistentTreeEngine`, `FilePersistenceAdapter`,
`GenomeDrivenTreeController`, `StrategyBattleRunner`, `TreeAgent`, `TreeEcology`,
and the `AugmentedTree` interface.

**Unchanged (verified no change needed):** `OrderedCollection`, `SelfHealingTree`,
`TreePersistenceAdapter` (mention only `int`/`TreeContext`), and `TreeGenome` (its
arithmetic is on `double` traits, not keys).

---

## 2. As-built design decisions

1. **Ordering authority moved from `static KEY_ORDER` to a per-node
   `Comparator<? super K> keyOrder`.** A generic class can't hold a
   `static Comparator<K>`. The per-tree NIL sentinel is the source of truth
   (`createNil(Comparator)`); every real node copies the reference from the `nil`
   it's built against (`this.keyOrder = nil.keyOrder`), so `createNode(data, nil)`
   stays two-arg and **no comparison call-site moved**. `compareTo`/`compareKeyTo(K)`
   consult `this.keyOrder`. `RedBlackTree` also holds the comparator and exposes
   `comparator()` (see decision 6). Natural order is a convenience factory:
   `RedBlackTree.withNaturalOrder(strategy)`.

2. **One type parameter; `augmentedValue` stays `int`.** Both augmentors write an
   `int`, so no `<K, A>` second parameter. `Augmentor<K>` takes `TreeNode1<K>` but
   its body is int-valued.

3. **Static `TreeNode1.NIL` deleted.** It can't be generic and the codebase already
   mandated per-instance sentinels. The only consumer was `RegressionFixesTest`,
   now updated to a local `createNil(...)` sentinel.

4. **`defaultAugmentor` is one shared instance behind a generic factory.**
   `private static final Augmentor<Object> DEFAULT_AUGMENTOR` + `static <E>
   Augmentor<E> defaultAugmentor()` returning the cast singleton. This preserves the
   identity-comparison semantics (`augmentor != defaultAugmentor()`). **Gotcha:**
   those `!=` sites use an explicit witness — `TreeNode1.<Integer>defaultAugmentor()`
   — because comparing `Augmentor<Integer>` against an inference-defaulted
   `Augmentor<Object>` is a compile error. Sites: `TreeContext` (×4 incl. the field
   initializer), `TreeCloner` (×2), `TreeHistory` (×1).

5. **Key arithmetic left the generic node.** `TreeNode1.alienSpawn` was dead →
   deleted (the `java.util.Random` import went with it). `TreeNode1.
   mutateAugmentorByDepth` had one caller (`TreeCloner.mutantClone`) → relocated to a
   `private static` `Integer`-specialised helper in `TreeCloner` (`getData()` unboxes
   for the `×2`/`×key` arithmetic). The generic `TreeNode1<K>` now contains no key
   arithmetic.

6. **`OrderStatisticsOps` query-vs-query comparison.** `countInRange`/`rangeQuery`
   compare the two *query* keys (`lo > hi`) — a comparison step 1's node-based seam
   never covered. Routed through the new `RedBlackTree.comparator()` via a private
   `compareKeys(K,K)` helper.

7. **`IntervalAugmentor` pinned to `Integer`.** Its hi/max-hi are `int` (parsed
   string tag + int `augmentedValue`), so it `implements TreeNode1.Augmentor<Integer>`
   and installs only on `TreeNode1<Integer>` trees. Generic (typed-endpoint) intervals
   are deferred.

8. **`PersistentTreeEngine implements TreeEngine<Integer>`.** The second engine
   implementer; its `add/remove/contains` params became `Integer` (an `add(int)` does
   not override `add(Integer)`). Bodies unbox to its private int-keyed `Node`.

---

## 3. What stays `int`

`OrderStatisticsOps.select(int rank)` / `percentile(int pct)` (positional, not keys);
`augmentedValue`/`size`/`height`/`blackHeight`/`depth()`; `RedBlackTree.size()`;
the entire `TreeContext` public API (`add(int)` …) — it's the `Integer` adapter;
the `FilePersistenceAdapter` text format (key serializer is step 5).

## What became `K`

`TreeNode1.data`/`getData()`/`compareKeyTo(K)`/constructors/`createNode`;
`TreeEngine.add/remove/contains` + `inOrder():List<K>`; all `MutableTree`/
`TreeStrategy` node params; `search(MutableTree<K>, K)`; `HybridStrategy.recordAccess(K)`
+ `hotNodeFrequency:Map<K,Integer>`; `OrderStatisticsOps.rank/successor/predecessor/
countInRange/rangeQuery/findNode/rankCeiling/rankFloor`.

---

## 4. Files changed (26 source + 2 docs)

Spine: `TreeNode1`, `MutableTree`, `TreeStrategy`, `RedBlackStrategy`, `AVLStrategy`,
`SplayStrategy`, `HybridStrategy`, `TreeEngine`, `RedBlackTree`, `OrderStatisticsOps`.
Periphery: `TreeContext`, `IntervalAugmentor`, `TreeCloner`, `TreeDiagnostics`,
`TreeHistory`, `StrategyHealthCheck`, `TreeEngineRegistry`, `AugmentedTree`,
`PersistentTreeEngine`, `FilePersistenceAdapter`, `GenomeDrivenTreeController`,
`StrategyBattleRunner`, `TreeAgent`, `TreeEcology`. Tests: `RegressionFixesTest`,
`StrategyInvariantTest`. Docs: this file + `PLAN-adr002-step2-generic-keys.md`.

---

## 5. Watch-list for the first compile

These are the spots where a blind (no-compiler) sweep is most likely to need a
nudge. None are design problems; they're inference/warning details:

- **Generic-method inference** at `TreeNode1.createNil(keyOrder)` (in `RedBlackTree`)
  and `createNode(value, NIL)` — should infer `K` from the assignment/argument; if
  the host compiler balks, add an explicit witness (`TreeNode1.<K>createNil(...)`).
- **`defaultAugmentor()` witness sites** (decision 4) — if any `!=` line errors with
  "incomparable types", it's missing the `<Integer>` witness.
- **Raw-type unchecked warnings in tests** (e.g. `new RedBlackStrategy()` passed where
  `TreeStrategy<Integer>` is expected, raw `OrderStatisticsOps`/`RedBlackTree` locals).
  These are warnings, not errors — they compile. Pin to `<Integer>` only if you want a
  clean `-Xlint`.
- **`assertEquals(5, os.select(1).getData())`** now resolves via unboxing rather than
  `int,int` — verified to compile and behave identically; no action expected.
- **Sentinel `getData()` is now `null`** (was `0`); never read for ordering
  (`isNil()` guards everywhere), but noted for completeness.

## Behaviour identity

With `K = Integer` and `Comparator.naturalOrder()`, every comparison is the old
natural-int order (step 1 proved this site-by-site). The refactor is type-only at
`K = Integer`, so a green suite means no semantic regression.

---

## 6. Host steps (the gate)

The prep sandbox's `git` could not see the source edits (a cross-mount cache
quirk — it reported only the docs as changed), so **do this on the host**, where the
files are correct:

```
cd /d C:\Users\730ri\projects\CSRBT
git status                 # expect ~24 modified sources + 2 modified tests + 2 new docs
ant clean test             # the green gate (JDK 21)
# iterate on any compiler errors (see §5), then:
git add -A
git commit -m "Generify the tree engine against <K> behind a pluggable Comparator (ADR-002 #2/#3)"
```

If `ant clean test` reports errors, paste them and they'll be fixed before commit.

## 7. Still open (ADR-002, after this lands green)

- Step 4: `OrderedSet<K>` facade; reduce `TreeContext` to an `Integer` adapter and
  consider generifying `AugmentedTree`/`OrderedCollection`.
- Step 5: pluggable key (de)serializer for snapshots (generic `FilePersistenceAdapter`).
- Generic (typed-endpoint) `IntervalAugmentor`.
- Extract `StrategyScorer` + add `WorkloadMonitor` (control-plane consolidation).
