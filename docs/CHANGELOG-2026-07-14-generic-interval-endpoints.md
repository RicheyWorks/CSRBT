# CHANGELOG 2026-07-14 — generic (typed) interval endpoints

The outer-ring ADR's Phase 7 closer, executed exactly as its 2026-07-12 implementation note
scoped it: the blocker was `TreeNode1.augmentedValue` being a plain `int` — it cannot hold a
generic (or even `long`) subtree max-hi, which is precisely why `IntervalAugmentor` was
`Integer`-bound. The fix is additive at every layer; no existing augmentor, test, or consumer
changes behavior.

## What landed

**`TreeNode1.augmentedRef`** — one new reference-typed slot beside the int `augmentedValue`,
with getter/setter (non-propagating, like `setTag`; callers `reaugment()`), cleared in
`clear()`, and reference-copied in `deepCopy`. The slot's contract: payloads are **immutable —
replace, never mutate** — which is exactly what makes the deepCopy reference copy safe (a clone
shares payload objects with its source until either side replaces them; replacement can't
bleed). Default augmentor and every int-slot augmentor ignore it.

**`GenericIntervalAugmentor<E>`** — the Comparator-parameterized interval augmentor
(`augment/GenericIntervalAugmentor.java`). Same CLRS 14.3 algorithms as the int version; the
encoding moves off `{String tag, int augmentedValue}` onto an immutable `Ref{hi, maxHi}` record
in the new slot. `over(Comparator)` / `natural()` factories; `insertInterval` (add-or-restamp,
identity-guarded augmentor install), `intervalSearch` (one overlap in O(log n), `null` = proven
miss), `intervalSearchAll` / `stabQuery` (pruned DFS), `intervals()` (in-order dump). Unstamped
keys read as degenerate `[lo, lo]` — the same fallback the int version's `parseHi` applies to a
missing tag. Queries on a non-empty set whose augmentor is someone else **fail loud**
(`IllegalStateException`) instead of pruning wrong off refs nobody maintains. Hosted on
`OrderedSet<E>` (the generic surface), not `TreeContext` (Integer-bound by design).

**`OrderedSet` ref carry** — `captureKeyRefs`/`restoreRefs`, the ref-slot twins of
`captureKeyTags`/`restoreTags`, wired into `setStrategy` and `selfRepair`. Restoring a payload
whose derived part (maxHi) is stale for the new tree shape is safe: each restore `reaugment()`s
to the root, and the ascending-key restore order finalizes every node bottom-up — the same
argument the tag carry has always relied on. So typed interval trees survive strategy morphs
and self-repair exactly like int ones; the `setStrategy` javadoc now says so.

**Untouched, by construction:** `augmentedValue`, tags, the int `IntervalAugmentor` (header now
points here; its "later, separate piece of work" note is retired), order statistics (intrinsic
`size`), and every existing test. The int path stays as the specialization.

## Evidence

`GenericIntervalAugmentorTest` — oracle-driven, deterministic seeds, house style:

- CLRS 14.3 worked shape at **epoch-millis scale** (endpoints ×10⁹, past `Integer.MAX_VALUE`):
  the hit and the theorem's proven miss.
- Seeded random oracle (300 intervals incl. raw-add degenerates, 200 queries): `searchAll`,
  `search`, and boundary `stab` all equal a brute-force scan of the reference map.
- `String` endpoints under `CASE_INSENSITIVE_ORDER`: the comparator, not the type, is the
  authority.
- Add-or-restamp + `lo > hi` validation, mirroring the int version.
- Coexistence pins: intrinsic size / select / median / maximum, tags stay empty.
- Morph + selfRepair carry: same oracle answers before RB→AVL, after, and after repair.
- deepCopy alias safety: restamp the original after cloning; the clone's max-hi must not move.
- Wrong-augmentor queries throw; empty sets are safely answerable by anyone.

## Held items / non-goals

- The ref slot is **not persisted** by `FilePersistenceAdapter` (v1): rebuild interval indexes
  from their source after a load, the way SmokeHouse rebuilds every index from the log.
- SmokeHouse consumption (epoch-millis `long` spans in `IndexedStore`, retiring its "CSRBT's
  IntervalAugmentor is deliberately Integer-bound in v1" note) is the follow-up step, per the
  ADR: "lands in CSRBT with its own oracle tests before SmokeHouse consumes it."
- Rotation pricing (ADR-009 §3) and the scorer's E3/E3b SELECT re-run remain open from the
  same-day scorer recalibration.
