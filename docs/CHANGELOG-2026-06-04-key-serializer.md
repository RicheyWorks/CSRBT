# CHANGELOG 2026-06-04 -- ADR-002 step 5: pluggable `KeySerializer<K>` for snapshots

Implements ADR-002 Option C, step 5: the snapshot text format -- the last `int`-pinned
seam in the core read/write path -- is generified over a pluggable `KeySerializer<K>`, so
persistence works for any key type. The `int` `TreeContext` snapshot path is **byte-identical**
to the legacy format (it delegates through a built-in `KeySerializer.INTEGER`).

Also lands a small repo-hygiene fix: a `.gitattributes` (`text=auto eol=lf`) that normalizes
line endings to LF, ending the recurring CRLF working-tree churn seen when the tree is edited
on Windows.

## What changed

- **`core.persistence.KeySerializer<K>` (new).** A two-method contract --
  `String serialize(K)` / `K deserialize(String)` -- with built-ins:
  - `INTEGER` (`Integer.toString` / `Integer.valueOf`) -- reproduces the historical
    int format exactly.
  - `LONG` (`Long.toString` / `Long.valueOf`).
  - `string()` -- for arbitrary **non-empty** strings. It percent-encodes the format's
    reserved characters (`%` first, then `,` `;` `#` `|`) so adversarial keys such as
    `"a,b"`, `"x;y"`, `"#"` round-trip; decoding is a generic `%XX` hex scan, so non-ASCII
    keys pass through untouched. (`StringKeySerializer`, package-private.)

- **`FilePersistenceAdapter` generified over `<K>`.** Only two lines actually touched a
  concrete `int` -- emitting a key (`sb.append(node.getData())`) and parsing one
  (`Integer.parseInt(parts[0])`). Those now go through `ks.serialize(...)` /
  `ks.deserialize(...)`. The surrounding helpers (`serializePreOrder`,
  `deserializePreOrder`, `parseToken`, the reconstruction `Frame`) and `resolveStrategy`
  are now `<K>`. New generic entry points:
  - `<K> void saveSnapshot(String name, OrderedSet<K> set, KeySerializer<K> ks)`
  - `<K> OrderedSet<K> loadOrderedSet(String name, KeySerializer<K> ks, Comparator<? super K> keyOrder)`
  - `<K extends Comparable<? super K>> OrderedSet<K> loadOrderedSet(String name, KeySerializer<K> ks)`
    (natural-order convenience).

  The existing `saveSnapshot(String, TreeContext)` / `loadSnapshot(String): TreeContext`
  keep their exact signatures and their `Integer`-only extras (the `INTERVAL` augmentor
  token, the `TreeDiagnostics` size cross-check, `forceSizeInternal`); they just pass
  `KeySerializer.INTEGER` to the generified helpers.

### Generic load reuses the step-4 out-of-band-rebuild hook

`loadOrderedSet` builds `new OrderedSet<>(strategy, keyOrder)`, reconstructs the root into
the set's live engine via `getEngine().setRoot(root)` (+ `setParent(NIL)` fix-up), then calls
`OrderedSet.resyncFromEngine()` -- the method step 4 added precisely for "the root was
replaced out of band". So no new `OrderedSet` surface was needed; the generic load mirrors
what the `int` `TreeContext` load already does via `forceSizeInternal`.

### Order statistics stay exact after load

Deserialization attaches children with `TreeNode1.setLeft`/`setRight`, both of which call
`recomputeAugmentAndPropagate()` -- recomputing each node's intrinsic subtree size and
propagating it up the (already-linked) parent chain. So once the tree is fully reconstructed
every node's subtree size is correct, and post-load `select`/`rank`/`median`/`percentile` are
exact. This is the same mechanism the `int` path already relied on; the generic path inherits
it unchanged.

## Compatibility

- **On-disk format unchanged for int snapshots.** `KeySerializer.INTEGER` emits and parses
  exactly what the old code did, so existing `.rbt` files load unchanged and the `int`
  `TreeContext` API is untouched. A round-trip test reads a file *written by the int path*
  back through the *generic* path to pin this.
- **The interval augmentor stays `Integer`.** The generic save records `AUGMENTOR=DEFAULT`;
  per-node tags still round-trip (they are `String`). A caller using a custom `Augmentor<K>`
  re-applies it after load (which recomputes augmented values from the restored tags) -- the
  same requirement the `int` path already has for non-built-in augmentors.
- **Comparators are not serialized.** Generic `load` takes the comparator from the caller
  (mirroring `java.util.TreeMap` deserialization); the natural-order overload covers
  `Comparable` keys.
- **`TreePersistenceAdapter`, `TreeContext`, `OrderedSet`, `RedBlackTree`, `TreeNode1` are
  unchanged** -- step 5 is additive on the concrete adapter plus the new serializer.

## Tests

`KeySerializerPersistenceTest` (new):
- `KeySerializer` unit: `INTEGER`/`LONG` over the numeric extremes; `string()` escaping over
  every reserved character (round-trip + "no raw delimiter leaks" + empty-string rejected).
- Generic round-trips through the adapter: `OrderedSet<String>` natural order (including
  delimiter-bearing keys), reverse `Comparator`, a 200-key Splay set, `Integer` via the
  generic API; each cross-checked for contents, size, and order statistics (`min`/`max`/
  `rank`/`median`), and strategy restored from the header.
- `Integer` back-compat: a `TreeContext` round-trips through the `int` path; and a file
  written by the `int` path reloads identically through the generic path.
- Edge cases: empty set (NIL root), single key, missing snapshot (`null`), null arguments.

## Verification status -- IMPORTANT

**This work was verified by static analysis only; it has NOT been compiled or run.** As in the
step-4 session, the sandbox had no JVM compiler (JRE 11 only -- no `javac` -- and no reachable
source for a JDK/ECJ), so `ant clean test` could not be executed here. Every call was checked
against the actual signatures of `OrderedSet`, `FilePersistenceAdapter`, `RedBlackTree`,
`TreeNode1`, and the strategies; generic inference at each call site was reasoned through; and
braces/EOL/UTF-8 were verified. **The full suite (the ~295-test `int` suite, `OrderedSetTest`,
and the new `KeySerializerPersistenceTest`) must be run on a host JDK 17 before relying on this
change.**

### Watch-list (to confirm on the host)

- `loadOrderedSet` order statistics are exact (depends on `setLeft`/`setRight` propagation,
  argued above).
- `string()` escaping survives the full save/load pipeline for keys containing `,` `;` `#`.
- `resolveStrategy` generification still infers `<Integer>` at the existing `int` call site.
- the two-arg natural-order `loadOrderedSet` overload resolves without ambiguity against the
  three-arg form.

## Out of scope (still pending, per ADR-002)

The control-plane consolidation (ADR-002 item 5: extract `StrategyScorer` from `TreeGenome`,
add a live `WorkloadMonitor`, wire the controller to drive `MorphPolicy` + the health-gated
`setStrategy`) is the next item. Generifying the evolution/experimental packages and the
remaining `Integer`-bound utilities (`TreeHistory`, `IntervalAugmentor`, `TreeCloner`,
`TreeDiagnostics`) remains separate, later work.
