# CSRBT capability audit — fed, shown, tested (2026-07-14)

Full sweep of every public capability in `csrbt-core` and `csrbt-experimental`, cross-referenced
against three questions: is it **tested** (CSRBT's own suite, 61 test classes), is it **fed**
(consumed by SuperBeefSort / SmokeHouse), and is it **shown** (visible in a demo/exhibit:
aquarium, store dashboard, visualizer, percentile service).

**Verdict up front:** the surface is in remarkably good shape. Of ~40 distinct capabilities, all
but one have direct test coverage, and the ecosystem feeds every production-intent surface. The
audit found **one untested surface** (the per-instance `optimisticVotes` pin, hardening L-1 — a
test now closes it), **one dead experimental class** (`TreeAgent`: zero tests, zero consumers),
and a handful of capabilities that are tested but never *shown* — exhibit gaps, not correctness
gaps. Details and the fix-list at the bottom.

---

## 1. Core `OrderedSet` facade

| Capability | Tested (CSRBT) | Fed (ecosystem) | Shown (demo) |
|---|---|---|---|
| add / remove / contains / inOrder / clear | OrderedSetTest, OrderedSetPropertyTest (jqwik) | everywhere — every feeder, both stores | aquarium, dashboard |
| `fromSorted` / `buildFromSorted` O(n) bulk build (ADR-014) | BulkBuildTest | BulkBuildFeeder, BalancedBuildFeeder; SmokeHouse recovery + every `IndexedStore.build()` | dashboard (recovery is the open path) |
| Order statistics: `select` / `rank` / `median` / `percentile` / `countInRange` / `rangeQuery` | SizeAugmentTest, WindowingTest, StrategyInvariantTest | SBS `OrderStatsTest`, PercentileService; SmokeHouse `countRange`/`nthKey`/`rankOf`/`medianKey`/`percentileKey` (oracle: CsrbtUnlockTest) | percentile service |
| `successor` / `predecessor` / `minimum` / `maximum` | OrderedSetTest | SmokeHouse `firstKey`/`lastKey`; range walks | — |
| `searchDepth` (measured read, 2026-07-08) | EnsembleWindowDepthTest, RotationDepthSeamTest; SearchDepthBenchmark (JMH) | **not fed by ecosystem main** — PhaseShiftWorkTest (in flight, SBS) is the first consumer-side exercise | — (exhibit gap, see §7) |
| Windowing `setMaxSize` (FIFO eviction) | WindowingTest, EnsembleWindowDepthTest | StreamingFeeder, aquarium window regimes; SmokeHouse `retainNewest` garbage ledger | aquarium ("window off" booth) |
| Events `setEventListener` (ADR-009 P3) | TreeEventExportTest | SmokeHouse retention ledger consumes `Evict` events — a load-bearing feed | visualizer (via recorder) |
| `selfRepair` + health gate | SelfRepairGateTest, StrategyInvariantTest | HealthGatedFeeder (SBS) — every non-RB bulk build is gated | dashboard (fallback verdicts) |
| `setStrategy` (live morph) | HealthGatedMorphTest, MorphControllerTest | WorkloadAdaptation (SBS), SmokeHouse ADAPTIVE tier pilot | aquarium + dashboard (strategy line) |
| `setAugmentor` (generic augmentors) | AugmentorCoexistenceTest, TagPreservationTest, CloneAugmentorTest | SmokeHouse interval index (`IntervalAugmentor` + sidecar) | — |
| `getEngine` / `resyncFromEngine` seam | indirect: every checkpoint/persistence restore crosses it (KeySerializerPersistenceTest, AuditFixesTest) | not fed — it exists for TreeContext/persistence collaborators, by design | n/a |
| Meters: `rotationCount`, `avgInsert/DeleteTimeMs` | WorkloadMonitorTest (as monitor source) | RollingWorkloadMonitor feed in both adaptation facades | aquarium tickers |
| Concurrent lock-free reads (ADR-004) | ConcurrentReadStressTest, PersistentEngineConcurrencyTest | SmokeHouse HTTP threads read the index off-lock | dashboard (SSE reads while driver mutates) |

## 2. Strategies

All five (`RedBlack`, `AVL`, `Splay`, `Hybrid`, `WeightBalanced`) are invariant-tested
(StrategyInvariantTest) and all five are fed: RB/AVL/Splay/Hybrid are the SBS morph family
(WorkloadAdaptation), WeightBalanced is the recovery-sort profile pick (StrategyAdvisor) and the
evolution machine's genome dimension (Δ, Γ). SmokeHouse's ADAPTIVE tier clamps WRITE_HEAVY to RB
precisely because WB is outside the morph family — the clamp itself is tested in SmokeHouse.
No gaps.

## 3. Control plane (ADR-006/-009)

`MorphController`, `MorphPolicy`, `RollingWorkloadMonitor` (CMS skew sketch),
`CostModelStrategyScorer`, `WorkloadFeatures`, `MorphHistory`, `StrategyId` — all directly tested
(MorphControllerTest, MorphPolicyTest/ControlTest, WorkloadMonitorTest, StrategyScorerTest,
ControllerConvergence/MonitorFeed/ControlPlaneFlagTest) and all fed through both `WorkloadAdaptation`
(SBS) and the SmokeHouse pilot. Shown live in the aquarium and the store dashboard (pilot verdicts).
**`PhaseShiftWorkTest` (SBS, in flight) is the capstone**: the first end-to-end measurement of
whether adaptivity *wins* — comparisons vs pinned RB/AVL/Splay and JDK TreeMap/SkipList on a
phase-shifting workload. It needs a host-side run (fix for the `withNaturalOrder` inference error
was applied 2026-07-13).

## 4. Ensemble (ADR-003/-005/-006/-007)

| Capability | Tested | Fed |
|---|---|---|
| MIRROR / VERIFIED / REBUILD_SHADOW / SAMPLED_SHADOW / READ_REPLICA modes | EnsembleOrderedSetTest + 13 mode-specific classes | EnsembleTargetFactory maps AccessPolicy → mode; SmokeHouse ENSEMBLE tier |
| Quorum voting + quarantine + primary failover (E4) | EnsembleVerifiedTest, EnsembleHealthTest | SmokeHouse ENSEMBLE tier (reads) |
| Verified sampling `verifyEvery` (ADR-006) | EnsembleVerifiedSamplingTest | EnsembleTargetFactory |
| Optimistic lock-free votes — global kill switch (ADR-007) | EnsembleVerifiedConcurrencyTest | default-on everywhere |
| **Per-instance `optimisticVotes` pin (hardening L-1)** | **was untested → `EnsembleOptimisticVotesKnobTest` (new, this audit)** | never pinned by ecosystem (acceptable: the default follows the global) |
| `parallelFanOut` / MemberExecutor | EnsembleFanOutTest | ParallelFeeder path (SBS) |
| `persistentMember` (path-copying engine as member) | EnsemblePersistenceTest, EnsembleEngineMemberTest | EnsembleTargetFactory |
| `engineMember` (BPlusTreeEngine as member, ADR-008) | BPlusTreeEngineTest, EnsembleEngineMemberTest | EnsembleTargetFactory (large-n policy) |
| `memoryCeilingBytes` / `maxMembers` | EnsembleReplicaTest | EnsembleTargetFactory |
| Ensemble window `setMaxSize` fan-out (2026-07-08) | EnsembleWindowDepthTest | SBS windowless-target guard (Gap-8) |
| `buildAllFromSorted` | BulkBuildTest | BulkBuildFeeder ensemble path |
| `promote()` public seam | exercised by 15 test classes via controllers | internal to EnsembleController — correct layering |
| No per-member `Evict` events | — | SmokeHouse *refuses* `retainNewest` on ENSEMBLE/EVOLUTION tiers because of it — the limitation is enforced and tested consumer-side |

## 5. Evolution machine (ADR-011) + engines + persistence

`PolicyGenome`/`Fitness`/`PolicyBandit`/`PolicySearchController` (V3) /
`PolicyEvolutionController` (V4) / `StrategyIdBridge`: all directly tested, all fed —
SBS `EvolutionAdaptation` drives V3+V4 on live ensembles; SmokeHouse's EVOLUTION tier feeds it from
a real store. Shown via `SearchArenaSession` → `demo/visualizer.html` arena replay.
`GenomeDrivenTreeController` (the older v2 controller) is tested and drives `ArenaSession`, but is
superseded for new feeding — fine. `TreeGenome` is deprecated and tested as such.
`StrategyBattleRunner` is exercised via EnsembleBenchmarkTest/TreeContextTester only — thin but
proportionate to its demo role.

Engines: `RedBlackTree` (everything), `PersistentTreeEngine` (PersistentTreeEngineTest +
concurrency), `BPlusTreeEngine` (dedicated oracle suite) — all tested; both alternates fed as
ensemble members. `PersistentRankedSet` standalone facade and `TreeEngineRegistry` are
tested-but-unfed (registry is internal glue; the persistent facade earns its keep as the
`persistentMember` body).

Persistence (`FilePersistenceAdapter`, `KeySerializer`, `StringKeySerializer`): tested
(KeySerializerPersistenceTest, EnsemblePersistenceTest, AuditFixesTest). Deliberately **not** fed
by SmokeHouse — the store's log is the only truth and every index is a rebuildable cache; tree
snapshots would violate that. By design, documented here so nobody "fixes" it.

Legacy `TreeContext` surface (Integer-only): `TreeHistory` undo/redo/checkpoints
(RegressionFixesTest, SizeAugmentTest, AuditFixesTest), `TreeCloner` (CloneAugmentorTest),
`TreeDiagnostics` (TreeContextTester, RegressionFixesTest), `IntervalAugmentor` stab/overlap
statics (AugmentorCoexistenceTest + SmokeHouse IntervalIndexTest oracle) — all covered.
`NavigableOrderedSet` JDK adapter: dedicated test + fed by BeefSort and SmokeHouse.
`TreeExport`/`TreeSessionRecorder`: tested, fed by FullOrganismDemo, shown in the visualizer.

## 6. Experimental module

`ViabilityMap` (ViabilityMapTest) and the cache-transfer stack `CacheGenome`/`SegmentedLruCache`/
`CacheEvolutionLoop` (CacheTransferExperimentTest) are tested experiment instruments — not fed,
correctly, since they're ADR-012 measurements. `ArenaSession`/`SearchArenaSession` are recorder
mains whose outputs are the checked-in `docs/arena-*.json` replays — verified by running, not by
suite. `TreeEcology` has thin coverage (TreeContextTesterAdditions only). **`TreeAgent` has zero
tests and zero consumers** — dead weight.

## 7. Findings and fix-list

1. **[closed by this audit] `optimisticVotes` pin untested.** The L-1 hardening (2026-07-08,
   `9c6b657`) added the per-instance pin; only the global switch had coverage.
   → `EnsembleOptimisticVotesKnobTest` (4 tests): oracle-parity churn under pin=false (every vote
   forced through `voteLocked`), pin=true immune to the global kill switch, unpinned follows the
   global in both positions, and quarantine fires through the pinned path with the global set to
   the *opposite* — proving the pin, not the static, chose the route. Host-side run required
   (sandbox is JRE 11): `.\gradlew :csrbt-core:test --tests "*EnsembleOptimisticVotesKnobTest"`.
2. **[in flight] Adaptivity earns-its-keep census.** `PhaseShiftWorkTest` (SBS) is written and
   compile-fixed; run host-side and read the VERDICT line. This is the largest untested *claim*
   (not surface) in the ring: that the control plane beats every static shape on shifting skew.
3. **[recommend: delete or test] `TreeAgent`** (experimental): zero tests, zero consumers, no ADR
   anchor. Either give it the ViabilityMap treatment or remove it; untested experimental code in a
   published-adjacent repo is where the next audit's bug lives.
4. **[exhibit gap] `searchDepth` is measured but never shown.** The store dashboard already ticks
   stats over SSE; publishing the index's probe depth for a hot key (one `searchDepth` call per
   stats tick, read-path, off-lock safe) would make morph wins *visible* — depth dropping when the
   pilot flips strategy under skew. Small, contained, high-payoff.
5. **[exhibit gap] Ensemble/evolution tiers have no live exhibit.** The dashboard demos the
   ADAPTIVE tier; ENSEMBLE/EVOLUTION are exercised only by tests and replay files. A dashboard
   toggle (or a second demo main) opening the store at `IndexTier.ENSEMBLE` would show quarantine
   and vote traffic live. Larger than #4; do it only if the exhibit earns audience.
6. **[minor, note only] SmokeHouse doesn't surface `successor`/`predecessor`** (floor/ceiling-style
   key navigation) even though the index funds them for free. Add `nextKey(K)`/`prevKey(K)` if a
   consumer ever asks; not worth speculative API.
7. **[re-audit note] `EnsembleOrderedSet.OPTIMISTIC_VOTES` is a public mutable static** — any code
   in the JVM can flip the vote path for every unpinned ensemble. ADR-007 accepts this as a kill
   switch; the L-1 pin is the mitigation. Flagged so the trade stays deliberate.

**Not audited here:** SmokeHouse's own log/compaction seams (covered by the 2026-07 Phase-4 debug
audit, `SmokeHouse/docs/phase4-audit-debug-report.md`) and SBS sort strategies (DifferentialTest
regime). This audit is the CSRBT surface and its feeding only.
