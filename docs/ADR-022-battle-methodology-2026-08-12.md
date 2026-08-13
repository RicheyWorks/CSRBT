# ADR-022: StrategyBattleRunner methodology — 2026-08-12

## Status

Accepted, implemented. Trigger: fourth-pass audit 2026-08-12, findings V-C and V-D.
**This change re-scores tournaments**: historical rank orders (and any notes derived
from them) do not carry over.

## Context

Two methodology defects made the tournament's verdicts structurally unsound.

**V-C — Splay was benchmarked with splaying disabled.** Battle searches ran through
`TreeContext.contains` → `OrderedSet.contains`, which is documented "never splays":
ADR-004 R1 reserves engine-level splaying for the write path, because a mutating read
cannot be lock-free. So in `LOCALITY_BURST` and `SEARCH_HEAVY` — the workloads the
runner's own header says "favor Splay" — the Splay competitor could never
self-adjust: the sequential insert phase built an O(n) chain that no search ever
repaired. Compounding it, the `avgSearchDepth` metric was the **root height** (the
worst case, weighted ×3 in the composite score), not any realized access cost. The
audit probe measured Splay at 176–237 ms with "depth" 3000 against 4–13 ms / depth
11–12 for the others — dead last in all seeds, unconditionally.

**V-D — cold-JIT single-pass timing.** No warmup, one timed pass, and the first
competitor in the registry (RedBlack) always paid JIT compilation on the clock:
62.4 ms cold vs 17.2 ms warm (3.6×) for identical work, producing **different rank
orders across identical inputs** — win counts were partly timing noise, against the
header's "same seed = same workload" reproducibility framing.

## Decision

1. **Search ops run the strategy's own search.** Each search does a measuring walk
   first (`OrderedSet.searchDepth` — realized pre-access depth + hit/miss in one
   pass), then `strategy.search(tree, value)` — the engine-level path where
   `SplayStrategy` actually splays the accessed key toward the root, and a plain
   descent for everyone else. Every competitor pays the identical two-walk cost, so
   relative timing stays fair; rotations performed by splaying are metered like any
   rotation (they are real work and real adaptation).
2. **`avgSearchDepth` is the realized mean** — nodes touched per search op, averaged
   over the phase — not the root height. This is the number the composite score's
   depth term was always pretending to be.
3. **Warmup + median-of-k timing.** One untimed full pass per competitor (JIT paid
   off the clock), then `TIMED_PASSES = 3` timed passes on fresh contexts;
   `totalTimeNs` is the median. Non-timing metrics come from the last pass (they are
   identical across passes — same ops, same strategy).

## Consequences

- Splay now competes as a self-adjusting structure: in `LOCALITY_BURST` its realized
  depth is small (hot keys sit near the root) instead of the chain height; probe
  `BattleMethodologyProbeTest` pins depth < 100 where the old proxy read ~3000, and
  pins cross-competitor fairness (identical hits and final sizes).
- **Tournament results change.** Any prior ranking produced by the old runner
  reflects the old methodology and should be regenerated, not compared.
- A battle costs 4× the passes (1 warmup + 3 timed). The runner is a diagnostics
  tool; serious benchmarking remains the JMH module's job.
- Rank order on identical inputs is now stable up to genuine timing variance
  (median-of-3 absorbs single-pass spikes); the depth and rotation terms are exactly
  reproducible.

## Held → decided (same day)

`OrderedSet.contains` still never splays — R1's read-path contract is untouched;
this ADR changes only what the *battle* exercises.

The composite-score weight question was held "until the new numbers warrant it" —
they did, within hours. Validating the re-scored tournament exposed T-1
(`TreeContext.getRotationCount()` read a dead legacy field — the rotation term had
been silently 0 forever), and with the meter fixed, the live numbers showed the
rotation term **double-charges self-adjustment**: Splay's ~178k locality-workload
splaying rotations are already priced into its wall time, and charging them again at
×2.0 pushed Splay back to last place in the very workloads the header documents it
should win. Decision: the rotation term is removed from `compositeScore`
(score = time×0.5 + depth×3.0); rotations remain a reported metric column. With the
live meter and the corrected score, the tournament verdicts finally match the
workload design: Splay wins both locality workloads on realized depth, the strict
balancers win the uniform/sequential/delete ones.
