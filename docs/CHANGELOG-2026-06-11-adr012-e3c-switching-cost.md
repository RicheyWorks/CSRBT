# CHANGELOG 2026-06-11 — ADR-012 E3c: the price of switching, and the oracle gap exposed as fiction

The held perception item (`CHANGELOG-2026-06-10-scorer-calibration.md`: a recency-aware
locality feature, "only if the oracle gap ever needs claiming") demanded a prior
question, asked first per house discipline — instruments before mechanisms: **is the
gap claimable by *any* architecture once the switcher pays its real switching bill?**
E3b's oracle switches strategies for free; nothing real can. Suite **529, green**.

## The instrument (`SwitchingCostExperimentTest`, E3c)

Schedule, seeds, meter, fixed-probe machinery: E3b's verbatim. Two **clairvoyant**
contestants, both handed the per-block winners table outright — an upper bound on any
detector, so the verdict can only be too generous to perception:

- **CV-MORPH** — one `OrderedSet`; at each block boundary it morphs to the coming
  block's winner via the real health-gated `setStrategy` (O(n) build-aside, every
  comparison counted at the seam).
- **CV-PROMOTE** — a MIRROR ensemble with one exact member per distinct winner; O(1)
  promote at each boundary, paying the standing K× write fan-out instead of rebuilds.

Criterion unchanged from E3b: claimable iff a clairvoyant beats best fixed by ≥10%
integrated cmp/op on all three seeds. Correctness hard (oracle-exact membership probes,
positive costs, full window series, ≥2 distinct block winners, CV-MORPH actually
switched); verdict printed, never asserted.

## The verdict: `event=adr012_e3c_verdict claimable=false (0/3)` — by ~50%, every seed

| seed | best fixed (AVL) | free oracle | CV-MORPH (3 morphs) | CV-PROMOTE | improvement |
|---|---|---|---|---|---|
| 11 | 17.34 | 14.99 | 26.61 | 26.04 | **−50.2%** |
| 2026 | 17.21 | 14.92 | 26.29 | 25.82 | **−50.1%** |
| 42 | 17.28 | 14.92 | 26.38 | 25.91 | **−49.9%** |

The free-switching oracle dangles ~2.4 cmp/op of prize; the *cheapest real way to
switch* costs ~8.6 cmp/op over the run. CV-MORPH's blocks tell the story plainly: it
rides AVL's exact rows until the first boundary, then every regime edge bills an O(n)
rebuild (the SPLAY→AVL edge alone adds ~30 cmp/op to its block) — and the freshly
rebuilt splay starts cold besides. CV-PROMOTE never rebuilds and still loses: the
second member's standing write fan-out (~8.6 cmp/op) exceeds the entire prize more
than threefold.

## What this retires, and what it re-prices

**The recency-aware locality feature is retired with receipts.** Both contestants have
*perfect* perception — the winners table itself — and lose by half. No detector
improvement can rescue an architecture whose switching bill exceeds the prize; the
residual ~13% of the calibration changelog was never reachable.

**The calibrated selector's hold is re-judged: correct economics, not failed
perception.** Staying on AVL through the sequential blocks — the behavior E3b's
post-calibration rows showed and the calibration changelog held as a perception
residue — is what a cost-aware optimum actually does at this block length. The
selector ties hindsight-best AVL within ~3.5% *because* holding is right, not despite
it.

**E3b's "oracle gap ~13.5%" gets a corrected reading.** The premise (no fixed strategy
wins every block) survives — block winners are still AVL×4/SPLAY×2. But "reachable in
principle by a perfect switcher" now carries its measured asterisk: reachable only by
a switcher that pays nothing to switch, which is not an architecture. At 6k-op blocks
against 20k+ keys, regime granularity sits below the smallest real switching quantum
this codebase owns (O(n) rebuild or K× standing fan-out), and the adaptive claim's
honest ceiling on discriminating schedules is exactly what the calibrated selector
already delivers: **match the best fixed choice without hindsight; don't pay to chase
blocks.**

The axis that *would* change the answer is named, not built: longer blocks (the
rebuild amortizes), or a switching mechanism cheaper than both quanta — neither has a
trigger today.
