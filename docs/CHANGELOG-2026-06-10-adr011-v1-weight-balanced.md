# CHANGELOG 2026-06-10 — ADR-011 V1: the parameter space opens (and immediately bites)

The evolution machine's first slice: a genuinely *parameterized* strategy on the seam, the
health-gate hook that validates parameterized candidates against their own parameters —
and, on the suite's very first run, the machine's first empirical finding.

## `core.strategy.WeightBalancedStrategy<K>(Δ, Γ)` (new)

- ADR-005's size-based BB[α] balance — verified at (3, 2) since it landed in the
  persistent engine — ported to the mutable `TreeStrategy` seam: CLRS-shape BST
  insert/delete (transplant identical to AVL's), with a one-rotation-per-level repair walk
  reading the per-node subtree `size` the structural setters already maintain. The
  strategy adds zero bookkeeping of its own; rotations stay O(1) local recomputes.
- (Δ, Γ) are constructor arguments — the genome dimension V2 will search. Structural
  bounds enforced (Δ ≥ 2, 1 ≤ Γ < Δ); (3, 2) is the documented literature-verified
  default; every other point is a *candidate arm*, empirical until proven.

## The hook (`TreeStrategy.validateInvariant` + `StrategyHealthCheck`)

- New default method on the seam: a strategy may supply its own structural invariant
  (default: silent — classic strategies keep the gate's built-in checks, behavior
  unchanged). The gate's `default` branch now calls it, so a parameterized candidate is
  validated against *its own* Δ at morph time. This is ADR-011's viability constraint:
  unsound parameters self-disqualify at the gate instead of being silently wrong.

## The finding: (5, 3) is unsound — discovered by the suite's first run

The grid test assumed (5, 3) was a sound arm. It is not: at op 500 of seeded delete churn,
the one-rotation-per-level repair fails to restore Δ-balance (a node with child sizes 2/0
survives the walk) and the strategy's own invariant hook catches it. **The
self-disqualification mechanism demonstrated itself before the bandit exists.** The
discovery is now a pinned regression test (`unsoundArmSelfDisqualifies`, on the
discovering seed) with two assertions worth reading: the violation *must* appear (if it
ever stops appearing, the repair changed and the sound region needs re-mapping), and even
the unsound arm **never loses data** — contents stay oracle-exact; only balance degrades.
That last line is the whole safety thesis of ADR-011 in one test.

## Tests (`WeightBalancedStrategyTest`, 7 tests; suite 487, green)

- Oracle parity + own-invariant checks every 250 ops under seeded churn at (3, 2) and
  (4, 2); sorted/reverse/organ-pipe inputs stay logarithmic; parameter bounds enforced.
- The (5, 3) self-disqualification regression above.
- Morph interop: the health gate accepts a healthy WB candidate *through the hook*
  (RB → WB(3,2) → Splay round trip, contents and order statistics exact); classic
  strategies' default hook stays silent.

Next per ADR-011: V2 (`PolicyGenome` + explainable `Fitness`).
