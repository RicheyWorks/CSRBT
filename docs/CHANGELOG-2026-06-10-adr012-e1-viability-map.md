# CHANGELOG 2026-06-10 — ADR-012 E1: the viability map. The region is a sliver.

The first ecology-turn slice: the health gate's lethality oracle — the strategy's own
`validateInvariant`, the exact hook that killed (5,3) in V1 — swept over the whole (Δ, Γ)
plane. Pure instrument, no new mechanism, suite **525, green**.

## The finding: 2 viable cells out of 46

| | result |
|---|---|
| **viable** | **(3, 2)** — the literature point — and **(4, 2)**. Nothing else. |
| Γ = 1 (whole row) | dies, every Δ from 2 to 32 — too eager to single-rotate |
| Γ ≥ 3 in-box | dies, all of it, most by **op 300** |
| (5, 3) | dies (V1's finding, now a map cell instead of an anecdote) |
| (2, 1) | dies (the `arena-search-session.json` death, same contract) |
| unboxed (Δ ≤ 32, sampled) | all dead by op 500 |

The thesis was "the viable region has nontrivial structure — it is not everything in the
box." The map says it is harsher than that: the region is a **sliver**, two cells wide.
This is the literature's narrowness result for integer-parameter weight-balanced trees
(essentially one safe pair, with irrational-α variants needed for more room) reproduced
empirically by the gate that was built to catch it — and it retroactively explains V5:
the search converged to WB(3,·) every time because *there was almost nowhere else viable
to go*. Mutational robustness made literal: a one-step mutation from (3,2) is lethal in
most directions, and the health gate is why that lethality was always a recorded death,
never a corrupted tree.

## What landed

- **`experimental.ViabilityMap`** — the instrument. Per cell: the identical V1
  discovering-churn stream per seed (55% add / 45% remove over 700 keys, invariant every
  100 ops, 8k ops, seeds 11/2026/42 — same streams across cells, so what dies, dies of
  its parameters). Probes stop at first violation (viability is decided; churning a
  known-unsound tree further only spams WARN) but always oracle-check contents at exit —
  `probe` **throws** on data loss, because that would be a correctness bug, not a map
  entry. Sweep = the box Δ∈[2,8], Γ∈[1,Δ) (28 cells) + unboxed samples
  Δ∈{10,12,16,20,24,32} × Γ∈{1,Δ/2,Δ−1} (18 cells). `main` writes the artifact.
- **`docs/viability-map.json`** — the artifact (`{"type":"ViabilityMap", ...}`, per-cell
  per-seed first-violation ops + the first violation message).
- **Visualizer renders it** — drop the file on `demo/visualizer.html`: the (Δ, Γ) plane
  as a heatmap, green = clean on every seed, red deepening with earlier death, blue
  borders = the search box. Smoke-tested headless: 46 cells drawn, the 2 viable cells
  green, no NaN in any style.
- **`ViabilityMapTest`** (2 tests) — house discipline: correctness hard (oracle-exact
  contents on every probe — the sweep is the assertion — plus pinned landmarks:
  (3,2)/(4,2) clean on all seeds; (5,3) and (2,1) die), the map's shape printed as rows
  with one `event=adr012_e1_viability` line, never hard-asserted beyond the landmarks.
  ~3.6 s.

## Notes for later slices

- The map is *relative to the V1 churn recipe* — deliberately, since that is the recipe
  that defines the gate's empirical standard. E3's regime-shift harness can re-probe
  under other diets if the boundary's workload-dependence becomes a question.
- (4,2) survived 8k ops × 3 seeds; the suite's grid test independently asserts it under
  its own seed. It remains *empirically* sound — only (3,2) carries a proof. The map
  records evidence, not theorems.
- E2 (diversity collapse, measured) now has its backdrop: with 2 viable cells, "the
  population converges" is near-tautological in-box — the interesting E2 number is how
  fast the gate + selection *finds* the sliver from diverse founders.

ADR-012 action item 1 ticked. E2 is next in stage order.
