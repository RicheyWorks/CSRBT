# ADR-021: Atomic navigation primitives on OrderedSet — 2026-08-12

## Status

Accepted, implemented. Trigger: deep-sweep audit 2026-08-12, finding D-1.

## Context

`OrderedSet` advertises a single-writer + torn-read-free concurrent-read model
(ADR-004 R1): every public read runs under one `guardedRead` acquisition — an
optimistic `StampedLock` stamp with step-bounded walks and a locked fallback — so an
individual read is atomic with respect to writes.

`NavigableOrderedSet`, the drop-in `NavigableSet` face over it, broke that model by
composition. Every navigation answer was assembled from 2–4 *independently* guarded
reads: `countAtMost(k)` was `countInRange(minimum(), k)` (itself two calls), `lower`
was count-then-`select`, `Range.size()` was two counts. Each piece was atomic; the
composition was not. A write landing between the epochs made **read-only navigation
fail**: the audit probe measured, against keys the writer never touched, **399
exceptions** (`select(0)` out of `[1, n]` when a count from one epoch met a tree from
the next) and **1,870 contract-violating answers** (`floor(k) > k`; `ceiling`
skipping a continuously-present key) in 3.7M calls over 5 seconds. Single-threaded
behavior was exact `TreeSet` parity throughout — which is why the whole suite was
green while the concurrent contract was broken.

## Decision

Give `OrderedSet` **native navigation primitives, each answered in one guarded
acquisition**, and rebase the adapter on them:

- `floor(k)`, `lower(k)`, `ceiling(k)`, `higher(k)` — one O(log n) BST navigation
  descent (`navigateReadOnly`) under one `guardedRead`, with `findReadOnly`'s exact
  concurrency discipline: step-bounded when optimistic, torn-pointer diversion, no
  mutation, locked fallback. No count/select composition exists to race.
- `countUpTo(k, inclusive)` — one rank descent over intrinsic subtree sizes
  (`TreeNode1.getSize()`, augmentor-independent).
- `countBetween(lo, loInclusive, hi, hiInclusive)` (null bound = unbounded) — **both**
  bound descents run inside a single `guardedRead`, exploiting the key property of
  the R1 machinery: any number of walks under one optimistic stamp are atomic
  together, because `validate(stamp)` rejects the lot if a writer overlapped.

`NavigableOrderedSet.lower/floor/ceiling/higher` now delegate 1:1; `countUpTo`
delegates; `Range.size()` is a single `countBetween` call. The subview navigation
methods (first/last/floor-in-view/…) compose a clamp with ONE atomic base call plus
value-only range checks, so they inherit atomicity. Semantics are unchanged
single-threaded — the pre-existing `NavigableOrderedSetTest` `TreeSet`-parity suite
passes untouched.

## Consequences

- Read-only navigation under a concurrent writer is now exception-free and
  contract-correct: the probe (`NavigationAtomicityProbeTest`, 3 readers × 2.5 s
  against a churning writer) records zero exceptions and zero violations, where the
  audit measured hundreds/thousands pre-fix.
- Navigation cost drops from two descents (count + select) to one.
- New public API on `OrderedSet` (six methods). The adapter no longer needs
  `select`-based navigation; `select`/`countInRange` remain for their own callers.
- `EnsembleOrderedSet` order statistics still route member-by-member; each member
  call is atomic per member (unchanged — cross-member consistency is the vote's job,
  per ADR-006/007).

## Held

Iterators and `snapshot()` on views still take an `inOrder()`/`rangeQuery` snapshot
(one acquisition, already atomic). `pollFirst`/`pollLast` compose a read and a write
— they are mutations, serialized by the writer lock like every mutation, and out of
scope for read atomicity.
