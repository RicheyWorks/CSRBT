# CHANGELOG 2026-06-10 — ADR-011 V5: the experiment ran. The answer is no.

The acceptance experiment is built, run, and reproducible — and the result is
**negative**: inside the verified box, the searched weight-balanced policy does not beat
the best of the four fixed strategies by ≥10% realized cost on any workload family,
sustained across seeds. Per the ADR's own honesty constraint, that is a finding, not a
failure: *four textbook structures are sufficient, and here is the instrument that
shows it.* **ADR-011 → Accepted, verdict published.**

## The experiment (`EvolutionAcceptanceExperimentTest`, 2 tests; suite **523, green**)

- **Design:** per (family × seed), the V4 evolution controller searches the box on the
  family's live stream (5 generations, founders (3,2)/(4,2), μ=2, λ=3) and *selects* a
  policy; the selected policy then races RB/AVL/Splay/Hybrid as plain single
  `OrderedSet`s on identical fresh streams (8k warmup + 30k measured ops). Five families:
  uniform, hot-key (80% on 100 keys), sequential (log-append, recent reads),
  delete-heavy (churn-down past a prefill), regime-switching (hot-read ↔ uniform-write
  every 4k ops). Seeds 11 / 2026 / 42.
- **Realized cost = comparisons per op, counted at the comparator seam** — deterministic:
  two full runs produced byte-identical cost rows (asserted by diff during development).
  Wall-clock ns/op is printed as context only.
- House discipline: hard assertions are correctness (every selected policy in-box and
  oracle-exact on every family); the verdict is printed rows + one
  `event=adr011_verdict` line, never hard-asserted.

## The verdict (representative run, comparisons/op)

| family | best fixed | evolved (always WB(3,Γ∈{1,2})) | margin |
|---|---|---|---|
| uniform | AVL ≈ 14.8–15.0 | ≈ 15.1–15.3 | −2% |
| hot-key | AVL ≈ 9.8–10.4 | ≈ 9.7–10.3 | −2% … +5% |
| sequential | Splay ≈ 16.2–16.7 | ≈ 22.3–22.5 | −33% … −39% |
| delete-heavy | Splay ≈ 15.9–16.1 | ≈ 19.3–19.4 | −20% |
| regime-switching | AVL ≈ 13.2–13.5 | ≈ 13.2–13.3 | ±1.5% |

`event=adr011_verdict success=false margin=10% sustainedFamilies=[]`

## The findings worth keeping

1. **The fixed four cover the space.** The searched WB policy beats *three* of the four
   fixed strategies almost everywhere (vs RB on uniform: ~15% fewer comparisons) — but on
   every family some hand-written specialist is already within 10%, or far ahead. The
   adaptive claim that matters stays with the *selector* (the scorer/controller choosing
   the right specialist per workload), not with a fifth structure.
2. **The search converged to the literature.** Every (family, seed) selected WB(3, 1) or
   WB(3, 2) — Δ=3, the verified default's neighborhood. The machine independently
   confirmed the containers point is locally optimal in the box. A negative result with
   teeth.
3. **No single scalar crowns a structure.** Wall-clock and comparison counts disagree
   loudly (RB wins uniform on time; AVL wins it on comparisons; Splay wins sequential on
   comparisons while losing on time): comparisons don't price rotations, time doesn't
   reproduce. The experiment switched to the deterministic meter after observing two
   wall-clock runs flip the verdict on shared hardware — both metrics are now printed,
   the deterministic one decides, the gap is documented. (Rotation counters on the
   mutable seam remain held per ADR-009 §3 — V5 is a consumer that would justify them if
   the verdict ever needs the composite metric.)

## Status

ADR-011 **Accepted**. V1–V5 all landed in one day, each slice green through
`ant clean test`: the parameterized strategy that found its first unsound point on its
first run, the genome and fitness, the bandit that turned that unsoundness into a live
mechanism, the population search with lineages in the arena, and the experiment that
ended the story with an honest no.
