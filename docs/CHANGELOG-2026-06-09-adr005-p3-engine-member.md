# CHANGELOG 2026-06-09 — ADR-005 P3 + ADR-003 leftovers: engine-tier ensemble members, Option C, memory controls

Two ADRs' held items cashed in one slice (commit `a8d40eb`), plus the test slice that should
have shipped with it (this follow-up — the feature commit landed with only 7 lines of test
adaptation; `EnsembleEngineMemberTest` and `EnsembleRebuildShadowTest`, 12 tests, close the gap).

## ADR-005 P3a — the `RankedSet` seam (`core/interfaces/RankedSet.java`, new)

- **The contract:** `OrderedCollection` + `OrderedSet`'s order statistics + the realized write
  meters + structural hooks (`height()`, `validateStructure()`, `estimatedMemoryBytes()`) with
  conservative defaults. VERIFIED voting compares answers with `Objects.equals`, so the javadoc
  pins every implementation to `OrderedSet`'s exact semantics (null returns, exceptions).
- **`OrderedSet` implements it** with its existing methods — no behavior change.
- **`EnsembleMember` holds a `RankedSet`**, not an `OrderedSet`: fan-out, voting, healing, and
  promotion speak the seam only. Strategy machinery moved behind `isStrategyBacked()` /
  `orderedSet()` (throws for engine members). Members are now labeled, since an engine member
  has no strategy class to name.

## ADR-005 P3b — the persistent engine joins (`core/PersistentRankedSet.java`, new)

- **Adapter** over the weight-balanced `PersistentTreeEngine`: method-for-method `OrderedSet`
  parity (boolean add/remove report effective change; successor/predecessor throw on absent
  arguments and return null at the extremes; min/max/median/percentile null on empty), realized
  write meters, 56-byte/node footprint model. Reads are wait-free by construction — the one
  member kind whose reads need no guard at all.
- **`Builder.persistentMember()`** adds one to any ensemble. It mirrors, serves, votes, heals,
  and fails over like any member; the cost-model scorer cannot rank it (no StrategyId), so the
  controller never promotes it *automatically* — explicit `promote()` or failover only.
- **Controller dispatch:** StrategyId indexing skips engine members; the meters line takes
  `RankedSet.height()` (the engine grew an iterative O(n) walk for it); the E3 health pass
  validates engine members by `validateStructure()` + content equality with the trusted primary
  (they are outside `StrategyHealthCheck`'s vocabulary).

## ADR-005 P3c — snapshot persistence (`FilePersistenceAdapter`)

- **`saveSnapshot(name, Snapshot, KeySerializer)`** writes a persistent-engine snapshot as a
  flat ascending key list (header token `PersistentTreeEngine`). No colors or structure — the
  engine is weight-balanced, so ascending replay on load rebuilds an equivalent tree. A key
  whose token contains `';'` fails loudly at save: silently dropping a *key* (unlike a tag)
  would corrupt the set.
- **`loadPersistent(name, KeySerializer, Comparator)`** replays into a fresh engine; null on
  missing/malformed/foreign files, comparator supplied by the caller (never serialized).

## ADR-003 Option C — `REBUILD_SHADOW` (held at E-series, landed now)

- The write-lean mode: the primary takes every write, shadows take **none** and are rebuilt
  wholesale from the primary every `rebuildEvery` writes (default 4096; builder-tunable). The
  rebuild runs after the triggering write commits, so the fresh copy includes it. A rebuilt
  shadow is exact and *warm* — an O(1) promotion target — until the next write strands it
  again; between rebuilds it no more serves, votes, or fails over than a sampled shadow, and
  the health pass treats its drift as design, not fault. `clear()` is never skipped.

## ADR-003 "Revisit" — memory controls

- **`memoryCeilingBytes(long)`** — soft ceiling over the summed `estimatedMemoryBytes()` of
  non-retired members, checked O(K) on every write. Breach latches
  `isOverMemoryCeiling()` and logs one loud `event=memory_ceiling` line (one on recovery). The
  ensemble never degrades itself — mode/K changes have semantic consequences (exactness,
  voting), so they stay the operator's call.
- **`maxMembers(int)`** — hard cap on K, enforced at `build()`.

## Tests (this follow-up; suite 443, green)

- `EnsembleEngineMemberTest` — engine member mirrors writes exactly and refuses `orderedSet()`;
  explicit promotion serves reads + order stats; VERIFIED voting with an engine voter; the
  health pass quarantines and heals a divergent engine member (key dropped out-of-band — the
  P3 validation path, invisible to `StrategyHealthCheck`); the controller never auto-promotes
  it across evaluation windows; persistent snapshot round-trip (frozen version, not the
  mutated engine; invariants validate after replay); missing/foreign loads return null and a
  `';'`-leaking serializer fails loudly.
- `EnsembleRebuildShadowTest` — the full cadence cycle (99 writes: shadows empty/inexact →
  100th: exact, includes the trigger → 101st: drifting again); sync-on-promote for a stale
  shadow; mid-cadence drift repairs nothing; ceiling latch + recovery; cap-K rejection at
  `build()`.

## Doc reconciliation

- ADR-005: item 5 closed; status now "P1–P3 landed".
- ADR-003: Option C "held as a future optimization" → landed as `REBUILD_SHADOW`; the memory
  ceilings "Revisit" bullet closed.
- Session index "deliberately open" list pruned accordingly.
