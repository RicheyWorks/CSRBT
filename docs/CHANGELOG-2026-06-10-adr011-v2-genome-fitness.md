# CHANGELOG 2026-06-10 — ADR-011 V2: the real genome and the explainable fitness

The second slice of the evolution machine: the two pure, deterministic units V3's bandit
will consume. No controller wiring yet — by design. Both are values-and-functions only,
unit-testable with hand-built inputs, which is the entire point of staging them ahead of
the search loop.

## `core.evolution.PolicyGenome` (new)

- An immutable, bounds-checked parameter vector: a `Family` tag (the four classics +
  WEIGHT_BALANCED) plus, for the parameterized family, the (Δ, Γ) genes. Where the
  deprecated `TreeGenome` was a self-interpreting trait soup, every gene here is a number
  an executable strategy actually reads — `toStrategy()` is the genotype→phenotype map.
- **The box:** construction enforces Δ ∈ [2, 8], Γ ∈ [1, Δ) — no out-of-bounds genome can
  exist. In-box ≠ sound (V1's (5,3) finding); the box is where the search may *look*, the
  health gate decides what *survives*. Out-of-box exploration stays V4's flagged business.
- **Pure operators:** `perturbed(rng)` is a bounded ±1 single-gene step, clamped by
  reflection (10k chained mutations provably never leave the box); `blended(other, rng)`
  is re-validated integer-midpoint crossover. Both consume the caller's seeded `Random` —
  same seed, same offspring. No static RNG, no clock, no UUID: the `TreeGenome` lesson,
  applied.
- **Value identity** (`equals` = family + genes) is exactly the "arm identity =
  family + grid point" representation ADR-011's consequences section said V3 would need.

## `core.evolution.Fitness` (new)

- The v1 model from the ADR, verbatim: `cost = writeFraction × rotationsPerWrite`
  (realized — the meters exist) `+ readFraction × meanDepth / log₂(n+1)` (structural —
  shadows don't serve reads, so read cost is estimated from the candidate's own shape,
  normalized by the balanced-depth bound). Lower = better, same convention as the scorer.
- Every evaluation is an `Evaluation` record carrying its named inputs and both partial
  costs, rendering to one log line — explainable like the `StrategyScorer` it
  generalizes. Probe-reads remain the ADR's held refinement with a documented trigger.
- `Fitness.meanDepth(tree)` is the one structural measurement (average nodes-on-path,
  same unit as the monitor's realized `meanSearchDepth`): iterative, O(n),
  evaluation-window cadence only — never per-op.

## Tests (`PolicyGenomeTest` 9 + `FitnessTest` 8; suite **504, green**)

- Genome: box enforcement at construction and misuse seams; 10k-mutation box closure with
  bounded steps; purity (same seed → same offspring; parents immutable); classics are
  points (perturbation = identity); blend within parents' span and across families; arm
  identity; genes survive `toStrategy()`.
- Fitness: exact hand-built vector (read=0.6, write=0.4, rot=2, depth=4, n=15 →
  cost=1.4 on a power-of-two bound); determinism; partial costs monotone in the right
  direction; n ≤ 1 degenerates read term to 0; loud validation; the log line contains
  every named input; `meanDepth` against hand-computed shapes plus a 1023-key sequential
  insert under WB(3,2) staying logarithmic.
- One test-side finding worth keeping: `new Random(seed)` for 50 consecutive small seeds
  gives a heavily biased *first* `nextBoolean()` (a known JDK artifact) — the
  cross-family blend test draws 50 times from one seeded stream instead.

Next per ADR-011: V3 — `PolicyBandit` (UCB1 over the discretized box) driving ensemble
shadows, `TreeEvent.Trial`, and an arena replay of a recorded search session.
