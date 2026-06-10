# ADR-011: The evolution machine — online structural evolution over the ensemble

**Status:** Proposed (V1 scoped for implementation; V2–V5 staged behind it)
**Date:** 2026-06-10
**Deciders:** Richmond
**Builds on:** every load-bearing seam in the codebase, deliberately: the `TreeStrategy`
seam (pluggable rebalancers), `StrategyHealthCheck` + quarantine (broken candidates cannot
corrupt data), the ensemble (shadows = cheap parallel evaluation on the live stream;
`promote` = O(1) selection), realized meters + `WorkloadFeatures` (fitness signal),
`MorphPolicy` (anti-thrash = selection hysteresis), ADR-005 (the verified BB[α] balance
math, ported back to the mutable seam as V1's parameter space), the event seam + recorder +
arena (the microscope). The deprecated `TreeGenome` named this ambition before the
machinery existed; this ADR is the rebirth with a real genome.
**Goal:** stop *choosing among* four hand-written balancing policies and let the system
*search the policy space itself* — online, against the live workload, with the existing
safety architecture as the viability constraint — ending in a falsifiable experiment, not
a demo.

---

## 1. Context

CSRBT today adapts by selecting among four fixed strategies (RB / AVL / Splay / Hybrid)
via an explainable cost model. That is selection over a population of four hand-authored
individuals. But balancing policies are not four points — they are *parameterized
families*:

- **Weight-balanced (BB[α])**: the rebalance condition is governed by (Δ, Γ). ADR-005
  ships Δ=3, Γ=2 because that point is literature-verified (the `containers` 2010 fix),
  but the verified region is a *box*, and the optimal point inside it is
  workload-dependent (rotation churn vs realized depth). The subtree-size augment every
  node already carries is exactly the information a weight-balanced rebalance reads.
- **Splay variants**: splay-with-probability-p, splay-only-above-depth-d — a continuous
  trade between access locality and write/rotation cost. p=1 is the textbook strategy.
- **Hybrid mixes**: the existing Hybrid is one fixed composition; the mix is a weight.

So a *policy genome* is not a metaphor: it is a small vector of real parameters, a
mutation is a bounded perturbation, and fitness is realized cost on the live stream. What
makes this buildable here and nowhere else is the **safety architecture**: a candidate
policy that produces an invalid tree is caught by the health gate at build-aside (the
incumbent survives, untouched), and one that misbehaves mid-write is quarantined by the
ensemble. The worst case of an evolutionary misstep is a discarded candidate — never
corruption. Research toys lack this; production libraries never try.

**The honesty constraint:** this is only special if it ends in a falsifiable claim. The
acceptance experiment (V5) is built into the ADR, and the negative result is a legitimate
finding ("four textbook structures are sufficient, and here is the instrument that shows
it"), not a failure.

---

## 2. Options considered

### Option A: Staged search — bandit over a verified grid first, evolution second (chosen)

V3 runs a UCB-style multi-armed bandit over a *discretized grid* of the parameter box,
evaluating arms as ensemble shadows on the live stream; V4 graduates to (μ+λ)
evolutionary search (mutation + crossover on the continuous vector) only after the bandit
machinery has proven the evaluation pipeline.

**Pros:** the bandit is honest about evaluation noise (its entire job is
explore/exploit under noisy rewards); arms on a verified grid cannot leave the safe
parameter region; convergence is inspectable arm-by-arm (house value: explainability);
the existing `MorphPolicy` hysteresis maps directly onto promotion decisions; if the
bandit alone already beats the fixed four, V4 is gravy.
**Cons:** a grid cannot discover points between its cells — that is exactly what V4 adds.

### Option B: Full genetic algorithm from day one

**Pros:** the romantic version.
**Cons:** evaluation on a live stream is *noisy and non-stationary*; a GA without a
proven fitness pipeline converges on noise artifacts; unverified offspring parameters can
leave the region where the balance condition is sound — solvable, but solving it requires
exactly the staged machinery Option A builds first. Rejected as a starting point,
embraced as V4.

### Option C: Learned policy (RL over rebalance decisions)

**Pros:** maximal search space.
**Cons:** opaque decisions in a codebase whose control plane exists to be *explainable
from a single log line*; training infrastructure (replay buffers, off-policy evaluation)
this project has rejected three times in smaller forms; per-operation inference cost on
the hot path. Rejected — the parameterized-family framing keeps every decision a number
a human can read.

### Option D: Status quo (the null hypothesis)

The four fixed strategies stay. **Not rejected — retained as the baseline.** Option A's
entire output is measured against it; D is what the machine must beat to justify itself.

---

## 3. Decision — the staged build

**V1 — the parameter space (first slice).** `WeightBalancedStrategy(Δ, Γ)` on the mutable
`TreeStrategy` seam: port ADR-005's size-based balance/rotation repair (the math is
already in-tree and verified) to strategy form, reading the existing per-node size
augment. Parameters are constructor arguments with the literature-verified box enforced
(`Δ=3, Γ=2` the documented safe default; the box's provenance documented inline).
`StrategyHealthCheck` gains a **strategy-supplied invariant hook**
(`TreeStrategy.validateInvariant(tree)`, default empty) so a parameterized strategy is
validated against *its own* Δ — the health gate stays exact as the population diversifies.
Oracle + invariant tests at multiple grid points, including the box edges.

**V2 — genome and fitness.** `PolicyGenome`: the parameter vector (family tag + Δ, Γ,
splay-p as the space grows), bounds-aware perturbation (mutation) and blend (crossover),
pure and unit-testable. `Fitness`: a deterministic function of realized meters and
structure — v1 fitness = workload-weighted realized write cost (the meters exist) +
height/depth-profile read estimate (shadows don't serve reads, so read cost is estimated
structurally; probe-reads are the held refinement). Every fitness evaluation is a value
with named inputs — explainable, like the scorer it generalizes.

**V3 — the bandit.** `PolicyBandit` (UCB1 over the discretized box) drives an ensemble in
shadow mode: each arm materializes as a shadow member running its parameterization on the
sampled stream for an evaluation window; rewards are V2 fitness; promotion of a winning
arm goes through the existing `MorphPolicy` gates (cooldown, hysteresis, minimum margin —
anti-thrash is selection pressure discipline). New `TreeEvent.Trial` events feed the
recorder, so the arena replays show arms being tried, scored, and selected. Caller-cadenced
like every controller in this codebase — no background threads.

**V4 — evolution proper.** (μ+λ) selection over `PolicyGenome`s on the population
ensemble: shadows are offspring, quarantine/retire is death, promotion is selection,
the recorder captures lineages. The `TreeEcology` ambition lands here as a real
experiment platform, not theatrics. Exploration outside the verified box is permitted
*only* here, behind a flag, because this is where the safety architecture earns its keep:
an unsound (Δ, Γ) candidate fails the health gate's strategy-supplied invariant and is
discarded — recorded, visible in the arena, harmless.

**V5 — the experiment (the acceptance test).** A benchmark suite of workload families
(uniform, hot-key skew, sequential, delete-heavy, regime-switching), fixed seeds, run
long enough to amortize morph costs. **Success criterion: the evolved/selected policy
beats the best of the four fixed strategies by ≥10% realized cost on at least one
family, sustained across ≥3 seeds.** Published as in-suite printed rows with the same
discipline as every benchmark before it. **The negative result is a documented finding**
— ADR-011 gets flipped to Accepted either way, with the verdict in its changelog; only
an unrun experiment is a failure.

---

## 4. Consequences

**Easier:** the project's claim graduates from "adapts among four structures" to
"searches a policy space, safely, and shows its work"; the ecology/arena layers become
instruments; every prior seam (health gate, shadows, meters, events, policy gates) gains
the consumer it was unknowingly built for.

**Harder:** evaluation noise is now a first-class engineering problem (windows, stride
bias, non-stationarity — the bandit confronts it, V4 inherits it); the strategy family
grows a constructor-parameterized member, so `StrategyId`-keyed machinery (scorer,
bridge) needs a representation for parameterized identities (V3 design detail: arm
identity = family + grid point); write amplification during search is the ensemble's
known cost, paid only while searching.

**Revisit:** probe-reads for direct read-fitness (when structural estimates prove
misleading); splay-p and hybrid-mix dimensions (V2+ as the space grows); RL (only if the
parameterized family provably saturates).

---

## 5. Action items

1. [x] **V1** — `WeightBalancedStrategy(Δ, Γ)` + strategy-supplied invariant hook in
   `StrategyHealthCheck` + grid-point oracle/invariant tests + morph interop (health-gated
   swaps RB ↔ WB(Δ,Γ)). _(Done 2026-06-10 — and the first run produced the machine's
   first finding: (5,3) is unsound and self-disqualifies, now a pinned regression. See
   CHANGELOG-2026-06-10-adr011-v1-weight-balanced.md.)_
2. [x] **V2** — `PolicyGenome` (bounds, perturbation, blend) + `Fitness` (explainable,
   deterministic, unit-tested). _(Done 2026-06-10 — both pure units in `core.evolution`,
   value identity = V3's arm identity; 17 tests, suite 504. See
   CHANGELOG-2026-06-10-adr011-v2-genome-fitness.md.)_
3. [x] **V3** — `PolicyBandit` over ensemble shadows + `TreeEvent.Trial` + arena replay of
   a recorded search session. _(Done 2026-06-10 — plus the predicted parameterized-identity
   seam: `TreeStrategy.samePolicyAs` (WB(3,2)→WB(4,2) was silently refused by the
   class-based no-op guard). (5,3) self-disqualifies live; WB(3,2) beats a splay primary
   through real gates; 11 tests, suite 515. See
   CHANGELOG-2026-06-10-adr011-v3-policy-bandit.md.)_
4. [x] **V4** — (μ+λ) population search; out-of-box exploration behind a flag; lineage
   recording. _(Done 2026-06-10 — `PolicyEvolutionController` (nursery slots as offspring
   bodies, elitism in slot 0, graveyard breeding, deposed-primary rotation),
   `weightBalancedUnboxed` behind the flag, `TreeEvent.Lineage` + CULLED in the recorder;
   6 tests, suite 521. See CHANGELOG-2026-06-10-adr011-v4-evolution.md.)_
5. [ ] **V5** — the experiment: workload-family benchmark, ≥10%/≥1 family/≥3 seeds, verdict
   published either way.

---

## 6. Verification & rollback

Each V is an additive slice shipping green through `ant clean test` per house discipline;
V1 is just a fifth strategy plus a default-empty hook (rollback: delete); V3/V4 run only
inside ensembles built for search (no default-path change anywhere). The safety argument
is not new code — it is the existing health gate and quarantine, now load-bearing for
their original unstated purpose.
