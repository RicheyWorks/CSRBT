# CHANGELOG 2026-06-09 — ADR-009 P2: the NavigableSet adapter

CSRBT can now be dropped into code written against `java.util.NavigableSet`/`TreeSet` —
the adoption gap the external review correctly named. One new class, zero engine changes.

## `core.adapter.NavigableOrderedSet<K>` (new)

- **Navigation rides the rank machinery:** `floor(x)` = select(count ≤ x), with
  `lower`/`ceiling`/`higher` the same walk nudged at the boundary — all O(log n) on
  `OrderedSet`'s existing `countInRange`/`select`/`minimum`/`maximum` surface; no new engine
  methods. Iteration is a torn-read-free snapshot (R1 semantics), so it never throws
  `ConcurrentModificationException` — documented as the deliberate divergence from
  `TreeSet`'s fail-fast iterators.
- **The base adapter is fully mutable:** add/remove/clear/pollFirst/pollLast/iterator.remove
  all delegate to the backing `OrderedSet` (exposed via `base()`).
- **Views are read-only — the ADR's honesty clause.** `subSet`/`headSet`/`tailSet` (all six
  overloads) and `descendingSet` navigate, iterate, count, and compose correctly (desc of a
  range, range of a desc, nested sub-ranges with `TreeSet`'s bound checks), but every view
  mutator throws `UnsupportedOperationException` naming the base set as the mutation point.
  Sub-range write-through is where `NavigableSet` adapters traditionally rot; this one
  refuses loudly instead of behaving subtly wrong. Views are live — base mutations appear in
  them immediately.
- `comparator()` returns the real comparator even for natural ordering (contract-legal;
  `TreeSet`'s `null` convention noted in the javadoc).

## Tests (`NavigableOrderedSetTest`, 5 tests; suite 466, green)

- Navigation parity with `TreeSet` for **every probe in [−3, 402]** over a 120-key set —
  present, absent, below-range, above-range, and both boundary classes.
- Range views: five ranges × all four inclusivity combinations, contents + size + four-way
  navigation parity per probe; empty views; `IllegalArgumentException` on inverted and
  escaping sub-ranges.
- Descending views: parity, `desc(desc(x)) == x`, composition both directions.
- Mutation: polls and iterator.remove hit the base; the read-only clause asserted on every
  view mutator; live-view visibility of base mutations.
- Contract edges: `first()` throws on empty, `pollFirst()` nulls, NPE on null probes.

Next per ADR-009: P3 (event listener + JSON tree export), G0 (GitHub Actions on Ant).
