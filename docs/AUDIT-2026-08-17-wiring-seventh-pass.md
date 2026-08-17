# Wiring audit — seventh pass, 2026-08-17

**Scope:** a second constructor-to-constructor **wiring audit** in the shape of
`AUDIT-2026-08-14-wiring-and-fifth-pass.md` — every public and package-private type in
`csrbt-core` and `csrbt-experimental` walked end to end: every constructor and builder
path, every interface seam and its implementations, every stub/dead-end marker, the
cross-module wiring from the ecology layer down to the core seams, and a full
test-only-reachability enumeration. Emphasis on the surface that did not exist on
2026-08-14: `CHANGELOG-2026-08-17-sixth-pass-fixes.md` (S6-01…S6-47) and **ADR-023**
(rotations carry the height), **ADR-024** (per-member rotation metering), **ADR-025**
(save failure signaling), **ADR-026** (load failure signaling), all landed the same day.

**Method:** mechanical reachability analysis (every declared type and every public method
cross-referenced against main, test and JMH sources, both directions), then hand-reading
of every constructor, every seam implementation and every new ADR's code against its ADR
text, then probe programs against the compiled classes for anything the reading suspected
— null-argument parity across both ensemble-load branches, `buildAllFromSorted` across
five ensemble configurations, and 40-tree sweeps of the `TreeEcology` indices. Nothing
below was decided by reading alone; each finding has a probe or a test behind it.

Suite before: **928 tests, 0 failures**. Suite after: **948 tests, 0 failures**, 0 javadoc
warnings, `--rerun-tasks` clean. JDK 21.

---

## Verdict: clean on the new surface, with seven findings, all of them wiring

**ADR-023, ADR-024, ADR-025 and ADR-026 are completely wired.** Every seam each of them
introduces is reachable, implemented, and consumed by the thing its ADR says consumes it,
and every deliberate non-consumer is documented at the point where a reader would ask:

- **ADR-023** — `rotateLeft`/`rotateRight` (carrying) vs `rotateLeftLocal`/`rotateRightLocal`
  (primitive) are correctly partitioned across all five strategies. `RedBlackStrategy` and
  `WeightBalancedStrategy` reach the carrying pair (RB via `MutableTree.rotateLeft` →
  `RedBlackTree:155-156`); `AVLStrategy`, `HybridStrategy` and `SplayStrategy` call the
  `*Local` primitives, each with its proof at the call site. No caller of the local pair is
  outside a height-refreshing walk. `refreshHeightUpward` starts at the strict parent, which
  is the node the `*Local` setters have just recomputed — the fixed-point precondition holds.
- **ADR-024** — `EnsembleMember`'s meter is driven from the only code that knows which members
  a write reached (`EnsembleOrderedSet.fanOutWrite:512,527` and `replicaWrite:679,690,715-717`),
  cleared at all three controllers' window boundaries (`EnsembleController:249`,
  `PolicySearchController:204`, `PolicyEvolutionController:275`), and consumed by
  `priceComparably` (V3) and the all-or-nothing generation gate (V4). `CostModelStrategyScorer`
  and `GenomeDrivenTreeController` are the two documented non-consumers and both say why.
  `clear()` is unmetered, as the ADR requires. A failed recipient's mark is never folded.
- **ADR-025 / ADR-026** — all four save shapes and all five load shapes have their reporting
  twin, the published `void`/`null`/`false`/`[]` shapes all delegate to it and discard, and
  the interface defaults are the two *different* honest defaults the ADRs argue for. One
  argument-validation hole on one branch: finding 1 below.

**No stubs.** Zero `TODO`/`FIXME`/`XXX`/"not implemented"/"placeholder" markers in main code
across both modules (one "for now" in `StrategyId`'s javadoc, describing a deliberate package
boundary). No empty method bodies, no `return null` stubs, no option accepted without effect
that is not documented as held (`MorphPolicy.evaluate`'s `features` parameter is the only one,
and its javadoc says so in the class doc *and* on the parameter).

**Cross-module wiring is real, not reached around.** All 28 `csrbt-experimental` types are
referenced by at least one other main type; the ecology layer consumes the core seams it
claims to (`EcologyRecorder implements WorkloadMonitor` and chains to a delegate;
`ExperimentLab`/`EcologyFieldDay`/`WorkloadTrace` drive real `TreeContext`s). Every ADR-015…
ADR-020 component is reachable from `ExperimentLab`, `EcologyFieldDay`, `WorkloadTrace` or
the `.eco` protocol — none is built once and never called. Every `.eco` directive
(`name/keys/seed/window/phase/factor/model/cross/data/note/tree/expect`) reaches an effect;
`factor:` in particular threads through `TheoreticalModels.Environment` into every
rate-bearing model.

The seven findings are below. Four are fixed with red-before/green-after regression tests,
two are fixed documentation-plus-report changes with the same discipline, one is a coverage
gap closed. Nothing here is a breaking change and **the next release is still 0.2.1**.

---

## Findings

### 1 (High). `loadEnsemble` validated its serializer on only one of its two branches — and blamed the file for the caller's bug. **FIXED**

`FilePersistenceAdapter.tryLoadEnsemble` dispatches on the snapshot's header: a
`PersistentTreeEngine` snapshot goes to `readFlatKeys`, everything else to
`tryLoadOrderedSet`. The `keySerializer` null check lived *inside* `tryLoadOrderedSet`, so
only the structured branch had one. Against a flat snapshot a `null` serializer sailed past
`snapshotStrategy` (which is already I/O), reached `readFlatKeys`, and NPE'd on the first key
token — where the terminal catch, correctly, classified a non-`IOException` as a bad *file*:

```
p2flat: null ks ACCEPTED (no throw)
ERROR FilePersistenceAdapter Failed to load snapshot 'p2flat'
 java.lang.NullPointerException: ... because "ks" is null
        at FilePersistenceAdapter.readFlatKeys(FilePersistenceAdapter.java:798)
```

The caller got `LoadResult[... MALFORMED: unreadable content: java.lang.NullPointerException]`
and `loadEnsemble` returned `false`. `MALFORMED` is defined as "the file exists and is not a
usable snapshot… the file is left on disk exactly as it was found" — a caller acting on it
goes and inspects a perfectly good snapshot, and (per ADR-026's own framing) must not
overwrite it. This is precisely the class of wrong answer ADR-026 exists to remove, produced
by ADR-026's own code, and it contradicts ADR-026 §5 verbatim: *"a null `KeySerializer` or a
null ensemble target still throw `IllegalArgumentException` before any I/O."*

**Fix:** `persistence/FilePersistenceAdapter.java:924` — the check moves to the top of
`tryLoadEnsemble`, beside the existing `target` check and before `snapshotStrategy`'s read.
Javadoc on both `loadEnsemble` and `tryLoadEnsemble` states the rule and why a caller defect
throws rather than reporting.

**Test:** `SeventhPassWiringTest$EnsembleLoadArgumentParity` — the flat branch throws through
both the reporting twin and the published boolean, the structured branch is asserted to match
(the parity this restores), validation is shown to precede I/O (an absent snapshot still
throws rather than reporting `ABSENT`), and `genuineMalformationStillReported` pins the guard
as *not* a blanket: a truncated flat snapshot is still `MALFORMED` and the target is still
untouched. Red before on `flatBranchRejectsNullSerializer`.

### 2 (High). `TreeContext.saveSnapshot` announced success for saves that failed. **FIXED**

```java
public void saveSnapshot(String name) {
    persistenceAdapter.saveSnapshot(name, cloner.snapshot());
    logger.info("Snapshot saved: '{}'", name);          // unconditionally
}
```

ADR-025 gave the adapter a save outcome; ADR-026 migrated `TreeContext.loadSnapshot` onto its
read-side twin precisely because the facade was *"claiming 'not found' for a file it found"*.
The save-side twin, eleven lines above it in the same class, was left behind. A full volume, a
revoked permission, a snapshot directory that never came up, or a commit rename that cannot
publish therefore produced the adapter's `ERROR ... previous file (if any) left intact`
immediately followed by the facade's `INFO Snapshot saved: 'x'` — and this is the worse
direction of the two, because the caller walks away believing state is durable.

**Fix:** `TreeContext.java:266` — `trySaveSnapshot`, and one log line per `SaveStatus`. The
signature stays `void` (published 0.2.0), the behavior stays best-effort and non-throwing, and
the previous-file guarantee is untouched; callers that need to *act* still go to the adapter.

**Test:** `SeventhPassWiringTest$FacadeSaveReporting` — a commit rename blocked by a non-empty
directory at the target path (uid-independent, so it cannot silently pass under root, per
ADR-025's own rejected-probe note) must produce no "Snapshot saved" line and must produce the
failure line; a real save must still produce the success line (so the pin is not vacuous); and
a third test holds the published behavior — still void, still non-throwing, other snapshots
and the live context untouched. The capture raises `TreeContext`'s logger to INFO for the
duration (`MorphControllerTest`'s pattern) — without that the pre-fix INFO success line would
be filtered by the root WARN level and the test would pass against the defect. Red before.

### 3 (High). Two structurally-constant indices were still printed as measurements, with interpretation bands, in the classroom report. **FIXED**

`EcologyRecorder`'s class javadoc has stated the ground truth since ADR-015:

> …`TreeEcology`'s distribution indices are constants on a duplicate-free BST: every stored
> key has abundance exactly 1, so Shannon H′ ≡ ln(S), evenness ≡ 1, **empirical z ≡ 1, and
> Pianka overlap between disjoint-by-construction subtrees ≡ 0**.

Only evenness was ever settled (EC-3 / sixth-pass **S6-27**): its accessor was deprecated onto
the instruments that measure, and `ecologyReport()` replaced the number with the reason.
`empiricalZValue()` and `nicheOverlap()` were left undeprecated, with javadoc that reads as if
the numbers vary ("z ≈ 0.30 means the tree's structure follows typical island dynamics";
"MacArthur's warblers maintained O ≈ 0.3–0.5"), and — the part that matters — **still printed
to four decimal places with an interpretation band beside each**, in a report written for a
classroom audience.

Measured, 40 random Red-Black/AVL/Splay trees of 3–300 keys plus the shipped fixtures:

```
distinct empiricalZValue over 40 random trees: [1.0, NaN]
distinct nicheOverlap    over 40 random trees: [0.0]
ascending AVL, n=100:  z=1.0  overlap=0.0
```

Both are theorems, not measurements. A BST is a *set*, so each subtree's species count S
equals its area A and `log(S2/S1)/log(A2/A1)` collapses to 1 (NaN only when a subtree is empty
or the two are equal-sized). And the two subtrees of a BST have disjoint key ranges by the
search-tree invariant, so every Pianka term `pL·pR` has a zero factor. Read against the
printed bands, *every* tree the library can build reports "extreme fragmentation" and
"complete partitioning" — a perfect tree exactly as loudly as a spine.

**Fix (the S6-27 settlement, applied consistently):** `experimental/TreeEcology.java:200`
(`empiricalZValue`) and `:260` (`nicheOverlap`) — both `@Deprecated`, both with the "read this
before quoting the number" caveat their siblings already carry, both naming the instrument that
does measure (`CommunityMetrics.rarefiedRichness` over access abundances;
`BetaDiversity.pianka` over two abundance distributions, which `ExperimentLab` already prints
per consecutive phase pair). Return values are unchanged, so no existing caller's arithmetic
moves. `ecologyReport()` (`:649-668`) replaces both numbers *and their bands* with the reason,
exactly as the Shannon block does for evenness; the one number in that block that genuinely
is a function of the tree — the species-area **prediction** `S = c·n^z` — is kept and
relabelled as a prediction rather than a measurement.

**Test:** `SeventhPassEcologyHonestyProbeTest` — the constants are pinned as constants (so the
new documentation cannot silently rot, with an explicit non-vacuity assertion that the sweep
actually reaches z's defined branch), the deprecations are asserted reflectively while the
replacements are asserted *not* deprecated, the report is asserted to quote neither number and
neither band while still naming both replacement instruments, and the rest of the report
(H′, `Split J'` 0.0000 vs 1.0000, Eve, broken stick) is pinned unchanged. Red before on three
of six.

*No artifact regeneration:* `TreeEcology` has no caller anywhere in main code — the report is
printed only by the non-asserting `TreeContextTesterAdditions` demo and by the two probe test
classes — so no checked-in session JSON, export bundle or lab page can be affected. Confirmed
after the full suite: nothing under `docs/` was rewritten.

### 4 (Medium). `TreeEcology.colonizationEquilibrium` — superseded, nondeterministic, and the only place that never said so. **FIXED**

Zero callers in main, zero in tests, zero in the report. `LogisticGrowth`'s class javadoc names
it as the thing it replaced — *"the deterministic replacement for
`TreeEcology.colonizationEquilibrium` (audit EC-2: the original derives rates from wall-clock
ms — nondeterministic; house rule is that deterministic meters decide)"* — and its own javadoc
carried no caveat at all. It also documented a parameter it does not use (`P = total values
ever inserted (auditLog size proxy)`, where the code takes `speciesPool` from the caller).

**Fix:** `experimental/TreeEcology.java:588` — `@Deprecated`, the EC-2 caveat stated in its own
javadoc (wall-clock rates, and the category error of treating a ratio of *latencies* as a ratio
of *rates*), the stale `P` line corrected, and both replacements named
(`LogisticGrowth.fit` over `EcologyRecorder.populationSeries()`, or
`TheoreticalModels.islandEquilibrium` with rates you actually measured). Behavior unchanged.

**Test:** `SeventhPassEcologyHonestyProbeTest.constantAndNondeterministicAccessorsAreDeprecated`.
Red before.

*Deliberately not removed:* deleting it would be a breaking API change on a published 0.2.0
module. See "Needs routing".

### 5 (Medium). `EnsembleOrderedSet.buildAllFromSorted` had no caller and no test — and an audit table said it did. **FIXED (coverage)**

The ensemble face of ADR-014's O(n) bulk build: public, gated, documented, and hardened by
sixth-pass **S6-10** (`requireOpen("buildAllFromSorted")`). It has **zero production callers
and zero test references** across both modules and the JMH rig — while
`AUDIT-2026-07-14-capability-coverage.md:70` lists it as covered by
`BulkBuildTest | BulkBuildFeeder ensemble path`. `BulkBuildTest` has four tests and a property,
none of which mentions an ensemble, and no type named `BulkBuildFeeder` exists in the repo.
That table entry is stale, and it is the reason nobody noticed.

Probed across five configurations — MIRROR, VERIFIED, a strategy+persistent-engine mix, a
bounded window, parallel fan-out, and a closed ensemble — the capability is **correct**: every
member ends an exact mirror, order statistics are live immediately, the engine-tier member
takes the element-wise fallback, `setMaxSize(10)` then a 64-key build leaves exactly the newest
ten in every member, and a closed ensemble refuses. So this is a missing test, not a missing
wire.

**Fix:** `SeventhPassWiringTest$EnsembleBulkBuild` — four tests covering all of the above,
including that the three gates (non-empty, non-exact mode, closed) really refuse. These pass
before and after by construction; they are the coverage the 2026-07-14 table claimed.

### 6 (Medium). The V3/V4 data-plane facades fed the monitor a literal `0` search depth. **FIXED**

`EnsembleController.contains` measures the realized walk through
`EnsembleOrderedSet.searchDepth` and documents it as *"closing the 'ensemble reads record depth
0' gap"*. `PolicySearchController.contains` — under a heading that reads
`// ── Data plane (mirrors EnsembleController: apply + feed the monitor) ──` — and
`PolicyEvolutionController.contains` — under `// ── Data plane (the V3 facade, verbatim) ──` —
both did:

```java
boolean present = ensemble.contains(key);
monitor.recordSearch(Objects.hashCode(key), 0);
```

This is the read-side twin of the literal-`0` rotation feed that sixth-pass fix **S6-12**
removed from these very classes, left in place because the write term was what finding 12 was
about. It is silent *inside* V3/V4 — `Fitness` measures depth structurally, because shadows do
not serve reads — but the monitor is a caller-supplied collaborator, and a caller who hands one
`RollingWorkloadMonitor` to a search controller and to anything that reads
`WorkloadFeatures.meanSearchDepth` (a `CostModelStrategyScorer`, an `EnsembleController`) had
that monitor's depth EWMA diluted toward zero by every read the evolution facade served.

**Fix:** `evolution/PolicySearchController.java:169` and
`evolution/PolicyEvolutionController.java:194` — the same two lines `EnsembleController` uses.
Vote semantics are untouched: `searchDepth` counts toward the VERIFIED stride exactly like
`contains`, and voted / replica / engine-served reads still record an honest zero rather than a
fabricated number.

**Test:** `SeventhPassWiringTest$SearchDepthFeed` — both facades must report a depth > 1 after
300 reads of a 500-key tree, absent keys must still answer correctly, and a third test pins the
honest zero: on a VERIFIED ensemble at the default stride every read votes, members legitimately
disagree on depth, so `meanSearchDepth` must stay exactly 0.0. Red before on both facades.

### 7 (Low). `CacheEvolutionLoop.resident(int)` — a published seam named for an external consumer, with no test. **FIXED (coverage)**

Documented as *"the residency seam an external value cache needs to trim its value map to the
champion's actual contents. Named by the first external consumer (Brine)."* Zero in-repo
callers (correct — it exists for an external consumer) and **zero tests**. Its delegate
`SegmentedLruCache.peek` is tested; the seam that exposes it is not.

**Fix:** `SeventhPassEcologyHonestyProbeTest.residentSeamIsExercised` — residency after
admission, non-residency for an unreferenced key, and the property the seam's whole contract
rests on: `resident()` must be a pure read, so repeated probing of the oldest key must not save
it from the eviction the next admission causes.

---

## Reported, not changed — needs routing

- **`TreeEcology` is now three-quarters deprecated.** `shannonEvenness` (S6-27),
  `empiricalZValue`, `nicheOverlap` and `colonizationEquilibrium` all carry `@Deprecated`;
  `brokenStickDeviation` is documented as perfect-halving rather than MacArthur's broken stick
  (fifth pass), and `shannonDiversity` is ln n by construction. What is left that measures the
  tree is `speciesRichness`, `subtreeEvenness`, `rKScore`/`rKLabel` (S6-27), `mitoEve` and
  `endosymbiosis`. **The retirement ADR-015 planned is now a small job rather than a large one**,
  and the class is `csrbt-experimental` public API on a published 0.2.0, so removing anything is
  a 0.3.0 decision. Your call whether to schedule it.
- **`TreeContext` hard-wires its persistence adapter.** `persistenceAdapter` is assigned
  `new FilePersistenceAdapter()` in the constructor and there is no setter, so
  `TreePersistenceAdapter` — a published seam with `default` methods explicitly designed for
  third-party implementors (ADR-025/026), and with a `LegacyAdapterDouble` in the suite — cannot
  be injected into the facade that is its main in-repo consumer. Adding an overload or a setter
  is purely additive (0.2.1-safe); leaving it is defensible, since `TreeContext` is the legacy
  `Integer` adapter. Reported rather than done because it is an API-surface decision. It is also
  why finding 2's test has to capture a log line instead of asserting on a double.
- **`AUDIT-2026-07-14-capability-coverage.md:70` is stale** (finding 5): it credits
  `buildAllFromSorted` to a `BulkBuildFeeder ensemble path` that does not exist. I did not edit
  it — it is a historical audit document, and the constraint says not to edit existing ADRs; the
  same instinct applies here. Worth a one-line correction by whoever owns that table.
- **`StrategyBattleRunner.tournament` / `formatTournament`** are public, uncalled and untested
  (`run` and `formatBattle`, which they wrap, are both tested). Legitimate public API for the
  ADR-022 battle surface — reported so it is a decision rather than an oversight.
- **`TreeNode1.createNodeWithAugment`** sets `augmentedValue` *after* the constructor has already
  run `augmentor.apply(this)`, so the caller's value survives only until the next re-augment. No
  caller, no test, and it predates the intrinsic `size` field that made the augment slot free for
  custom augmentors. Harmless today; would be a trap for the first caller.
- **`EnsembleOrderedSet.mode` is assigned after construction** in `build()` (`:323`), the same
  shape sixth-pass **S6-39** removed for `optimisticVotesOverride`. **Considered and not a
  defect:** `mode` is `volatile` *and* genuinely mutable at runtime through the public
  `setMode`, so it cannot be final and the S6-39 argument (a construction-time pin that a data
  race lets a reader escape) does not apply. Recorded so the next pass does not re-open it.

## Checked and clean

**Constructors.** Every constructor in both modules read. Twelve classes have more than one
constructor (`BPlusTreeEngine`, `TreeNode1`, `RollingWorkloadMonitor`, `EnsembleController`,
`EnsembleMember`, `GenomeDrivenTreeController`, `PolicyBandit`, `TreeGenome`, `HybridStrategy`,
`WeightBalancedStrategy`, `EcologyRecorder`, `SnapshotLineage`); in every case the short forms
`this(...)`-chain to the long one, so no overload can wire a different set of fields and no
default differs by entry point. No field is left uninitialized on any path. Two constructors
call out to pluggable code (`TreeNode1`'s `augmentor.apply(this)`, `CacheEvolutionLoop`'s
`materialize`), both as the last statement with every field already assigned. `EnsembleMember`'s
two package-private constructors differ only in the label, which is exactly the ENGINE-tier
distinction `strategyName()` reads (and S6-18 already corrected). Builder paths:
`EnsembleOrderedSet.Builder` applies every default in field initializers and validates the
mutually-exclusive pair (`parallelFanOut` vs `executor`) at `build()`.

**Records' compact constructors.** Five records have one: `SaveResult` and `LoadResult`
(ADR-025/026 — the FAILED-carries-cause and LOADED-carries-value invariants are enforced and
match their javadoc exactly), `TheoreticalModels.Environment` (area > 0, the other three ≥ 0 —
matches), `CacheGenome`, `LifeTable.Lifespan`. The records without one are passive carriers
whose producers validate (`WorkloadFeatures` is deliberately a plain vector so
`CostModelStrategyScorer` stays a pure function testable with hand-built inputs, and
`Fitness.evaluate` validates its own inputs instead) — checked, not overlooked.

**Seams and collaborators.** Every implementation of every named seam is reachable and wired:
`TreeEngine` (`RedBlackTree`, `PersistentTreeEngine`, both via `TreeEngineRegistry`);
`RankedSet` (`OrderedSet`, `PersistentRankedSet`, `BPlusTreeEngine` — all three reachable as
ensemble members, and all three now share the null-argument parity S6-14/S6-44 established);
`TreePersistenceAdapter` (`FilePersistenceAdapter`, plus the test double that pins the additive
defaults); `KeySerializer` (`INTEGER`, `STRING` → `StringKeySerializer`, factory-fronted);
`WorkloadMonitor` (`RollingWorkloadMonitor`, `EcologyRecorder` — the cross-module one, which
chains rather than replaces); `StrategyScorer` (`CostModelStrategyScorer`); `MemberExecutor`
(`SequentialMemberExecutor` via `MemberExecutor.sequential()`, `ParallelMemberExecutor` via
`parallelFanOut()` or injection); `TreeEventListener` (`TreeSessionRecorder`, wired by `attach`
and by `SearchArenaSession`; all five `setEventListener` seams are exercised);
`TreeStrategy` (five implementations, all constructible through `StrategyId.newStrategy()`,
`TreeEngineRegistry`, `PolicyGenome.toStrategy()` or directly); both augmentors
(`IntervalAugmentor.INSTANCE`, `GenericIntervalAugmentor.over/natural`). `RankedSet`'s two
defaulting hooks (`height`, `validateStructure`) are overridden by both non-`OrderedSet`
implementations, so `EnsembleController.isHealthy`'s engine-tier branch is not vacuous.
No implementation nothing constructs; no seam a caller can set that a path then ignores.

**Test-only reachability, enumerated.** Four main types have no reference from any other main
type: `ArenaSession`/`SearchArenaSession`/`ViabilityMap` (Gradle `JavaExec` mains feeding the
visualizer's checked-in replay JSONs — `arenaSession`, `searchArenaSession`, `viabilityMap`
tasks, all present since W-1) and `CacheEvolutionLoop` (ADR-012 E6's transfer experiment,
consumed externally by Brine — the reason `csrbt-experimental` is published at all).
`NavigableOrderedSet` is referenced from main only in a comment: it is the `java.util.NavigableSet`
adapter, public API for library users by construction, and carries four test classes.
`StrategyBattleRunner` is the ADR-022 battle surface, driven by three test classes.
All are legitimate; none is orphaned. The two genuinely uncovered public capabilities found —
`EnsembleOrderedSet.buildAllFromSorted` and `CacheEvolutionLoop.resident` — are findings 5 and 7
and now have tests.

**Fields written but never read.** One: `TreeContext.rotationCount`, written by the
`@Deprecated` `incrementRotations()` and no longer feeding `getRotationCount()` (T-1,
2026-08-12). Honestly labelled at both ends; removing the field would be a breaking API change
for the deprecated method. Nothing else.

**Overrides that only call `super`.** None.

**Also verified clean this pass:** ADR-023's rotation partitioning across all five strategies
and the `refreshHeightUpward` fixed-point precondition; ADR-024's meter lifecycle across
fan-out, replica writes, promotion, heal and morph (including that a failed recipient's mark is
never folded and that `clear()` is excluded); ADR-025's four save shapes and ADR-026's five load
shapes, their delegation, their two distinct interface defaults, and the nine load causes;
`TreeEngineRegistry`'s seven `StructureType` values (five buildable, two rejected with a reason);
`StrategyIdBridge` totality in both directions; `EnsembleOrderedSet`'s builder defaults and
gates; `EnsembleController`'s live index and per-call strategy identity (S6-09/S6-18 hold);
`PolicySearchController.priceComparably` and `PolicyEvolutionController`'s all-or-nothing
generation pricing against ADR-024 clause 3; `Fitness.informative` gating at both controllers
(S6-08 holds); the `.eco` directive surface end to end including `factor:` → `Environment` →
every rate-bearing model; `EcologyRecorder`'s window/eviction accounting and the S6-28 absolute
window labelling; `FieldData`'s RFC-4180 splitter and its "reported, never guessed" rule
(S6-45); `GenericIntervalAugmentor`'s installed-guard and query pruning; `RankedSet` voting
parity; and the two wall-clock-sensitive tests (`TreeEventExportTest` "unobserved write path
pays nothing", `EnsembleVerifiedSamplingTest` "sampled verification beats per-read voting"),
which passed on every run here.

---

## Build

```
./gradlew --no-daemon build -x :csrbt-benchmarks:jmh
BUILD SUCCESSFUL
948 tests, 0 failures, 0 javadoc warnings   (--rerun-tasks clean)
```

Baseline before this pass: 928 tests, 0 failures. The 20 new tests are
`SeventhPassWiringTest` (14) and `SeventhPassEcologyHonestyProbeTest` (6). Each behavioral fix
was verified red by reverting it in isolation and re-running: findings 1, 2 and 6 gave 4 red in
core; findings 3 and 4 gave 3 red in experimental. The coverage additions (5, 7) pass either
way — that is what they are for.
