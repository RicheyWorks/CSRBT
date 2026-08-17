# AUDIT 2026-08-17 — sixth pass (front end + back end)

Scope: full sweep of `csrbt-core`, `csrbt-experimental`, and all three HTML pages
(`demo/visualizer.html`, `docs/tree-visualizer.html`, `docs/ecology-lab.html`), cross-checked
against the emitters they consume. Five parallel hunters, then an adversarial verification pass
that tried to refute every candidate.

**37 candidates → 34 confirmed, 3 refuted.** Core and persistence findings were reproduced by
compiling `csrbt-core` (`javac --release 17`, log4j stubs) and running repro programs; control /
evolution findings were reproduced the same way; ecology math was re-derived in Python; JS
semantics were checked in node against the shipped session payloads.

Severity ladder: **S1** = data loss / crash on a supported path, **S2** = wrong answers or a stuck
control loop, **S3** = wrong metadata / degraded UX, **S4** = cosmetic or doc-only.

---

## S1 — data loss or crash on a supported path

### 1. `util/TreeHistory.java:328` — restored root's parent is `null`, not the NIL sentinel
`restoreFrom` installs `setRoot(...deepCopy(...))` without the `setParent(NIL)` every other rebuild
path performs (`FilePersistenceAdapter:216,444`; `TreeCloner:92,189`).

*Reproduced:* `saveCheckpoint("cp")` → mutate → `restoreCheckpoint("cp")` → next `add` throws
`NullPointerException` at `TreeStrategy.rotateLeft:79` via `RedBlackStrategy.fixInsert:129`. Fires
for RB, AVL and Splay. **New.**

### 2. `strategy/RedBlackStrategy.java:245-247, 279-281` — `fixDelete` case 2 has no `w.isNil()` guard
When the sibling is the shared NIL sentinel, `w.setColor(RED)` recolors the per-tree sentinel, and
the follow-on case-1 branch rotates about `NIL`, whose `setLeftLocal` overwrites `NIL.left` /
`NIL.parent` and calls `setRoot(NIL)`. CLRS guarantees `w != T.nil` only on a *valid* RB tree;
nothing enforces that here.

*Reproduced through public API only:* `add(1..63)` → `new TreeCloner(ctx).shallowClone(2)` →
`remove(k)`. Sentinel turns RED on the 3rd removal; on a black chain `10→5→2`, `remove(2)` throws
NPE **and empties the tree** — `inOrder()` goes `[2,5,10]` → `[]`. Silent total data loss. **New.**

### 3. `persistence/FilePersistenceAdapter.java:544-599` — persistent loader never checks the declared size
`loadPersistent` / `readFlatKeys` validate the strategy token and version but never compare
`header[3]` against the number of keys actually parsed. Deep-sweep **P-2** landed exactly this
tripwire on the int path (`:225-229`) and the generic path (`:448-454`); the persistent path was
missed, so P-2's "the header field is no longer advisory" is only two-thirds true.

*Reproduced:* save a 200-key snapshot, truncate the data line → loads as **114 keys**, logs
`size=114`, and the trailing partial token parses as a valid-but-wrong key (`"12"` from `"123"`).
**New (gap in P-2).**

### 4. `persistence/FilePersistenceAdapter.java:651-666` — `loadEnsemble` wipes the target, then replays a partial file
Same root cause on the `PERSISTENT_LABEL` branch (`:654-655`), but `target.clear()` at `:661` runs
*before* replay and the method returns `true`.

*Reproduced:* a snapshot declaring 300 keys → destination ensemble wiped and repopulated with
**118**, return value `true`. The javadoc's "`false` if malformed (the target is left untouched)" is
false in both halves. **New.**

---

## S2 — wrong answers, corrupted state, or a stuck control loop

### 5. `persistence/FilePersistenceAdapter.java:72-74` — concurrent saves of one name share a temp file
`tempPathFor` derives the staging path from the target name alone, so two threads saving `"r"` open,
truncate and write the same `.rbt.tmp`; one `commitAtomically` renames a file the other is still
writing. **4 of 25 rounds** left a committed target that `loadOrderedSet` refuses (`null`) — the
previously-good snapshot destroyed. This is precisely what the D-3 comment at `:65-71` promises can
never happen. Fix: unique temp name (PID/UUID/counter) or a per-name lock. **New.**

### 6. `util/TreeCloner.java:260-266` — `copyNodeFields` drops `augmentedRef`
Copies color/tag/augmentedValue/lastRotation/pathCompressed but not the generic augment slot, so
`snapshot()`, `deployCloneArmy()`, `mutantClone()`, `shallowClone()` and `TreeHistory.saveCheckpoint()`
silently discard it — contradicting `GenericIntervalAugmentor`'s javadoc and `TreeNode1.deepCopy:521`,
which *does* copy it.

*Reproduced:* intervals `[10,50],[20,25],[30,90]` → `snapshot()` → clone reports `[[10,10],[20,20],[30,30]]`
and `stabQuery(45)` returns `[]` where the source returns 2. No exception, wrong answers. **New.**

### 7. `adapter/NavigableOrderedSet.java:182, 427` — the descending view's iterator mutates the base set
`Desc` declares itself read-only and throws `UnsupportedOperationException` from `add`/`remove`/`clear`/
`pollFirst`/`pollLast` (`:443-447`), but `Desc.iterator()` delegates to `asc.descendingIterator()` —
the live-removing `SnapshotIterator`. `AbstractCollection.retainAll` / `AbstractSet.removeAll` reach
mutation through it.

*Reproduced:* base `[1,2,3,4,5]`; `descendingSet().remove(3)` correctly throws, but
`descendingSet().retainAll(List.of(1))` returns `true` and leaves the **base** as `[1]`. `removeAll` is
size-dependent — throws on one shape, silently empties the base on another. Regression introduced by
**F-3**'s parity fix (AUDIT-2026-08-14). Fix: give `Desc` a non-removing iterator, as `Range` already
has at `:267-275`. **New.**

### 8. `evolution/Fitness.java:90` + `PolicySearchController.java:186-192` — an empty trial shadow scores 0.0 and wins forever
Cost is 0 for an empty tree (meanDepth 0) and hard-zeroed for `size <= 1`; the write term is
identically 0 (finding 12). On the documented `SAMPLED_SHADOW` path the trial shadow is legitimately
tiny while the primary holds thousands.

*Reproduced:* `shadowSampleRate(0.02)` → shadow size 0, primary 40 keys → `armCost 0.0000` vs
`incumbentCost 0.5497` → **promoted on the first trial**, and the arm keeps `meanCost = 0.0`, so
`bandit.bestArm()` is pinned to it for every subsequent round. The arm that won this way was
WB(Δ=2,Γ=1) — the one deep-sweep **D-5** names as self-disqualifying. Same pattern at
`PolicyEvolutionController.java:258`. **New.**

### 9. `ensemble/EnsembleController.java:144-159` — promotion target is never checked for liveness
`available` is filtered only by `byStrategy.containsKey(...)`, and `byStrategy` (built once at `:71`)
is never pruned. `EnsembleOrderedSet.promote` throws `IllegalStateException` for a non-ACTIVE member
(`:817-818`). `EnsembleController.checkHealth` itself retires members (`:345,358`), and `retire`'s
javadoc says a retired member "is never served, fanned to, or **promoted**".

*Reproduced:* a MORPH decision naming a retired/quarantined member throws out of
`evaluateAndMaybePromote` on every evaluation. A dead member should be a hold, not a crash. **New.**

### 10. `ensemble/ParallelMemberExecutor.java:103` + `EnsembleOrderedSet.java:888` — `shutdownNow()` orphans futures that are then awaited forever
`shutdownNow()` drains the queue and returns the pending `Runnable`s; those `FutureTask`s stay NEW and
are never run or cancelled, so `f.get()` at `:72` blocks permanently. `close()` takes no lock.

*Reproduced:* 3 members + `ParallelMemberExecutor(1)` (a documented builder seam), `close()` on another
thread during an in-flight write → writer parked forever **while holding `writeLock`**; a second writer
went BLOCKED. Also reachable via `parallelFanOut()` whenever K-1 exceeds the core count. **New.**

### 11. `OrderedSet.java:707-709` → `captureKeyTags():837` — morph rebuilds from an `equals`-keyed map
The element list is `keyTags.keySet()` from a `LinkedHashMap`, so keys that are `equals` but compare
non-zero collapse into one entry; the health gate can't catch it because clause 1 compares the
candidate against that same collapsed list. (`selfRepair:759` correctly uses `new TreeSet<>(keyOrder)`.)

*Reproduced:* set ordered by `id`, `equals` by `name`; three elements → `setStrategy(new AVLStrategy<>())`
returns **true** and the set silently becomes size 2. The equals-vs-comparator class is a documented
deferral (deep-sweep **D-4**, ecology **B-4**) — **this site is new, and its consequence is element
loss rather than window ordering.**

### 12. `evolution/Fitness.java:85` — `rotationsPerWrite` is structurally always 0
`RollingWorkloadMonitor.rotEwma` is fed only by the `rotations` argument of `recordAdd`/`recordRemove`,
and every production caller passes 0 (`EnsembleController:105,112`; `PolicySearchController:107,114`;
`PolicyEvolutionController:139,146` via the `WorkloadMonitor:59,62` defaults; `GenomeDrivenTreeController:179,186`
explicitly). So `writeCost = writeFraction × rotationsPerWrite` is identically 0.0 and ADR-011 V3/V4
promotion is decided purely by the structural read term — a rotation-thrashing policy wins whenever its
tree is momentarily shallower.

**Already reported as `AUDIT_2026-07-21` F-E1** (open, priority #3). `CHANGELOG-2026-08-12-t1-rotation-meter`
fixed `getRotationCount`, the battle runner and the genome STRESS metric — it did not touch the fitness
feed. The genome controller's 0-feed is separately pinned as deliberate (`ControllerConvergenceTest` G5).
Re-raising because finding 8 compounds it.

### 13. `PersistentRankedSet.java:53-76` — return values and meters are computed with a non-atomic `size()` pair
Effective-change is inferred from `engine.size()` before/after, and `totalInsertTime`/`insertCount`/
`totalDeleteTime`/`deleteCount` (`:33-34`) are plain non-volatile fields mutated outside any lock —
though `PersistentTreeEngine` explicitly supports concurrent writers and this class claims "concurrency
is inherited, not added."

*Reproduced:* 4 threads × 20 000 `add`. The engine stays correct (19 618 keys, deterministic), but `add()`
returned `true` 20 127 / 21 929 / 27 928 / 24 724 / 25 428 times across five rounds — up to **42 % over-report**.
In an ensemble that is the value voted on for `OrderedCollection.add`. **New.**

### 14. `BPlusTreeEngine.java:140, 204, 330, 438, 471` — null-argument semantics diverge from the other engines
`contains(null)` → `false`, `countInRange(null, x)` → `0`, `rangeQuery(null, x)` → `[]` where
`OrderedSet`/`PersistentRankedSet` throw NPE; `add(null)`/`remove(null)` throw `IllegalArgumentException`
where the others throw NPE. `RankedSet`'s javadoc demands exact parity because VERIFIED voting compares
thrown-exception classes (`EnsembleOrderedSet.Thrown.equals:1070-1077`).

*Reproduced:* one `ensemble.contains(null)` call on a VERIFIED ensemble → RB and AVL throw, the B+tree
answers `false`, majority wins, and the structurally healthy B+tree member is **QUARANTINED**. One bad
caller argument removes a good member. **New.**

### 15. `strategy/HybridStrategy.java:178` vs `:302` — the ±2 relaxation is keyed on depth at *write* time, re-judged at *validation* time
Depths change as the tree grows and rotates, so a node legitimately relaxed while deep is later judged at
tolerance 1. The **H-2** fix (routing Hybrid to its own tolerance-aware check) therefore does not achieve
its goal for finite thresholds.

*Reproduced:* 600 random inserts under `HybridStrategy(7)` → `validateInvariant` reports 8 violations on a
tree Hybrid itself built; `setStrategy(new HybridStrategy<>(7))` is silently refused in 7/20 seeds (5/20 at
threshold 6), and `selfRepair()` fails its short-circuit and pays a futile O(n) rebuild. Adjacent to
deep-sweep **H-2** and `AUDIT_2026-07-21` **F-C3**; the depth-keying mechanism itself is **new**.

### 16. `experimental/ecology/PopulationGenetics.java:85-91` — Euler–Lotka bisection has a hardcoded bracket and no containment check
`lo = -5, hi = 5`, and an out-of-bracket root is returned as the bracket endpoint, labelled *exact*.

*Verified numerically:* `lx = {1,1}, mx = {0,250}` → true r = ln 250 = 5.5215; the code returns
**rExact = 5.0000** while `rApprox` correctly reports 5.5215, and `ExperimentLab:640` prints them side by
side. Mirrored for r < −5 (−6.9078 → −5.0). Reachable from student text: `model: eulerlotka 1:0 1:250` in a
`.eco` file; `ExperimentSpec:348` validates only R₀ > 0, so it flows into the report and `session.json`.
**New.**

---

## S3 — wrong metadata, degraded UX, or a self-contradicting page

### 17. `docs/ecology-lab.html:426-428` — the shipped page contradicts itself
The "disagree" branch hardcodes *"the ratio estimator predicts an **empty** archipelago"* while the tile
row directly above prints the real value. With the embedded session (`:141`: `levins 0.833333`,
`observed 1`, |Δ| = 0.167 > the 0.15 threshold) the page renders "83% Levins predicted occupancy" six
lines above prose claiming an empty archipelago — **out of the box, no user input required.** Stale prose
left by **F-5** (AUDIT-2026-08-14), which changed levins 0 → 0.833333 and regenerated both session copies
but not the narrative or the threshold.

### 18. `ensemble/EnsembleController.java:71, 85-98` — `byStrategy` is a one-shot index
Built in the constructor from each member's *current* strategy class and never rebuilt, though
`PolicySearchController.beginTrial:146` and `PolicyEvolutionController.beginGeneration:218` both call
`setStrategy` on members by design.

*Reproduced:* after morphing member 1 to Splay, the controller logged `promoted RED_BLACK->AVL` for a
member actually running Splay; `currentPrimaryId()` and every `event=morph_eval` line are wrong.
`EnsembleMember.strategyName()` is likewise frozen at construction. Observability corruption only. **New.**

### 19. `util/TreeCloner.java:80-108` — `snapshot()` drops the sliding-window bound
The clone is built as a bare `new TreeContext(strategy)`, so a "fully independent deep copy" of a bounded
context is unbounded. *Reproduced:* `setMaxSize(4)`, add 1..10 → size 4; clone reports `maxSize = 0` and
grows to 9 keys. **New.**

### 20. `util/TreeHistory.java:326-340` — checkpoint restore bypasses the window bound
`forceSizeInternal` → `resyncFromEngine` recomputes size and FIFO but never evicts, contradicting this
class's documented contract. *Reproduced:* checkpoint 10 keys, `setMaxSize(3)`, restore → size 10 with
`maxSize == 3`; the next `add` evicts 8 keys at once. Same contract family as deep-sweep **D-2**, which
CHANGELOG-2026-08-12-consolidation fixed for `undo` only.

### 21. `strategy/TreeStrategy.java:63-102` — rotations leave `height`/`blackHeight` caches stale for ancestors
Both rotations use the `*Local` link variants, justified by a comment about *subtree size* being
ancestor-invariant — true for `size`, false for `height`/`blackHeight`. AVL and Hybrid mask it via
`refreshHeight()` on the way up; RB and WeightBalanced do not.

*Reproduced:* RB engine, `Random(0)` mixed ops — after 21 ops node 39 reports `getHeight() == 5` where the
real height is 4. `TreeNode1.getHeight()` is public and documented as "maintained automatically."
**Explicitly deferred** in AUDIT-2026-08-14 F-1 ("rotations still use the non-propagating local setters") —
listed here only because the public accessor's javadoc still promises otherwise.

### 22. `docs/ecology-lab.html:236, 242` — `lineChart` has no `yMax` floor
`yMax = max(values) * 1.08`, so an all-zero series gives `yMax === 0` and `Y(v)` evaluates `0/0`.
*Reproduced in node:* `d = "M40,NaNL62.5,NaN…"` — the curve silently vanishes with no error. `barChart:212`
has the `Math.max(1, …)` floor; `lineChart` does not. Live path: Theory Bench with `logistic`/`exponential`
N₀ = 0 (`:1507,1511`) or `levins` p₀ = 0 (`:1515-1518`) — all natural "start from nothing" inputs.

### 23. `docs/ecology-lab.html:1117-1135` — `parseCounts` splits on `/[,\t]/` with no RFC-4180 quoting
The card advertises spreadsheet paste (`:983`) and the comment at `:1116` claims it mirrors
`FieldData.parseLines`. *Reproduced in node:* `"oak, white",12` yields one species literally named
`"oak, white",12` with count **1** and `skipped: 0` — silent corruption, nothing reported. Two
aggravations: the Java oracle *reports* that same line as a problem (violating the house "reported, never
guessed" rule), and `FieldData.toCsv` deliberately emits quoted names (`FieldDataTest.csvExport` asserts
`site,"a,b",3`), so pasting the tool's own export back in corrupts it. `ExperimentExport.splitCsv:109-135`
already implements quoting.

### 24. `docs/ecology-lab.html:332, 559, 577, 593, 606, 624` — session strings go into `innerHTML` unescaped
`ExperimentLab` escapes for JSON only (`WorkloadTrace.escapeJson`), while the same module's
`ExperimentExport.escapeHtml:104-106` proves the codebase knows the difference. `note:` / `tree:` / `data:`
values are free text a student types into a shared `.eco` protocol. Failure without any malice:
`note: nesting <in the hedge>` parses as an unknown element and the text silently disappears from the
notebook card. A shared protocol is also a script-injection vector for whoever drops it into the lab page.

### 25. `demo/visualizer.html:431` — the resize handler never recomputes layout
It only re-runs `frame()`, which lerps to `tx/ty` targets computed by the last `applyState:303` against
the old `cv.clientWidth`; `draw():358-360` does resize the backing store. Widen the window and the tree
stays packed in the old width; narrow it and right-hand nodes clip off-canvas — permanent for a statically
loaded file.

### 26. `docs/tree-visualizer.html:433, 365` — compare-mode canvases are sized once
`buildCmp` sizes the four backing stores; the only `resize` listener calls `fit()`, which resizes the
single-tree canvas exclusively, while `frame():446` keeps drawing with the *new* `o.el.clientWidth`.
Enter compare mode, widen the window → the right third of every tree is cut off (plus upscaling blur)
until compare mode is toggled off and on.

### 27. `experimental/TreeEcology.java:241-274` — `rKScore`'s lower half is unreachable
`shannonEvenness()` (`:77-81`) is provably ≡ 1.0 on a duplicate-free BST (distinct keys → H′ = ln n,
S = n), so `raw = 0.25 + 0.4·eff + 0.35·dens` and the score is strictly > −0.5 — making `rKLabel()`'s
"strongly r-selected" branch at `:277` dead code. A maximally right-skewed 15-node tree (the most
pathological possible) scores −0.4997 and is labelled *"weakly r-selected"*. Root cause already documented
as **EC-3** (AUDIT-2026-08-09-ecology-module) and **E-1** (deep-sweep) and consciously not fixed; the dead
branch is the new part.

### 28. `experimental/ecology/ExperimentLab.java:219-231` — drift transition labels are off by the eviction count
Labels are `(i+1)->(i+2)` over the *retained* window list, but `EcologyRecorder:201-202` caps retention
(call sites at `:107,119` pass 64) and evicts the oldest. `window: 50` + a 5000-op phase = 100 windows →
36 evicted → `drift.csv` row "1->2" actually labels windows 37→38. A student charting the export reads
end-of-run drift as opening drift. Bray values themselves are correct; only the CSV label column is wrong.
**New.**

---

## S4 — cosmetic, doc-only, or unreachable from shipped data

29. `docs/tree-visualizer.html:372` — node radius floored at 7 with no crowding cap (the sibling page has
    `crowdCap` at `:309-310`); overlap begins at n ≥ 42 on a ~620 px canvas, reachable in 5 clicks of
    "+10 random", and at r = 7 the `if(r>8)` guard also drops key labels.
30. `docs/tree-visualizer.html:97-102` vs `:389` — the legend lists red/black/amber/blue, but every node in
    AVL / WB / Splay mode is teal `#2c6e5f`, a color the legend never explains.
31. `docs/ecology-lab.html:969` — `crit: CHI_CRIT[df-1]` with only 8 tabulated values (`:877`), and
    `ok: chi <= undefined` is always false. `jsCross` permits 3 loci (`:880`); an incomplete-dominance
    trihybrid (27 classes, df = 26) prints "critical **undefined**" and "❌ significantly off the ratio"
    for a perfect Mendelian fit.
32. `docs/ecology-lab.html:947, 954` — only 4 phenotype tints, the 4th `transparent`, with
    `Math.min(phenIdx, 3)` collapsing the rest; an incomplete-dominance dihybrid (9 classes) colors 3 and
    leaves 6 blank, so the "colors by phenotype" claim at `:553` is false for exactly the crosses that need it.
33. `docs/ecology-lab.html:1383` — `mulberry32(+seed || 42)`: seed 0 is falsy, so a student asking for
    seed 0 silently gets the default deck order (verified in node).
34. `docs/ecology-lab.html:1393-1397` — the "reviewing the N you missed" message is written to
    `out.innerHTML` and unconditionally overwritten by `card()` at `:1408` in the same synchronous turn;
    it can never paint, and the counter silently resets to "card 1 of 5".
35. `docs/ecology-lab.html:1409, 1413` — flashcard prompt/answer interpolated into `innerHTML`; content is
    self-authored, so the failure is render mangling (`homology = <derived> trait` loses text), not XSS.
36. `docs/ecology-lab.html:635` — `isl.timeline.at(-1)` is unguarded, unlike the `S.meadow && S.meadow.phases`
    pattern nearby. Island is the last station, so the effect is a missing card plus a cryptic error banner,
    not a blank page.
37. `experimental/ecology/PhyloTree.java:186` — `json()` formats branch lengths with `%.6f`, the exact defect
    `trimmed():140-150` was patched to avoid for `newick()` (**F-6** residual). Lengths below ~5e-7 serialize
    as `0.000000`. No impact on the shipped consumer — the lab's cladogram reads only `name`/`children`.
38. `experimental/ecology/LogisticGrowth.java:50-51` vs `EcologyFieldDay.java:133-139` — the javadoc says
    `census()` "guards this by fitting only plateaued runs"; the code truncates to t ≤ 1200 with the *opposite*
    rationale. Replayed with a Java-`Random` port (seed 11): the slice does include the plateau, so K̂ is fine —
    the contradiction is purely in the prose, and a maintainer tightening the cutoff would be misled.
39. `ensemble/EnsembleOrderedSet.java:77, 314` — `optimisticVotesOverride` is a plain (non-volatile) `Boolean`
    assigned after construction in `build()`, while the sibling `mode` assigned at `:313` *is* volatile; under
    unsafe publication a reader observes `null` and falls back to the process-global static the pin exists to
    escape. **Already `AUDIT_2026-07-21` F-P2**, still unfixed.
40. `docs/ecology-lab.html:258-259` — the draw-on animation hardcodes `len = 3000` for both `--len` and
    `stroke-dasharray` and never removes the dasharray, so a path longer than 3000 user units sits in the gap
    permanently. The shipped session's longest animated paths measure ~504 and ~426 units; it needs a
    ~1000-point trace to fire.
41. `demo/visualizer.html:323-324, 350` — `applyState` re-tweens a returning node without clearing the
    `exiting` flag set at `:329`, so `frame()` deletes it at `t === 1`. Autoplay is 1600 ms vs `DURATION = 750`,
    so triggering needs a remove-then-re-add plus manual stepping inside 750 ms; the shipped
    `arena-session.json` has 0 such occurrences.
42. `demo/visualizer.html:333-335` — `meta.innerHTML` interpolates `state.strategy`/`size`/`height` from the
    dropped file unescaped. Only `strategy` is a string in `visualizer-contract.json`, and the file is local.
43. `docs/ecology-lab.html:339, 350-351` — `lineChart:234` filters empty series but the shared `tipFn` still
    walks the unfiltered `m.phases`, so a `rarefaction: []` phase throws on every mousemove. No emitter can
    produce it (`rarefactionCurve` returns `[]` only for total = 0, and every `ExperimentLab` phase has ≥ 1 op);
    hand-edited JSON only.

---

## Refuted

- **`MorphController.java:79-86`** — a health-gate rejection advancing the cooldown clock is intentional and
  test-pinned (`:80-81` cites plan §12.3 F3/F7; `MorphControllerTest.healthRejectedKeepsIncumbent` asserts
  exactly it). Cost is one build-aside per caller-driven eval interval; suppressing `observed()` would freeze
  the clock instead. No wrong result.
- **`FieldData.toEcoLine`** — the `#` half cannot happen (both entry parsers strip `#` before a name is
  formed), and the label half has no production caller; the JS workbench emits hardcoded labels.
- **`demo/visualizer.html:138-141`** (zero-cell ViabilityMap) — `iw/0` is `Infinity`, not NaN; the loops are
  no-ops and the header honestly reports "0 cells". `ViabilityMap.sweep()` cannot emit zero cells anyway.
- **`docs/ecology-lab.html:1137`** (`ecoName` and `#`) — `parseCounts:1121` already does `raw.split("#")[0]`,
  so no name reaching `ecoName` can contain `#`.

---

## Verified clean

Randomized differential fuzz vs `TreeSet` across RB/AVL/Splay/Hybrid/WB (60 seeds × 400 mixed ops) checking
BST order, parent links, per-node size, RB/AVL/WB invariants and sentinel integrity — only finding 21 fired.
Order statistics exact for all five strategies including empty/single/duplicate/root-delete edges.
`IntervalAugmentor` max-hi exact under insert+delete churn. `buildBalanced`/`buildFromSorted` RB-valid for
n = 0..64. All 20 morph pairs preserve contents and size.

B+tree split/merge/borrow/root-collapse/leaf-chain: differential fuzz at fanout 4/5/7/8/32 with
`validateStructure()` after every op — zero violations. Persistent structure sharing: 200 trials × 300
mutations with snapshots every 17 ops re-verified at the end — no leakage into older versions.
`NavigableOrderedSet` floor/ceiling/higher/lower on base, all four `subSet` inclusivity combos, descending
views, and sub-bound throw parity — **0 divergences** vs `TreeSet`. `StringKeySerializer` percent-encoding
and its `%`-escape boundary; UTF-8 on both ends of every snapshot; `TreeExport`/`TreeSessionRecorder` JSON
escaping stays brace-balanced through Morph and Repair points.

`CostModelStrategyScorer` constant algebra (the AVL/Hybrid w ≈ 0.08 crossover and RB's +6 % read gap both
reproduce); `PolicyBandit` UCB1 including the degenerate `log(totalPulls)` cases; `PolicyGenome`
reflect/perturb/blend bounds at every wall including Δ = 2; `RollingWorkloadMonitor`'s lazy-decay sketch;
`MorphHistory`'s saturating clock; `voteLocked` majority/uniqueness tally.

Ecology math verified against source: Shannon/Simpson/Hill/Chao1/rarefaction (incl. the log-space
hypergeometric identity), broken-stick and geometric-series expectations, Pianka/Bray–Curtis/Renkonen/
Jaccard/Sørensen/Whittaker with all empty-population guards, Chapman estimator and Seber variance,
Hardy–Weinberg χ², Punnett gamete enumeration and the 3:1 / 1:2:1 / 9:3:3:1 ratios (Mendel's 5474:1850
reproduces χ² = 0.2629), life-table lx/qx/class-width/median, quadrat binning, Morisita,
`SegmentedLruCache` segment accounting, `CacheIsland` immigration−extinction bookkeeping,
`CacheEvolutionLoop` (μ+λ) selection, Newick parse/round-trip incl. nested parens and malformed rejection,
all 8 CSV header/field-count pairings, `splitCsv` RFC-4180 round-trip, `ViabilityMap`'s sweep.

Frontend contract check: every `TreeSessionRecorder` field consumed by `demo/visualizer.html` matches the
Java emitters exactly, including the deliberate `breedOp` rename; `ViabilityMap` field names all match;
`drift.bray` can never be empty (`WorkloadTrace:84` requires ≥ 3 windows); no `localStorage`/`sessionStorage`
anywhere; no dead buttons or undefined-function references in any of the three pages; all SVGs set `viewBox`.

---

## Suggested fix order

1. Findings **1–4** — crash and data-loss paths, all small localized fixes.
2. Findings **5–7** — snapshot race, dropped augment payload, view mutating the base.
3. Findings **8–16** — control-loop and parity fixes; 8 and 12 should land together.
4. Finding **17** — the lab page contradicts itself on load; one-line prose/threshold fix.
5. The rest as a batch, with 22–24 (chart NaN, CSV quoting, HTML escaping) grouped since they share the
   student-input surface.
