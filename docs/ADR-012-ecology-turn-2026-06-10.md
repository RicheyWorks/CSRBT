# ADR-012: The ecology turn — from policy optimizer to observable adaptive system

**Status:** Proposed (staged E1–E6; E1–E2 scoped for implementation, E3+ staged behind them)
**Date:** 2026-06-10
**Deciders:** Richmond
**Builds on:** ADR-011 in full (the evolution machine: parameterized strategies, genome,
fitness, bandit, (μ+λ) population search, health gate as viability filter, recorder +
arena as the microscope). This ADR does not replace ADR-011; it reinterprets what the
machine is *for* in light of ADR-011's V5 verdict.
**Goal:** keep the falsifiable-optimization discipline, and add a second, equally rigorous
goal — study the *dynamics* of a safe evolutionary system under selection — by pointing
the existing machinery at the one axis V5 never measured: **adaptation under a changing
environment.**

---

## 1. Context — what V5 actually settled, and what it left open

ADR-011 V5 asked: *does a searched weight-balanced policy beat the four fixed strategies
by ≥10% on a workload family, sustained across seeds?* The answer was **no**, deterministic
and reproducible: every (family, seed) converged to WB(3, ·) — the literature point — and
no family cleared the margin. The fixed four cover the steady-state space.

But read the V5 method precisely: it **searched once per family, then raced on a fresh,
stationary stream.** Two consequences follow.

1. **V5 measured steady-state cost, not adaptability.** The whole premise of an adaptive
   structure — that it tracks a *changing* workload better than any fixed choice — was
   never on the bench. A stationary workload is exactly the case where a fixed specialist
   should win; we confirmed it does.
2. **V5 demonstrated the optimization/diversity collapse first-hand.** Pure fitness
   pressure drove every population to one point. That is not a bug to fix; it is *the
   classic result* — selection without a diversity mechanism canalizes. We have it on the
   record, reproducibly.

So the optimization thesis is closed (honestly, negatively). The interesting questions are
the ones a *terrarium* asks, and they are still open and still falsifiable:

- Under a **non-stationary** workload, does any adaptive scheme beat the best *fixed*
  choice — and does a *diverse* population re-adapt faster than a converged elite?
- What is the **shape of the viable region**? V1 found (5,3) is in-bounds but unsound; the
  health gate + strategy invariant give us a lethality oracle over the whole box. Mapping
  it is a study of mutational robustness / canalization, for free.
- What is the **cost of exploration** under a real viability constraint, and how does a
  population trade robustness against evolvability?

These are general principles of *adaptive informational systems under selection with a
hard viability filter*. The honest scope (see §4): this is a microscope for those
principles, not a claim about biological life. The mapping (low-dimensional policy genome,
narrow environment, performance-only fitness) is too lossy for biological discovery. It is
not too lossy for genuine artificial-life and complex-systems questions, and we are
unusually well-placed to ask them because we already built the two things such projects
usually lack: a **hard safety boundary** (so we can run evolution live, not just offline)
and **full observability** (recorder + arena, so we can see what happened, not just the
winner).

---

## 2. The reframe (the load-bearing decision)

Treat the system as having **two parallel outputs**, both first-class, both instrumented:

- **Performance artifact** — the current best viable policy + reproducible evidence on a
  workload (the ADR-011 track; V5 is its first, negative, entry).
- **Evolutionary artifact** — the population's *history*: lineages, extinctions, the
  viability-rejection spectrum, diversity over time, and the population's *response to
  environmental change*.

The health gate, shadows, and recorder already serve both. The gate makes the performance
numbers trustworthy (nothing unsafe was promoted) **and** makes the evolutionary story
trustworthy to watch (every death is a recorded gate/invariant/selection verdict).

The single design rule that keeps both honest: **at every slice, ask whether it makes the
system more measurably alive — diversity, lineages, response to change — not just whether
it tunes a number.** A slice whose only output is "which parameter won" fails this test.

---

## 3. Options considered

### Option A: Declare ADR-011 done and stop (the null option)
The roadmap's last frontier closed with a clean negative result. Defensible — but it
leaves the most interesting axis (non-stationary adaptation) untested and the machinery
(population, lineages, viability oracle) unexploited. **Rejected as premature**: V5's "no"
is an answer to the *narrow* question, not the program.

### Option B: Chase a positive optimization result by widening the genome immediately
Add splay-p, hybrid-mix dimensions and re-run V5 hoping a richer space beats the fixed
four on steady-state cost. **Rejected as the first move**: it repeats V5's axis (steady
state), where the fixed four already win, just in higher dimensions. Worth doing only
*after* the non-stationary harness and diversity machinery exist (E5), where a richer space
can actually express speciation.

### Option C: The ecology turn — instrument dynamics first, mechanisms second (chosen)
Build the observational instruments (viability map, diversity metrics) and the
non-stationary harness *before* adding any new evolutionary mechanism, so that when we do
add diversity-preservation or new genome dimensions we can *measure* whether they help.
Falsifiable theses at every stage; negative results published, as in V5.

---

## 4. Decision — the staged build (E-slices)

Each is one additive slice, green through `ant clean test`, with a named falsifiable
hook and an artifact. Instruments before mechanisms.

**E1 — the viability map (instrument, no new mechanism).** Sweep the box (and, behind the
V4 flag, beyond it): for each (Δ, Γ), run seeded churn and record whether the health gate
+ strategy invariant reject it, and at what op the first violation appears. Output: a
rejection-spectrum artifact (JSON the arena can render as a heatmap of the parameter
plane). *Thesis:* the viable region has nontrivial structure — it is not "everything in
the box" (V1's (5,3) is the first counterexample); map the boundary. This is mutational
robustness made literal, and it costs only instrumentation.

**E2 — diversity as a first-class output.** Add population-diversity metrics to the
recorder (genotypic spread of the live parents, distinct-lineage count, extinction events
per generation). *Thesis (confirmatory, sharp):* (μ+λ) under a *stationary* workload
collapses diversity to ~1 effective genome within K generations — quantify K, the V5
collapse measured instead of merely observed. No mechanism yet; just see it clearly.

**E3 — the non-stationary harness (the axis V5 skipped).** A long run whose workload
*shifts regime* (read-heavy ↔ write-heavy ↔ hot-key ↔ churn) on a schedule, against three
contestants on identical streams: (a) the best *fixed* strategy, (b) elite-only evolution
(E2's converged population), (c) the full population. Measure **re-adaptation lag** (ops to
recover steady-state cost after a shift) and integrated cost over the whole run. *Thesis
(the real one):* under non-stationarity, *some* adaptive scheme beats the best fixed choice
on integrated cost — the claim V5 never tested. Publish the verdict either way, V5-style.

**E4 — diversity-preserving selection (first new mechanism).** Add a lightweight
niching/fitness-sharing or novelty term, plus a small *elite archive* alongside the diverse
population (the dual-track structure). *Thesis:* preserved diversity reduces E3's
re-adaptation lag without raising steady-state cost beyond a documented bound. This is
where the "both goals at once" claim is put on the bench: if diversity helps adaptability
*and* steady-state cost stays within tolerance, both outputs win together; if not, the
trade-off is quantified and published.

**E5 — widen the genome (speciation room).** Add splay-p and hybrid-mix dimensions
(ADR-011 §"Revisit"), so the policy space is rich enough for distinct stable parameter
clusters. *Thesis:* under a *heterogeneous or cyclic* environment, distinct viable
"species" (separated parameter clusters) emerge and persist, rather than one global
optimum. Only worth building after E3–E4 show the harness and diversity machinery work —
otherwise it is Option B and repeats V5.

**E6 — generalize the seam (the long arrow, optional).** Point the same
evolve-under-viability loop at a second policy space — cache eviction is the natural first
target (a clean genome, a clear viability check, realized hit-rate fitness). *Thesis:* the
machinery (genome → strategy, health gate, shadow eval, selection, recorder) transfers with
only a new genome + fitness + viability oracle, no change to the loop. If it transfers, the
contribution is the *pattern*, not the tree.

---

## 5. Consequences

**Easier / unlocked:** the project graduates from "a tree that tunes α" (which V5 showed is
not worth it on steady state) to "a safe, observable adaptive system you can run live and
study" — with the optimization track preserved as the rigor anchor and the ecology track as
the longevity and the actual open questions. The arena becomes a scientific instrument
(viability map, diversity-over-time, lineage trees, regime-shift response), which also
makes it the *demo* — far more compelling than a parameter log.

**Harder / honest costs:** non-stationary experiments are longer and noisier than V5's
single races; diversity metrics need a defensible definition; E4's diversity mechanism can
hurt steady-state cost and must be measured, not assumed. Evaluation noise — already V3's
first-class problem — grows under non-stationarity. None of this is new in kind; it is the
V5 discipline applied to a harder axis.

**Explicitly out of scope (the honesty boundary):** no claims about biological life. The
genome is low-dimensional, the environment narrow, fitness performance-only. What this can
legitimately surface is *general principles of adaptive informational systems* —
robustness/evolvability trade-offs, viability-filter structure, the cost of exploration,
diversity under environmental change. In the "life is data" framing those are real; in the
"this explains gene regulation" framing they are not, and the ADR will not pretend
otherwise.

**Revisit:** the composite cost metric (comparisons + w·rotations) from the V5 changelog
becomes relevant again at E3/E5 — re-adaptation cost should price rotations, and rotation
counters on the mutable seam (ADR-009 §3, held) finally have a consumer if E3's verdict
turns on it.

---

## 6. Action items

1. [x] **E1** — viability-map sweep over the (Δ, Γ) plane (+ unboxed behind the flag);
   rejection-spectrum artifact + arena heatmap. Instrument only. **Done 2026-06-10** —
   `experimental.ViabilityMap`, `docs/viability-map.json`, visualizer heatmap,
   `ViabilityMapTest`; finding: the viable region is a *sliver* — 2 cells of 46
   ((3,2) and (4,2)); see `CHANGELOG-2026-06-10-adr012-e1-viability-map.md`.
2. [x] **E2** — population-diversity metrics in the recorder; measure the stationary
   (μ+λ) collapse rate K. **Done 2026-06-10** — `TreeEvent.Diversity` + controller
   ancestry/metrics + recorder + visualizer + `DiversityCollapseTest`; finding:
   **K_collapse = 1 and the attribution flips** — the viability filter collapses the
   population to one lineage in generation 1 (selection never had diversity to
   squander); the mutation walk to E1's sliver takes 6–7 generations. See
   `CHANGELOG-2026-06-10-adr012-e2-diversity.md`.
3. [x] **E3** — non-stationary workload harness; fixed vs elite-only vs full-population on
   re-adaptation lag + integrated cost. The axis V5 skipped. Verdict published either way.
   **Done 2026-06-10 — verdict negative, decisively**: with exploration priced at the
   ensemble's comparator seam, ELITE costs 2.7× and POP ~5× the best fixed (AVL) on
   integrated cmp/op, all seeds; the bill is O(n) candidate rebuilds per generation, not
   shadow serving. Only SPLAY shows measurable re-adaptation lag. E4's bar: cut lag
   *without adding rebuilds*. Same-day addendum: the ADR-002 *selector* raced too —
   ~1.5× best fixed (per-morph beats per-generation rebuilds) but still −52%; on this
   (AVL-dominated, fixed-in-advance) schedule **no adaptive scheme of any architecture
   wins**. See `CHANGELOG-2026-06-10-adr012-e3-nonstationary.md`. **E3b (same day,
   pre-registered):** on a discriminating schedule (oracle gap ~13.5%, premise
   hard-asserted), still no — and the diagnosis is sharp: **the selector never morphed
   once** through a 36% opportunity; its cost model doesn't track the realized meter.
   The premise survives; the perception fails. Named consumer: scorer calibration
   against realized meters. See
   `CHANGELOG-2026-06-10-adr012-e3b-discriminating-schedule.md`. **Calibration done
   (same day, suite 528):** scorer constants refit to the realized comparisons tables,
   shape kept; SELECT goes from never morphing to tying hindsight-best AVL (~1% E3,
   ~3.5% E3b) while paying its own rebuilds. Both verdicts stand (tying ≠ the ≥10%
   win). Residual ~13% oracle gap (sequential blocks) named and held: recency-aware
   locality feature, only if that gap needs claiming. See
   `CHANGELOG-2026-06-10-scorer-calibration.md`. **E3c (2026-06-11,
   `SwitchingCostExperimentTest`): the gap is unclaimable — claimable=false 0/3
   seeds, ~−50% each.** Two clairvoyant switchers (real O(n) morph rebuilds; MIRROR
   ensemble O(1) promote with standing fan-out) were handed the winners table and
   still lost half again over best fixed: the switching bill (~8.6 cmp/op cheapest)
   exceeds the free-oracle prize (~2.4 cmp/op) more than threefold. The recency
   feature is retired; the selector's hold on AVL was correct economics. See
   `CHANGELOG-2026-06-11-adr012-e3c-switching-cost.md`.
4. [ ] **E4** — diversity-preserving selection + elite archive; does it cut E3's lag
   without a steady-state cost regression beyond a documented bound?
5. [ ] **E5** — widen the genome (splay-p, hybrid-mix); do stable species emerge under
   heterogeneous/cyclic environments?
6. [ ] **E6** — (optional, long) generalize the loop to a second policy space (cache
   eviction); does the machinery transfer unchanged?

---

## 7. Verification & rollback

Each E-slice ships green through `ant clean test` per house discipline; instruments
(E1–E2) carry oracle/correctness assertions, experiments (E3–E5) carry correctness
assertions hard and the dynamics verdict as printed rows with one `event=...` line (the
V5 pattern — wall-clock is weather, deterministic meters decide). Rollback is per slice:
instruments are additive and removable; the non-stationary harness is test-only; the one
mechanism with live-behavior impact (E4 diversity-preserving selection) sits behind a flag,
defaulting to the V4 pure-(μ+λ) behavior, so the existing controller is unchanged unless
asked. No slice weakens the health gate — the viability filter is load-bearing for the
entire premise and only ever gets *more* observable, never more permissive.
