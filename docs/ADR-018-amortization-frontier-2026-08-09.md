# ADR-018: The amortization frontier — perception meets economics

**Status:** Accepted (2026-08-09) — experiment landed and green
(`AmortizationFrontierTest`, 2 tests, ~4.5 s, verdicts pinned as regressions).
**Date:** 2026-08-09
**Deciders:** Richmond
**Builds on:** ADR-012 (E3b: the selector's *perception* failed; E3c: switching cannot
pay at 6k-op blocks — quantum &gt; 3× prize; re-arming trigger #1 held for "blocks long
enough that the quantum amortizes") and the early-warning experiment (lag-0 detection,
zero false positives — perception solved). This ADR closes the loop: with perception
free, **where do the economics turn?**

---

## 1. The question, pre-registered

Race three contestants on identical seeded read streams whose regime alternates in
blocks of B ops: FIXED-AVL, FIXED-RB, and an **EWS-morpher** whose perception is
entirely the ecology layer (window Bray–Curtis &gt; 0.5 detects a shift; window evenness
J′ &lt; 0.75 classifies the new regime) and whose action is the live morph seam
(`setStrategy` — the full rebuild-and-validate bill lands on the comparator meter,
V5's metric). Sweep B ∈ {2k, 8k, 32k, 128k, 256k}, 3 seeds, 6 blocks.

**Premise, hard-asserted first (E3b discipline):** the best strategy must *flip*
between regimes. It does: ascending-built Red-Black holds the smallest keys shallow
and wins the hot-small-key regime (≈9.5 vs 10.4 cmp/op); AVL's uniform depth wins the
uniform scan with in-range misses (≈10.5 vs 11.1). Honesty note: the RB hot advantage
is a property of the ascending-rebuild *shape* (which `setStrategy` reproduces
deterministically), not RB superiority in general — the experiment's claim is the
amortization mechanism, not a strategy ranking.

## 2. The verdict (2026-08-09, all seeds)

| Block length | switcher cmp/op | ratio vs best fixed |
|---|---|---|
| 2k | 23.07 | **2.244** |
| 8k | 13.32 | 1.296 |
| 32k | 10.88 | 1.059 |
| 128k | 10.28 | 1.000 |
| 256k | 10.17 | **0.990** |

Three findings, each pinned as a hard assertion:

1. **Perception is no longer the bottleneck.** 5/5 regime changes detected and
   correctly classified at every block length, exactly one morph per change, zero
   morph storms — E3b's failure mode ("the selector never morphed once") is closed by
   the ecology layer's detector.
2. **E3c stands where it was measured.** At 2k-op blocks the switcher loses by 2.2× —
   short-block switching remains bad economics even with free, perfect detection. The
   bill is the O(n log n) rebuild + health-gate validation, exactly as E3c priced it.
3. **The frontier exists, is monotone, and crosses at B\* ≈ 128k ops.** The ratio
   declines 2.24 → 1.30 → 1.06 → 1.00 → 0.99 and breaks even at ~128k-op blocks
   (~64 windows), with a clear (if modest, ~1%) win at 256k.

## 3. Consequences

**ADR-012 re-arming trigger #1 now has its number.** "A real workload with regime
blocks long enough that the switching quantum amortizes" means, for this population
size and regime pair: **blocks of order 10⁵ ops**. A production workload whose
`WorkloadTrace` drift chart shows regime stretches that long is the signal to revisit
E4; anything shorter, the fixed-strategy conclusion stands. The detector to check is
already shipped (drift station, early-warning method).

**The margin is honest and small.** ~1% at 256k blocks against best fixed — consistent
with the whole arc of ADR-011/012: adaptivity's wins at this scale are thin, and the
machinery's real value is knowing *precisely when* they exist. The prize scales with
the per-regime gap; a workload with a larger flip (e.g. above-range miss storms, where
ascending-built RB degrades badly) would move B\* down — the experiment's harness
measures that directly if such a trace appears.

**Scope:** read-only regimes, one population size, one regime pair, comparator-seam
metric. The numbers are claims about this bench; the *mechanism* (detection → classify
→ morph, billed at the seam, break-even by amortization arithmetic) is the portable
result.

## 4. Verification & rollback

Green with the full suite (721 tests); the experiment runs in ~4.5 s, deterministic
(seeded streams, op-clocked windows, counted comparators — no wall clock anywhere).
Rollback: the test file deletes cleanly; no production code was touched.
