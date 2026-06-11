# CHANGELOG 2026-06-10 — ADR-012 E2: the collapse, measured. The gate did it, not selection.

Diversity is now a first-class output: `TreeEvent.Diversity`, emitted once per
`endGeneration`, recorded, replayable, read back into **nothing** (mechanisms are E4's).
Suite **526, green**.

## The finding: K_collapse = 1, K_find ≈ 6–7 — and the attribution flips

The ADR's E2 thesis said *(μ+λ) under a stationary workload collapses diversity to ~1
effective genome within K generations — quantify K*. Measured, from four deliberately
unsound founders at the corners of the box ((2,1), (6,1), (5,4), (8,7)), 12 generations
× 3 seeds, stationary mixed workload:

| seed | G_collapse (1 lineage, spread ≤ 1) | G_sliver (first survivor in {(3,2),(4,2)}) | final parents |
|---|---|---|---|
| 11 | **1** | 6 | (3,2), (3,1) |
| 2026 | **1** | 6 | (3,1), (3,2) |
| 42 | **1** | 7 | (3,1), (3,2) |

Three of four founders die by their own invariant in generation 1, every seed. The
population is **one lineage from the first generation onward** — selection never had any
diversity to squander. **The attribution in the thesis was wrong, and the instrument
caught it: the viability filter collapses diversity, not (μ+λ).** Selection's role is the
slow part — the ±1 mutation walk from the surviving corner down to the sliver takes 6–7
generations (watch the survivors column: Δ literally walks 6→5→4→3 while Γ finds 2),
after which every seed sits at (3,2) plus one mutation neighbor. The literature point,
found from outside the sliver, again.

Two E1 cross-checks worth pinning in prose: (6,1) — dead by op 800 under E1's
delete-churn diet — survives all 12 generations here under a milder mixed diet, so
**viability is diet-relative** (E1's changelog said so; E2 demonstrates it); and the
final populations *are* E1's sliver plus its mutation halo, two instruments agreeing
through different ends of the microscope.

For E3/E4 this sharpens the question: re-adaptation after a regime shift must come from
a population that is *already* one lineage wide — so if diversity is to help, E4 has to
actively preserve what the gate kills. That is now a measured constraint, not a guess.

## What landed

- **`TreeEvent.Diversity`** — generation, survivors, distinct founder lineages, mean
  pairwise L1 spread over same-family parameterized survivor pairs (NaN → null when no
  pair), deaths split disqualified/culled. Ancestry: founders root themselves, offspring
  follow parentA, a rediscovered genome value keeps its first root.
- **`PolicyEvolutionController`** — tracks founder roots at breeding (one
  `roots.putIfAbsent` per birth), computes the two metrics over survivors at selection
  close, emits the event, and appends `lineages=`/`spread=` to the existing
  `generation_eval` log line (still exactly one line).
- **`TreeSessionRecorder`** — serializes Diversity decision points (additive, v1 schema).
- **Visualizer** — ◆ chips and full narration for Diversity frames; render smoke-tested.
- **`DiversityCollapseTest`** — hard: one event per generation, fields consistent with
  the `GenerationResult`, recorder carries the type; soft: per-generation rows and one
  `event=adr012_e2_collapse` line per seed. ~3.6 s.

ADR-012 action item 2 ticked. E3 — the non-stationary harness, the axis V5 skipped —
is next, and it now starts from a measured baseline: one lineage, spread ≤ 1.
