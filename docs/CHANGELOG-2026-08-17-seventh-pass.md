# CHANGELOG 2026-08-17 — seventh pass

The consolidation session after the sixth-pass fixes: three held items cleared with their own ADRs, one new
feature slice, an adversarial hunt over the freshly-changed surface, a constructor-to-constructor wiring
audit, an edge-case hardening pass, and a browser-driven verification of all three HTML pages.

**Build:** `./gradlew build -x :csrbt-benchmarks:jmh` → **BUILD SUCCESSFUL**, **1063 tests, 0 failures,
0 javadoc warnings**, verified across repeated `--rerun-tasks` runs. Baseline entering this session was 887.

**Method:** every behavioural fix was verified red-before / green-after by reverting it in isolation. Every
bug-hunt finding required a reproduction with observed-vs-expected values before it was accepted. The HTML
pages were driven in headless Chromium, not reasoned about.

**Nothing here is a breaking API change.** Every addition is additive — `default` interface methods, new
overloads, new nested records. The next release remains **0.2.1**.

New documents: `ADR-023`, `ADR-024`, `ADR-025`, `ADR-026`, `AUDIT-2026-08-17-wiring-seventh-pass.md`.

---

## Part 1 — held items cleared

### ADR-023 · rotation cache propagation (closes AUDIT-2026-08-14 **F-1**)

`getHeight()` is ancestor-exact again. Rotations now carry a fixed-point height climb that stops at the first
ancestor whose height recomputes unchanged (`TreeNode1.refreshHeightUpward:335`, wired at
`TreeStrategy.rotateLeft/rotateRight:100-121`); the old non-propagating bodies became `rotateLeftLocal` /
`rotateRightLocal` (`:131,154`), mirroring the existing `setLeft` / `setLeftLocal` naming. AVL, Hybrid and
Splay call the `*Local` primitives with the proof recorded at each call site — they already refresh on the way
up — while RedBlack and WeightBalanced use the carrying pair.

The staleness was not marginal. Root height was wrong after **98.7%** of ascending-insert operations on
RedBlack and 74.3% on WeightBalanced (max error 8); AVL, Hybrid and Splay were always correct. Exactly one
in-repo consumer drew a wrong conclusion — `TreeContextTesterAdditions:128` printed `h=7` where the real
height was 6.

Cost, measured A/B interleaved in one JVM over 51 rounds with paired medians against a same-code control noise
floor of ±6% worst / ±3% typical:

| strategy | sorted-insert | random-insert | mixed add/remove |
|---|---|---|---|
| RedBlack | **+27.2%** | +1.9% | −1.8% |
| WeightBalanced | +4.1% | −0.1% | +3.1% |
| AVL | −3.1% | −0.3% | −1.3% |
| Splay | — | +0.4% | +0.1% |
| Hybrid | +0.4% | +0.9% | −1.3% |

Thirteen of fourteen cells are in the noise. The fourteenth is a shape for which the library already ships an
O(n) rotation-free path. Three cheaper variants were measured and rejected (unconditional eager climb, a
`maintainsAncestorHeights()` query inside the rotation body — megamorphic, +10–12% on Splay while climbing
nothing, and carrying black-height on the same walk). Dirty-bit and refresh-on-read were rejected on
reasoning recorded in the ADR: both are O(subtree) on first read, and refresh-on-read makes a read *mutate*,
which ADR-004 R1 forbids.

`blackHeight` stays inexact **by accepted decision** — its dominant source is `setColor`/`flipColor`
(O(log n) recolours per RB write), not rotation, so exactness there is a different and much hotter change.
`getBlackHeight()` now states its own limits and points at `blackHeight()` for the exact answer.
ADR-018's `AmortizationFrontierTest` tripwire re-verified: 2.3236 → 1.3161 → 1.0638 → 1.0007 → 0.9902,
monotone, 256k crossing intact.

*Held, with trigger:* maintaining height once per write instead of twice. Instrumenting both walks shows a
monotone stream pushes a height change up 26.7 levels/op via the BST link and takes it back off over 22.7
levels/op via the rotation. Dropping the height leg from `recomputeAugmentAndPropagate` would likely leave RB
monotone insert *faster* than before this ADR — but that path is F-1's own fix, pinned by
`ReconstructionHeightProbeTest`, and each reconstruction path would need its own repair.

*Tests:* `RotationHeightPropagationTest` (5) — 8 of 20 sweep cells fail against pre-fix classes. JMH rig at
`csrbt-benchmarks/.../RotationHeightPropagationBenchmark.java` so the cost model is re-runnable.

### ADR-024 · per-member rotation metering (closes ADR-011's held refinement, extends S6-12)

Each ensemble member now meters its own rotations over the writes that member actually received, and is
priced on its own rate. S6-12 had plumbed real rotation deltas into the fitness feed but from the **primary
only**, so a rotation-thrashing member and a rotation-cheap one looked identical in the write term — in an
ensemble whose members run different strategies, which is the entire point.

The comparability rule is explicit and tested, in three clauses: **own churn, own denominator** (metered in
the fan-out, the only code that knows which members a write reached); **`MIN_METERED_WRITES = 8`**, below
which `rotationsPerWrite()` is `NaN` — *no* observation rather than a cheap one, the same discipline S6-08
applied to size; and **both sides per-member, or neither**, since `MorphPolicy` reads a ratio and mixing a
per-member cost with a stream-priced one is two measurements in one number. Falling back is exactly S6-12's
behaviour, so the refinement can never be worse than what it replaces.

Rotations-per-write is an *intensive* quantity — a property of the policy, not of the stream's length — which
is why a sampled shadow's rate is comparable with a full-stream member's even though its count is not.

`EnsembleMember.java:104-215` (meter), `EnsembleOrderedSet.java:332-346, 466-479, 517-547, 697-746`
(fan-out and replica paths), `PolicySearchController.java:195-199, 247-256, 285-333`,
`PolicyEvolutionController.java:260-264, 288-334, 359-395`, `EnsembleController.java:249-252, 290-310`
(`rot/w` on the `morph_eval` meters line). `WorkloadMonitor.java:21`'s broken `{@link #size()}` fixed in
passing.

*Bug found and fixed while doing this:* `pickTrialSlot` can return `null` after a promotion (engine-tier
primary deposed, no strategy-backed slot left); the log line would have NPE'd there.

*Tests:* `PerMemberRotationMeterTest` (10), red-before across four separate reverts.
*Amended same day* — see Part 3, item C.

### ADR-025 · snapshot save failure signaling (closes the fifth-pass held ADR candidate)

All four save shapes used to log-and-swallow every `IOException` behind a `void` return: open failure,
mid-write I/O error, full disk and commit-rename failure all looked identical to success. S6-05's staging
scheme does hold — the previous file survives and staging files are cleaned — but that guarantee was
**invisible**.

`void saveSnapshot` is kept byte-for-byte as-is. Added alongside it: `trySaveSnapshot` returning a
`SaveResult` record with `SAVED` / `FAILED` / `UNREPORTED`, as a **`default`** method on
`TreePersistenceAdapter` so existing implementors compile unchanged and inherit `UNREPORTED` rather than a
fabricated `SAVED`. `orThrow()` makes the exception option opt-in per call site. There is deliberately **no
`PARTIAL`** — the ensemble save has no fan-out (it snapshots the primary only, one file), so partial member
failure is not a reachable state, and a state nothing can produce is one every caller handles for nothing.

A checked exception would break every caller; an unchecked one would silently change every existing caller's
runtime behaviour with no compile warning; a boolean cannot distinguish "retry" from "reconfigure". Caller
defects (bad name, null argument, a `';'` key) still throw — deterministic, and not retryable.

`TreePersistenceAdapter.java` (rewritten), `FilePersistenceAdapter.java:114-198, 409-434, 562-598, 747-777`
— `stageAndCommit` replaces four copies of the same try/catch/finally.

*Tests:* `SnapshotFailureSignalingTest` (9), with real failure modes — a commit rename blocked by a non-empty
directory at the target path, and an open that cannot create the staging file (name over the 255-byte limit).
A read-only-directory probe was written first and **rejected**: the suite can run as root, where permission
bits are bypassed and the probe passes while testing nothing.

*Held:* `loadSnapshot` returning `null` for both "absent" and "malformed" — closed by ADR-026 below. No
`fsync`, so `SAVED` means "the filesystem has it", not "it survives a power cut".

### EC-3 · the evenness metric, and a javadoc sweep

`shannonEvenness()` is provably identically 1.0 on a duplicate-free BST and had been documented-but-unfixed
since 2026-08-09. S6-27 stopped `rKScore` depending on it; the accessor was still reporting a constant to
students as a measurement.

**Decision: keep the value, deprecate the accessor, and stop printing a constant as a measurement — do not
re-point a named index at a different partition.** Pielou's J′ = H′/ln S is defined on a species-*abundance*
vector. A duplicate-free BST supplies a species *list* — incidence data, every key present exactly once — and
ecology draws exactly this line: incidence data supports richness and incidence-based similarity (Jaccard,
Sørensen, Chao2), but abundance-based diversity and evenness are undefined on it (Magurran 2004, ch. 2). The
formula was never wrong; the sample was.

The "redefine over depth strata" alternative was measured before being rejected, per house discipline: Pielou
J′ over depth-class counts **runs backwards and is size-dependent** — a 15-node spine scores 1.000 (one node
per stratum, a perfectly even canopy), a perfect 15-node tree 0.820, a perfect 1023-node tree 0.599. "Most
even" would name the most pathological tree. Calling that "Shannon evenness" would repeat precisely the fault
the sixth pass diagnosed in `rKScore`.

`TreeEcology.java:79-133` — `@Deprecated`, return value unchanged so no caller's arithmetic moves, javadoc
routing to the two honest instruments (`CommunityMetrics.pielouEvenness` over `EcologyRecorder` access
abundances, and `subtreeEvenness()`). `:46-63` — `shannonDiversity()`'s javadoc no longer claims the
frequency map is an abundance distribution. `:516-599` — `ecologyReport()` explains in plain English why it
prints no evenness number there, and prints the evenness it *does* measure (`Split J'`) in the r/K block. A
spine reads `Split J' = 0.0000`; a perfect 15-node tree reads `1.0000`. They no longer print an identical
number.

**Javadoc warnings: 17 → 0.** All were real markup defects — unescaped `<` and `&` in prose parsed as markup,
one broken `@link` — fixed properly with `{@code}` / `&lt;` / `&amp;`, never suppressed.
`GenomeDrivenTreeController:32`, `IntervalAugmentor:95,150`, `OrderStatisticsOps:55,149`,
`TreeEcology:17,20,96,166-167,277`, `WorkloadMonitor:21`.

**Build scripts: `options.encoding = "UTF-8"` added to all three `build.gradle.kts` files.** javac's default
source encoding is the platform default charset (UTF-8 only from JDK 18 / JEP 400), and this project pins
`options.release = 17` with **no toolchain**, so a JDK 17 host is supported — on windows-1252 it decodes `→`
as `â†'`, and those characters are in **string literals** in `ecologyReport()`, not just comments.
Demonstrated by compiling `TreeEcology.class` under a forced windows-1252 default: byte-identical with the
fix, different without it. Javadoc *output* needed no change (`-docencoding` follows `-encoding`, which both
modules already set) and no redundant options were added.

*Tests:* `TreeEcologyEvennessHonestyProbeTest` (4) — 3 red against pristine source; the fourth is a
deliberate characterization test pinning `shannonEvenness() ≡ 1.0` so the doc cannot silently rot.

---

## Part 2 — ADR-026, the new slice

### ADR-026 · snapshot load failure signaling

Three candidates were weighed. **Picked** load-side signaling: it is the only one whose trigger had actually
fired, and it fired *the same day* — S6-03, S6-04 and the M-2 gate each converted "silently loads wrong data"
into "returns `null`", growing the malformed→`null` population on the very day ADR-025 gave the write side an
answer and left the read side without one. Reusing ADR-025's already-argued design was strictly better than
inventing a second one for the twin problem.

*Rejected:* maintaining height once per write (ADR-023's Held #1) — trigger has not fired, and its own text
says each reconstruction path would need explicit repair against a three-day-old pinned fix. And the
Workbench "import `.eco`" affordance (ADR-020's Held) — ADR-020 held the reverse path explicitly because "the
forward path is the one classrooms need first", and no classroom has asked. That one remains a reasonable
follow-on; it is self-contained in `docs/ecology-lab.html` plus its `.eco` parser mirror.

Probed first: **nine** distinct causes, one `null` — absent, empty file, short header, non-numeric size, no
data line, size mismatch (S6-03), M-2 structural rejection, undecodable key token, and a real `IOException`.
The in-repo consumer drawing the wrong conclusion was `TreeContext.loadSnapshot`, which logged **"not found"**
for all nine.

`TreePersistenceAdapter.java:234` `LoadStatus` (LOADED / ABSENT / MALFORMED / FAILED / UNREPORTED), `:271`
`LoadResult<T>` with two compact-constructor invariants, `:359` `orThrow` escalating FAILED *and* MALFORMED
but not ABSENT, `:91,117` the additive `default` twins, `:128` `ALL_SNAPSHOTS`.
`FilePersistenceAdapter.java:263` `loadFailure` (the `IOException`-vs-format split), `:275` `propagate`, and
five reporting implementations. The published `loadSnapshot` / `loadOrderedSet` / `loadPersistent` /
`loadEnsemble` / `listSnapshots` now delegate and discard — same log lines, same refusals, same returns.
`TreeContext.java:264` reports the real reason.

*Tests:* `SnapshotLoadSignalingTest` (13), all against the real filesystem, with a uid-independent
`IOException` probe (a directory occupying the target path) rather than the read-only-directory probe ADR-025
documents rejecting. Six reversions verified red in isolation.

*Held:* `deleteSnapshot`'s `false` meaning both "nothing to delete" and "delete failed"; `MALFORMED` naming
the gate rather than the bytes; no checksum, so `LOADED` catches truncation and shape-changing tampering but
not a flipped bit inside a valid token — named so `LOADED` is not read as more than it is, exactly as ADR-025
named the missing `fsync`.

---

## Part 3 — the seventh pass

### Bug hunt over the changed surface

Six findings, each reproduced before being accepted. Four were fixed here; two were fixed in parallel by the
wiring and edge-case passes below and are recorded there.

**C · ADR-024's comparability rule held within a window but not across the pool the decision reads —
CONFIRMED end to end, FIXED.** `perMemberChurn` was decided per generation, but the ranked pool at
`PolicyEvolutionController:349-351` is this generation's scores **plus surviving parents' costs from earlier
generations**, so a stream-priced generation and a per-member-priced one got sorted against each other and
the winner fed `policy.shouldMorph`. Same shape in V3: `bandit.meanCost(winner)` averages arm costs recorded
across windows that may have been priced either way. Reachable — a `SAMPLED_SHADOW` body at
`shadowSampleRate(0.02)` takes 1 write per 50, so any generation shorter than ~400 stream ops sits below the
`MIN_METERED_WRITES` floor.

Reproduced: Splay incumbent / RB lab at rate 0.1, `Random(11)` — a 70-op window (7 received writes,
stream-priced, cost 1.3724) then a 3,000-op window (per-member, 0.6897, incumbent 10.4777) → mixed mean
1.0311 → improvement 0.9016 versus 0.9342 consistently priced. At `MorphPolicy(0, 0.9179, 1)` the live run
**holds** where consistent pricing promotes.

Fix: every cost carries both prices and the comparison picks the basis every participant has.
`PolicyBandit` keeps `meanStreamCost` / `meanOwnChurnCost` plus `perMemberBasis()` (`recordCost(arm, cost)`
unchanged, new 3-arg overload); `PolicySearchController:263-289`; `PolicyEvolutionController:333-346,
365-392, 399`. ADR-024 gained an "Amendment, same day" section and two new Held clauses.
*Test:* `SeventhPassClosureTest$PoolWideComparability` (6).

**D · the ADR-024 meters were non-volatile plain `long`s — FIXED.** Written under `writeLock`, read without
it, while every other cross-thread member field is `volatile` or atomic. `EnsembleMember.java:126-162`: the
three meter words are now `volatile`, plus a `meterVersion` seqlock so `rotationsPerWrite()` reads the
numerator and denominator as a *pair* rather than possibly pairing one write's rotations with the previous
write's count. Measured write-path cost: **none detectable** — 400k writes × 3 members, 7 timed runs, median
1588.5 ms with versus 1573.3 ms without (1.0%, inside a 1552–1766 / 1544–1713 spread; ~4 ns on a ~1320 ns
member write). *Test:* `SeventhPassClosureTest$MeterMemoryModel` (2).

**A · `TreeContext.loadSnapshot` silently discarded the sliding-window bound — FIXED.** The third instance of
the family S6-19 and S6-20 closed; the snapshot path was missed. `ctx.setMaxSize(3)`, add 1..10, save, load →
`maxSize 3 → 0`, and the context then grew to 14 keys. `TreeContext.java:337` captures `getMaxSize()` before
adopting the snapshot's `OrderedSet` and re-applies it through the same one path `resyncFromEngine` uses.
**Decision: respect the live bound, do not restore a saved one** — the snapshot header has never recorded a
bound, so every 0.2.0 snapshot would fall back to the live one anyway, and a restoring load could silently
*unbound* a bounded context, which is the direction that loses data. The bound is a property of the
container, not the payload. *Test:* `SeventhPassClosureTest$SnapshotLoadRespectsTheWindow` (4).

**B · the lab page's `parseCounts` was not the mirror of `FieldData.parseLines` it claimed to be — FIXED,
both sides.** The RFC-4180 splitters themselves were an exact mirror (differential-tested over 16,915 inputs,
0 divergences); the surrounding bare-token logic was not, over 398 count-divergences in a 1,865-line corpus.

Two families, resolved differently. **`key=value`: Java was right** — the page emits that shape from its own
"build .eco lines" button, so a student round-tripping got a species literally named `oak=5` with count 1.
The page was fixed. **Bare number column: neither was right** — the page's `sp1` auto-naming fabricates a
species name into the student's exported data (`sp1,4` plus `7` silently merged to `sp1: 11`, and reordering
renamed it), while Java's reading made a pasted count column into N species of abundance 1 with J′ ≡ 1.0000.
Both sides now *report* it, per the house rule. `docs/ecology-lab.html:1206-1345` was rewritten as a
transliteration of the oracle — `addToken`, `jTrim`, `splitAtLastSpace`, Java-`Long` parsing, `raw.trim()`
problem subjects, the oracle's wording — and `FieldData.java` gained the ambiguity report and one shared
`NON_POSITIVE` sentence.

Differential-tested: **25,066 records / 62,498 lines / 17,745 counts / 39,530 problem messages, 0
divergences**, including embedded quotes, trailing separators, lone quote, CRLF, quoted newline, `Long`
boundary and Unicode digits. *Stated residual:* counts above 2^53 agree to double precision, not exactly — JS
has no 64-bit integer; the accept/reject decision agrees exactly. *Tests:* `FieldDataTest` (+3),
`FieldDataJsMirrorTest` (drives the shipped HTML through node).

**Verified clean and not to be redone:** ADR-023 staleness exhaustively refuted (11 strategy configs × 5
workload shapes × 5 seeds × 900 ops, full-tree cached-vs-recomputed after *every* op → 0 stale nodes) and all
reconstruction paths clean (5 strategies × 10 sizes × build/morph/clone/checkpoint/persist round-trips).
S6-15 Hybrid grants clean (12 thresholds × 30 seeds × 1500 mixed ops → 0 violations, 0 refusals; the default
unbounded strategy grants nothing, so non-vacuity holds). Engine correctness: 7 configs × 40 seeds × 500
mixed ops against a `TreeSet` oracle checking return parity, contents, ordering, parent links, cached size
and height, and sentinel integrity after every op → 0 failures. ADR-024 meter accounting exact in all five
ensemble modes. ADR-025/026 all nine `null` causes distinct; every `void`/`null` twin agrees with its
reporting twin. S6-10/11/20/44 interactions: 40 seeds × 900 ops of mixed writes, health checks, back-channel
morphs, promotions and quarantines against a `TreeSet` oracle → 0 failures.

### Wiring audit — `AUDIT-2026-08-17-wiring-seventh-pass.md`

**Verdict: the new surface is completely wired.** Every ADR-023/024/025/026 seam is reachable, implemented,
and consumed by the thing its ADR says consumes it, with every deliberate non-consumer documented at the
point a reader would ask. No stub markers, no empty bodies, no `return null` stubs, no field
written-but-never-read except one honestly-labelled deprecated hook, no override that only calls `super`. All
28 experimental types are reachable; every `.eco` directive reaches an effect. Seven findings, all disposed:

1. **(High)** `tryLoadEnsemble` validated `keySerializer` on only the *structured* branch — a null serializer
   against a `PersistentTreeEngine` snapshot NPE'd inside `readFlatKeys` and came back `MALFORMED`, the
   adapter blaming a good file for the caller's bug, contradicting ADR-026 §5 verbatim. Fixed:
   `FilePersistenceAdapter.java:924`, hoisted above any I/O.
2. **(High)** `TreeContext.saveSnapshot` logged `"Snapshot saved"` unconditionally — announcing success over
   the adapter's own ERROR, eleven lines below where ADR-026 had just migrated `loadSnapshot` onto its twin.
   Fixed: `TreeContext.java:266`, one line per `SaveStatus`, still `void`, still non-throwing.
3. **(High)** `TreeEcology.empiricalZValue()` ≡ 1.0 and `nicheOverlap()` ≡ 0.0 on every BST — theorems of the
   search-tree invariant, confirmed over 40 random trees — still printed to 4 dp **with interpretation
   bands** in the classroom report. The exact defect EC-3 had just removed for evenness. Deprecated with
   honest javadoc; report prose replaces both constants and both bands.
4. **(Med)** `TreeEcology.colonizationEquilibrium` — wall-clock-derived, superseded at EC-2, named as
   superseded in `LogisticGrowth`'s javadoc and nowhere in its own, and documenting a `P` parameter the code
   ignores. Deprecated and corrected.
5. **(Med)** `EnsembleOrderedSet.buildAllFromSorted` had zero callers and zero tests while
   `AUDIT-2026-07-14-capability-coverage.md:70` credited it to a `BulkBuildFeeder` ensemble path that does
   not exist. Probed correct across 5 configurations — a missing test, not a missing wire. Coverage added; a
   dated correction appended to that audit's new `## Corrections` section, original finding text untouched.
6. **(Med)** `PolicySearchController.contains` / `PolicyEvolutionController.contains` fed
   `recordSearch(hash, 0)` under headings claiming to mirror `EnsembleController`, which measures — the
   read-side twin of the literal-0 rotation feed S6-12 removed from these same classes. Now measured.
7. **(Low)** `CacheEvolutionLoop.resident(int)` — a published seam "named by the first external consumer
   (Brine)", zero tests. Coverage added.

*Tests:* `SeventhPassWiringTest` (14), `SeventhPassEcologyHonestyProbeTest` (6).

**Orphan / test-only reachability table** is in the audit doc. Two members had zero reachability and are now
tested; `TreeNode1.createNodeWithAugment` is a genuine orphan — it stamps `augmentedValue` after the
constructor has already augmented, and the value decays on the first `setLeft` (measured: 999 at
construction, 2 after). It is `public` on published 0.2.0, so deleting it would force 0.3.0; deprecated at
`TreeNode1.java:126` naming the working replacement, with a test pinning both the decay and the replacement.

### Edge-case hardening

Systematic sweep over size, key domain, structure shape, ranges and order statistics, windows, lifecycle,
persistence, and the ecology layer. Most axes were already correct and are now **pinned by tests**; eight
were actually wrong and are fixed. Every fix is a *refusal* added at the entry point that owns the argument —
none change a signature.

- **(S1)** `EnsembleOrderedSet.add(null)` quarantined the fleet. One bad argument threw
  `IllegalStateException` (wrong class — every other implementation throws NPE) and marked every non-primary
  member `QUARANTINED`, even though the entry guards mean no member was half-applied. In `READ_REPLICA`
  every subsequent write then threw *"needs a second ACTIVE member to flip to"* — **permanent loss of write
  availability**. Recovery was only via `checkHealth`'s O(n) rebuild of every member; a bare ensemble used
  without a controller never recovered. This is the write-side twin of what S6-14 fixed on the read side, and
  S6-44 had *broadened* its trigger. Fixed: `requireNonNull` on `add` / `remove` / `buildAllFromSorted`.
- **(S2)** `OrderedSet.buildFromSorted` linked a null key in — `buildFromSorted(singletonList(null))` gave
  `size=1, inOrder=[null]`, and the next unrelated `contains(1)` threw NPE far from the cause. The ascending
  check needs a *pair*, so a lone null never reached a comparison. Inherited by `fromSorted` /
  `fromSortedNatural` and by `buildAllFromSorted`, which built the null into *every* member. Same class as
  S6-44, on the bulk path it missed.
- **(S2)** A reentrant `TreeEventListener` deadlocked the mutating thread forever — the listener's `add`
  parks in `StampedLock.acquireWrite` against a stamp it holds itself, and the monitor stays held so every
  other writer blocks behind it. Documented as *"reentry can deadlock"*, but a silent unrecoverable hang is
  the worst way to report a contract violation. Now refused explicitly on all nine mutators.
- **(S3)** `IntervalAugmentor.intervalSearch(All)` with inverted bounds answered with exactly the intervals
  that straddle the inversion — `intervalSearchAll(ctx, 9, 3)` returned `[MIN,MAX]`, because
  `lo <= qhi && qlo <= hi` is satisfied by precisely those. `insertInterval` already refused `lo > hi` and
  `GenericIntervalAugmentor.requireQuery` already refused it on both sides: two implementations of one
  operation, one of them right. **Release-note worthy** — this now throws where it previously returned
  arbitrary results.
- **(S3)** The pre-order save path did not enforce the `KeySerializer` token contract. A serializer emitting
  `1;x` saved fine and died on reload with an `ArrayIndexOutOfBoundsException` reported as MALFORMED — in a
  different process, with no hint that the caller's own serializer was the cause. The flat path already
  refused `';'` at save with a clear message; the pre-order path, which reserves `','` too, checked nothing.
  **Release-note worthy.**
- **(S2, ecology)** A zero carrying capacity wrote `NaN` into `session.json` — and `NaN` is not valid JSON,
  so `docs/ecology-lab.html` could not parse the session at all. `model: competition … K1=0 …` turned *both*
  species' entire series to `NaN`. `ExperimentSpec` domain-validated `markrecapture` / `hardyweinberg` /
  `eulerlotka` at parse time but not these.
- **(S2, ecology)** A non-finite Newick branch length — `tree: t (A:1e400,B);` → `"length": Infinity`, same
  consequence. A literal `NaN` was silently *dropped* instead, since NaN is the class's own "absent length"
  marker.
- **(S4, ecology)** `keys:` printed `⚠ spec: keys:  (For input string: "")` — the one place in the
  student-facing layer leaking a JDK exception message.

*Tests: 81 added* — `EdgeCaseBoundaryTest` (51), `EdgeCasePropertyTest` (6 jqwik properties: whole-int-domain
churn, navigation, ranges at arbitrary bound pairs, three-implementation parity, the window invariant, B+tree
at the fanout floor), `EcologyEdgeCaseTest` (24). All eight fixes reverted in isolation and confirmed red.
The shipped `docs/experiment-out/` bundle and `docs/ecology-experiment-session.json` regenerate
**byte-identical**.

### Non-finite output, closed at the choke point

The edge-case pass fixed two `NaN`/`Infinity`-into-JSON escapes; browser verification found a third still
live, and investigation found it was **three models, not one**. `exponential`, `island` (c + e < 0) and
`predation` (even on entirely positive parameters at 100k steps) could all produce non-finite points, and
`ExperimentLab.appendSeries`'s `%.4f` wrote a literal `Infinity` token — `model: exponential 0.7 1 1200`, a
plausible "bacteria doubling" line, produced a `session.json` that `JSON.parse` rejects outright.

Closed as a model-layer gate: `TheoreticalModels.representable(...)` applied to all six trajectories,
reporting the step it breaks at in plain English; `ExperimentSpec.parseModel` now probes every trajectory
over its **real step count** (the old one-point probe structurally could not see this); `ExperimentLab`
catches a factor-amplified overflow, reports `⚠ exponential: …` and omits the model with no dangling comma;
and `appendSeries` refuses to write a non-finite value at all — the single choke point, unreachable by
construction, throwing rather than encoding a substitute.

Separately, `levinsEquilibrium` / `levinsTrajectory` / `islandEquilibrium` / `islandTrajectory` now require
`c ≥ 0, e ≥ 0`. A negative rate is not a slower process — it reverses it: `e = -1` evaluated `1 − e/c = 3.5`,
which the `[0,1]` clamp turned into a confident `p* = 1.0000`, and in island a negative rate flips decay
toward equilibrium into growth away from it. The lab page received the matching guard.

*Tests:* `ModelRangeAndOutputPathProbeTest` (10).

### Browser verification

All three pages driven in headless Chromium against every shipped payload, 92 hand-built degenerate payloads,
580 discrete control interactions, 4,023 tooltip hovers and 24 resizes across every mode. **Zero console
errors and zero page errors everywhere.** Eight page defects found and fixed:

1. **(High)** Theory Bench K ≤ 0 and competition K₁/K₂ ≤ 0 emitted `M42,NaN…` — invalid SVG, console error,
   curve gone, while the caption still read "effective K=0". The consumer half of the two Java defects above.
2. `+el.value` turned a blank parameter box into **0** silently.
3. A trajectory overflowing to `Infinity` drew the whole curve flat on the baseline under an axis labelled
   `NaN, ∞, ∞, ∞, ∞`.
4. Habitat factors silently clamped — **area 0 became 1**, and the chip then reported "area 1".
5. The growth-fit lambda reimplements `LogisticGrowth.Fit.predict` but dropped its `n₀ ≤ 0 → 0` guard.
6. `barChart` never got the axis floor `lineChart` got in S6-22 — one non-finite value made every gridline
   label print `NaN`.
7. **(High)** A sibling of S6-26: S6-26 wired `fit()` into the resize listener, but in compare mode
   `#singleWrap` is `display:none`, so a resize sized the single-tree canvas from `clientWidth = 0` and
   `setCompare(false)` never refit. Returning to single view showed a **blank tree panel** (0 opaque pixels)
   while Metrics reported 13 nodes / height 4.
8. A session missing `final` threw *after* `enterReplay` had installed the chip bar and cleared the stage,
   and alerted a raw `Cannot read properties of undefined`. Now validated before mutating, per the repo's own
   validate-then-mutate rule.

Two further page defects were found in post-merge re-verification: `parseLong` accepted supplementary-plane
decimal digits that Java refuses (`oak,𝟏𝟐` counted **twelve oaks** on the page, reported as not-an-integer in
Java), and `ecoName` ran `\s+→-` then `=→-` in sequence so a mixed run became **two** hyphens — `"a= b",5`
round-tripped as `a--b` on the page and `a-b` through `FieldData.toEcoLine`.

**Rendering of shipped data is unchanged**, verified by serializing `#main` + `#terrarium` + `#workbench`
(animation attributes stripped) before and after: byte-identical across the embedded session and all three
ecology payloads.

---

## Other changes

- **`TreeContext` gained an injectable persistence adapter** — additive `TreeContext(strategy, adapter)`,
  `setPersistenceAdapter`, `getPersistenceAdapter` (`:101-151`). The `TreePersistenceAdapter` seam was built
  for third-party implementors in ADR-025/026 but could not be used with its main in-repo consumer. Test: a
  recording in-memory adapter must be consulted for save *and* load, and no file may appear.
- **`docs/arena-search-session.json` regenerated** — 46 events (12 TRIED / 11 SCORED / 5 CULLED /
  1 DISQUALIFIED / 1 SELECTED, 2 Morphs) against the shipped 44. S6-08 stopped an empty shadow scoring a free
  0.0 and pinning the bandit, and S6-12 made `rotationsPerWrite` a real number; both are strictly more
  correct, so the shipped sample was demonstrating a search the library no longer performs. Schema, key set
  and every event type's field set are identical, so the visualizer needed no change. `arena-session.json`,
  `viability-map.json` and all three ecology payloads regenerate byte-identical.
- **`csrbt-experimental/build.gradle.kts:52-56`** — `workingDir = rootDir` added to the `arenaSession` /
  `searchArenaSession` / `viabilityMap` tasks, which the three ecology tasks already had.
  `./gradlew viabilityMap` used to fail outright with `NoSuchFileException: docs/viability-map.json`.
- **Running your own spec no longer clobbers the shipped samples.** `ExperimentLab.main` defaulted `out` to
  `docs/ecology-experiment-session.json` and `exportDir` to `docs/experiment-out/`, and the Gradle task only
  wired `-Pspec` — so `./gradlew ecologyExperiment -Pspec=mine.eco`, the exact invocation the lab page prints
  for students, silently overwrote both. Defaults now derive from the spec (`mine.eco` → `mine-session.json`,
  `mine-out/`); the task passes the shipped paths explicitly only when no `-Pspec` is given, so regeneration
  stays byte-exact.
- **`StrategyBattleRunner.tournament` / `formatTournament`** — the ADR-022 battle surface, previously uncalled
  and untested. Coverage added (structure only, never a winner).

## Export-shape changes

1. `docs/arena-search-session.json` regenerated — same schema, different event stream.
2. `session.json`: a model whose trajectory is not representable now produces a reported problem and **no
   model object**, the same shape as S6-16's eulerlotka change. Nothing changes for representable models —
   all shipped bundles regenerate byte-identical.
3. `report.txt` / `report.html` gain a `⚠ <model>: …` line only when a factor-amplified model is dropped.
4. `drift.csv`, `report.txt` and `session.json` tree lengths are as the sixth pass left them — unchanged here.
5. Default output *paths* for `ExperimentLab.main` without explicit arguments; file contents unchanged.

## Release-note items for 0.2.1

- `IntervalAugmentor.intervalSearch(All)` now throws on `qlo > qhi` (previously: arbitrary results).
- The pre-order save path now throws on a `KeySerializer` violating the documented token contract
  (previously: an unreadable file discovered later, in another process).
- `PolicyBandit.meanCost(arm)` now returns the basis-selected mean. Signature unchanged, 0.2.1-safe, but it
  is published API.
- Reentrant mutation from a `TreeEventListener` now throws instead of deadlocking.

## Still open / deliberately deferred

- **Maintaining height once per write instead of twice** — ADR-023 Held #1, with the measurement and an
  explicit trigger.
- **`blackHeight` remains ancestor-inexact** — ADR-023, accepted decision; its dominant source is recolouring,
  not rotation.
- **`shannonEvenness()` still returns 1.0**, now deprecated and no longer reported as a measurement. Its
  removal is a 0.3.0 decision, as is `TreeEcology`'s broader retirement — four of its indices now carry
  `@Deprecated`, so ADR-015's planned retirement is a small job whenever you want it scheduled.
- **`TreeNode1.createNodeWithAugment`** — orphaned, deprecated, deletable only at 0.3.0.
- **`GenomeDrivenTreeController`'s literal-0 rotation feed** — pinned by `ControllerConvergenceTest` G5.
- **Sampling still biases a shadow's key distribution** — ADR-024 Held; rate normalization fixes the unit,
  not the traffic. Probe-reads would close it.
- **`deleteSnapshot`'s ambiguous `false`**, **`MALFORMED` naming the gate not the bytes**, and **no checksum**
  — ADR-026 Held.
- **No `fsync`** — ADR-025 Held. `SAVED` means the filesystem has it, not that it survives a power cut.
- **`loadSnapshot` also drops the `OrderedSet`'s event listener**, by the same wholesale-adoption mechanism
  the window-bound fix addressed. Reported, not fixed — no reproduction was requested.
- **`buildEco` was not brought along with `runTheory`** — it still reads the parameter boxes with `+el.value`,
  so a blank or zero K emits into the `.eco` protocol the line the Theory Bench just refused to draw.
  `ExperimentSpec` reports it at parse time so it is not silent, but the page is internally inconsistent. The
  remedy is a design call.
- **`FieldData.BARE_NUMBER` uses `\p{Nd}` (code-point based) while `Long.parseLong` is char-based**, so the
  oracle answers "is this a number?" two different ways for supplementary-plane digits. Neither output is
  wrong; the page now mirrors the asymmetry rather than resolving it.
- **`TreeEcology` javadoc mojibake** — closed by the UTF-8 encoding pin above.
