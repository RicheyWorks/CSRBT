# CHANGELOG 2026-06-10 — ADR-011 V4: evolution proper

The machine breeds. (μ+λ) selection over `PolicyGenome`s runs on the live ensemble:
offspring are bred with V2's operators, materialized as shadow members through the health
gate, scored on the sampled stream, selected, and — when a winner clears the gates —
crowned. Deaths are the safety architecture's verdicts. The `TreeEcology` ambition,
landed as an instrument.

## `core.evolution.PolicyEvolutionController<K>` (new)

- **The generation:** `beginGeneration()` breeds onto the **nursery** (the strategy-backed
  non-primary slots; λ = slot count): slot 0 re-materializes the best parent — elitism, so
  the reigning policy is re-scored on the *current* workload and stays promotable under
  non-stationarity — and the rest take fresh offspring (mutation of one parent or
  integer-midpoint blend of two, seeded coin; generation 1 materializes the founders).
  Every birth emits `TreeEvent.Lineage`; every materialization passes the health gate.
  `endGeneration(ops)` makes each genome answer to its own invariant (dead permanently),
  scores survivors with `Fitness` on shared features, pools them with the scored parents,
  keeps the best μ, culls the rest, and considers promotion — the V3 gate math verbatim
  (−cost desirability through `MorphPolicy.shouldMorph`, arm-keyed win streaks). A
  promotion rotates the deposed primary into the nursery: selection pressure all the way up.
- **Permanent death:** gate kills and invariant kills land in a graveyard; breeding walks
  past dead genomes (repeated mutation pressure, not re-rolls — it escapes dead pockets);
  extinction (every founder dead, nothing breedable) fails loudly.
- **Determinism:** one constructor-seeded `Random`; selection has no randomness at all.
  Same seed + same op stream = same lineage, byte for byte (pinned by a test).

## Out-of-box exploration — behind the flag, as the ADR demanded

- `PolicyGenome.weightBalancedUnboxed(Δ, Γ)`: structural bounds only
  (Δ ≤ `DELTA_STRUCTURAL_MAX` = 32, Γ ∈ [1, Δ)); plus `inVerifiedBox()`. This factory
  exists exclusively behind the controller's `allowOutOfBox` flag — flag off, mutation
  reflects at the verified box walls exactly like `perturbed`; flag on, Δ may cross the
  box, and what survives out there is decided by the gate and the strategy's own
  invariant, on the record. The one place in the codebase allowed to construct an
  unverified genome, because it is the place built to kill one safely.

## `TreeEvent.Lineage` + recorder (additive to session format v1)

- `Lineage(generation, child, parentA, parentB, op)` with op ∈ founder / mutation / blend;
  deaths reuse `Trial` (DISQUALIFIED for gate/invariant kills, new **CULLED** phase for
  selection deaths), so a recorded session carries complete family trees: born, tried,
  scored, culled or crowned.

## Tests (`PolicyEvolutionControllerTest`, 6; suite **521, green**)

- Generations evolve with founders-then-offspring ordering, elite re-scoring, μ survivors,
  and oracle-exact contents throughout; identical seeds breed identical lineages; the
  unsound (5,3) founder dies by its own invariant, stays dead through subsequent
  generations, and loses no data on the way down; out-of-box genomes appear **iff** the
  flag is on (founder pinned at the box edge so any +Δ step must cross); promotion deposes
  a splay primary, rotates it into the nursery, and the loop keeps breeding after the
  succession; a recorded session carries Lineage births and CULLED deaths in parseable JSON.

Next per ADR-011: V5 — the acceptance experiment. Workload families (uniform, hot-key
skew, sequential, delete-heavy, regime-switching), fixed seeds, long runs; success =
evolved/selected policy beats the best fixed strategy by ≥10% realized cost on ≥1 family
across ≥3 seeds; the verdict is published either way and ADR-011 flips to Accepted.
