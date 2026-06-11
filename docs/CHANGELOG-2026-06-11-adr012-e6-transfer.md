# CHANGELOG 2026-06-11 — ADR-012 E6: the transfer experiment — the pattern moves, the loop doesn't

The one staged slice whose premise survived the disposition, executed: point the
evolve-under-viability machinery at a second policy space (cache eviction) and measure
what actually transfers. Suite **533 green** (529 + 4).

## The second space (`experimental.cache`, three files, 552 lines)

- **`CacheGenome`** — two genes shaped like (Δ, Γ): `protectedTenths ∈ [0,10]`,
  `promoteAfter ∈ [1,4]`. The structural box deliberately contains a lethal point:
  `protectedTenths = 10` leaves no probation, so an admitted key is evicted on arrival
  — this space's WB(5,3). The constructor enforces only the walls; lethality inside
  the box is the gate's to discover.
- **`SegmentedLruCache`** — the body: fixed-capacity segmented LRU (insertion-ordered
  probation, access-ordered protected segment, promotion at `promoteAfter` hits,
  demotion on protected overflow). **Viability oracle** = `validateInvariant()`:
  segment disjointness, per-segment capacity, hit-bookkeeping residency, and admission
  liveness. **Fitness** = realized window hit rate — measured at the seam, not
  modelled, the cache analog of comparisons/op.
- **`CacheEvolutionLoop`** — the generation protocol, step for step: founders →
  elitism → bounded mutation walk and midpoint blend past a graveyard →
  materialization through the viability gate → live shadow evaluation on the mirrored
  reference stream → own-invariant death → (μ+λ) selection → gated promotion (O(1)
  pointer swap; the deposed primary rejoins the nursery).

## The verdict: `event=adr012_e6_verdict patternTransferred=true loopReusedVerbatim=false`

The ADR's thesis read "transfers with only a new genome + fitness + viability oracle,
**no change to the loop**." Scored in two parts, registered before the run:

1. **Code transfer: NO**, by inspection. `PolicyEvolutionController` names
   `PolicyGenome` and ensemble member types in its signature, operators, and fitness
   call; it cannot run a second space unchanged. The protocol had to be re-typed
   (~345 lines including docs).
2. **Pattern + seam transfer: YES**, measured. Three seams crossed unchanged —
   `MorphPolicy` (hit rate is already desirability-form, so the promotion gate slots
   in without even the tree's negation), the `TreeEvent` vocabulary
   (`Lineage`/`Trial`/`Diversity` carry strings and numbers, nothing tree-shaped), and
   `TreeEventListener` (the recorder/arena consume the new space's history as-is).
   The protocol receipts are hard-asserted on all three seeds: the lethal founder dies
   at the gate (`Trial DISQUALIFIED`), zero unsafe promotions, 61 recorded births, one
   `Diversity` line per generation, every survivor viable, determinism pinned
   (same seed ⇒ same lineages, throne, and graveyard).

## The performance row (the motif again, in a space the tree never saw)

Drifting workload (85% refs to a 200-key hot set sliding 150 keys every 5k ops, 15%
cold over 50k; capacity 256):

| seed | LRU(0/10) | SLRU(5/10,p4) | SLRU(8/10,p2) | evolved | Δ vs best fixed |
|---|---|---|---|---|---|
| 11 | **0.629** | 0.490 | 0.510 | LRU → 0.629 | +0.000 |
| 2026 | **0.629** | 0.486 | 0.502 | LRU → 0.629 | +0.000 |
| 42 | **0.623** | 0.485 | 0.524 | LRU → 0.623 | +0.000 |

Two findings, both honest. The "textbook" segmented split *loses* to pure LRU under
drift — frequency-earned protection is a liability when the hot set moves (stale keys
squat in the protected segment while the new hot set churns probation) — and evolution
found that: it converged to `SLRU(0/10,p1)`, promoted it, and held. And the recurring
result holds in the second space exactly as it held in the first: **the machine
converges to the best fixed point and ties it (Δ+0.000); it does not beat it.** V5's
"the searched policy converged to the literature default" has a cache-shaped echo.

## ADR bookkeeping

E6 ticked in ADR-012 §6 with this changelog as the pointer. The corrected thesis the
experiment leaves behind: *the contribution is the pattern **and the seams** — the
generation protocol, the viability-gate discipline, and the control/observability
vocabulary transfer; the loop class is a per-space instantiation.* If a third space
ever appears, extracting a generic loop core has a measured case (two instantiations
to unify); until then it is a held item with a named trigger, not a refactor done on
spec.
