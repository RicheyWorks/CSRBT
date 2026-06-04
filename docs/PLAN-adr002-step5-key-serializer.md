# PLAN: ADR-002 step 5 — pluggable key (de)serializer for snapshots

**Status:** Ready to execute (step 4 `OrderedSet<K>` facade landed)
**Date:** 2026-06-04
**Owner:** Richmond
**Implements:** ADR-002 Option C, step 5 ("Pluggable key (de)serializer for persistence;
the text format currently assumes `int`"). Builds on the step-4 facade
(`PLAN-adr002-step4-orderedset.md`, branch `adr002-step4-orderedset`): `OrderedSet<K>`
exists and already exposes `getEngine()` + `resyncFromEngine()`, the two hooks a
wholesale-rebuild load needs.

> **Why this is a written plan.** Like step 4, step 5 is *additive then delegating*, not a
> type-system sweep. The snapshot text format is the last `int`-pinned seam in the core
> read/write path, and it is pinned in exactly two spots — emitting a key
> (`sb.append(node.getData())`) and parsing one (`Integer.parseInt(parts[0])`). The thinking
> worth writing down is (a) the **delimiter contract** a generic key token must honour so the
> flat `… ; … , …` format stays parseable for arbitrary `K`, and (b) the **scope boundary**:
> what genuinely needs `K` (the two key I/O points and the strategy resolver) versus what
> stays `Integer` (the `TreeContext` adapter's `saveSnapshot`/`loadSnapshot`, the interval
> augmentor token, undo/redo) so step 5 doesn't sprawl into the control-plane items (5+).

---

## 1. Goal and non-goals

**Goal.** Make snapshot persistence work over any key type `K` by routing the two
key-touching points of the text format through a pluggable `KeySerializer<K>`
(`String serialize(K)` / `K deserialize(String)`), and add generic
`saveSnapshot(name, OrderedSet<K>, KeySerializer<K>)` /
`loadOrderedSet(name, KeySerializer<K>, Comparator)` entry points on
`FilePersistenceAdapter`. The existing `int` `TreeContext` snapshot API and its tests keep
passing unchanged, now delegating through the same generic core with a built-in
`KeySerializer.INTEGER`.

**In scope — what becomes `K`:**

- A new `core.persistence.KeySerializer<K>` contract with built-ins: `INTEGER` (back-compat),
  `LONG`, and a `string()` factory that **escapes the format's reserved characters** so
  arbitrary strings round-trip.
- `FilePersistenceAdapter`'s private serialize/deserialize helpers
  (`serializePreOrder`, `deserializePreOrder`, `parseToken`, the reconstruction `Frame`)
  generified over `<K>` and a `KeySerializer<K>`.
- `resolveStrategy` generified to `<K> TreeStrategy<K>` (the four strategies are already
  key-agnostic; `new RedBlackStrategy<>()` etc. infer `K`).
- New generic public methods on `FilePersistenceAdapter`:
  - `<K> void saveSnapshot(String name, OrderedSet<K> set, KeySerializer<K> ks)`
  - `<K> OrderedSet<K> loadOrderedSet(String name, KeySerializer<K> ks, Comparator<? super K> keyOrder)`
  - `<K extends Comparable<? super K>> OrderedSet<K> loadOrderedSet(String name, KeySerializer<K> ks)`
    (natural-order convenience).

**Explicitly out of scope (resist starting these here):**

- **Changing the `TreePersistenceAdapter` interface.** It names `TreeContext` and stays the
  `Integer` adapter contract. The generic methods are *added on the concrete*
  `FilePersistenceAdapter`, purely additive — no interface ripple.
- **`TreeContext` internals.** `TreeContext.saveSnapshot`/`loadSnapshot` and its
  `cloner.snapshot()` path are unchanged; they keep flowing through the `Integer`
  adapter methods. No edits to `TreeContext.java` or `OrderedSet.java` are required —
  `OrderedSet` already exposes `getEngine()` + `resyncFromEngine()`.
- **Interval augmentor identity for generic keys.** `IntervalAugmentor` is `Integer`-bound,
  so the generic save records `AUGMENTOR=DEFAULT`. Per-node **tags still round-trip**
  (they are `String`, key-agnostic); a caller who set a custom `Augmentor<K>` re-applies it
  after load (which recomputes augmented values from the restored tags), exactly as the
  `int` path already requires for non-built-in augmentors.
- **Comparator persistence.** A `Comparator` can't be serialized, so generic `load` takes the
  comparator from the caller (mirroring how `java.util.TreeMap` deserialization needs its
  comparator supplied). Natural-order keys use the `Comparable` overload.
- **Empty-string keys / binary keys.** The flat format reserves `#` (NIL) and the empty token;
  the `string()` serializer supports any **non-empty** string and throws on `""`.
- **Control-plane consolidation** (`StrategyScorer` / `WorkloadMonitor`) — ADR-002 item 5,
  a separate step.

---

## 2. Pivotal design decisions

### 2.1 `KeySerializer<K>` is a tiny, persistence-owned contract

```java
package core.persistence;

public interface KeySerializer<K> {
    /** Render a key as one delimiter-safe token (see the contract below). */
    String serialize(K key);
    /** Parse a token produced by {@link #serialize}. */
    K deserialize(String token);

    KeySerializer<Integer> INTEGER = /* Integer.toString / Integer.parseInt */;
    KeySerializer<Long>    LONG    = /* Long.toString / Long.parseLong */;
    static KeySerializer<String> string() { /* escaping impl */ }
}
```

It lives in `core.persistence` (next to the adapter), so `core.OrderedSet` does **not** gain a
dependency on persistence — the layering (`persistence → core`, never the reverse) is
preserved. No persistence methods are added to `OrderedSet`.

### 2.2 The delimiter contract (the one real subtlety)

The format is flat: nodes are separated by `;`, a node is `DATA,COLOR[,TAG]` split on `,`
(limit 3), `#` marks NIL, and an empty token is treated as NIL. Therefore a key token
**must not contain `,` or `;`, must not be `#`, and must not be empty** (`|` is a *header*
delimiter only and never appears on the node line, but the `string()` serializer escapes it
too for safety). `INTEGER`/`LONG` satisfy this for free. `string()` percent-encodes
`% , ; # |` (with `%` first so decode is unambiguous), so any non-empty string round-trips —
including adversarial keys like `"a,b"`, `"x;y"`, `"#"`. Decoding is a generic `%XX` hex
scan, so it is robust to any two-hex escape. This keeps the human-readable, dependency-free
format while making it correct for real string keys.

### 2.3 Generify the two key-I/O points; everything else is mechanical `<K>`

Only two lines actually touch a concrete `int`:
- **emit:** `sb.append(cur.getData())` → `sb.append(ks.serialize(cur.getData()))`
- **parse:** `int data = Integer.parseInt(parts[0]); TreeNode1.createNode(data, nil)` →
  `K data = ks.deserialize(parts[0]); TreeNode1.createNode(data, nil)`

The surrounding helpers (`serializePreOrder`, `deserializePreOrder`, `parseToken`, `Frame`)
become `<K>` carriers of `TreeNode1<K>`; the header (VERSION, timestamp, strategy simple name,
size, augmentor token) is already key-agnostic.

### 2.4 The `int` path delegates; behaviour is identical at `K = Integer`

`saveSnapshot(String, TreeContext)` and `loadSnapshot(String): TreeContext` keep their exact
signatures and their `Integer`-only extras (interval `AUGMENTOR=INTERVAL` token,
`forceSizeInternal`, the `TreeDiagnostics` size cross-check), but call the generified helpers
with `KeySerializer.INTEGER`. Because `INTEGER.serialize/deserialize` are
`Integer.toString`/`Integer.parseInt`, every byte of an existing `.rbt` file is produced and
parsed exactly as before — old snapshots load unchanged and the ~295-test suite is the proof.

### 2.5 Generic `load` reuses `OrderedSet`'s existing out-of-band-rebuild hook

`loadOrderedSet` builds `new OrderedSet<>(strategy, keyOrder)`, reconstructs the root into the
set's live engine via `getEngine().setRoot(root)` (+ parent fix-up), then calls
`resyncFromEngine()` — the method step 4 added precisely for "the root was replaced out of
band (snapshot load / undo / clone)". So no new `OrderedSet` surface is needed; the generic
load mirrors what the `int` `TreeContext` load already does through `forceSizeInternal`.

---

## 3. What becomes `K` vs what stays `int`

**New / becomes `K`:**

| Symbol | Form |
|---|---|
| `core.persistence.KeySerializer<K>` (new) | `String serialize(K)` / `K deserialize(String)`; `INTEGER`, `LONG`, `string()` |
| `FilePersistenceAdapter.serializePreOrder` | `<K>(TreeNode1<K>, TreeNode1<K>, StringBuilder, KeySerializer<K>)` |
| `FilePersistenceAdapter.deserializePreOrder` / `parseToken` / `Frame` | `<K>` over `TreeNode1<K>` + `KeySerializer<K>` |
| `FilePersistenceAdapter.resolveStrategy` | `<K> TreeStrategy<K>` (inferred at call sites) |
| `saveSnapshot(name, OrderedSet<K>, KeySerializer<K>)` (new) | generic save |
| `loadOrderedSet(name, KeySerializer<K>, Comparator)` / natural-order overload (new) | generic load |

**Stays `int` / `Integer` (do not touch):**

| Symbol | Why |
|---|---|
| `TreePersistenceAdapter` interface | names `TreeContext`; the `Integer` adapter contract |
| `TreeContext.saveSnapshot/loadSnapshot`, `cloner.snapshot()` | unchanged; delegate via the `Integer` adapter methods |
| `saveSnapshot(String, TreeContext)` / `loadSnapshot(String): TreeContext` | the `Integer` entry points; now call the `<K>` helpers with `KeySerializer.INTEGER` |
| `IntervalAugmentor` + the `INTERVAL` augmentor token | intervals stay `Integer`; generic save is `DEFAULT` |
| `TreeHistory` (undo/redo) | unchanged |
| `OrderedSet.java`, `RedBlackTree.java`, `TreeNode1.java` | already generic; no edits — load reuses `resyncFromEngine()` |

---

## 4. Execution order (each phase ships green)

### Phase A — add `KeySerializer<K>` (isolated, additive)
1. New `core.persistence.KeySerializer<K>` with `INTEGER`, `LONG`, `string()` (escaping +
   `%XX` decode). Nothing references it yet. **Gate:** compiles.

### Phase B — generify the adapter's private helpers; delegate the `int` path
2. `serializePreOrder` / `deserializePreOrder` / `parseToken` / `Frame` → `<K>` + a
   `KeySerializer<K>` parameter. `resolveStrategy` → `<K>`. The existing
   `saveSnapshot(String, TreeContext)` / `loadSnapshot(String)` pass `KeySerializer.INTEGER`.
   No public `Integer` signature changes. **Gate:** the `int` snapshot tests
   (`RegressionFixesTest`, `AuditFixesTest`, `TagPreservationTest`) still pass — byte-identical
   format.

### Phase C — add the generic entry points
3. `saveSnapshot(name, OrderedSet<K>, KeySerializer<K>)` and the two `loadOrderedSet`
   overloads, reconstructing through `getEngine().setRoot(...)` + `resyncFromEngine()`.
   **Gate:** additive; nothing depends on them yet.

### Phase D — tests
4. `KeySerializerPersistenceTest`: `OrderedSet<String>` round-trip via `string()` (incl.
   keys with `,` `;` `#` to exercise escaping); a reverse-`Comparator` round-trip (same
   comparator supplied to `load`); a `KeySerializer.INTEGER` `OrderedSet<Integer>` round-trip;
   and an `Integer` `TreeContext` round-trip to pin back-compat. Cross-check against a
   `TreeSet` oracle; clean up `.rbt` files in a `finally`. **Gate:** green.

### Phase E — docs
5. Flip ADR-002 action item 4 → done and item 5 → done; add
   `CHANGELOG-2026-06-04-key-serializer.md`; update the README persistence bullet to mention
   the pluggable key serializer.

---

## 5. Verification and rollback

- **Behaviour-identity argument (the `int` path):** at `K = Integer` the generified helpers run
  `Integer.toString`/`Integer.parseInt` exactly where the old code did, so existing `.rbt`
  files and the `TreeContext` API are byte- and behaviour-identical. A green `int` suite after
  Phase B proves no regression.
- **Generic path:** new `OrderedSet<String>` / custom-comparator / `Integer`-via-generic
  round-trips, oracle-checked, prove the `K` path.
- **Local gate (this environment):** the full `ant clean test` needs JDK 17 (host). Here, the
  persistence closure (`OrderedSet`, `FilePersistenceAdapter`, `KeySerializer`, `TreeContext`,
  `RedBlackTree`, strategies, `util`, `augment`, `interfaces`) is independent of
  `evolution`/`TreeEngineRegistry`/`PersistentTreeEngine` (which use JDK-16 syntax), so that
  subset + the new test compile under `--release 11` and the new test is **run** here as a
  smoke gate. Host runs the authoritative full suite.
- **Atomicity / rollback:** one branch; one commit per phase. The generic additions
  (A/C/D) are independently revertible; Phase B (the delegation) is the only edit to existing
  behaviour and is guarded by the `int` snapshot tests — revert `FilePersistenceAdapter.java`
  alone if it misbehaves.
- **Watch-list:**
  - key token must avoid `,` `;` `#`/empty — covered by the `string()` escaping + a test with
    adversarial keys.
  - `loadOrderedSet` must `resyncFromEngine()` after `setRoot` (size + FIFO window), and set
    `root.setParent(NIL)`.
  - `resolveStrategy` generification must still infer `<Integer>` at the existing call site.
  - generic save records `AUGMENTOR=DEFAULT`; document that custom augmentors are re-applied
    post-load (tags persist).

---

## 6. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A string key contains a format delimiter and corrupts the stream | Medium | `string()` escapes `% , ; # |`; a test uses `"a,b"`, `"x;y"`, `"#"` |
| The `int` path drifts from byte-identical | Low | `INTEGER` = `toString`/`parseInt`; `int` snapshot tests are the guard |
| `resolveStrategy<K>` breaks the inferred `<Integer>` call site | Low | one call site; verified on first compile |
| Generic `load` desyncs size/window | Low–Med | reuse `resyncFromEngine()` (the step-4 hook) |
| Scope creep into the interface / `TreeContext` / control plane | Medium | §1 non-goals; generic methods are additive on the concrete adapter |
| Empty / binary keys unsupported | Low | documented; `string()` throws on `""` |

---

## 7. First-edit checklist (start here)
1. **Phase A:** add `core.persistence.KeySerializer<K>` (`INTEGER`, `LONG`, `string()` with
   escaping + `%XX` decode).
2. **Phase B:** generify `serializePreOrder`/`deserializePreOrder`/`parseToken`/`Frame` and
   `resolveStrategy`; route `saveSnapshot(String,TreeContext)`/`loadSnapshot(String)` through
   `KeySerializer.INTEGER`. Keep all `Integer` signatures.
3. **Phase C:** add `saveSnapshot(name, OrderedSet<K>, ks)` + `loadOrderedSet(...)` (×2).
4. **Phase D:** `KeySerializerPersistenceTest` (String + reverse comparator + Integer +
   TreeContext back-compat); clean up `.rbt` files.
5. **Phase E:** ADR-002 items 4 & 5 → done; `CHANGELOG-2026-06-04-key-serializer.md`; README
   persistence bullet. Step 5+ (extract `StrategyScorer`, add `WorkloadMonitor`) is next.
