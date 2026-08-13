# Deep-sweep bug audit — 2026-08-12 (the pre-ecology surface)

**Scope:** the older, never-adversarially-audited code, swept in four parallel passes:
(1) the public API surface — `OrderedSet`, `NavigableOrderedSet`, `OrderStatisticsOps`,
the interval augmentors; (2) persistence and util — `FilePersistenceAdapter`, the key
serializers, `TreeCloner`, `TreeHistory`, `TreeExport`, `TreeSessionRecorder`; (3) the
older experimental surface — `SegmentedLruCache`, `CacheEvolutionLoop`, `CacheGenome`,
`TreeEcology`, `ViabilityMap`; (4) strategies and control plane — all five strategies,
`TreeContext`, `TreeNode1`, `StrategyHealthCheck`, `RollingWorkloadMonitor`,
`CostModelStrategyScorer`. This complements the same-day post-ADR-020 audit
(`AUDIT-2026-08-12-model-domain.md`).

**Method:** hand-derivation plus heavy differential testing against independent oracles
(`TreeSet`/`TreeMap` parity per op, brute-force interval scans, an independent SLRU
model at 4.8M ops, per-op invariant validation across ~460k strategy ops and the full
6×6 morph matrix). Every fixed defect has a probe test that FAILED against the unfixed
code (10 probes, all red pre-fix, all green post-fix). Suite after: **782 green**
(624 core + 158 experimental, +10 probes), 0 failures. Built and run on JDK 21.

**Result: eight defects fixed (probe-verified), two hygiene items, five documented
findings left as design decisions.** The balancing core is clean: all five strategies'
rebalance paths (including RB delete fixup and Splay zig-zig ordering), rotations,
`TreeContext` morphing (no NIL leakage across engines), `OrderStatisticsOps`, the
interval augmentors' max-endpoint maintenance through rotations/removals/morphs,
`SegmentedLruCache`, `TreeExport`/`TreeSessionRecorder`, `ViabilityMap`, `CacheGenome`,
`RollingWorkloadMonitor`, and `CostModelStrategyScorer` all survived their oracles.

---

## Fixed (probe-verified)

### P-1 (High). A string key containing a newline silently corrupted the snapshot — up to total data loss.

`StringKeySerializer` escaped the inline delimiters (`% , ; # |`) but not line
terminators, while the `.rbt` format is line-based (`readLine`). A key containing
`\n`/`\r` split the data line: a set whose only key was `"\nhello"` saved and then
loaded back as a **non-null empty set**; mixed sets loaded `null` via a swallowed
parse exception. This broke the class's own promise ("any non-empty string
round-trips"). *Fix:* all control characters < 0x20 are now percent-encoded (`%0A`,
`%0D`, …); the decoder already handled arbitrary `%XX`. Probe: `newlineKeyRoundTrips`.

### P-2 (High). A truncated snapshot silently loaded as a smaller, wrong tree.

`deserializePreOrder` reads token exhaustion as NIL children, so any pre-order
*prefix* parses cleanly — and the header SIZE was compared but explicitly ignored
("using parsed"). Truncating a 7-key snapshot at each byte offset produced several
offsets that loaded wrong trees (e.g. `[1,2,3,4,6]`) which then *passed* the M-2
structural gate — the exact partial-write failure that gate exists to stop. *Fix:*
a header/parsed size mismatch is now a refusal (`null` + error log) on both the int
and generic paths. The header field is the tripwire; it is no longer advisory.
Probe: `truncatedSnapshotRefused` (exhaustive over every truncation offset).

### P-3 (Medium). WeightBalanced snapshots could never be loaded.

`resolveStrategy` mapped unknown names to Red-Black. WB colors every node BLACK, so
the RB fallback applied red-black validation to the WB shape, the health gate failed,
and **every** WB save→load round-trip returned `null`. *Fix:* `WeightBalancedStrategy`
added to the switch (its own `validateInvariant` then passes). Probe:
`weightBalancedRoundTrips`.

### H-1 (High). The health gate's BST check was local-only — and selfRepair fed it a tautology.

`StrategyHealthCheck.isBst` compared each node only to its immediate children, so a
key violating an *ancestor's* range passed clause 3. `TreeContext.selfRepair` passes
the tree's own `inOrder()` as the expected keys, making clause 1 vacuous — so a
globally-invalid BST was certified "healthy", self-repair declined to repair it, and
the corruption persisted (with `contains()` misses for the displaced key). This
validator is the self-healing system's only eye. *Fix:* min/max bounds are threaded
down the recursion; every node must lie strictly inside its ancestors' window.
Probe: `ancestorRangeViolationDetected` (plants a key of 0 inside the right subtree,
color-preserving, expected = the tree's own inOrder — the selfRepair configuration).

### H-2 (Medium). Finite-threshold Hybrids were permanently "unhealthy" — and re-parameterizing morphs were silently refused.

Two related seams. The health gate demanded strict AVL balance (|bf| ≤ 1) from every
`HybridStrategy`, but Hybrid's documented invariant is depth-relaxed (tolerance 2
below `depthThreshold`) — so a finite-threshold Hybrid with legitimate |bf| = 2 nodes
failed validation forever: every `selfRepair()` paid a futile O(n) rebuild and
reported FAILURE on a healthy tree. And Hybrid never overrode `samePolicyAs` despite
being parameterized — `setStrategy(Hybrid(64))` on a `Hybrid(4)` incumbent returned
`false` as a "same-policy no-op", the exact trap `TreeStrategy.samePolicyAs`'s javadoc
warns about (WB overrode it; Hybrid didn't). *Fix:* Hybrid now overrides
`validateInvariant` (tolerance-aware, heights recomputed not cached) and
`samePolicyAs` (threshold compared); the health gate routes Hybrid through the
ADR-011 default branch like WB. Probe: `hybridReparameterizationIsARealMorph`.

### C-1 (Medium). Clones shared the original's strategy instance.

`TreeCloner.snapshot()` built every clone around the ORIGINAL strategy object,
violating its "no references are shared" contract: 100 inserts into a clone pushed
the original Hybrid's `insertCount` from 50 to 150 — corrupting the counters that
feed Hybrid's relaxation metrics, and cross-contaminating `deployCloneArmy` (N clones,
one shared strategy) and `strategyParallelClones` benchmarks. *Fix:*
`freshStrategyLike` gives each clone a new strategy instance carrying the same policy
(Hybrid's threshold and WB's Δ/Γ preserved; reflective no-arg fallback; sharing only
as a last resort, with a warning). Probe: `cloneDoesNotShareStrategyState`.

### C-3 (Medium). `buildFromSorted` silently discarded a pre-installed custom augmentor.

`buildBalanced` creates every node with the default subtree-size augmentor, and
`buildFromSorted` never called `reapplyAugmentor()` — unlike `setStrategy` and
`selfRepair`, which both do. `getAugmentor()` still reported the custom augmentor
installed (defeating `GenericIntervalAugmentor.requireInstalled`'s fail-loud guard),
but no node maintained max-hi: interval queries pruned on garbage and returned empty
forever, and the tree never healed (the identity guard skipped re-installation).
*Fix:* `buildFromSorted` reapplies a non-default augmentor after the bulk build.
Probe: `buildFromSortedKeepsCustomAugmentor`.

### C-4 (High, published API). A promoted cache champion stayed in its own trial pool.

`CacheEvolutionLoop.endGeneration` swapped the winning shadow into `primary` but left
the same object in `onTrial` (cleared only at the next `beginGeneration`). In the gap
— and `lookup()` is the public data plane the external consumer (Brine) drives
continuously — every lookup processed the primary twice: once as primary, once as its
own shadow. A fresh-key miss was recorded as miss+hit (the published `primaryHitRate`
floored near 50%), probation hits double-counted (keys promoted after *half* the
genome's `promoteAfter` — the champion no longer executed its own policy), and
recency double-bumped; the distortion persisted past the next generation. *Fix:*
`onTrial.remove(body)` at promotion. Probe: `promotedPrimaryLeavesTrialPool` (drives
a real promotion, then asserts pool membership and hit-rate honesty).

### E-1 (Medium). `rKScore` returned values far outside its documented [-1, +1] range.

Three compounding causes in `TreeEcology`: it read the node's *cached* height, which
only AVL/Hybrid maintain (a perfect 7-node RB tree reported h=2, true 3); `hMin` used
`floor(log2(n+1))`, correct only for perfect sizes, charging optimally-balanced trees
imbalance; and neither `efficiency` nor `density` was clamped, so both exceeded 1.
Observed: rKScore = **2.539** for the perfect 7-node RB tree — and `rKLabel()` read
"strongly K-selected" for everything. *Fix:* height measured by an iterative
traversal, `ceil` for `hMin`, both components clamped into [0, 1]. Probe:
`TreeEcologyRkScoreProbeTest` (perfect and non-perfect sizes).

## Hygiene (fixed, no probe)

- `FilePersistenceAdapter.listSnapshots` leaked the `Files.list` directory stream —
  now try-with-resources.
- Node tags containing control characters would split the data line exactly like P-1 —
  the existing `';'` drop-with-warning guard now covers control characters too.

---

## Documented, not fixed (design decisions, flagged for their own ADR moment)

### D-1 (High under concurrency). `NavigableOrderedSet` navigation is non-atomic over the R1 concurrent-read seam.

Every navigation method (`floor`/`ceiling`/`lower`/`higher`, `Range.size()`) composes
2–4 independently lock-guarded reads on the base set (`countAtMost` → `contains` →
`select`). `OrderedSet` advertises single-writer + torn-read-free readers (ADR-004
R1), but a write landing between the adapter's epochs makes read-only navigation
throw (`select(0)` out of bounds) or violate its contract (`floor(k) > k`) — probe
measured 399 exceptions / 1,870 wrong answers in 3.7M concurrent calls, against keys
the writer never touched. Single-threaded use is unaffected, which is why the whole
suite is green. *The fix is an API decision:* add single-lock navigation primitives
to `OrderedSet` (each composition under one read acquisition) and delegate the
adapter to them — new public surface, so it deserves its own change, not a drive-by.

### D-2 (Medium). `TreeHistory` undo permanently loses window-evicted keys.

With a sliding window active (`setMaxSize`), `add` can evict the oldest key, but only
`ADD(v)` is recorded: capacity 3, contents `[1,2,3]`, `add(4)` → `[2,3,4]`, `undo()` →
`[2,3]` — key 1 is unrecoverable, and undo/redo cycles compound the loss, against the
class's "undo restores the tree's contents" contract. Fix requires recording the
eviction in the command (or refusing history under a window) — a semantic choice.

### D-3 (Medium). Saves are non-atomic and swallow write failures.

`saveSnapshot` writes directly to the final path and catches/logs `IOException` as
`void` — an encoding failure at writer close (e.g. an unpaired surrogate in a key)
leaves a truncated file on disk with no signal to the caller. P-2's fix means that
file is now *refused* on load rather than silently loaded wrong, which removes the
sting; the full fix (temp file + atomic rename + a throwing/boolean save) changes the
adapter's public contract.

### D-4 (Low). `OrderedSet`'s FIFO window tracks keys by `equals`, the tree by comparator.

With a comparator inconsistent with equals (e.g. case-insensitive), `add("a")`,
`remove("A")`, `add("a")` leaves `"a"` holding its ORIGINAL window slot, so windowed
eviction can evict a just-reinserted key as "oldest". Same seam class as the B-4
`SnapshotLineage` caveat (ADR-002 discipline): no live defect with current key types;
canonicalize `liveOrder` membership through the comparator when a custom-comparator
key type arrives.

### D-5 (Low, latent). Assorted booby traps, written down so they stay disarmed.

`TreeNode1`'s NIL sentinel carries `augmentedValue == 1` from birth (every current
reader guards with `isNil()` first); `CacheEvolutionLoop`'s (μ+λ) pool refill and
elite slot don't consult the graveyard (unreachable today — deaths only occur at
materialization, before scoring); `TreeEcology.brokenStickDeviation` reads
`getAugmentedValue()` where `getSize()` is the augmentor-independent intent;
`EcologyFieldDay`/`WorkloadTrace` JSON emitters format some doubles with raw `%.6f`
bypassing the finite-only `num()` guard (no reachable non-finite input today);
`WeightBalancedStrategy(2,1)` is constructible as an initial strategy without any
gate (documented as a self-disqualifying candidate arm, but nothing checks an
*initial* strategy the way morphs are checked).

---

## Verified clean (differential-tested, worth not re-deriving)

- **All five strategies + rotations:** ~460k ops with per-op `TreeSet` parity and
  independent invariant checks (global BST, parent links, cycles, cached size/augment/
  height vs recomputed, RB black-height/red-red, AVL |bf| ≤ 1, WB Δ-balance); RB
  delete fixup exercised by delete storms; Splay zig-zig order verified
  Sleator–Tarjan; AVL cached heights exactly match recomputed. The historic
  NIL-vs-null bug is genuinely fixed (explicit `xParent` threading).
- **Morphing:** the full 6×6 strategy matrix mid-stream — content parity, order
  statistics, tag/window resync, and no NIL-sentinel leakage across engines.
- **`OrderStatisticsOps`:** select/rank/countInRange/rangeQuery/successor/predecessor/
  median differential-clean over 30 seeds × 5 strategies, including after
  `buildFromSorted`.
- **Interval augmentors:** the classic max-endpoint-after-rotation bug is absent —
  randomized insert/restamp/remove vs a brute-force oracle across RB/AVL/Splay,
  interleaved with morphs and selfRepairs: zero failures.
- **`NavigableOrderedSet` single-threaded:** exact `TreeSet` parity across all
  boundary classes, view/sub-view/descending combinations, and exception parity.
- **`SegmentedLruCache`:** 4.8M ops against an independent model across capacities ×
  protectedTenths × promoteAfter: promotion at exactly `promoteAfter`, probation-first
  eviction in insertion order, protected-LRU demotion, zero size drift.
- **`OrderedSet` R1 concurrency (the set itself):** 3-thread stress on RB and Splay —
  no torn reads, no unsorted snapshots, no reader exceptions (the concurrency defect
  is confined to the adapter's composition, D-1).
- **`TreeExport`/`TreeSessionRecorder`:** JSON escaping correct (validated by parsing);
  `CostModelStrategyScorer`'s documented crossovers reproduce exactly;
  `RollingWorkloadMonitor` feature math verified at the corners; `ViabilityMap` and
  `CacheGenome` boxes/reflection correct.
