# CHANGELOG 2026-08-09 — ADR-018: the amortization frontier (perception meets economics)

The payoff experiment of the ecology arc: the validated early-warning detector pointed
at the live morph seam, racing E3c's economics across block lengths. Suite **721
green** (617 core + 104 experimental, +2 tests), 0 failures; the experiment itself
runs in ~4.5 s, fully deterministic.

## What landed

`AmortizationFrontierTest` — pre-registered, probe-first (the probe surfaced and fixed
two of its own bugs before the experiment counted: a window-count check that saturated
at the retention cap, and an all-hits "uniform" regime whose gap was noise — real
uniform scans include in-range misses).

- **Premise, hard-asserted (E3b discipline):** the best strategy flips between regimes
  on the comparator meter — ascending-built RB wins hot-small-key reads (the rebuild
  shape holds small keys shallow), AVL wins the uniform scan. All seeds.
- **Contestants:** FIXED-AVL, FIXED-RB, and the EWS-morpher — perception entirely from
  the ecology layer (window Bray–Curtis > 0.5 detects, evenness J′ < 0.75 classifies),
  action through `setStrategy` with the whole rebuild + health-gate bill on the meter.

## The verdict (pinned as regressions)

| B | ratio vs best fixed |
|---|---|
| 2k | 2.244 |
| 8k | 1.296 |
| 32k | 1.059 |
| 128k | 1.000 |
| 256k | 0.990 |

1. **Perception closed:** 5/5 shifts detected, correctly classified, one morph each,
   zero storms, at every block length — E3b's "never morphed once" failure is over.
2. **E3c stands at short blocks:** 2.2× worse at 2k even with free perfect detection —
   the rebuild bill, exactly as E3c priced it.
3. **The frontier: B\* ≈ 128k ops** — monotone decline to break-even at ~128k-op
   blocks, ~1% win at 256k. ADR-012 re-arming trigger #1 now has its number: regime
   blocks of order 10⁵ ops. The drift station of `WorkloadTrace` is the shipped
   instrument for spotting such workloads in the wild.

## Honesty notes (in the ADR and the test javadoc)

The RB hot advantage is a property of the ascending-rebuild shape, reproduced
deterministically by `setStrategy` — the claim is the amortization mechanism, not a
strategy ranking. The margin at 256k is ~1%: thin, like every adaptivity win this
project has measured, and stated as such. Scope: one population size, one regime pair,
read-only streams, comparator-seam metric; the portable result is the mechanism and
the arithmetic, not the specific constants.

Also: README ecology section updated with the frontier result; ADR-018 records the
full method and consequences.
