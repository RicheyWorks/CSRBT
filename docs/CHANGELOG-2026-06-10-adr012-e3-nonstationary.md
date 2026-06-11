# CHANGELOG 2026-06-10 — ADR-012 E3: the non-stationary experiment. No again — and now we know the price of exploration.

The axis V5 skipped, on the bench: a 48k-op run whose workload shifts regime on a fixed
schedule (hot-read → uni-write → seq-append → churn, twice around), seven contestants on
byte-identical streams — the fixed four as plain sets, plus two **live** evolution
controllers (ELITE: μ=1, sliver founders; POP: μ=2, diverse founders) adapting during the
run, generations caller-cadenced every 1.5k ops, shadows at 0.25 sampling, promotions
through the morph gates, nothing pre-searched. Cost = comparisons/op at the comparator
seam, V5's deterministic meter — and for the adaptive contestants the comparator is the
**ensemble's**, so exploration is on the bill. Suite **527, green**.

## The verdict (printed, `event=adr012_e3_verdict success=false sustainedSeeds=0/3`)

| contestant | integrated cmp/op (seeds 11 / 2026 / 42) |
|---|---|
| **AVL (best fixed)** | **16.19 / 16.26 / 16.12** |
| SPLAY | 18.61 / 18.70 / 18.60 |
| HYBRID | 19.85 / 19.91 / 19.69 |
| RB | 24.70 / 24.60 / 24.26 |
| ELITE (μ=1) | 44.30 / 43.71 / 42.02 |
| POP (μ=2, diverse) | 80.35 / 73.66 / 83.28 |

**Under non-stationarity, with exploration priced, no adaptive scheme comes within 10%
of the best fixed strategy — it isn't close: 2.7× for the converged elite, ~5× for the
diverse population.** ADR-012's E3 thesis ("*some* adaptive scheme beats the best fixed
choice on integrated cost") is answered no for these contestants, published V5-style.

## The mechanism (the finding inside the finding)

The per-block series show *where* the money goes. The adaptive contestants' cost
**grows block over block** (POP: 10.9 → 153 cmp/op) while the fixed four repeat their
per-regime profile. The dominant bill is **candidate materialization**: every
generation's build-aside `setStrategy` is an O(n) rebuild per nursery slot, so
exploration cost scales with *n* while serving cost scales with log *n*. Live evolution
pays a tree-sized toll every 1.5k ops to keep trying things; sampling shadows at 0.25
prices the *write fan-out* but not the rebuilds. This quantifies "the cost of exploration
under a real viability constraint" (ADR-012 §1, third open question) — and it is the
named consumer the held rebuild-amortization ideas have been waiting for.

**Re-adaptation lag** (windowed cost, 1.10× band of each block's tail): ~0 for every
balanced fixed tree — they have no policy to re-adapt; rebalancing is per-op and
instant at a regime boundary. Only SPLAY shows measurable transients (143–357 ops mean,
re-shaping to the hot set). The evolvers register 0 — not because they re-adapt
instantly, but because rebuild spikes dominate their windows throughout. Lag, as a
concept, belongs to *locality-carrying* structures and (in principle) policy switches;
the balanced fixed four simply don't have transients on this schedule.

## What this does to the program

- The E3 verdict sharpens E4's bar considerably: diversity preservation now must not
  only cut re-adaptation lag, it must do so without adding rebuilds — the rebuild toll,
  not selection pressure, is the binding constraint. An E4 mechanism that breeds *more*
  is going the wrong way on this bill.
- Documented gaps, honestly: (1) generation cadence is a free parameter — 1.5k ops was
  chosen, slower cadence amortizes rebuilds linearly; the verdict is for these
  contestants, not all possible schedules. (2) Comparisons still don't price rotations
  (V5's gap, inherited). (3) The fixed four pay zero exploration by construction — that
  asymmetry is the experiment's point, not its flaw.
- The adaptive claim's last defensible home — ADR-002's *selector* over fixed
  specialists (which pays a morph, not per-generation rebuilds) — was not a contestant
  here and remains untested on this axis. That is a legitimate E3 follow-up if the
  question ever needs closing completely.

## What landed

`NonStationaryExperimentTest` (1 test, ~4 s): `RegimeStream` schedule, windowed
comparator sampling, mean re-adaptation lag, per-block cost rows, hard correctness floor
(positive costs, full window series, both adaptive contestants answer a 2k-key
membership sample oracle-exactly at run end), soft verdict.

ADR-012 action item 3 ticked. E4 — if attempted — now has a measured bar to clear.
