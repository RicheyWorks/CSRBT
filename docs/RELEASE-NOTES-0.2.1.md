# CSRBT 0.2.1 — the pass that made 0.2.0 safe to run

A correctness release. Two adversarial sessions over the 0.2.0 tree (2026-08-17) found
and fixed 34 confirmed audit findings, then cleared the held items behind them with four
ADRs, a wiring audit, an edge-case sweep and a browser-driven verification of all three
HTML pages. The headline is unglamorous and worth stating plainly: **0.2.0 had reachable
paths that lost data, emptied a tree, deadlocked an ensemble, and loaded a truncated
snapshot while reporting success.** All of them are closed here.

Nothing in this release breaks source or binary compatibility with 0.2.0. Everything new
is additive — `default` interface methods, new overloads, new nested records. Six
deprecations were added; nothing was removed.

## Coordinates

```kotlin
dependencies {
    implementation("io.github.richeyworks:csrbt-core:0.2.1")
    implementation("io.github.richeyworks:csrbt-experimental:0.2.1")   // arena, ecology, cache evolution
}
```

Both artifacts ship jar + sources + javadoc with full POMs; `csrbt-benchmarks` (JMH)
stays build-from-source.

## Why upgrade

**A restored checkpoint crashed the next write.** `TreeHistory.restoreFrom` gave the
restored root a `null` parent instead of the NIL sentinel, so
save → mutate → restore → `add` threw `NullPointerException` out of `rotateLeft` — on
Red-Black, AVL **and** Splay. Fixed; the root's parent is the sentinel again.

**`remove()` could empty the tree.** Red-Black's `fixDelete` recolored and rotated the
*shared* NIL sentinel. After a `shallowClone`, the third removal turned the sentinel RED;
on a black chain `10→5→2`, `remove(2)` threw NPE and left `[2,5,10]` as `[]`. The sentinel's
colour and links are now never written, and a 2 000-op churn against a `TreeSet` oracle
pins that the new guard is inert on valid trees.

**Truncated snapshots loaded as smaller, wrong trees.** The persistent flat loader ignored
the size its own header declared: a 200-key snapshot with a truncated data line loaded as
114 keys, logged that as success, and parsed the trailing partial token `"12"` out of
`"123"` as a valid key. All three load paths now refuse on a size mismatch, and the flat
path gained the ordering gate the structured paths already had.

**`loadEnsemble` destroyed the destination before validating the source.** A snapshot
declaring 300 keys wiped the target ensemble, repopulated it with 118, and returned `true`
— contradicting its own javadoc. Validation is now complete before any mutation.

**Concurrent saves of one name could destroy the previous good snapshot.** Two threads
shared a single staging file; 4 of 25 rounds left a committed target the loader refused.
Staging paths are now unique per call and across JVMs.

**A concurrent `close()` deadlocked the ensemble permanently.** `shutdownNow()` orphaned
futures that were then awaited forever — with `writeLock` held, so every subsequent writer
blocked behind it. Reachable through ordinary `parallelFanOut()` whenever K−1 exceeded the
core count. Futures are cancelled, cancellation maps to a failed outcome, and `close()` is
idempotent; reads still work on a closed ensemble, writes throw.

**A morph could silently drop elements.** The rebuild went through an `equals`-keyed map,
so a set ordered by `id` with `equals` on `name` went from size 3 to size 2 on
`setStrategy` — and still returned `true`, because the health gate compared against the
same collapsed list. The rebuild now uses the engine's own in-order, comparator-distinct
walk.

**Clones and snapshots quietly lost state.** `TreeCloner` dropped the generic augment slot
(so a clone of interval data answered `stabQuery` with `[]` where the source returned 2)
and dropped the sliding-window bound (a `maxSize(4)` source cloned to an unbounded set that
grew to 9 keys). Checkpoint restore and, separately, `TreeContext.loadSnapshot` bypassed the
window bound the same way. All four entry points now carry both.

**`PersistentRankedSet` over-reported changes by up to 42 %** under concurrency — and that
return value is exactly what a VERIFIED ensemble votes on. The check-and-mutate is
serialized and the meters are `LongAdder`s.

**One null argument could take the fleet down.** `EnsembleOrderedSet.add(null)` threw the
wrong exception class and marked every non-primary member QUARANTINED; in `READ_REPLICA`
every subsequent write then failed for want of a second ACTIVE member — permanent loss of
write availability, recoverable only through `checkHealth`'s O(n) rebuild. On the read side,
`ensemble.contains(null)` had Red-Black and AVL throw while the B+tree answered `false`, so
the majority quarantined the structurally healthy member. Null handling is now identical
across all three implementations, at every size.

**The control plane could pin itself.** An empty trial shadow scored a free `0.0` and kept
`meanCost = 0.0`, pinning the bandit to that arm for every subsequent round; a promotion
target that had since been retired threw out of `evaluateAndMaybePromote` on *every*
evaluation. Uninformative trials now record no observation at all, and a dead candidate is
a hold rather than a crash.

## Behaviour changes you must know about

These are the changes that can alter what your code sees at runtime. None of them changes a
signature; all of them are unchecked exceptions on input that was previously a caller bug or
an undefined answer.

- **`IntervalAugmentor.intervalSearch` / `intervalSearchAll` now throw
  `IllegalArgumentException` when `qlo > qhi`.** Previously they returned exactly the
  intervals that straddle the inversion — an arbitrary result that looked like an answer,
  because `lo <= qhi && qlo <= hi` is satisfied by precisely those. `insertInterval` and
  `GenericIntervalAugmentor` already refused inverted bounds; this was the one implementation
  of the operation that did not.
- **The pre-order save path now throws when a `KeySerializer` violates the documented token
  contract.** A serializer emitting `1;x` used to save cleanly and die on reload with an
  `ArrayIndexOutOfBoundsException` reported as MALFORMED — in a different process, with no
  hint that the caller's own serializer was the cause. The flat path already refused `';'`
  at save time; the pre-order path, which reserves `','` too, checked nothing.
- **Reentrant mutation from a `TreeEventListener` now throws `IllegalStateException`.**
  It previously deadlocked the mutating thread forever and blocked every other writer behind
  it. The contract always forbade reentry ("reentry can deadlock"); an unrecoverable hang is
  the worst possible way to report a contract violation.
- **`BPlusTreeEngine` null arguments now throw `NullPointerException`** where they previously
  threw `IllegalArgumentException` or returned `false`. This is parity with the other two
  implementations, and it is the fix for the ensemble-quarantine bug above. If you catch
  `IllegalArgumentException` around a B+tree call specifically to handle nulls, adjust it.
- **`OrderedSet` null semantics no longer depend on the set's size.** On an *empty* set,
  `contains(null)` returned `false`, `rank(null)` threw `NoSuchElementException`, and
  `add(null)` **silently inserted null** — where all three threw NPE on a populated set.
  `buildFromSorted(singletonList(null))` had the same hole on the bulk path. Both now throw
  NPE at the entry point. (`countBetween` / `rangeSnapshot` are unchanged: `null` means
  "unbounded" there by contract.)
- **`PolicyBandit.meanCost(arm)` now returns the basis-selected mean.** The signature is
  unchanged and the method stays published API, but the number can differ: costs are now
  recorded with both a stream price and a per-member price, and the comparison picks the
  basis every participant actually has, rather than averaging the two together.
- **`TreeContext.loadSnapshot` now respects the live sliding-window bound** instead of
  discarding it. The decision is deliberate: the bound is a property of the container, not
  the payload, and the snapshot header has never recorded one — so a restoring load could
  only ever silently *unbound* a bounded context, which is the direction that loses data.

## New API (all additive)

**Snapshot save signaling (ADR-025).** `void saveSnapshot` is kept byte-for-byte. Alongside
it, `trySaveSnapshot` returns a `SaveResult` record carrying `SAVED` / `FAILED` /
`UNREPORTED`, with `orThrow()` making the exception option opt-in per call site. It is a
`default` method, so an adapter written against the 0.2.0 seam compiles unchanged and
inherits `UNREPORTED` rather than a fabricated `SAVED`. Previously all four save shapes —
open failure, mid-write I/O error, full disk, commit-rename failure — looked identical to
success.

**Snapshot load signaling (ADR-026).** The twin: `tryLoadSnapshot` and `tryListSnapshots`
return a `LoadResult<T>` with `LOADED` / `ABSENT` / `MALFORMED` / `FAILED` / `UNREPORTED`.
`loadSnapshot` used to answer `null` for **nine** distinct causes — absent, empty file,
short header, non-numeric size, no data line, size mismatch, structural rejection,
undecodable key token and a real `IOException` — of which only the first makes "start fresh"
the right response. `orThrow()` escalates FAILED and MALFORMED but not ABSENT.

**An injectable persistence adapter.** `TreeContext(strategy, adapter)`,
`setPersistenceAdapter` and `getPersistenceAdapter`. The `TreePersistenceAdapter` seam was
built for third-party implementors but could not be used with its main in-repo consumer.

**Per-member rotation metering (ADR-024).** Each ensemble member now meters its own rotations
over the writes that member actually received, and is priced on its own rate —
`EnsembleMember.meteredRotations()` and `rotationsPerWrite()`, with
`PolicyBandit.meanStreamCost` / `meanOwnChurnCost` / `perMemberBasis()` and a three-argument
`recordCost` overload. Previously every member was priced on the *primary's* churn, so a
rotation-thrashing member and a rotation-cheap one were identical by construction — in an
ensemble whose members run different strategies, which is the entire point. Below
`MIN_METERED_WRITES = 8` the rate is `NaN`: no observation rather than a cheap one.

**Rotation-local primitives (ADR-023).** `TreeStrategy.rotateLeftLocal` /
`rotateRightLocal` and `TreeNode1.refreshHeightUpward`, exposed because `rotateLeft` /
`rotateRight` now carry a fixed-point height climb.

## Correctness under the hood

**`getHeight()` is ancestor-exact again (ADR-023).** Root height was wrong after **98.7 %**
of ascending-insert operations on Red-Black and 74.3 % on WeightBalanced, with a maximum
error of 8. Rotations now carry a height climb that stops at the first ancestor whose height
recomputes unchanged. The cost was measured rather than assumed: thirteen of fourteen
strategy × workload cells sit inside the noise floor, and the fourteenth (+27 %, Red-Black
monotone inserts) is a shape for which the library already ships an O(n) rotation-free path.
`blackHeight` stays ancestor-inexact by accepted decision — its dominant source is
recolouring, not rotation.

**Metrics stopped reporting constants as measurements.** `TreeEcology.shannonEvenness()` is
provably identically 1.0 on a duplicate-free BST; `empiricalZValue()` ≡ 1.0 and
`nicheOverlap()` ≡ 0.0 are theorems of the search-tree invariant. All three were printed to
four decimal places with interpretation bands. They are now deprecated with honest javadoc,
their return values unchanged so no caller's arithmetic moves, and the classroom report
prints the evenness it actually measures (`Split J'`) instead. `rKScore`'s lower half was
unreachable for the same reason and now uses subtree split evenness — a maximally
right-skewed tree scored −0.4997 and was labelled "weakly r-selected"; it now scores −0.9997.

**Javadoc warnings: 17 → 0.** All were real markup defects — unescaped `<` and `&` in prose
parsed as markup, one broken `@link` — fixed properly, never suppressed. Separately,
`options.encoding = "UTF-8"` is now pinned in all three build files: the project targets
JDK 17 with no toolchain, and javac's default source encoding is the platform charset before
JEP 400, so a windows-1252 host baked mojibake into string literals.

## The experimental module

**`session.json` could be unparseable JSON.** Three models — `exponential`, `island` with
`c + e < 0`, and `predation` even on entirely positive parameters — could produce non-finite
points, and the writer emitted a literal `Infinity` token. A zero carrying capacity wrote
`NaN`. Both are invalid JSON, so `docs/ecology-lab.html` could not parse the session at all.
Closed at the choke point: trajectories are probed over their real step count, a
non-representable model is reported and omitted rather than written, and the series writer
refuses a non-finite value by construction. `levinsEquilibrium` / `islandEquilibrium` and
their trajectories now require `c ≥ 0, e ≥ 0` — a negative rate does not slow a process, it
reverses it, and the `[0,1]` clamp turned that into a confident `p* = 1.0000`.

**Euler–Lotka had a hardcoded bracket.** `lx={1,1}, mx={0,250}` returned `rExact = 5.0000`
where the true value is ln 250 = 5.5215, printed beside a correct approximation. The bracket
now expands geometrically with a root-containment check, and an unsolvable schedule in a
student's `.eco` file becomes a reported problem rather than a fabricated number.

**Drift export labels were off by the eviction count.** A 5 000-op phase closed 100 windows
of which 36 were evicted, so `drift.csv`'s row `1->2` actually labelled windows 37→38 — a
student charting the export read end-of-run drift as opening drift. Transitions now carry
absolute window numbers, and the report says so in plain English when eviction happened.

**Field data round-trips.** `FieldData.parseLines` could not read the CSV `FieldData.toCsv`
writes: a quoted species name containing a comma came back as a reported problem. Both the
Java reader and the lab page's mirror are now RFC-4180 splitters with matching semantics,
differential-tested over 25 066 records / 62 498 lines / 39 530 problem messages with zero
divergences.

**The lab page.** Session strings went into `innerHTML` unescaped, so a shared `.eco`
protocol could execute script on whoever dropped it in — ~40 call sites now route through an
escaper. Plus: chart axis floors (an all-zero series drew `M42,NaN…` and vanished), a χ²
table covering df 1–30 with an honest "cannot be graded" path, 27 distinct Punnett tints
instead of 3, guarded renderers so a truncated payload renders valid cards instead of a blank
page, and a compare-mode resize fix that had been showing a blank tree panel. Both visualizer
pages got their resize handlers repaired. All three pages were driven in headless Chromium
across every shipped payload, 92 degenerate payloads, 580 control interactions, 4 023 tooltip
hovers and 24 resizes: **zero console errors, zero page errors**, and rendering of shipped
data byte-identical before and after.

**Tooling.** `./gradlew viabilityMap` used to fail outright with `NoSuchFileException` —
three recorder tasks were missing `workingDir = rootDir`. And `./gradlew ecologyExperiment
-Pspec=mine.eco`, the exact invocation the lab page prints for students, silently overwrote
the shipped `docs/ecology-experiment-session.json` and `docs/experiment-out/`; outputs now
derive from the spec name.

## Compatibility notes

- **Session format is unchanged.** `docs/arena-search-session.json` is regenerated — 46
  events against the shipped 44 — because the sixth pass stopped an empty shadow scoring a
  free 0.0 and made `rotationsPerWrite` a real number, so the shipped sample was
  demonstrating a search the library no longer performs. Schema, key set and every event
  type's field set are identical; the visualizer needed no change. `arena-session.json`,
  `viability-map.json` and all three ecology payloads regenerate byte-identical.
- **`drift.csv`** carries absolute window numbers on runs exceeding 64 windows;
  `report.txt` / `report.html` gain one line when windows were evicted, and a `⚠ <model>:`
  line when a model is dropped as non-representable. Nothing changes when neither happened.
- **`session.json`** writes tree branch lengths exactly (`0.5`, `1.0E-7`) rather than
  `%.6f` — same JSON number type, different text. A model whose trajectory is not
  representable now produces a reported problem and no model object.
- **Existing `.rbt` snapshots load unchanged.** The new refusals fire only on files that
  were already malformed.
- **Deprecated, not removed:** `TreeEcology.shannonEvenness()` / `empiricalZValue()` /
  `nicheOverlap()` / `colonizationEquilibrium()`, `TreeNode1.createNodeWithAugment`, and
  `TreeContext.incrementRotations()`. Their removal is a 0.3.0 decision.

## Quality

**1063 tests** (JUnit 5 + jqwik), 0 failures, **0 javadoc warnings**, green on the JDK 17/21
CI matrix — up from 806 at 0.2.0. Every fix in both passes carries a regression test verified
red-before / green-after by reverting the fix in isolation; every bug-hunt finding required a
reproduction with observed-versus-expected values before it was accepted. Staging publication
verified end to end for both artifacts (jar / sources / javadoc / POM + md5/sha1/sha256/sha512).

## Held for later (named triggers)

- **Maintaining height once per write instead of twice** — ADR-023 Held #1, with the
  measurement and an explicit trigger; each reconstruction path would need its own repair.
- **`blackHeight` stays ancestor-inexact** — accepted decision; recolouring, not rotation,
  is its dominant source.
- **No `fsync`** (ADR-025) — `SAVED` means the filesystem has it, not that it survives a
  power cut. **`deleteSnapshot`'s ambiguous `false`**, **`MALFORMED` naming the gate rather
  than the bytes**, and **no checksum** (ADR-026) — `LOADED` catches truncation and
  shape-changing tampering, but not a flipped bit inside a valid token.
- **Sampling still biases a shadow's key distribution** — ADR-024 Held; rate normalization
  fixes the unit, not the traffic.
- **`loadSnapshot` also drops the `OrderedSet`'s event listener**, by the same wholesale
  adoption the window-bound fix addressed. Reported, not fixed.
- **`shannonEvenness()` still returns 1.0**, now deprecated; `TreeEcology`'s broader
  retirement (ADR-015) is a small job whenever it is scheduled — four of its indices already
  carry `@Deprecated`.
- **`GenomeDrivenTreeController`'s literal-0 rotation feed**, pinned by
  `ControllerConvergenceTest` G5.
- **`buildEco` was not brought along with `runTheory`** on the lab page — it still reads
  parameter boxes with `+el.value`, so it can emit the line the Theory Bench just refused to
  draw. Reported at parse time, so not silent; the remedy is a design call.
- Carried from 0.2.0: paged file backing for the B+tree (ADR-008 D2); the
  comparator-vs-equals window seam (D-4); JUnit 6.x (jqwik Platform-6 support); a third
  evolve-under-viability policy space.
