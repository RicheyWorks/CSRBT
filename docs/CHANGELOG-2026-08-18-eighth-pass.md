# CHANGELOG 2026-08-18 — eighth pass

Three parallel tracks after 0.2.1 was staged: the ecology-teaching slice that lost to ADR-026, the
performance item ADR-023 held with a trigger, and the remaining small held clauses from ADR-025/026
and the seventh pass.

**Build:** `./gradlew build -x :csrbt-benchmarks:jmh` → **BUILD SUCCESSFUL**, **1091 tests, 0 failures,
0 skipped, 0 javadoc warnings**. Baseline entering this pass was 1063.

**Nothing here is a breaking API change.** Every addition is additive — a new `default` interface
method, a new constructor overload, a new nested record. 0.2.1 still stands as the pending release.

New documents: `ADR-027`, `ADR-028`, and a same-day amendment to `ADR-026`.

---

## ADR-027 · `.eco` protocol import in the Workbench

ADR-020 held this deliberately — the lab page could *emit* `.eco` protocol lines but not read them
back, on the reasoning that "the forward path is the one classrooms need first". It was the runner-up
when ADR-026 was chosen. The consequence in practice: a student with no JDK could not check a protocol
they had written. That loop is now closed, and `docs/ecology-lab.html` is a complete authoring tool
rather than a one-way exporter.

A pasted protocol, or a `.eco` file dropped anywhere on the page, is parsed with the engine's
semantics, loaded into the controls that can hold it, and everything else is **listed** — never
dropped. Every entry lands in exactly one of three counted lists.

- **Loaded:** `data:` (three count boxes; a dataset labelled `myfield`/`siteA`/`siteB` claims its own
  box so a protocol this page wrote round-trips into the boxes it came from, the rest fill what is
  left in file order), `model: hardyweinberg`, `model: markrecapture`, the six trajectory models,
  `factor:` (all four knobs reset every time — an absent factor *is* the neutral value), `cross:`,
  `tree:`.
- **Read and shown, honestly declared:** `name:` / `keys:` / `seed:` / `window:`, `phase:` (traffic
  against a live CSRBT — there is no tree in a browser), `note:`, `expect:` (parsed and shape-checked,
  which is the real value: a student can now check a hypothesis without a JDK; grading still needs the
  run), `model: eulerlotka`, and second-and-later models / crosses / trees.

Inventing controls for the unsupported directives was rejected: they would be dead ends the transfer
box cannot write back, and `phase:` is structurally unreachable in a page. The boundary is "what a
Workbench control already holds".

**The parser is a strict transliteration of `ExperimentSpec.parse`** — every directive, every bound,
every domain probe the oracle runs before accepting a model (probed over its **real** step count), and
every problem message **verbatim**, including those that originate in `TheoreticalModels`,
`PopulationGenetics`, `MarkRecapture`, `MendelianGenetics` and `PhyloTree` underneath it. Mirroring the
messages forced mirroring `Double.parseDouble` (JS reads `Number("0x10")` as 16, Java refuses it;
`"1f"` is 1.0 in Java and `NaN` in JS), `Double.toString`, `String.split`'s trailing-empty rule *and
its no-match exception*, `Character.isWhitespace`, and the `(long)` / `(int)` casts.

`jsNewick` was also rewritten as a real mirror of `PhyloTree.parse`. Its comment claimed it "mirrors
the Java parser exactly" and it did not — four different message texts, and an untrimmed branch length
quoted back at the student. There is one Newick parser now, not two that disagree.

**Differential evidence** (`ExperimentSpec` compiled standalone; the page's parser lifted out of the
shipped HTML by source range, never a copy; doubles compared as raw 64-bit patterns, problems verbatim):

```
records 27,585   lines 52,641   directives 11,279   problems 40,469   divergences 0
```

Corpus: `sample-experiment.eco` whole and line-by-line, 289 hand-built lines across every directive,
25,000 randomised records, 24 directives × 87 hostile numeric tokens, and prototype-inherited names fed
to every directive. A targeted **67,000-value** probe of the two number formatters: 0 divergences. 128
distinct problem-message families exercised, so the result is non-vacuous.

Two divergence families were found by the test and would not have been found by reading:
`String.split`'s no-match case (which made `expect: richness() > 1` report the wrong problem, and
`model: eulerlotka 1.0:` parse instead of refuse) and `Double.toString`'s single-digit clause (10 of
67,000, all subnormals).

### `buildEco` now refuses what the engine would refuse

The seventh pass left this as a design call. `buildEco` still read its parameter boxes with `+el.value`,
so a blank or zero K emitted `model: logistic 0.15 0 5 60` into the protocol — the literal line
`runTheory` refuses to draw and `ExperimentSpec` reports as a `⚠ spec:` problem. The page contradicted
itself.

**Every candidate line is now handed to `parseEco` before it is written; if the engine would report it,
it is not written.** Clamping K to 1 would answer a question the student did not ask, in a file they
keep. Silently omitting is the third bad option — so the refusal travels *with* the protocol as a `#`
comment (legal `.eco`, survives copy-paste into a file, arrives with the data at the lab partner) and is
also shown under the button. Parameter boxes use the `numField` discipline, so a blank box is reported,
not read as zero. The two directions are now consistent by construction: what the page emits, the page
and the oracle accept.

The same treatment caught three siblings the brief had not named: `model: hardyweinberg 0 0 0`,
`cross: … observed <one count>`, and `markrecapture` with R > min(M, C).

### Two defects found on the way

JavaScript objects inherit names; Java's `LinkedHashMap` and `switch` do not. `parseCounts`'s count
table was a plain `{}`, so a species named `constructor` / `toString` / `valueOf` never entered the
insertion order and its count was added to a *function*. The importer's own arity and band tables had
the same shape. Both closed, and the corpus now feeds those names to every directive.

### Verification

Headless Chromium: **88 checks, 0 failures, 0 console errors, 0 page errors** across boot, all four
payloads, sample-import (pasted and dropped), 17 malformed and degenerate inputs, and the `buildEco`
refusal paths.

**Round-trip:** a chosen bench state → `buildEco` → all boxes scrambled → import → all 16 scalar
controls, the model parameter vector and all seven rendered readings restored identically, and
`buildEco` re-run is **byte-identical**. The importer is a fixpoint of the exporter.

**Rendering of shipped data is unchanged:** `#main` and `#terrarium` byte-identical for the embedded
session and all three ecology payloads; `#workbench` byte-identical for its entire existing 20,044 B
with the 1,086 B import panel appended as a suffix, so the claim could be stated exactly.

---

## ADR-028 · height maintained once per write (closes ADR-023's Held bullet 1)

ADR-023 made `getHeight()` ancestor-exact by having rotations carry a fixed-point climb, and paid
**+21.7%** on Red-Black monotone insert for it (re-measured here; ADR-023 reported +27.2% on a quieter
machine). Its instrument showed why: on a monotone stream the BST link push moves a height change up
26.7 levels per op and the rotation then takes it back off over 22.7 — height was maintained **twice per
write, in opposite directions**, while the tree's real height moves only O(log n) times.

**Landed.** The engine's BST links no longer propagate height, rotations go through the `*Local`
primitives, and each write ends with a single fixed-point climb. `getHeight()` stays ancestor-exact on
every path, and **F-1's reconstruction fix is not touched at all**.

**Height recomputes per operation** (n = 100k, seed 7, instrumented per arm; the ADR-023 column
reproduces that ADR's own instrument to two decimals):

| strategy / shape | ADR-023 | ADR-028 |
|---|---|---|
| RedBlack / sorted | 27.72 + 22.73 = **50.45** | **6.00** |
| RedBlack / random | **14.86** | **3.57** |
| RedBlack / mixed | **16.21** | **3.63** |
| WeightBalanced / sorted | 21.34 + 17.34 = **38.68** | **10.63** |
| AVL, Hybrid / sorted | **31.38** | **15.69** |
| Splay / random | **18.40** | **0.00** |

**Wall clock**, A/B/C interleaved in one JVM behind isolated class loaders, arm order rotated per round,
12 untimed warmups + 51 timed rounds, paired medians, **5 independent JVM runs = 255 paired rounds per
cell**, `-Xms2g -Xmx2g -XX:+UseSerialGC`:

| strategy / shape | new vs ADR-023 | new vs pre-ADR-023 | ADR-023 vs pre-ADR-023 |
|---|---|---|---|
| RedBlack / sorted | **−17.5%** (4/255) | **+1.1%** (157/255) | **+21.7%** (253/255) |
| WeightBalanced / sorted | −5.5% | +9.5% † | +14.8% † |
| RedBlack / random | −3.3% | −0.7% | +2.5% |
| RedBlack / mixed | −3.9% | −3.0% | +1.1% |
| AVL / Splay / Hybrid, all shapes | −2.9% … +0.5% | −3.4% … −0.5% | ‡ |

‡ byte-identical code in both arms — a second same-code control, spanning −3.2%…+0.9%.
† unresolved on this hardware: the pre-ADR-023 arm is bimodal across JVMs on that one cell (38.8–50.5 ms)
and two *identical* arms disagree by up to 5% inside one JVM, so WB/sorted cannot be resolved below
about ±10% here. Flagged rather than quoted as a result.

**Noise control:** two other agents were building throughout (load 0.9–3.3 on 2 cores). Interleaving
means both arms of every ratio see the same interference in the same round; two independent controls put
the floor at ±3% typical. The baseline was reproduced first.

**ADR-023's specific prediction — that RB monotone insert would end up *faster* than before ADR-023 — is
NOT confirmed.** It lands at parity (+1.1%, 157/255). The deterministic table shows why: the link walk's
height leg was fused into a walk already visiting those nodes and was nearly free; the whole +21.7% lived
in the 22.7-level rotation climb, a second pointer chase. ADR-028 records that as an overclaim, and
ADR-023's Held section now carries a back-reference saying so.

**Paths.** Every caller of the propagating setters was enumerated before anything was touched. The
decisive finding: eight of the ten are not the engine's write path, so `setLeft` / `setRight` /
`recomputeAugmentAndPropagate` are unchanged and no file outside the strategies and `TreeNode1` was
edited. Untouched and still exact: snapshot deserialization, the two-pass deep copy, the depth-limited
clone, `TreeNode1.deepCopy`, `reaugment()`, `setAugmentor`, `buildBalancedNode`, and
`MutableTree.rotateLeft/rotateRight`.

Three origins of height change had to be handled, and **two were found red by the build, not by
reading**: a rotation is invisible from below (WB ascending went wrong at n = 38 — fixed by taking the
adopter of the write's highest rotation), and a successor splice is a second origin (RB mixed went wrong
at op 122 — fixed by an explicit second repair from the spliced node).

**Tripwires:** `AmortizationFrontierTest` (ADR-018) reproduces 2.3236 → 1.3161 → 1.0638 → 1.0007 →
0.9902, monotone, 256k crossing intact, identical to ADR-023's to four decimals.
`ReconstructionHeightProbeTest` and `RotationHeightPropagationTest` pass unmodified. An independent
stale-height sweep over every node after each 20k build: **0 stale in all 14 cells** for both the new and
the ADR-023 arms; the pre-ADR-023 arm leaves 21–1021 stale in 5 cells.

*Test:* `OneClimbPerWriteHeightTest` (4) — 5 strategies × 8 shapes × 3 seeds checked after every
operation, a 6000-op run per strategy, reconstruct-then-keep-writing on RB and WB, and the out-of-band
`MutableTree.rotateLeft` seam. Red-before verified by reverting each decision in isolation: pure fixed
point → 3 red; drop the successor repair → 2 red; simulate the F-1 regression → 3 red here plus all 3 of
`ReconstructionHeightProbeTest`.

*Held:* AVL and Hybrid's own unconditional refresh walk is now the largest per-write height cost at
15.69/op; the three origins are enumerated by inspection rather than enforced; the mark is threaded by
hand rather than tracked; WB/sorted is unresolved on this hardware.

---

## ADR-026 amendment · the delete signal, and what durability `SAVED` may claim

**`deleteSnapshot`'s `false` meant both "nothing to delete" and "delete failed"** (ADR-026 Held clause 1).
Closed the way ADR-025 and ADR-026 established: additive `tryDeleteSnapshot` returning a `DeleteResult`
record, with the `boolean` original kept — `deleteSnapshot` is now `tryDeleteSnapshot(name).deleted()`,
which is exactly what the boolean always meant.

Status set is **DELETED / ABSENT / FAILED / UNREPORTED**. No `MALFORMED` — a delete never reads the file,
so it is a state nothing can produce, which is ADR-025's `PARTIAL` test applied again. No `DENIED` — an
`AccessDeniedException` lives inside FAILED, and that split belongs in `detail`. `gone()` = DELETED ∨
ABSENT is the retention sweep's real question, and honours ADR-026's own objection that most callers do
not need the split. `orThrow` escalates FAILED **only** — sharper than `LoadResult`'s, because here ABSENT
*is the goal met* and escalating it would fire on the successful half of `gone()`.

*Correction recorded in the amendment:* `listSnapshots`' I/O ambiguity was ADR-025 Held bullet 2, and
**ADR-026 already closed it** (`tryListSnapshots`, pinned by "listing separates empty from unreadable").
Noted so nobody hunts for it again.

**`fsync` — landed, opt-in.** `new FilePersistenceAdapter(true)` forces the staged file before the commit
rename and the directory after it; the no-arg constructor is unchanged. Measured on the real save path
(ext4/virtio, 200 saves per config, two rounds): 100 keys 0.16–0.27 → 0.53–0.59 ms; 10,000 keys 0.30–0.32
→ 0.83–0.98 ms — about +0.4–0.6 ms, near-constant in payload (two device flushes, not proportional work),
so a 2–3× multiple here and larger on rotating or networked storage. **Not a default**, because silently
repricing every existing caller's write path is the uncompiled behaviour change ADR-025 refused. **Not
omitted either**, because `DIR` and the paths are private, so a caller had no way to fsync around this
class. Verified by `strace`: 0 fsync calls with the flag off, exactly 2 with it on. Implemented by
reopening the closed staging file, so the encode-and-write path is untouched.

**The javadoc was the part that mattered.** `SaveStatus.SAVED` said "reached durable storage",
`SaveResult.saved()` said "the snapshot is durable", and `saveSnapshot` promised "durable storage" — four
published claims for a guarantee only ADR-025's Held list retracted. Corrected to what is true, with the
mode-by-mode meaning stated on the new constructor.

**Checksum — assessed and deferred, with a sharper trigger.** The hole is real but narrow: a flipped bit
inside a token that still parses *and* leaves the keys ascending. Two findings. ADR-026's claim that it
would need a format version bump is **wrong** — the `AUGMENTOR` field is the precedent for extending the
header in both directions. So the deferral now rests on the real obstacle: a checksum *cannot* be opt-in
the way fsync is. Written only by opted-in adapters, `LOADED` would mean "verified" or "unverified"
depending on the file — the exact defect ADR-025/026 exist to remove; written unconditionally, it changes
the bytes of every `.rbt` in a pending release and obsoletes the shipped samples. Trigger sharpened from
"someday" to an event: a snapshot crossing a medium this library did not write it on (network copy, backup
restore, pulled onto another machine), or one observed load that passes both gates and produces a key
nobody wrote.

---

## Other changes

- **`TreeContext.loadSnapshot` dropped the `OrderedSet`'s event listener** — reported at the end of the
  seventh pass, reproduced here: the listener travels with the discarded set and silently never fires
  again. Fixed the way the window bound was (`TreeContext.java:394` capture, `:407` re-apply), with a new
  `OrderedSet.getEventListener()`. Re-attached *after* the window eviction on purpose: a load emits no
  `Insert` for the keys it brings in, so it must emit no `Evict` either.
- **The mirror-image defect, found by auditing the whole adoption rather than patching the one field:**
  `stressEvents` / `recentInsertions` **survive** a wholesale engine replacement, where `selfRepair()` and
  `clear()` both reset them. Reachable — over 5,000 random inserts per strategy, only `HybridStrategy`
  ever drives the red-red counter above 0 (684 inserts non-zero, peak 3); RB, AVL and Splay are flat 0.
  With auto-morph enabled a stale count can trip a morph one insert after a load. Fixed at
  `TreeContext.java:418-419`.
- **`FieldData`'s two definitions of "digit" resolved.** `BARE_NUMBER` used `\p{Nd}` (code-point based)
  while `Long.parseLong` is char-based, so the oracle answered "is this a number?" two ways for
  supplementary-plane digits. Now `Character.digit(char, 10)` everywhere (`FieldData.java:224`); the
  `BARE_NUMBER` pattern is gone. The deciding argument: the old report's premise was false and its advice
  unfollowable — `𝟏𝟐` was called *ambiguous* and told to "write `name,𝟏𝟐` for a count", which then returns
  `count '𝟏𝟐' is not an integer`. Only one reading was ever available, so it is a species name.
  `docs/ecology-lab.html` got the matching one-condition change, and four supplementary-plane cases were
  added to `FieldDataJsMirrorTest`'s corpus — which its BMP-only `١٢` case did not catch.
- **`*.orig` and `*.rej` added to `.gitignore`.** A `FilePersistenceAdapter.java.orig` turned up in
  `src/main/java` during this pass and was flagged as release-affecting, since anything there is swept
  into the published sources jar. It traced back to a `patch(1)` backup created inside the build
  sandbox while merging two agents' edits to that file — **it was never in the repository**, and a
  `find` over the working tree confirms none exists. The ignore rule stands anyway: the failure mode
  is real, and the only thing that stopped it here was that the leftover happened to live outside
  the repo.
- **`csrbt-benchmarks/build.gradle.kts:10`'s stale `version = "0.1.0"` line dropped** rather than rolled:
  the module is never published, so a version is a coordinate nothing consumes and no release step touches
  — it went stale through two releases proving exactly that. Asserting nothing is self-maintaining.

## Export shapes

None changed. Snapshot file bytes are pinned identical across fsync modes; no session JSON, CSV or report
output was touched; all shipped payloads render identically.

## Still open / deliberately deferred

- **Snapshot checksums** — ADR-026 amendment, with the event-shaped trigger above.
- **A custom `Augmentor` is lost across `loadSnapshot`** — *not* the same defect as the listener. The
  header records the augmentor identity, so the augmentor is payload by design, and the format can only
  record `DEFAULT` / `INTERVAL`; for a custom lambda a load cannot tell whether the file's `DEFAULT` means
  "no augmentor" or "one it could not name". Guessing either way is what the house rule forbids. **A
  format decision, not a bug fix — needs a call.**
- **Insert/delete timings reset to 0.0 across a load** — consistent with the two decisions already written
  in that block (`rotationCount` and `frequencyMap` both take the snapshot's).
- **AVL and Hybrid's own unconditional refresh walk** — now the largest per-write height cost (ADR-028 Held).
- **`MendelianGenetics`' genotype message vs. the page's Punnett box** now differ for the same defect. The
  importer uses the engine's wording; the Punnett box keeps its own, which is arguably the better UI text.
  Resolving it means changing a message the engine prints (ADR-027 Held).
- **`FieldDataJsMirrorTest`'s extraction anchors** force a duplicated `jTrim` inside the extracted source
  range. Removing the duplication means re-anchoring that test, which its own comment invites (ADR-027
  Consequences).
- **`shannonEvenness()`**, **`TreeNode1.createNodeWithAugment`**, and the broader `TreeEcology` retirement —
  all deprecated, all 0.3.0 decisions.
- **`GenomeDrivenTreeController`'s literal-0 rotation feed** — pinned by `ControllerConvergenceTest` G5.
- **Sampling still biases a shadow's key distribution** — ADR-024 Held; probe-reads would close it.
