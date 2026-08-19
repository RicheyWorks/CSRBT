# ADR-029: B+ tree registry + genome slot — 2026-08-19

## Status

Accepted, implemented. Fires ADR-008's held D3 — **ahead of D2, by owner decision**
(2026-08-19: "fire all four held items"). D2 (pages to disk) remains held.

## Context

ADR-008 shipped `BPlusTreeEngine` as a first-class ensemble member but deliberately
kept it out of `TreeEngineRegistry` and `TreeGenome.StructureType`: D3 said "only
once D2 exists, because 'recommend the disk engine' is meaningless while it is an
in-memory structure with worse constants than RB below ~10⁵ keys." The owner has now
chosen to fire the slot anyway — the registry is the single source of truth for what
is buildable, and an engine reachable only by knowing its factory by name is exactly
the silent gap the registry exists to eliminate.

One mechanical obstacle: the registry builds `TreeEngine<Integer>`s, but
`BPlusTreeEngine implements RankedSet` whose `boolean add/remove` (the VERIFIED
voting requirement) collide with `TreeEngine`'s `void` signatures — one class cannot
implement both seams.

## Decision

1. **`StructureType.B_PLUS_TREE`** joins the enum (appended last, so no ordinal
   shifts for the existing seven).
2. **`BPlusTreeEngine.asTreeEngine()`** — a thin live view (same object, same
   monitor, no copying) carries the engine across the `TreeEngine` seam, mirroring
   how `PersistentRankedSet` carries the persistent engine across the opposite one.
3. **Registry slot**: `Support.ENGINE`, built via the view. The capability note is
   honest about the timing: in-memory today, wins at large n, pointer BSTs have
   better constants below ~10⁵ keys, disk pages are D2 and still held.
4. **Genome fitness model** (`bPlusFitness()`): rewards locality exploitation
   (cache-line-wide nodes), ordered bulk scans / rank-select, and disk-readiness at a
   discount; penalizes priority-queue preference; aspirational bias kept modest per
   ADR-008's small-n caveat. `ScoreCard` grows to eight structures — an **API-breaking
   constructor change** riding the 0.x line (next release 0.3.0); `bestStructure`,
   `scoreOf`, `average` (now /8), `range`, and `toString` all carry the new column.
   `prefersSearchTreeFamily()` includes B_PLUS_TREE.
5. **Controller**: `GenomeDrivenTreeController.buildStrategy` adds B_PLUS_TREE to the
   fail-loud non-strategy branch — a `TreeContext` cannot morph to an engine, same as
   PERSISTENT_TREE. Morph *selection* is unaffected (`implementedTypes()` still lists
   only the four strategies).

## Consequences

- `TreeEngineRegistry.create(B_PLUS_TREE)` returns a working engine; the exhaustive
  registry tests (`TreeContextTester`) pick the new value up automatically, and
  `BPlusRegistrySlotTest` pins the view's liveness, the note's honesty, and the
  genome column.
- The genome can now *recommend* B_PLUS_TREE diagnostically (`scoreCard`,
  `recommendedStructure`) without the controller ever silently no-op morphing to it.
- Firing D3 before D2 means the fitness model's disk-readiness term is aspirational;
  the weights say so, and D2 keeps its trigger.
