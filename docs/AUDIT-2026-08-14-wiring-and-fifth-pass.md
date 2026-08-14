# Wiring audit + fifth-pass bug hunt — 2026-08-14

**Scope:** (1) a constructor-to-constructor **wiring audit** — every class traced from
the public seams to its instantiation point, every README/ADR-019/020 capability claim
traced to an entry point plus a test or checked-in artifact, plus a stub/dead-code
sweep; (2) a **fifth bug-hunt pass** over the v0.2.0 surface: the ADR-021/022
hardening-day code, the ecology program (ADR-015–020), and the older
core/persistence/strategy/ensemble/control/evolution code (complementing the four
2026-08-12 passes, whose fixes were spot-verified as landed — including D-2 and D-3,
which the deep sweep listed as "documented, not fixed" but were actually fixed in the
consolidation).

**Method:** four parallel adversarial passes (wiring, ADR-021/022, ecology,
older core), hand-derivation plus probe programs against the compiled classes
(TreeSet/TreeMap differential oracles, concurrency stress, 30-seed reconstruction
probes, numeric cross-checks of every ecology formula against hand-computed cases).
Suite after: **all green** including three new probe test classes. JDK 21.

---

## Wiring audit verdict: effectively "no stubs left" clean

Every mechanically-flagged suspect resolved to a real seam: `ArenaSession` /
`SearchArenaSession` are `JavaExec`-task mains feeding the visualizer's checked-in
replay JSONs; `MemberExecutor`, `StringKeySerializer`, `GenericIntervalAugmentor` are
factory-fronted; `StrategyHealthCheck`, `StrategyIdBridge`, `TreeExport` are static
utilities wired into main-code call sites. All README + ADR-019/020 claims trace
end-to-end (`.eco` directives, experiment runner, FieldData bus, MarkRecapture,
PhyloTree/Newick, exports, Workbench). `TreeEngineRegistry` maps all 7 `StructureType`
values (5 constructible, 2 rejected-with-note, exhaustively tested). Deferred features
(native xlsx/pptx, B+ registry slot, Workbench `.eco` import) are all explicitly held
with named triggers — none half-wired. No TODO/FIXME/stub markers, no empty bodies,
no dead `return null` stubs in main code.

Wiring defects found and fixed:

- **W-1** `ViabilityMap` was the one recorder skipped when its siblings got Gradle
  `JavaExec` tasks post-Ant; its javadoc still said
  `java -cp build/classes experimental.ViabilityMap` (stale classpath AND pre-rename
  package). Now: task `viabilityMap`, javadoc updated.
- **W-2** `NavigableOrderedSet.countUpTo` (package helper "views size themselves with
  this") was dead — views use `countBetween`. Removed.
- **W-3 (host-side, not done here)** `_to_delete/` still carries ~1.7 MB of
  git-tracked tarballs (`_audit_snapshot.tar.gz`, `csrbt-src.tgz`). Run
  `git rm -r _to_delete` from a host terminal.
- **Documented, deliberate, flagged for a future ADR:** the three
  `FilePersistenceAdapter.saveSnapshot` variants log-and-swallow `IOException` with a
  `void` return — a caller cannot programmatically detect a failed save. Changing to
  `boolean`/`UncheckedIOException` is an API decision, not a stub.

---

## Fixed — probe-verified (new probe classes in parentheses)

### F-1 (High). Reconstructed trees carried stale cached heights; AVL/Hybrid broke
### their own invariant on the next insert. (`ReconstructionHeightProbeTest`)

`TreeNode1.recomputeAugmentAndPropagate()` walked to the root refreshing **size +
augment only** — heights were updated only locally in `setLeft`/`setRight`. Every
tree wired top-down or in arbitrary order therefore converged to correct sizes with
stale cached heights: `FilePersistenceAdapter.deserializePreOrder` (pre-order attach),
`TreeCloner.deepCopyTwoPass` (arbitrary-order wiring), and transitively
`TreeHistory.restoreFrom` (checkpoint clones copy heights verbatim). AVL/Hybrid
rebalance refreshes heights only along the insert path; balance factors read off-path
siblings' stale values → spurious/missed rotations. Pre-fix probes: one insert on a
150-key AVL clone violated |bf| ≤ 1 in **30/30 seeds** (violations up to 5);
load-then-insert violated in 20/30 seeds within 300 inserts, several on insert #1.
The load-time gate passed (it computes real heights), so the corruption was silent;
`selfRepair` then reported the tree unhealthy forever. RB/Splay/WB unaffected (they
do not read cached heights; sizes were always propagated).

**Fix:** height + black-height ride the same propagation walk as sizes
(`recomputeAugmentAndPropagate` now refreshes all three at each step; the redundant
local calls in `setLeft`/`setRight` folded in). O(1) extra per step on an already
O(height) walk; rotations still use the non-propagating local setters.

### F-2 (Medium-high). Sub-views could escape an exclusive parent endpoint.
### (`ViewBoundsParityProbeTest`)

`NavigableOrderedSet.Range.inRangeForBound` admitted a bound equal to the view's own
endpoint **unconditionally** — but TreeSet/TreeMap only admit an equal endpoint when
the parent bound is inclusive or the new bound is exclusive. Since child ranges are
built directly against the base set, `headSet(10,false).headSet(10,true)` produced a
view containing 10 — outside the parent's range — where TreeSet throws
`IllegalArgumentException`. Same for `tailSet(5,false).tailSet(5,true)` and the
`subSet` variants. **Fix:** `inRangeForBound(k, inclusive)` — TreeMap's
`inRange(key, inclusive)` semantics exactly.

### F-3 (Medium). View iteration and first()/last() spanned multiple lock epochs —
### NPE and contract-violating null under a concurrent writer. (`ViewBoundsParityProbeTest`)

`Range.snapshot()` composed `isEmpty → minimum → maximum → rangeQuery` across four
independently-guarded acquisitions; a writer emptying the set between the first two
made `minimum()` return null and the comparator NPE **out of a read-only iterator**.
Base `first()`/`last()` composed `isEmpty → minimum` and could return null
(`SortedSet.first()` must never). Pre-fix probe: 4 NPEs + 11 null `first()` returns in
3 s under one writer. ADR-021 fixed navigation and `size()` but not view iteration.
**Fix:** new `OrderedSet.rangeSnapshot(lo, loInc, hi, hiInc)` — a pruned in-order walk
under ONE guarded acquisition (same step-budget/torn-diversion protocol as
`inOrderReadOnly`); `first`/`last`/`pollFirst`/`pollLast` are now single base calls;
`Range.lower/floor/ceiling/higher` fold the view bound into the query *before*
navigating (min/max of the two constraints) instead of patching out-of-view answers
with a second acquisition. Bonus parity fix: `descendingIterator().remove()` now
delegates to the live set like the ascending iterator (TreeSet supports both).

### F-4 (Medium). Battle-runner fairness: asymmetric duplicate-insert logging + no
### blackhole.

RedBlack/Splay/Hybrid logged a WARN per duplicate insert on the timed path — under
the test config (root=WARN, console appender) three of four competitors paid
console-write cost per duplicate while AVL (silent `else return`) paid nothing, a
systematic AVL advantage in duplicate-heavy workloads (RANDOM_UNIFORM: ~3.7k dupes
per 20k-op pass). Now DEBUG (M-3 precedent). The discarded pure-search result gained
a volatile sink (JMH-blackhole equivalent) so the JIT cannot eliminate RedBlack/AVL's
pure descents while Splay/Hybrid keep their side-effectful ones. Degenerate
`opCount` guards added (SEQUENTIAL opCount 1 / DELETE_HEAVY opCount < 3 threw
`nextInt(0)`). See the ADR-022 follow-up note.

### F-5 (Medium). Levins p* estimator was structurally degenerate at steady state.

`EnsembleCommunity.levinsEquilibrium()` used cumulative event totals
(p* = 1 − extinctions/recolonizations): any record where every extinction is healed —
the steady-state regime itself — has equal totals and pinned **p* = 0 while observed
occupancy sits at 1.0** (the shipped field-day demo narrated "the model disagrees with
observation" on every run — an index that cannot vary, the ADR-015 EC-1 class).
**Fix:** rates per unit exposure — ê = extinctions/occupied patch-samples,
ĉ = (recolonizations/empty patch-samples)/p̄ (observed colonization per empty patch is
c·p). The field-day record now predicts 83% vs 100% observed. Tests updated to the
exposure arithmetic; `docs/ecology-lab-session.json` + the embedded lab-page copy
regenerated (only the levins value changed).

### F-6 (Medium). Newick parser rejected whitespace before '(' — "(A, (B,C));" threw.

Handout-style spaces after commas hit the label scan and died on an empty name, while
`(A, B);` worked — confusingly selective. Fixed in `PhyloTree.parseNode` (skip
whitespace first) and the lab page's `jsNewick` mirror. Also: `trimmed()`'s `%.6f`
destroyed branch lengths < 5e-7 (`(A:1e-7);` → `A:0;`, breaking the round-trip
contract) — now falls back to `Double.toString` when fixed-point would change the
value; and `jsNewick` accepted an empty branch length as 0 (`Number("")`) where the
Java oracle errors — now rejected identically.

### F-7 (Medium). FieldData round-trips silently corrupted multi-word names.

Table form legitimately produces names with spaces ("great heron,5"), but `toEcoLine`
emitted them unquoted into the whitespace-tokenized token form: `{great heron=5}` →
`data: siteA great heron=5` → re-parsed as `{great=1, heron=5}` with **zero reported
problems**. Names now hyphen-normalized (same convention as multi-word bare names).
Also: a trailing separator ("oak,") silently tallied the species `"oak,"` — comma/tab
lines with a bad or empty count are now reported problems ("reported, never guessed"),
while space-separated multi-word bare names keep their fallback.

### F-8 (Low-medium). `note(Target):` could never attach to a mixed-case phase.

The directive key is lowercased for dispatch, but phase/dataset names are stored
case-sensitively — `note(Bloom):` drew "unknown phase/dataset 'bloom'" AND rendered
detached. The target is now extracted from the original line. Also `expect:
richness() > 1` (blank args) is now a parse-time spec problem instead of degrading to
UNGRADEABLE at run time.

### F-9 (Low-medium). `GenomeDrivenTreeController.applyStructure` ignored the
### health-gate verdict.

`context.setStrategy(...)` returns false on a refused morph (health gate / same
policy); the controller discarded it and committed `activeStrategyType`, genome
mutation, `morphCount`, the cooldown clock, and a `MorphEvent` for a morph that never
happened — the write-side twin of the read-side desync G-B fixed on 2026-08-12
(`MorphController` already checked correctly). Now commits only on `true`.

### F-10 (Low). Interrupted parallel fan-out abandoned in-flight members.

`ParallelMemberExecutor` threw on `InterruptedException` mid-collect; submitted tasks
kept running and mutating members, so the write was reported failed with an unknown
subset applied and still ACTIVE (the E-D silent-divergence class). Now finishes
collecting uninterruptibly and restores the interrupt flag, so quarantine bookkeeping
sees every outcome.

### F-11 (Hygiene). Evolution controllers' `emit()` hardened (M-1 parity).

`PolicyEvolutionController`/`PolicySearchController` forwarded listener exceptions —
a throwing observability hook could abort `beginGeneration`/`endTrial` mid-slot.
Same try/catch as `OrderedSet.emit`.

---

## Documented (no code change)

- `TreeEcology`'s indices remain degenerate/superseded per ADR-015 (its
  `brokenStickDeviation` is perfect-halving, not MacArthur's broken stick — the
  correct model lives in `CommunityMetrics.brokenStickExpected`); retirement already
  planned.
- `LogisticGrowth.fit` plateau caveat now in the javadoc (ramp-only series
  underestimate K, overestimate r, with high R²).
- Lab-page dichotomous key gained a cycle guard (`1 | 1 | 1` walked forever);
  Workbench `innerHTML` interpolation of pasted data is self-XSS-only (offline, own
  data) — `escapeHtml` exists if it ever matters.

## Verified clean this pass (beyond the fixes)

ADR-021 navigation quadrants/count algebra/guardedRead protocol; Desc-view mappings
and comparator discipline; OrderStatisticsOps; ADR-022 median/warmup/depth-measurement
/splay-actually-splays/score formula; RB insert-delete fixups (xParent threading, NIL
sentinel edges); Splay zig-zig ordering and split-join delete; AVL/Hybrid rebalance
walks (given fresh heights — see F-1); WeightBalanced (Δ,Γ) repair;
StrategyHealthCheck completeness; ensemble vote math, quarantine-before-throw,
READ_REPLICA drain, checkHealth 3-pass; MorphPolicy/MorphHistory (no EWS double-fire
path exists in core; B5 saturating clock holds); persistence refusal gates and atomic
saves; interval augmentors through rotations; every ecology formula cross-checked
numerically (Shannon/Pielou/Simpson/Hill/Chao1/rarefaction, Jaccard/Sørensen/
Bray-Curtis/Renkonen/Pianka/Whittaker, Lincoln-Petersen + Chapman + CI, Hardy-Weinberg
χ², Euler-Lotka bisection, Mendelian crosses incl. 9:3:3:1 walnut comb, life tables,
Morisita/dispersion, Environment worked numbers); ExperimentSpec/Lab parse-time
discipline and export escaping (RFC-4180, HTML); Workbench JS mirrors match the Java
oracles; cache-evolution invariant oracle and C-4 fix hold.
