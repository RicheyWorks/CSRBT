# Static review — ADR-002 step 2 generic-keys changeset (2026-06-02)

**Reviewer pass:** full static "be-the-compiler" review of the uncommitted
`adr002-step2-generics` branch, performed without a JDK (sandbox is JRE-11 only,
the build needs `release=17`). Goal: get the first host `ant clean test` as close
to green as possible by finding the errors a compiler would find.

**Verdict:** `src/main` (all 24 changed files) is internally consistent and should
compile. The test suite had **6 genuine compile errors** the previous session
missed — all now fixed in place. A follow-up pass also pinned every remaining raw
test local to `<Integer>`, so a `-Xlint` build should be clean too (see §4).

> **Update (same day):** the count rose from 4 to 6 during the `-Xlint` pinning pass —
> two more hard errors surfaced that a symbol-grep doesn't catch (see §6 for why).
> Everything here is still **uncompiled** by me; the host `ant clean test` remains the gate.

---

## 1. What was verified clean

**Generic spine (10 files), read end-to-end.** `TreeNode1<K>`, `MutableTree<K>`,
`TreeEngine<K>`, `TreeStrategy<K>` + `RedBlack/AVL/Splay/Hybrid` strategies,
`RedBlackTree<K>`, `OrderStatisticsOps<K>`. Confirmed: the static `NIL`, `KEY_ORDER`
and `alienSpawn` are gone; ordering is the per-sentinel `Comparator<? super K> keyOrder`
read by `compareTo`/`compareKeyTo`; `createNode(K, nil)` stays two-arg; `select`/
`percentile` correctly stay `int` while `rank`/`successor`/`countInRange`/`rangeQuery`
became `K`; `compareKeys` routes the two-query-key comparison through
`RedBlackTree.comparator()`; no strategy does key arithmetic.

**Periphery (14 files), `<Integer>`-pinned.** `TreeContext`, `IntervalAugmentor`,
`TreeCloner`, `TreeDiagnostics`, `TreeHistory`, `StrategyHealthCheck`,
`TreeEngineRegistry`, `AugmentedTree`, `PersistentTreeEngine`, `FilePersistenceAdapter`,
`GenomeDrivenTreeController`, `StrategyBattleRunner`, `TreeAgent`, `TreeEcology`.
Spot-confirmed the high-risk items:

- All **7 `defaultAugmentor()` identity sites** use the explicit `<Integer>` witness
  (4× `TreeContext`, 2× `TreeCloner`, 1× `TreeHistory`) — the `!=` checks compile and
  keep their semantics.
- **`PersistentTreeEngine implements TreeEngine<Integer>`** with `add/remove/contains(Integer)`
  — the override trap is handled; its `value == n.key` comparisons unbox against the
  primitive `int` field.
- **`mutateAugmentorByDepth`** relocated to a `private static` `TreeNode1<Integer>`
  helper in `TreeCloner`; its `getData()*2` / `getData()*getData()` unbox correctly.
- `RedBlackStrategy::new` etc. infer `Supplier<TreeStrategy<Integer>>`; `buildStrategy()`
  and `resolveStrategy()` return `TreeStrategy<Integer>` via diamond.
- Every `src/main` `getData()` arithmetic site is on `TreeNode1<Integer>` (TreeAgent,
  TreeCloner) and unboxes — no generic-node arithmetic remains.

---

## 2. The 4 compile errors found and fixed

The previous session's note — "everything else compiles (raw-type warnings at worst)"
— conflated two different things. *Raw type usage* is a warning. But a **raw operand in
a relational (`<`, `>`, `<=`) or `int`-assignment context is a hard error**, because a
raw node's `getData()` erases from `K` to `Object`, and `Object < Object` / `int = Object`
do not compile. These four lines used to compile only because pre-generics `getData()`
returned `int`.

| File | Line | Broken expression | Why it errors | Fix applied |
|---|---|---|---|---|
| `StrategyInvariantTest` | 76 | `n.getLeft().getData() < n.getData()` | `checkBst(TreeNode1 n)` raw → `Object < Object` | param → `checkBst(TreeNode1<Integer> n)` |
| `StrategyInvariantTest` | 81 | `n.getRight().getData() > n.getData()` | same raw helper | (same one-line fix covers both) |
| `AuditFixesTest` | 108 | `hit.getData() <= 31` | `TreeNode1 hit` raw → `Object <= 31` | decl → `TreeNode1<Integer> hit` |
| `TreeContextTester` | 238 | `int m = os().median().getData()` | `os()` raw → `int = Object` | `os()` returns `OrderStatisticsOps<Integer>` (+ diamond) |
| `TreeContextTester` | 330 | `new core.RedBlackTree(new RedBlackStrategy())` | the deleted 1-arg constructor; no longer exists | `RedBlackTree.withNaturalOrder(new RedBlackStrategy<Integer>())`, engine pinned `TreeEngine<Integer>` |
| `HealthGatedMorphTest` | 97–101 | `DroppingStrategy implements TreeStrategy` with `search(MutableTree, int)` | raw impl + old `int` param → no longer overrides `search(MutableTree<K>, K)`; `@Override` fails | reparameterized to `TreeStrategy<Integer>` with generic method signatures |

Rows 1–4 are one class: a raw node's `getData()` erases from `K` to `Object`, and
`Object < Object` / `int = Object` do not compile (they used to, because pre-generics
`getData()` returned `int`). The fixes pin the node/ops to `<Integer>` so `getData()`
returns `Integer` and unboxes — exactly the Phase-C step-15 cleanup the plan anticipated.

Rows 5–6 are a different class and the more dangerous miss: a **deleted-constructor call**
(`new core.RedBlackTree(strategy)`) and a **custom interface implementation left on the old
signature** (`DroppingStrategy`). Neither is a `getData()` issue; both surfaced only when the
`-Xlint` pinning pass forced a closer read. `AuditFixesTest` and `HealthGatedMorphTest` were
not even edited by the previous session, so their breakage would only have appeared on the host.

---

## 3. Confirmed-correct from last session

- `RegressionFixesTest` (lines 379–391): the static-`NIL` consumer now builds a local
  sentinel via `createNil(ord)` + `createNode(5, nil)` — correct.
- `StrategyInvariantTest` line 47: the old 1-arg `RedBlackTree` constructor →
  `RedBlackTree.withNaturalOrder(s)` — correct. (My first pass wrongly concluded this was
  the *only* constructor breaker: a `new RedBlackTree(...)` grep missed the package-qualified
  `new core.RedBlackTree(...)` at `TreeContextTester:330` — see error row 5 and §6.)

---

## 4. `-Xlint` pinning pass (done)

Every remaining **raw** test local/param/type-arg of a now-generic type was pinned to
`<Integer>` across all 12 test files: `RedBlackTree`, `TreeNode1`, `OrderStatisticsOps`,
`TreeStrategy`, `MutableTree`, `TreeEngine` declarations; `Supplier<TreeStrategy>` →
`Supplier<TreeStrategy<Integer>>`; `BiConsumer<RedBlackTree, …>`; `Deque<TreeNode1>`
type-arg; and `new XStrategy()` → `new XStrategy<>()` (every site sits in an inferable
context — `tree(...)` / `setStrategy(...)` / `new TreeContext(...)` / a cast). After the
pass, a tree-wide grep finds no raw usage of these types outside `@DisplayName` prose, so
`-Xlint:rawtypes,unchecked` should be clean for them.

These edits are mechanical and **uncompiled** — they were applied with `sed` and verified
by diff review, not by a compiler. The host build is still the confirmation.

---

## 5. Host gate (unchanged)

```
cd /d C:\Users\730ri\projects\CSRBT
git status                 # ~24 modified sources + ~10 modified tests + new docs
ant clean test             # the green gate (JDK 17+)
# expect green; if anything is red, paste it
git add -A
git commit -m "Generify the tree engine against <K> behind a pluggable Comparator (ADR-002 #2/#3)"
```

The static review covered type-consistency, not runtime behaviour; the ~295-test suite
remains the behaviour gate. The behaviour-identity argument still holds: at `K = Integer`
with `Comparator.naturalOrder()` every comparison is the old natural-int order, so a green
suite means no semantic regression.

---

## 6. Why a symbol-grep missed two errors (and a compiler wouldn't)

The first pass leaned on `grep` for changed/removed symbols. That reliably finds
reference breakers but has three blind spots, all of which a compiler closes for free:

- **Package-qualified forms.** `new RedBlackTree(` does not match `new core.RedBlackTree(`.
  The deleted 1-arg constructor call at `TreeContextTester:330` hid behind the `core.` prefix.
- **Custom implementations of a changed interface.** `DroppingStrategy implements TreeStrategy`
  re-declares the interface's methods with the *old* `search(MutableTree, int)` signature. Nothing
  references a removed symbol — the class simply stops overriding the (now generic) method, so
  `@Override` fails. A grep for call-sites can't see this; you have to read every `implements`.
- **Erased-type contexts that flip a warning into an error.** A raw `TreeNode1`/`OrderStatisticsOps`
  is normally just a warning, but the moment its erased `Object` return feeds a `<`/`>`/`int =`
  (rows 1–4), it's a hard error. Distinguishing the two requires type-checking the surrounding
  expression, not pattern-matching the symbol.

Net: a static review gets you most of the way and is worth doing when no JDK is available, but
`ant clean test` on the host is the only thing that closes these gaps with certainty. If it comes
back red, paste the output and the remaining fixes will be quick.
