# CSRBT — change log, 2026-05-31 (comparator seam)

Implements **ADR-002 Option C, step 1**: route every key comparison through a
single ordering authority, behind the existing `int` API. Internal only — no
public behaviour change, no signature change, the `int` facade is untouched.
This is the foundation the later generic-`<K>` steps build on.

## The problem it sets up
The engine compared keys by reaching into `getData()` directly at ~26 sites
(`a.getData() < b.getData()`, `value - node.getData()`, etc.) spread across the
four strategies, order statistics, the interval code, diagnostics and the
health-check. To make keys generic (`<K> + Comparator<K>`) later, *every one* of
those sites would have to change. Step 1 funnels them through one chokepoint now,
so step 2 changes ordering in exactly one place instead of re-sweeping the tree.

## The change — one key-ordering authority
- **`TreeNode1.KEY_ORDER`** — a `Comparator<Integer>` = `Comparator.naturalOrder()`,
  the single source of truth for key order.
- **`TreeNode1.compareTo(TreeNode1)`** now delegates to `KEY_ORDER` (was
  `Integer.compare`); **new `TreeNode1.compareKeyTo(int)`** compares a node
  against a raw query key through the same authority (sign matches
  `this.key - otherKey`).
- **Every comparison site re-routed** to `compareTo` (node vs node) or
  `compareKeyTo` (node vs query key):
  - `RedBlackStrategy`, `AVLStrategy`, `SplayStrategy`, `HybridStrategy` — insert
    navigation + `search`.
  - `OrderStatisticsOps` — `rankCeiling`, `rankFloor`, `findNode`.
  - `IntervalAugmentor` — interval insert navigation.
  - `TreeDiagnostics` — `findNode`.
  - `StrategyHealthCheck` — BST invariant + order-stat spot check.
  - `TreeNode1.isLessThan` — via `compareTo`.

After the sweep, **no code compares `getData()` values directly** (only non-ordering
reads remain: logging, construction, serialization, morph arithmetic).

## Why behaviour is identical
`KEY_ORDER` is natural int order, so each rewrite is sign-preserving by
construction: `a.getData() OP b.getData()` ≡ `a.compareTo(b) OP 0`, and the
search loops' `value - node.getData()` (sign) ≡ `node.compareKeyTo(value)` with
the branch direction flipped accordingly. (Side benefit: the search rewrite drops
the `value - getData()` subtraction, removing a latent `int` overflow at extreme
keys — `Integer.compare` is overflow-safe.)

## Verification
- **Completeness** — a repo-wide grep confirms no key-ordering `getData()` / `.data`
  comparison remains outside the chokepoint.
- **Behaviour** — all 11 distinct rewrite patterns were modelled (original vs new
  branch decision) and proven to produce identical results across an exhaustive
  input range.
- **Structure** — the modified `TreeNode1` was read in full and reviewed; the new
  member and method placements are sound.
- Full `ant clean test` is the authoritative green gate and should be run on a
  JDK host (the dev sandbox this was prepared in has a JRE only).

## Compatibility
No public API removed or changed. `compareKeyTo(int)` and `KEY_ORDER` are
additive (the latter package-private). The `int` `TreeContext` facade and the
~295-test regression suite are unaffected.

## Still open (ADR-002)
- #2 second half / #3: generify `TreeStrategy`, the engine, `OrderStatisticsOps`
  and the augmentor against `<K>`; promote `KEY_ORDER` to a per-engine pluggable
  `Comparator<K>` (now a one-place change).
- #3 (step 4): `OrderedSet<K>` facade; `TreeContext` becomes an `Integer` adapter.
- #4 (step 5): pluggable key (de)serializer for snapshots.
- #5: extract `StrategyScorer` + add `WorkloadMonitor`.
