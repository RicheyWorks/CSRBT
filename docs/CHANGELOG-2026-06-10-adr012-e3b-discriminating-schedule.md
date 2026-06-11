# CHANGELOG 2026-06-10 — ADR-012 E3b: the pre-registered schedule. The selector never moved.

E3's verdict carried one caveat: its schedule was AVL-dominated, so the adaptive premise
(no single fixed structure covers the run) was false there. E3b closes that gap with a
registration protocol, and the answer is the sharpest of the day. Suite **528, green**.

## The registration (declared before any adaptive contestant ran)

- **Schedule:** alternate ADR-011 V5's published *uniform* family (AVL's diet, per the
  V5 verdict table) with its *sequential* family (Splay's diet) — generators verbatim,
  sequential keyspace offset to 1e6, six 6000-op blocks (u,s,u,s,u,s), seeds 11/2026/42.
  No new tuning: the discriminator is built entirely from already-published fixed costs.
- **Fixed-only probe** (allowed — fixed costs may shape the discriminator, adaptive
  behavior may not): block winners **AVL ×4, SPLAY ×2** (Splay loses its first sequential
  block to warm-up — appends splay too; the read dividend arrives later), best single
  fixed AVL ≈ 17.2–17.3 cmp/op, per-block oracle ≈ 14.9 — an **oracle gap of ~13.5%**,
  so the criterion (≥10% vs best single fixed, all seeds — E3's, unchanged) is reachable
  in principle by a perfect switcher.
- The premise is hard-asserted in the test: ≥2 distinct block winners, every seed.

> **Superseded note (same day):** the SELECT rows below are the *pre-calibration*
> scorer. After the scorer calibration
> (`CHANGELOG-2026-06-10-scorer-calibration.md`) SELECT scores 17.81–17.96 — within
> ~3.5% of hindsight-best AVL. The verdict line is unchanged (tying ≠ the ≥10% win the
> registration demands), but the diagnosis below is what the calibration fixed.

## The verdict (`event=adr012_e3b_verdict success=false sustainedSeeds=0/3`)

| contestant | integrated cmp/op (11 / 2026 / 42) |
|---|---|
| oracle (per-block best fixed) | 14.99 / 14.92 / 14.92 |
| **AVL (best single fixed)** | **17.34 / 17.21 / 17.28** |
| SPLAY | 19.06 / 19.13 / 19.04 |
| SELECT (ADR-002) | 27.05 / 26.59 / 27.22 |
| ELITE | 46.37 / 38.65 / 41.71 |
| POP | 70.67 / 67.51 / 73.38 |

## The finding: the selector sat still through a 36% opportunity

**SELECT's per-block rows are identical to RB's — every block, every seed. It never
morphed.** On a schedule where switching to AVL alone would have paid ~36% (27 → 17),
and where the oracle clears the pre-registered margin, the production decision stack
(`CostModelStrategyScorer` → `MorphPolicy.defaults()`: 4000-op cooldown, 20% margin,
3 consecutive wins) held the starting Red-Black for all 36k ops. The true gap (36%)
exceeds the policy's own 20% margin — so the failure is upstream of the gates: **the
cost model's predicted scores do not track realized comparison costs on these diets**
well enough to ever clear the margin three windows running.

This is the day's most actionable result. E3 established that the *evolution*
architectures can't pay their rebuild bill (confirmed again here: ELITE ~2.3×, POP ~4×
best fixed). E3b establishes that the *selector* — V5's "the adaptive claim stays with
the selector," the last home of the premise — fails not on cost but on **perception**:
it pays almost nothing to switch and still doesn't, because its model is miscalibrated
against the realized meter. The premise itself survives: a switcher that *saw* what the
comparator seam sees would win by ≥13%.

**Named consumer created:** calibrating the scorer against realized meters (e.g.
comparison counts or realized depth from the monitor, rather than the static cost
model) now has a measured, reproducible failure case to fix and a pre-registered
benchmark to win. That is a mechanism slice with a real trigger — staged for a future
session, not smuggled into this one.

## What landed

`DiscriminatingScheduleExperimentTest` (1 test, ~5 s): the registered schedule, eight
contestants, per-block oracle bound printed, registration premise hard-asserted,
adaptive contestants oracle-exact on a 2k-key membership sample, verdict soft. The
registration paragraph was written into the test javadoc before the adaptive contestants
first ran, per protocol.
