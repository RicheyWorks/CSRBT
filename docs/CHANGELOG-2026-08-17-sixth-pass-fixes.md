# CHANGELOG 2026-08-17 — sixth-pass fixes

Closes every confirmed finding in `docs/AUDIT-2026-08-17-sixth-pass.md` (34 of 37 candidates; 3 were
refuted during verification), plus four follow-up defects the fix work itself surfaced.

**Build:** `./gradlew build -x :csrbt-benchmarks:jmh` → **BUILD SUCCESSFUL**, **887 tests, 0 failures**,
re-verified across three consecutive full runs with `--rerun-tasks`. No test was flaky, including the two
wall-clock-sensitive ones (`TreeEventExportTest` "unobserved write path pays nothing",
`EnsembleVerifiedSamplingTest` "sampled verification beats per-read voting").

**Method:** each fix has a regression test that was verified red-before / green-after by temporarily
reverting the fix in isolation. Where a batch's suite was run against reverted sources, the counts are
recorded below.

Fix ids are `S6-nn`, cross-referenced to the audit's finding numbers.

---

## S1 — crash and data-loss paths

### S6-01 · finding 1 · restored root's parent was `null`, not the NIL sentinel
`util/TreeHistory.java:326-345` — `restoreFrom` now captures the sentinel and calls
`restoredRoot.setParent(nil)` after `setRoot`, matching `FilePersistenceAdapter:216,444` and
`TreeCloner:92,189`.
*Was:* `saveCheckpoint` → mutate → `restoreCheckpoint` → `add` threw `NullPointerException` at
`TreeStrategy.rotateLeft:79` for RedBlack, AVL **and** Splay.
*Test:* `SixthPassAuditTest$RestoreRootParent` — all three strategies, save → mutate → restore → 30 adds,
plus a direct assertion that the root's parent is the sentinel.

### S6-02 · finding 2 · `fixDelete` recolored and rotated the shared NIL sentinel
`strategy/RedBlackStrategy.java:249, 285` — both case-2 branches now short-circuit through a new
`cannotRebalance(w)` helper (`:326-343`): a NIL sibling terminates the fixup (`x = tree.getRoot(); break;`)
instead of recoloring the sentinel or rotating about it. The terminal recolor is guarded at `:311`
(`if (!x.isNil()) x.setColor(BLACK)`). The sentinel's color and links are now never written.
*Was:* `add(1..63)` → `TreeCloner.shallowClone(2)` → `remove(k)` turned the shared sentinel RED on the third
removal; on the black chain `10→5→2`, `remove(2)` threw NPE **and emptied the tree** (`[2,5,10]` → `[]`).
*Test:* `SixthPassAuditTest$SentinelSafety` — the shallowClone-then-remove path, the black-chain case, and a
2 000-op RB churn against a `TreeSet` oracle proving the guard is inert on valid trees.

### S6-03 · finding 3 · persistent flat loader ignored the declared size
`persistence/FilePersistenceAdapter.java:656` — `readFlatKeys` now parses `header[3]` and refuses when
`keys.size() != declaredSize`, with the same message and refusal semantics as the int (`:245`) and generic
(`:468`) paths. `loadPersistent` additionally applies an ordering gate (`:573`, helper `flatOrderFailure` at
`:599`) so duplicates and inversions are refused the way `validateRestored` refuses them on the structured
paths. This completes deep-sweep **P-2**, which had landed on two of the three paths.
*Was:* a 200-key snapshot with a truncated data line loaded as 114 keys, logged `size=114` as success, and
parsed the trailing partial token as a valid-but-wrong key (`"12"` from `"123"`).
*Test:* `SixthPassFixesTest$Persistence.truncatedPersistentSnapshotRefused` (all 700+ truncation points of a
200-key file), `.tamperedSizeFieldRefused`, `.unorderedKeyListRefused`.

### S6-04 · finding 4 · `loadEnsemble` wiped the target, then replayed a partial file
`persistence/FilePersistenceAdapter.java:729-745` — validation is now complete before any mutation. The flat
branch gets the size gate from S6-03 plus an ordering gate keyed on `target.comparator()`, and returns
`false` **before** `target.clear()`. The structured branch already parsed into a throwaway, fully-validated
`OrderedSet`. The rest of the method was audited: the only other target contact is `target.comparator()` /
`members()`, both reads. Javadoc updated to state validate-then-mutate.
*Was:* a snapshot declaring 300 keys wiped the destination ensemble, repopulated it with 118, and returned
`true` — violating the documented "the target is left untouched in that case".
*Test:* `.loadEnsembleRefusesWithoutWipingTarget`, `.loadEnsembleRefusesTruncatedPreOrder`,
`.loadEnsembleStillWorks`.

---

## S2 — wrong answers, corrupted state, stuck control loops

### S6-05 · finding 5 · concurrent saves of one name shared a staging file
`persistence/FilePersistenceAdapter.java:65-94` — `tempPathFor` now emits `<name>.rbt.<pid>.<seq>.tmp` from a
static PID plus an `AtomicLong`, unique per call and across JVMs. The atomic-rename commit is unchanged. The
D-3 comment now describes what is actually guaranteed: each call writes a file only it touches; concurrent
saves still race to commit, but the target is always exactly one complete snapshot.
*Was:* 4 of 25 two-thread rounds left a committed target that `loadOrderedSet` refused — the previously-good
snapshot destroyed.
*Test:* `.concurrentSavesNeverCorruptTheTarget` (25 rounds × 2 threads).

### S6-06 · finding 6 · `TreeCloner.copyNodeFields` dropped `augmentedRef`
`util/TreeCloner.java:285` — the generic augment slot is now copied, matching `TreeNode1.deepCopy:521`.
*Was:* `snapshot()`, `deployCloneArmy()`, `mutantClone()`, `shallowClone()` and `TreeHistory.saveCheckpoint()`
silently discarded it — a clone of intervals `[10,50] [20,25] [30,90]` reported `[[10,10],[20,20],[30,30]]`
and `stabQuery(45)` returned `[]` where the source returned 2.
*Test:* `SixthPassAuditTest$GenericAugmentClone` — `snapshot()`, checkpoint round-trip and `shallowClone` all
reproduce `stabQuery` and `intervalSearchAll`.

### S6-07 · finding 7 · descending view mutated the base set
`adapter/NavigableOrderedSet.java:434-445` — `Desc.iterator()` / `descendingIterator()` now wrap the delegate
in a non-removing iterator, mirroring what `Range` gets from its unmodifiable-list iterators.
`NavigableOrderedSet.descendingIterator()` itself is untouched, so **F-3**'s base-adapter parity survives.
*Was:* `descendingSet().retainAll(List.of(1))` returned `true` and left the base as `[1]`; `removeAll` was
size-dependent — threw on one shape, silently emptied the base on another.
*Test:* `SixthPassFixesTest$DescendingViewIsReadOnly` — `bulkMutatorsThrowWithoutTouchingTheBase` (retainAll
plus both `removeAll` shapes), `iteratorsAndDeclaredMutatorsRefuse`, `descendingRangeViewIsReadOnly`,
`baseDescendingIteratorStillRemoves` (the F-3 regression guard), `descendingViewStillReads`.

### S6-08 · finding 8 · an empty trial shadow scored a free 0.0 and pinned the bandit forever
`evolution/Fitness.java:46-77` — `MIN_INFORMATIVE_SIZE = 2` and an `informative(long)` predicate.
`evolution/PolicySearchController.java:220-240` — an uninformative trial returns `scored=false`, records **no**
bandit observation and cannot promote (engine-tier `+∞` incumbent semantics preserved per MorphPolicy V-B).
`evolution/PolicyEvolutionController.java:290-302, 345-352` — the body is not scored, the genome is not killed,
and an incumbent-too-small is a hold. `Fitness.evaluate`'s `size<=1 → readCost 0` arithmetic is untouched:
informativeness is enforced at the controllers, which is where "observation vs. arithmetic" is decidable, so
`FitnessTest`'s pins hold.
*Was:* `SAMPLED_SHADOW` at `shadowSampleRate(0.02)` gave shadow size 0 vs primary 40 keys → `armCost 0.0000`
vs `incumbentCost 0.5497` → promoted on the very first trial, and the arm kept `meanCost = 0.0` so
`bandit.bestArm()` was pinned to it for every subsequent round.
*Test:* `SixthPassFitnessFeedProbeTest.emptyShadowIsNotAFreeWin` (also asserts the bandit later measures the
arm at a real cost and moves to a *different* arm), `.emptyNurseryBodyIsNotSelected`,
`.informativeIsTheGateOnComparability`.
*Judgment call:* an uninformative trial leaves the arm at `pulls == 0`, so UCB1 offers it again next window —
an unmeasured arm is genuinely untried. A permanently-empty shadow therefore stalls on one arm while promoting
nothing, which is the safe direction. Both halves are pinned by the test.

### S6-09 · finding 9 · promotion target was never checked for liveness
`ensemble/EnsembleController.java:118-126` — new `liveIndex()`, ACTIVE-filtered and rebuilt per evaluation;
`:198-209` skips a dead candidate and logs `event=morph_candidate_skipped`; `:221` guards with
`target.isActive()`.
*Was:* a MORPH decision naming a retired or quarantined member threw
`IllegalStateException: cannot promote a non-active member` out of `evaluateAndMaybePromote` on every
evaluation — and `checkHealth` retires members itself (`:345,358`).
*Test:* `SixthPassEnsembleProbeTest.retiredPromotionTargetIsAHoldNotACrash`, `.healedMemberBecomesPromotableAgain`.

### S6-10 · finding 10 · `shutdownNow()` orphaned futures that were then awaited forever
`ensemble/ParallelMemberExecutor.java:137-140` — `shutdown()` now cancels every drained `FutureTask`;
`:103-109` maps `CancellationException` to a failed `Outcome`; `:72-83` and `:118` report a mid-submit
`RejectedExecutionException` as failed outcomes for the members it never reached, preserving one outcome per
member. `ensemble/EnsembleOrderedSet.java:895-902` — `close()` now runs under `writeLock`, is idempotent, and
latches `closed`; `requireOpen` guards `fanOutWrite` / `replicaWrite` / `buildAllFromSorted` / `setMaxSize`,
and a new `isClosed()` is exposed. Reads still work on a closed ensemble; writes throw `IllegalStateException`.
*Was:* 3 members + `ParallelMemberExecutor(1)` + a concurrent `close()` parked the writer forever at `:72`
**while holding `writeLock`** — a permanent ensemble deadlock. Also reachable via `parallelFanOut()` whenever
K-1 exceeded the core count.
*Test:* `.shutdownDuringFanOutDoesNotPark`, `.closeDuringInFlightWriteTerminates` — both run the blocking half
on a daemon thread and `join(timeout)`, so a regression fails rather than hangs the suite.

### S6-11 · finding 11 · morph rebuilt the set from an `equals`-keyed map
`OrderedSet.java:705-707, 759, 848-905` — `captureKeyTags` / `captureKeyRefs` / `restoreTags` / `restoreRefs`
are replaced by a single in-order `captureNodeState()` → `List<CapturedNode<K>>` plus `restoreNodeState()`.
The element list now comes from the engine's own in-order walk (comparator-ordered, comparator-distinct)
rather than a hash-keyed key set.
*Was:* a set ordered by `id` with `equals` on `name` silently dropped an element on `setStrategy` — size 3 → 2,
with the call still returning `true`, because the health gate compared the candidate against the same
collapsed list.
*Test:* `SixthPassAuditTest$MorphKeyCollapse`.
*Note:* the first implementation used a `TreeMap<>(keyOrder)` — correct, but it added O(n log n) comparator
calls per morph and broke the pinned ADR-018 frontier (`AmortizationFrontierTest`, 256k ratio 1.0006 > 1.0).
The list form is faithful **and** cheaper than the original two-map/two-search version; the frontier reprints
its pinned `ratioVsBestFixed=0.9902`. No test assertion was rewritten.

### S6-12 · finding 12 / `AUDIT_2026-07-21` F-E1 · `rotationsPerWrite` was structurally always 0
Real per-op rotation deltas from the primary member's `OrderedSet.rotationCount()` now feed the two-arg
`recordAdd` / `recordRemove` at all three facade call sites: `ensemble/EnsembleController.java:134-186`,
`evolution/PolicySearchController.java:105-142`, `evolution/PolicyEvolutionController.java:137-174` — each with
a `rotationMeter` / `rotationsSince` pair, clamped at 0 for the morph and self-repair engine swap per
`rotationCount()`'s contract. Builds on `CHANGELOG-2026-08-12-t1-rotation-meter`, which made
`TreeContext.getRotationCount()` correct but did not plumb it into the fitness feed.
*Was:* `writeCost = writeFraction × rotationsPerWrite` was identically 0.0, so ADR-011 V3/V4 promotion was
decided purely by the structural read term and a rotation-thrashing policy won whenever its tree was
momentarily shallower.
*Test:* `.everyFacadeFeedsTheRotationMeter`, `.liveWriteTermDampsReadDepthOnlyPromotions`.
*Deliberately excluded:* `GenomeDrivenTreeController:179,186` keeps its literal-0 feed, pinned by
`ControllerConvergenceTest` G5 ("plan decision 12.2.2"), which still passes.
*Judgment call:* the meter is the **primary's** delta, matching `PolicySearchController`'s documented "the
realized write term is the stream's, not per-member" (a shadow sees only a sampled stream). Per-member
rotation meters remain the ADR's held refinement.

### S6-13 · finding 13 · `PersistentRankedSet` change signal and meters were not thread-safe
`PersistentRankedSet.java:70, 85, 102` — `PersistentTreeEngine.add/remove` return `void` and expose no exact
change signal, so the check-and-mutate is serialized on a new adapter `writeLock` (`clear()` too); the four
meters at `:43-44` are now `LongAdder`s, read at `:137-146`.
*Was:* 4 threads × 20 000 adds had `add()` return `true` 20 127 / 21 929 / 27 928 / 24 724 / 25 428 times
against 19 618 real insertions — up to 42 % over-report, and that return value is what a VERIFIED ensemble
votes on.
*Test:* `SixthPassFixesTest$PersistentAdapterConcurrency.concurrentAddsReportChangeExactly` (sum of `true`
equals the final key count), `.concurrentRemovesReportChangeExactly`, `.sequentialSemanticsUnchanged`.

### S6-14 · finding 14 · B+tree null-argument semantics diverged from the other engines
`BPlusTreeEngine.java:145, 209, 334, 444-445, 478-479` — all five sites now `Objects.requireNonNull`
(`rank:401` already did; `successor` / `predecessor` inherit it). The class javadoc records the parity rule.
*Was:* one `ensemble.contains(null)` call on a VERIFIED ensemble had RB and AVL throw NPE while the B+tree
answered `false`; the majority won and the structurally healthy B+tree member was **QUARANTINED**.
*Test:* `SixthPassFixesTest$NullParity.nullArgumentsThrowIdentically` (10 key-taking `RankedSet` /
`OrderedCollection` calls across all three implementations),
`.ensembleContainsNullKeepsEveryMemberActive`.
*Pinned test changed, deliberately:* `BPlusTreeEngineTest.edgeSemantics:172-174` pinned exactly the divergent
behavior this finding says is wrong (`contains(null)` → false, `add(null)` → `IllegalArgumentException`).
Those three assertions now expect NPE and were extended to `remove` / `countInRange` / `rangeQuery`, with a
comment explaining why. The unrelated `IllegalArgumentException` for `fanout < MIN_FANOUT` is unchanged.

### S6-15 · finding 15 · Hybrid's ±2 relaxation was keyed on depth at write time, re-judged at validation time
`strategy/HybridStrategy.java` — grants are now recorded where they are made (`:216-231`, weak-identity set
`relaxedNodes:75-97`), post-rotation grants cover the rewired triangle (`:245, 254, 292-317`), and
`checkBalance` reads the grant (`:418`) instead of re-deriving it from the node's current depth.
`validateInvariant` is **not** loosened: an unrecorded node must hold strict AVL balance, nothing may exceed
±2, and grants are revoked — the node rotated straight — the next time a write walks through it in the strict
region.
*Was:* 600 random inserts under `HybridStrategy(7)` produced 8 reported violations on a tree Hybrid itself
built; `setStrategy(new HybridStrategy<>(7))` was silently refused in 7/20 seeds (5/20 at threshold 6), and
`selfRepair()` failed its short-circuit and paid a futile O(n) rebuild.
*Test:* `SixthPassAuditTest$HybridRelaxation` — 600 inserts × 20 seeds × thresholds {6,7}: zero violations,
zero refusals; `selfRepair` short-circuits; 3 000-op churn asserts the ±2 ceiling and that every |bf| = 2 node
carries a grant; **non-vacuity** is pinned by a hand-wired 9-node right spine that is still reported, and by
the default unbounded threshold marking nothing and holding strict AVL.
*Two caveats now documented in the code:* (a) a rotation fired at a relaxed node can leave |bf| = 2 residue at
the strict boundary — removing it would cascade the very rotations the relaxation exists to avoid, so it is
recorded rather than hidden; (b) grants live on the strategy instance, so a `TreeCloner`-made clone gets a
fresh instance, may be judged strictly once, and pays one rebuild.

### S6-16 · finding 16 · Euler–Lotka bisection had a hardcoded bracket and no containment check
`ecology/PopulationGenetics.java:79, 105, 120-155` — the fixed `lo=-5, hi=5` is replaced by geometric
expansion capped at `R_BRACKET_CAP = 700` (past that `e^(−rx)` leaves the double range), with a root-containment
check that reports a plain-English `IllegalArgumentException` instead of returning a bracket endpoint as
"exact". `R₀ == 1 ⇒ r = 0` is now exact — that is `g(0) = R₀`, the one case where the function can be flat.
Because `ExperimentSpec:348` already validates the domain at parse time, an unsolvable schedule in a student's
`.eco` file becomes a `⚠ spec:` problem rather than a crash, matching the existing markrecapture and
hardyweinberg probes.
*Was:* `lx={1,1}, mx={0,250}` (R₀ = 250, T = 1) returned `rExact = 5.0000` where the true r = ln 250 = 5.5215,
printed side by side with a correct `rApprox` — and mirrored for r < −5 (−6.9078 → −5.0).
*Test:* `PopulationGeneticsBracketProbeTest` (6 tests) — ln 250, ln 0.001, in-bracket roots byte-unchanged, and
`model: eulerlotka 1:0 1:250` printing one rate in both columns.

---

## S3 — wrong metadata, degraded UX, self-contradicting output

### S6-17 · finding 17 · the lab page contradicted itself on load
`docs/ecology-lab.html:462-478` — the hardcoded "empty archipelago" branch is replaced with prose that
interpolates the real numbers, the direction of the miss, and the timeline's own occupancy range. The 0.15
threshold is **kept** — it is `FieldReport.LEVINS_AGREEMENT`, and widening it would make the page grade more
leniently than the oracle — and the prose now explains why it fires: `levins` averages the whole record,
`observed` is the last snapshot, and the 6-survey / 3-patch record swings 33 points, wider than the ±15 band.
*Was:* the shipped page rendered "83% Levins predicted occupancy" six lines above "the ratio estimator predicts
an **empty** archipelago" — stale prose left by **F-5**, which changed levins 0 → 0.833333 and regenerated both
session copies but not the narrative.
*Verified:* in headless Chromium against the embedded session — the card now reads "Levins predicts 83% … the
last survey found 100% … 17 points below … 33-point range", and "empty archipelago" appears nowhere in the file.

### S6-18 · finding 18 · `byStrategy` was a one-shot index and `strategyName()` was frozen
`ensemble/EnsembleMember.java:78-80` — `strategyName()` reads through to the live strategy; the frozen field is
now `label`, used only for engine-tier members. `ensemble/EnsembleController.java:99-106` — `idOf` resolves per
call, the constructor-time index is gone, and `currentPrimaryId()` delegates to it.
*Was:* after `PolicySearchController.beginTrial` or `PolicyEvolutionController.beginGeneration` morphed a
member, the controller logged `promoted RED_BLACK->AVL` for a member actually running Splay, and every
`event=morph_eval` line was wrong.
*Test:* `.controllerReportsLiveStrategyIdentity` — morphs a member to Hybrid behind the controller's back and
asserts it is both seen as a candidate and named correctly in `PromotionResult.to()`.

### S6-19 · finding 19 · `TreeCloner.snapshot()` dropped the sliding-window bound
`util/TreeCloner.java:74-86` — new `cloneContextLike()` carries `maxSize`, used by `snapshot()` (`:93`) and
`shallowClone()` (`:194`); `deployCloneArmy`, `mutantClone` and `strategyParallelClones` inherit it via
`snapshot()`.
*Was:* `setMaxSize(4)` + add 1..10 → source size 4, clone reported `maxSize = 0` and grew to 9 keys.
*Test:* `SixthPassAuditTest$ClonedWindow` — all four entry points; an unbounded source still clones unbounded.

### S6-20 · finding 20 · checkpoint restore bypassed the window bound
`OrderedSet.resyncFromEngine():803-826` — now evicts down to the bound after resyncing, with the rationale
noted at `TreeHistory.restoreFrom:339-341`. FIFO after a wholesale rebuild is the ascending fallback, so the
survivors are the newest `maxSize` keys — identical to what `undo`'s D-2 replay produces.
*Was:* a 10-key checkpoint restored under `maxSize=3` gave size 10, and the next single `add` evicted 8 keys at
once.
*Test:* `SixthPassAuditTest$RestoreRespectsWindow` — restores `[8,9,10]`, next `add` evicts exactly one,
undo/restore agree, unbounded still restores all 10.

### S6-21 · finding 21 · rotation cache staleness was documented dishonestly
`strategy/TreeStrategy.java:53-85` — the misleading size-based justification is replaced by a per-quantity
statement: `size` and `augmentedValue` are provably correct for all ancestors; `height` and `blackHeight` may
go stale for ancestors; AVL and Hybrid refresh on the way up via `refreshHeight()`, RedBlack and
WeightBalanced do not. `TreeNode1.getHeight()` (`:242-273`) and `getBlackHeight()` (`:207-220`) — which had no
javadoc at all, only the implicit promise — now state what is exact, what may be stale, under which
strategies, and the recompute path (post-order `refreshHeight()`, or a structural walk that ignores the cache);
`getBlackHeight()` adds that it is informational on non-RB strategies and that `blackHeight()` is the exact
invariant-checking answer. **Hot path untouched** — the AUDIT-2026-08-14 F-1 deferral stands, it is now
honestly described.

### S6-22 · finding 22 · `lineChart` had no `yMax` floor
`docs/ecology-lab.html:250` — `if (!(yMax > 0)) yMax = 1`.
*Was:* an all-zero series gave `yMax === 0`, `Y(v)` evaluated `0/0`, and the path came out
`M42,NaNL351,NaN…` — the curve silently vanished. Reachable from Theory Bench with logistic/exponential
N₀ = 0 or Levins p₀ = 0, all natural "start from nothing" inputs.
*Verified:* reproduced pre-fix in node; post-fix all three live paths draw a flat line on the baseline with a
0–1 axis.

### S6-23 · finding 23 · `parseCounts` had no RFC-4180 quote handling
`docs/ecology-lab.html:1206` — new `splitCsvLine` with the exact semantics of `ExperimentExport.splitCsv`
(plus tab); `:1224` — `parseCounts` rewritten to mirror `FieldData.parseLines` **including its problems list**,
and `runField` / `runSites` now print each bad line verbatim with its reason (`problemHtml`, `:1276`).
*Was:* `"oak, white",12` produced one species literally named `"oak, white",12` with count 1 and
`skipped: 0` — silent corruption, in a card that advertises spreadsheet paste, from a page whose own comment
claims to mirror the Java oracle that *reports* that line.
*Verified:* through the live page over 17 cases — the quoted name now parses to count 12, and
`oak,notanumber` / `oak,` / `oak,0` / `,5` are all reported with the oracle's wording.

### S6-24 · finding 24 · session strings went into `innerHTML` unescaped
`docs/ecology-lab.html:172` — new `esc()`, routed through ~40 call sites: `tile()` and `dataTable()` escape
centrally, plus every station's names / labels / notes / hypotheses / genotypes, every tooltip carrying session
values, `err.message` in the Punnett and Newick handlers, the dichotomous-key walker, and the drop handler.
The sweep covered the whole file, not just the six audited lines.
*Was:* `ExperimentLab` escapes for JSON only, so `note: nesting <in the hedge>` silently vanished from the
notebook card — and a shared `.eco` protocol could execute script on whoever dropped it in.
*Verified:* a hostile session with `<img src=x onerror=…>` in the note / tree / model / cross / entered /
hypothesis / phase slots → `window.__pwned === null`, zero injected `<img>`, and
`note: nesting <in the hedge> & "quoted"` renders verbatim.

### S6-25 · finding 25 · the visualizer's resize handler never recomputed layout
`demo/visualizer.html:441-447` — added `lastState`; the resize handler re-runs `applyState` (the heatmap
short-circuits to `draw()`).
*Was:* only `frame()` re-ran, while `tx/ty` came from a `W = cv.clientWidth` captured in `applyState:303` —
permanent misalignment for a statically loaded file.
*Verified:* at 1400 px nodes span 93–1307; after resizing to 700 px they span 70–630 and fit. Also checked on
the 1264-node final frame of `arena-session.json`.

### S6-26 · finding 26 · compare-mode canvases were sized once
`docs/tree-visualizer.html:369, 445` — the compare-canvas sizing is extracted out of `buildCmp` into `fitAll` /
`fitCmp` and wired into the resize listener and boot.
*Was:* the single `resize` listener called `fit()` for the single-tree canvas only, while `frame():446` kept
drawing with the new `clientWidth` — the right third of every tree clipped, plus upscaling blur.
*Verified:* reproduced pre-fix (backing 570 vs client 450 after resize); post-fix all four backing stores match
at every width.

### S6-27 · finding 27 · `rKScore`'s lower half was unreachable
`experimental/TreeEcology.java:287-290`, new `subtreeEvenness()` at `:311` and `splitEvenness` at `:344` — the
degenerate term is replaced by what the code comment always claimed it was: Shannon evenness of each node's
two-daughter size split, weighted by the nodes it divides. Weights and thresholds are untouched.
`shannonEvenness()` itself is unchanged, so **EC-3 / E-1** stays deliberately deferred.
*Was:* `shannonEvenness()` is identically 1.0 on a duplicate-free BST, so `raw = 0.25 + 0.4·eff + 0.35·dens`
and the score could never reach −0.5 — `rKLabel()`'s "strongly r-selected" branch was dead code, and a
maximally right-skewed 15-node tree scored −0.4997 and was labelled *"weakly r-selected"*.
*Now:* spine → −0.9997 (bottom label), perfect tree → +1.0 (top label), random RB/AVL trees stay in the
transitional / weakly-K bands their labels name.
*Test:* `TreeEcologyRkRangeProbeTest` (3 tests, including a mid-range guard).
*Judgment call worth reading:* the suggested "drop the term and rescale to `0.55·eff + 0.45·dens`" was measured
first and rejected — it opens the bottom band but drags an ordinary sorted-insert Red-Black tree to **−0.956**,
labelled "strongly r-selected (splay-like, opportunistic)", because `density = n/(2^h−1)` already
double-counts height. That would have traded a dead branch for a new wrong label. Consumers checked:
`ecologyReport()`, the non-asserting `TreeContextTesterAdditions` demo, and `TreeEcologyRkScoreProbeTest`
(passes untouched).

### S6-28 · finding 28 · drift transition labels were off by the eviction count
`ecology/EcologyRecorder.java:170-183, 223` — the recorder counts every window it ever closes and exposes
`closedWindowCount()` / `evictedWindowCount()`. `ecology/ExperimentLab.java:225-247` — the export labels
transitions with absolute 1-based window numbers, and the report states plainly *"Drift: 101 windows of 50 ops
closed, the most recent 64 kept — windows 1–37 were dropped, so this series starts at window 38."* — only when
eviction actually happened.
*Was:* `window: 50` plus a 5000-op phase closed 100 windows, 36 were evicted, and `drift.csv` row "1->2"
actually labelled windows 37→38 — a student charting the export read end-of-run drift as opening drift.
*Test:* `ExperimentDriftLabelProbeTest` (4 tests) — first row `38->39`, last `100->101`, nothing labelled
`1->2`, plus an unchanged no-eviction run.

---

## S4 — cosmetic, doc-only, defensive

- **S6-29 · finding 29** — `docs/tree-visualizer.html:377-382`: ported `crowdCap` from the sibling page,
  replacing the `Math.max(7, …)` floor with `Math.max(2.2, …)`. Confirmed the audit's figure exactly: on a
  620 px canvas overlap started at **n = 42** pre-fix and never occurs post-fix (checked at n = 41/42/50/63/100).
- **S6-30 · finding 30** — `docs/tree-visualizer.html:100`: added the teal `#2c6e5f` swatch, labelled "node in
  AVL / WB / Splay (these strategies don't colour nodes)"; "black node" now reads "black node (RB)".
- **S6-31 · finding 31** — `docs/ecology-lab.html:930-948`: the χ² table now covers df 1–30 with a
  Wilson–Hilferty fallback returning `{value, exact:false}`, and an impossible df yields `crit: null` which is
  *reported* ("the fit cannot be graded, so it is not being graded") rather than rendered as `undefined`.
  Verified: incomplete trihybrid df 26 → crit 38.885, perfect fit → ✅; df 40 → ≈55.753 flagged approximate;
  Mendel 5474:1850 still χ² = 0.263 / crit 3.841 / ✅.
- **S6-32 · finding 32** — `docs/ecology-lab.html:1006-1019`: `phenTint` is now a generated scale — 9
  widely-spaced hues (the first three matching `--s1/--s2/--s3`) × 3 lightness bands = 27 distinct tints, low
  alpha so white cell text keeps contrast. Incomplete trihybrid: 64 cells, **27 distinct tints, 0 transparent**
  (was 3 colored / 6 blank on the dihybrid).
- **S6-33 · finding 33** — `docs/ecology-lab.html:1538-1540`: `+seed || 42` replaced with an explicit
  empty/NaN check, so seed 0 is honored.
- **S6-34 · finding 34** — `docs/ecology-lab.html:1545-1566`: the review-round banner is no longer overwritten;
  it renders with an explicit "review the N you missed" button that starts the round on click.
- **S6-35 · finding 35** — `docs/ecology-lab.html:1571, 1576`: flashcard prompt and answer routed through
  `esc()`, so `homology = <derived> trait` survives in both.
- **S6-36 · finding 36** — `docs/ecology-lab.html:683` + the initial render at `:1760`: `lastSurvey` guarded,
  every station renderer swept for the same unguarded `.at(-1)` / sub-array dereference (meadow, drift,
  demography, archipelago, fossils, grid, entered, trees, island; plus `d.deaths[i]`, `lv.counts`, `q.counts`,
  `t.root`), and the initial embedded render wrapped in the same `try` the drop handler already had. A truncated
  payload now renders 3 valid cards with 0 errors; a throwing embed produces an error card with the Terrarium
  and Workbench still live, instead of a blank page.
- **S6-37 · finding 37** — `ecology/PhyloTree.java:193`: `json()` now uses the same `trimmed()` exactness
  fallback as `newick()` (the F-6 residual). Test: `PhyloTreeJsonLengthProbeTest` — 1e-7 survives as `1.0E-7`
  (valid JSON), and `json()` agrees with `newick()` through a re-parse.
- **S6-38 · finding 38** — `ecology/LogisticGrowth.java:45-56`: javadoc corrected — no caller is guarded,
  `census()` truncates to `t ≤ 1200` for the *opposite* reason (it wants the colonization ramp), the slice
  happens to reach the plateau so K̂ is currently sound, and tightening the cutoff silently breaks that.
- **S6-39 · finding 39 / `AUDIT_2026-07-21` F-P2** — `ensemble/EnsembleOrderedSet.java:84`:
  `optimisticVotesOverride` is now `private final`, threaded through the private constructor (`:130-144`,
  `:322`) instead of assigned after construction in `build()`. Test: `.optimisticVotesPinIsSafelyPublished`
  (modifier assertion plus a behavioral pin check with the global flipped).
- **S6-40 · finding 40** — `docs/ecology-lab.html:270-284`: the draw-on animation measures
  `path.getTotalLength()` (append-then-measure; 3000 kept only as a fallback) and removes the dasharray on
  `animationend`. Shipped paths report 938/938/565/504 units as their own dasharray, and all six are `null`
  after the animation completes.
- **S6-41 · finding 41** — `demo/visualizer.html:331-334`: `exiting: false` added to the re-tween assign.
  Reproduced on a pre-fix copy (node deleted at `t === 1` though present); post-fix it survives.
- **S6-42 · finding 42** — `demo/visualizer.html:102, 343, 131`: new `esc()`; `strategy` / `size` / `height`
  and the heatmap's `ops` / `checkEvery` escaped.
- **S6-43 · finding 43** — `docs/ecology-lab.html:365-382`: the rarefaction chart and `tipFn` now walk the same
  filtered `rPhases` list, plus an index clamp in `lineChart`'s mousemove for unequal-length series.

---

## Follow-up defects found during the fix work

### S6-44 (NEW) · `OrderedSet` null semantics collapsed on an empty set
Found while building the S6-14 parity test. On an **empty** `OrderedSet` the descent never reached a
comparison, so `contains(null)` returned `false`, `rank(null)` threw `NoSuchElementException`, and
`add(null)` **silently inserted null into the set** — where all three throw NPE on a populated set. Same class
of defect as finding 14, and the `add` case is worse than any of them: it blows up later, far from the cause.
`OrderedSet.java:203, 239, 270, 294, 604, 613, 622, 637-638, 648-649` now `Objects.requireNonNull` at the
public entry points, so the thrown class no longer depends on the set's size. `PersistentRankedSet` and
`BPlusTreeEngine` were checked and already had the property; `TreeContext` and `EnsembleOrderedSet` inherit the
fix by delegation. `countBetween` / `rangeSnapshot` were deliberately left alone — `null` there means
"unbounded" by contract.
*Test:* `SixthPassFixesTest.NullParity.nullArgumentsThrowIdentically` now loops sizes 0/1/9 across all three
implementations (the comment excluding empty sets is gone), plus `addNullNeverBecomesAnElement` and
`nonNullArgumentsUnchangedOnEmptySets`. Before: `add(null)` on an empty set left `size=1, inOrder=[null]`.

### S6-45 (NEW) · `FieldData.parseLines` could not read the CSV `FieldData.toCsv` writes
`parseLines` split raw on `[,\t]` with no quote handling, so a species name containing a comma — which
`toCsv` deliberately emits quoted, as `FieldDataTest.csvExport` asserts — came back as a reported problem
instead of round-tripping. New `FieldData.splitFields` (`:137-162`) is an RFC-4180 splitter with
`ExperimentExport.splitCsv`'s exact semantics plus TAB, wired in at `:91`, with optional leading-dataset-column
support at `:98-103`. The house rule is intact and separately pinned by `malformedRowsAreStillReported`
(7 problems, 0 counts), which passes both before and after — that is the point.
*Test:* `FieldDataTest.csvRoundTrip`, `.quotedNamesParse`, `.datasetColumnIsOptional`.
*Ambiguity call:* two-column dataset support would be ambiguous (`name,count` vs `dataset,name`), so only the
three-field shape carries a dataset label — the only shape `toCsv` emits. A two-field row is always
`name,count`. The label is dropped rather than returned (`Parsed` is a single name→count table), so rows from
two datasets merge, exactly as a repeated name already accumulates; documented at `:70-75`. One consequence:
under RFC-4180 an *unquoted* comma is a separator, so `oak, white,12` now reads as an export row rather than
being reported — format-correct, and documented at `:66-68`.
`docs/ecology-lab.html:1252-1259` was updated in step so the JS mirror stops reporting export rows, closing the
round trip from both ends.

### S6-46 · `EcologyFieldDay` truncation comment
`ecology/EcologyFieldDay.java:135-137` — a comment at the `t ≤ 1200` truncation naming the dependency the
corrected `LogisticGrowth` javadoc describes: `K̂ = max(N) + nudge` is sound only because the seeded run has
already plateaued by t = 1200; tighten the cutoff and K̂ is silently underestimated and r overestimated.

### S6-47 · finding 16's confirmation of the refuted zero-cell path
`demo/visualizer.html:146-165` — re-checked, **no change made**. The audit's refutation holds: a `cells: []`
map renders "0 cells, 0 viable, 0 unsound", `maxG = -Infinity` makes both loops no-ops, and resizing while it
is displayed produces no error. Recorded here so the next pass does not re-open it.

---

## Export-shape changes

1. `drift.csv` — the `transition` column carries absolute window numbers on runs exceeding 64 windows
   (`38->39` … `100->101` instead of `1->2` …). Header, row count and `brayCurtis` values unchanged;
   `session.json`'s `drift.bray` array untouched.
2. `report.txt` (and `report.html`, which embeds it verbatim) gains one line when windows were evicted.
   Nothing changes when they were not.
3. `session.json` `trees[].root.length` is written exactly (`0.5`, `1.0E-7`) instead of `%.6f` (`0.500000`) —
   same JSON number type, different text. The shipped sample tree has no branch lengths, so
   `docs/ecology-experiment-session.json` and the whole `docs/experiment-out/` bundle regenerate
   **byte-identical to baseline** (verified by diff).
4. A reproductive schedule with no intrinsic rate now produces a `⚠ spec:` problem and no `eulerlotka` model
   object in `session.json`, where it previously emitted a fabricated `rExact` of ±5.
5. `FieldData.toCsv` output is unchanged — only the reader learned to accept it.

## Frontend verification

Zero console errors and zero page errors on all three pages — on load, and under every shipped payload
(`ecology-lab-session.json`, `ecology-experiment-session.json`, `ecology-trace-session.json`,
`arena-session.json`, `arena-search-session.json`, `viability-map.json`, `visualizer-contract.json`), 99
tooltip hovers across all charts, hostile / truncated / empty sessions, autoplay, every button and keyboard
shortcut, and resizes in every mode. All three pages render the shipped data identically apart from the
intended changes, verified by before/after full-page screenshots. Driven in headless Chromium; the pages
remain self-contained with no new dependencies.

## Still open / deliberately deferred

- **Rotations still use the non-propagating local link setters** (AUDIT-2026-08-14 F-1). S6-21 corrected the
  documentation rather than the hot path; making `height` / `blackHeight` ancestor-exact would cost a
  propagation walk per rotation.
- **`shannonEvenness()` remains identically 1.0 on a duplicate-free BST** (EC-3 / E-1). S6-27 stopped
  *depending* on it in `rKScore`; the metric itself is still reported as-is.
- **`GenomeDrivenTreeController`'s literal-0 rotation feed** stays pinned by `ControllerConvergenceTest` G5
  (plan decision 12.2.2).
- **Per-member rotation meters** — S6-12 feeds the primary's delta, which matches the documented "the realized
  write term is the stream's, not per-member". Per-member metering remains the ADR's held refinement.
- **`saveSnapshot` failure signaling** — unchanged held ADR candidate from the fifth pass.
- **Hybrid grants are per-strategy-instance**, so a `TreeCloner`-made clone may be judged strictly once and pay
  one rebuild (S6-15 caveat b).
- **`TreeEcology` javadoc mojibake** — `MacArthur & Wilson (1967)?` and similar render as `?` under the
  javadoc task's platform charset, producing 8 warnings on every build. Pre-existing, not touched here;
  worth an encoding pass.
