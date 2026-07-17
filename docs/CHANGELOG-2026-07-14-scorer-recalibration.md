# CHANGELOG 2026-07-14 — recalibrating the scorer to the single-descent write path

The second recalibration of `CostModelStrategyScorer`, forced by the same rule that forced the
first: **where the meters disagree, the deterministic one decides** — and the deterministic
meter changed underneath the model. The single-descent write fix (census finding A, this same
day: `RedBlackTree.addIfAbsent`/`removeIfPresent`, one comparison per insert step) invalidated
the 2026-06-10 calibration tables, which had been measured through a write path that descended
twice per successful mutation and compared twice per insert step in RB/Splay/Hybrid.

## The evidence (post-fix, all on the record)

Re-run E3 probe (hot-read → uni-write → seq-append → churn, 3 seeds), fixed arms, cmp/op:

| arm | seed 11 | seed 2026 | seed 42 |
|---|---|---|---|
| HYBRID | **11.56** | **11.61** | **11.58** |
| AVL | 11.84 | 11.90 | 11.86 |
| RB | 14.19 | 14.17 | 14.09 |
| SPLAY | 14.81 | 14.95 | 14.84 |

E3b (uniform ↔ sequential): same shape — HYBRID 12.20–12.24 best-fixed on **every seed**, AVL
+2.7%, RB +22%, and SELECT (still steering by the old model, sitting on AVL) trailed best-fixed
by ~5%. The phase-shift censuses (SBS `docs/phase-shift-census-findings.md` §5–6) add the two
pure diets: uniform reads are a family-wide near-tie (RB = JDK TreeMap **bit-exactly**; AVL and
Hybrid within ~1.5% either side), and uniform 50/50 churn is Hybrid ≈ RB < AVL by ~1.5%.

Three facts the old model now gets wrong: (1) "AVL beats RB on every diet" was mostly the
double-compare artifact — reads are a tie and uniform churn slightly favors RB; (2) Hybrid —
AVL balance, RB delete machinery, single-compare insert — is the measured best-fixed on every
diet that contains writes; (3) RB's genuine remaining deficit is concentrated in
sequential/windowed write blocks, which the r/w/s feature space cannot see.

## The refit (shape kept, constants refit, Hybrid gets its own line)

| | old | new | consequence |
|---|---|---|---|
| AVL | BASE .46, −.12r, +.04w | unchanged | the read-side baseline; first on read-dominant diets |
| HYBRID | mean of three + .02 tie penalty | BASE .462, −.12r, +.015w | its own calibrated line; crosses under AVL at **w ≳ 0.08** — writes fund it, pure reads don't |
| RB | BASE .62, −.05w, −.04r | BASE .56, −.20r, +.06w | read parity (+6% at r=1, inside the 20% margin ⇒ read diets HOLD an RB incumbent instead of buying a rebuild worth nothing); the sequential/windowed deficit lands in the write term, crossing the morph margin vs Hybrid near w ≈ 0.8 |
| SPLAY | (2026-06-10 line) | unchanged | skew story intact; noted that post-ADR-004 its wins are write-path-funded |

Morph behavior under `MorphPolicy.defaults()` (20% margin), verified arithmetically per diet:
read diets hold any balanced incumbent (measured: correct — the morph buys ≤1.5%); balanced
50/50 holds RB (measured: RB ≈ Hybrid there); write-heavy (w ≳ 0.8) morphs RB → Hybrid (23% at
w=1, matching the measured +22%); skewed reads still morph anything → Splay (70%+).

**Correction (same day, from the red build):** the paragraph above originally claimed SBS's
`WorkloadAdaptationTest` survives intact "at pure reads" — but its diets are *not* pure reads in
the window. `buildAdaptive` folds the construction feed (~2,210 distinct keys) into the 4096-op
rolling monitor via `recordFeed`, so at eval time the tests sat at w ≈ 0.20–0.40 — past the new
w ≈ 0.08 Hybrid/AVL crossover — and the zero-margin `relaxed()` policy morphed to HYBRID (3 red:
uniform-reads, once-optimal-holds, born-right). The 2026-06-10 model masked this because its
Hybrid tie penalty kept AVL first at any moderate w. Re-pinned SBS-side by lengthening the read
diets to 10k reads (w decays to ≈ 0.038, where AVL is cheapest again: 0.3461 vs Hybrid 0.3472,
RB → AVL improvement 6.4%), so each test's stated "read-only" workload is finally true of the
window it scores. Expectations unchanged — AVL is still the read-diet winner. Production-gate
behavior is unaffected: the feed residue's Hybrid lead is ~1–2%, far inside the 20% margin.

**Re-pinned tests** (the pins *were* the stale calibration, recorded with their evidence):
`StrategyScorerTest` write-heavy and balanced-mix now expect HYBRID first; "Hybrid never ranks
first" is retired and replaced by the w ≈ 0.08 crossover pin; `ControllerConvergenceTest` G4
(both) converge to HYBRID; SBS `WorkloadAdaptationTest` read diets extended to 10k reads (see
correction above). Surviving untouched: the §10 trace (Splay first, RB last), read-heavy
→ AVL, max-skew margin, G3 Splay convergence, `WorkloadAdaptationTest`'s hot-key → Splay and
WeightBalanced-rejection cases, and both SmokeHouse `CsrbtUnlockTest` pins (the WRITE_HEAVY
clamp test sits inside the cooldown; the born-AVL test's write diet holds AVL at 4.6%).

## Held items, restated

Rotation pricing (ADR-009 §3) remains unpriced — RB still rotates least (150k vs 186k in the
write census) and buys nothing for it on this meter. Newly noted: Hybrid's per-write
instrumentation (`recordAccess` frequency map) is likewise unpriced by comparisons; if Hybrid's
promotion to default-winner ever needs wall-clock defense, that is the JMH row to add. The E3/E3b
SELECT rows will improve on the next run (the selector will now land on Hybrid); their verdicts
remain success=false unless SELECT *beats* best-fixed by the pre-registered 10% — converging to
it is still not beating it.
