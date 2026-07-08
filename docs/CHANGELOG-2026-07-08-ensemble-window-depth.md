# 2026-07-08 — Ensemble window + depth-measuring reads

Closes both follow-ups from `CHANGELOG-2026-07-07-workload-signal-seam.md`. Additive only.

## `EnsembleOrderedSet.searchDepth(K)` — ensemble reads record real depths

The design constraint: depths must never vote. Two members holding the same keys in different
shapes legitimately disagree on depth, so voting on it would make every VERIFIED read escalate.
The seam therefore measures **only where a single authoritative walk serves the read**:

- MIRROR (and shadow modes' primary-served reads): the primary's `OrderedSet.searchDepth` — one
  walk answers containment *and* depth.
- VERIFIED, non-voted strides (`verifyEvery > 1`): the primary's measured walk; the call counts
  toward the verification stride exactly like `contains`.
- VERIFIED voted reads: containment is voted exactly as `contains` would, and the result carries
  the **unmeasured** encoding (`0` present / `~0` absent) — an honest zero, never a fabricated
  depth. Same for READ_REPLICA and engine-tier primaries.

`EnsembleController.contains` now routes through it, so `meanSearchDepth` — the scorer's primary
tree-shape signal, previously always 0 on the ensemble path — carries real numbers wherever they
exist. Encoding matches `OrderedSet.searchDepth` (`depth ≥ 1` / `~depth`).

## `EnsembleOrderedSet.setMaxSize(int)` / `supportsWindow()` / `getMaxSize()` — windowed ensembles

`OrderedSet`'s sliding window, fanned across members. Correctness argument: all writes fan out
under the single writer lock in one order, so every exact member sees the identical insert
sequence, builds the identical FIFO, and evicts the identical keys — eviction is deterministic per
member, therefore uniform across mirrors (asserted member-by-member in the test).

Refusals and caveats, honestly: an ensemble with any engine-tier member (persistent engine,
B+tree) **refuses** the window (`IllegalStateException`; `supportsWindow()` = false) — a
half-windowed ensemble would silently diverge. SAMPLED_SHADOW shadows are already inexact and stay
that way. A member healed from the primary re-enters with an ascending-order FIFO (`OrderedSet`'s
documented safety net), so its evictions can diverge until the next health cadence — windowed
ensembles pair best with periodic `checkHealth`.

Downstream: SuperBeefSort's bounded `StreamingFeeder`/`ExternalMergeSorter` feeds can now target
all-strategy ensembles; their loud windowless-target rejection now fires only for genuinely
windowless ones (e.g. `withSnapshot()` mixes).

Tests: `test/core/EnsembleWindowDepthTest`.
