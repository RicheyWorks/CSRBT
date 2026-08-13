# CHANGELOG 2026-08-12 — deep sweep: eight probe-verified fixes across the pre-ecology surface

Four parallel adversarial passes over the code the recent audits never touched — the
public API surface, persistence/util, the older experimental package, and the
strategy/control plane — with heavy differential testing against independent oracles
(per-op `TreeSet` parity, brute-force interval scans, a 4.8M-op SLRU model, the full
6×6 morph matrix). Full findings, including five documented-not-fixed design items, in
`docs/AUDIT-2026-08-12-deep-sweep.md`. Every fix probe-first: 10 new tests, all red
against the unfixed code. Suite **782 green** (624 core + 158 experimental), 0 failures.

## Fixed — persistence

- **P-1 (High) — `StringKeySerializer`:** keys containing `\n`/`\r` split the
  line-based format — a set could save and reload as EMPTY, silently. Control
  characters < 0x20 are now percent-encoded.
- **P-2 (High) — `FilePersistenceAdapter`:** the header SIZE was advisory, and a
  truncated pre-order prefix parses cleanly (token exhaustion = NIL), so a partially
  written file loaded as a smaller wrong tree that PASSED the structural gate. A size
  mismatch is now a refusal on both the int and generic paths.
- **P-3 (Medium) — `FilePersistenceAdapter.resolveStrategy`:** WB snapshots fell back
  to Red-Black on load, failed RB validation against WB's all-black shape, and every
  round-trip returned null. WB added to the switch.

## Fixed — health gate & morphing

- **H-1 (High) — `StrategyHealthCheck.isBst`:** compared each node only to its
  immediate children; with `selfRepair` feeding the tree's own `inOrder()` as expected
  keys, a globally-invalid BST was certified healthy and never repaired. Now
  range-bounded (min/max threaded down the recursion).
- **H-2 (Medium) — `HybridStrategy`:** (a) the gate demanded strict AVL balance from
  every Hybrid, branding finite-threshold Hybrids (legitimate |bf| = 2 below the
  threshold) permanently unhealthy — selfRepair looped futile O(n) rebuilds; Hybrid
  now supplies its own tolerance-aware `validateInvariant` and routes through the
  ADR-011 default branch. (b) Hybrid is parameterized but never overrode
  `samePolicyAs`, so `Hybrid(4) → Hybrid(64)` was refused as a no-op; now overridden.

## Fixed — cloning & bulk build

- **C-1 (Medium) — `TreeCloner`:** clones shared the ORIGINAL strategy instance
  ("no references are shared" contract): clone inserts mutated the original Hybrid's
  counters; clone armies shared one strategy. Each clone now gets a fresh instance
  carrying the same policy (Hybrid threshold, WB Δ/Γ preserved).
- **C-3 (Medium) — `OrderedSet.buildFromSorted`:** never reapplied a pre-installed
  custom augmentor (setStrategy/selfRepair do), so interval queries silently returned
  empty forever while `getAugmentor()` claimed the augmentor was installed. Now
  reapplied after the bulk build.

## Fixed — experimental

- **C-4 (High, published API) — `CacheEvolutionLoop`:** a promoted champion stayed in
  `onTrial` until the next generation, so every `lookup()` in the gap (the data plane
  Brine drives continuously) processed the primary TWICE — hit rate floored near 50%,
  probation promotions at half the genome's `promoteAfter`, recency double-bumped.
  The champion now leaves the trial pool at promotion.
- **E-1 (Medium) — `TreeEcology.rKScore`:** returned 2.539 on a perfect 7-node RB tree
  against its documented [-1, +1] range — stale cached heights (only AVL/Hybrid
  maintain them), a floor-instead-of-ceil `hMin`, and unclamped components. Height now
  measured by traversal; `ceil`; both components clamped.

## Hygiene

`listSnapshots` no longer leaks the `Files.list` stream; node tags with control
characters are dropped-with-warning like `';'` tags (they would split the data line).

## Documented, not fixed (design decisions — see the audit)

`NavigableOrderedSet` navigation is non-atomic over the R1 concurrent-read seam
(probe: 399 exceptions / 1,870 contract-violating answers in 3.7M concurrent calls;
fix needs single-lock navigation primitives on `OrderedSet` — new API).
`TreeHistory` undo loses window-evicted keys. Saves are non-atomic and swallow write
failures (defanged by P-2's load-side refusal). The FIFO window tracks keys by
`equals` vs the tree's comparator (ADR-002 seam class). Plus assorted latent traps
written down in the audit (NIL augment value, graveyard re-admission, raw `%.6f`
JSON emitters, ungated initial WB(2,1)).

## Verified clean

All five strategies' rebalance paths and rotations (~460k validated ops, RB delete
storms, Splay zig-zig order, AVL height cache exactness); the 6×6 morph matrix with
no NIL leakage; `OrderStatisticsOps` and both interval augmentors against oracles;
`NavigableOrderedSet` single-threaded `TreeSet` parity; `SegmentedLruCache` (4.8M-op
model); `OrderedSet`'s own R1 read path under stress; `TreeExport`/
`TreeSessionRecorder` JSON validity; scorer/monitor math at the corners.
