# Ecology module audit — 2026-08-09

**Scope:** the ecology surface of `csrbt-experimental` (`TreeEcology`, `ViabilityMap`, `experimental.cache`)
and its seams into core. Baseline verified first per house rule: full suite green in this sandbox
(608 core tests + experimental, JDK 21 targeting release 17, `./gradlew build`, 0 failures).

**Context:** ADR-012's instrument phase is complete (E1–E3c, E6 done; E4/E5 parked with named
re-arming triggers). `TreeEcology` predates the E-slices and never got the same rigor pass.
This audit is that pass, and it motivates the next layer.

---

## Findings

### EC-1 (High, correctness-of-measurement). Four TreeEcology indices are constants on this data structure.

The tree is a set — `TreeContext.add` has a dedup guard (`OrderedSet.add` returns false on duplicate),
so `inOrderTraversal()` always yields **distinct** values, every "species" has abundance exactly 1, and:

| Index | Claimed meaning | Actual value, always |
|---|---|---|
| `shannonDiversity()` | key-distribution diversity | ≡ ln(S) — its own theoretical max |
| `shannonEvenness()` | evenness of abundance | ≡ 1.0 (n > 1) |
| `empiricalZValue()` | island vs mainland structure | ≡ 1.0 (S=A in both subtrees; NaN when sizes equal) |
| `nicheOverlap()` | left/right niche partitioning | ≡ 0.0 — the BST invariant makes left/right key sets disjoint **by construction** |

The Pianka case is the sharpest: the index doesn't measure niche partitioning, it measures the BST
ordering property, which is asserted elsewhere by the invariant tests. An index that cannot vary
carries no information (its own H' = 0, as it were).

**Root cause:** abundance is taken from *stored keys* instead of an *access/abundance distribution*.
The class Javadoc even names `frequencyMap` as "the species abundance distribution" — but (a) the code
never reads it, and (b) `frequencyMap` is itself ≈ all-1s: it merges +1 only on a *successful* insert
and `remove()` deletes the entry, so it tracks membership, not abundance.

### EC-2 (Medium). `colonizationEquilibrium` is wall-clock-driven — nondeterministic.

It derives immigration/extinction rates from `avgInsertTimeMs()`/`avgDeleteTimeMs()`. House discipline
since V5 is explicit: *wall-clock is weather, deterministic meters decide.* Every other instrument in the
module (ViabilityMap, cache loop) is seeded and byte-reproducible; this one changes answer run to run.

### EC-3 (Medium). `rKScore` inherits EC-1: its evenness term (25% of the weight) is the constant 1.0.

The score still varies through the efficiency and density terms, but a quarter of the weighted sum is a
fixed offset, and the published [−1, +1] scale is effectively compressed.

### EC-4 (Medium). Zero test coverage.

`TreeEcology` is the only substantial class in the module with no tests (`ViabilityMapTest` and
`CacheTransferExperimentTest` cover the rest). Nothing would catch EC-1 — which is presumably why
nothing did.

### EC-5 (Low). `brokenStickDeviation` reads `getAugmentedValue()` as subtree size.

Correct only when the size augment is stamped; silently produces zeros otherwise. Needs a guard or a
fallback count.

### EC-6 (Note). Integer-bound.

`TreeEcology` targets `TreeContext`/`TreeNode1<Integer>` while core went generic (ADR-002). Acceptable
for the experimental module; noted for whenever it graduates.

### Seam inventory (what exists to build on)

- `WorkloadMonitor.recordSearch(keyHash, depthTouched)` / `recordAdd` / `recordRemove` — the ADR-002 §9.2
  seam already carries per-op key identity, but no per-key tally is retained anywhere; `accessSkew` is a
  scalar. **A small deterministic per-key access tally is the one missing piece** that turns EC-1's
  constants into live measurements.
- `TreeHistory` records add/remove per op — enough to reconstruct per-key lifespans (birth op, death op)
  for demography without new instrumentation on the hot path.
- The ensemble exposes per-member trees — natural "communities" for between-community comparison.

---

## Disposition

EC-1 is not fixed by patching formulas — with abundance ≡ 1 there is nothing to compute. The fix and the
next layer are the same object: **found abundance on access counts, not membership.** Once a key's
abundance is how often the workload touches it, the existing indices become real (hot-key workloads →
low evenness; uniform scans → high; skew shifts move H′), and the standard undergrad toolkit lines up
behind it with actual signal to measure. Proposed build order is in the companion design note /
AskUserQuestion; each layer is additive, deterministic, oracle-tested, and lands green per house rule.
