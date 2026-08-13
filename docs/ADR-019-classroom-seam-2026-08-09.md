# ADR-019: The classroom seam — pluggable experiments

**Status:** Accepted (2026-08-09) — engine landed and green
(`ExperimentLabTest`, `TheoreticalModelsTest`, `PopulationGeneticsTest`,
`MendelianGeneticsTest`: 31 tests, all hand-oracle; full suite 752 green).
**Date:** 2026-08-09
**Deciders:** Richmond
**Builds on:** ADR-015 (the instruments), ADR-016 (engine ecology), the field-day
narrator, and the lab page. This ADR turns the instrument rack into an **experiment
engine**: a student writes a plain-text protocol, the engine runs it against a live
CSRBT tree, grades the student's pre-registered hypotheses, and exports the whole run
in formats humans actually use.

---

## 1. The problem

Everything before this ADR was *our* experiments: pre-registered, pinned, but authored
in Java by whoever maintains the repo. A student in a classroom or in the field cannot
write a JUnit class. What they can write is a protocol — "three phases, small pond,
helpful wind, here are my crosses, here is what I predict" — and what they need back
is a graded report they can open in Excel, print to PDF, or paste into slides.

The requirements, as stated:

- **Pluggable experiments** for field and classroom work, including purely theoretical
  runs (no field data at all — just models).
- **A more robust human↔software seam** for entering field or theoretical data.
- **Graduate-level equations**: Hardy–Weinberg; the calculus of the population-biology
  textbooks (logistic, exponential, Lotka–Volterra competition and predation,
  Euler–Lotka); the island-biogeography equations, including **abiotic factors** —
  pond size (area), wind, temperature, distance — applied to rates and capacities.
- **Punnett squares** for the famous crosses (Mendel's peas, chicken combs, the blue
  Andalusian), with easy visual display, so the audience spans elementary students
  tracking chicken types up through AP Biology and graduate thesis work.
- **Exports**: CSRBT session JSON, Excel-ready CSV, HTML, PowerPoint-ready output.

## 2. The decision

One new seam, six pieces, all in `csrbt-experimental`'s ecology package, all
dependency-free, all deterministic.

### 2.1 The `.eco` protocol file (`ExperimentSpec`)

A line-oriented plain-text format a student can write in Notepad. Directives:

| directive | meaning |
|---|---|
| `name:` / `keys:` / `seed:` / `window:` | experiment identity and determinism knobs |
| `phase: <name> uniform <ops>` | even traffic across the key population |
| `phase: <name> hot <ops> <hotSet> <share%>` | a bloom — few keys carry most traffic |
| `phase: <name> churn <ops> <addPct>` | turnover — births and deaths |
| `factor: area\|temperature\|wind\|distance <v>` | the abiotic environment |
| `model: logistic\|exponential\|levins\|island\|competition\|predation ...` | theory bench |
| `model: hardyweinberg <AA> <Aa> <aa>` | genotype census → equilibrium test |
| `model: eulerlotka <lx:mx> ...` | life-table schedule → R₀, T, r |
| `cross: Rr x Rr [incomplete] [observed n...]` | Punnett square (+ χ² grading) |
| `expect: metric(phase) op value` | a pre-registered hypothesis |

Parsing is honest: a malformed line is **reported as a problem, never guessed at**,
and the run continues with what parsed. Duplicate phase names are flagged. The
`expect:` metrics are the ADR-015 instruments (`richness`, `shannon`, `evenness`,
`hill1`, `chao1` on one phase; `brayCurtis`, `pianka` across two).

### 2.2 The runner (`ExperimentLab`)

Simulates each phase against a live `TreeContext` (Red-Black) instrumented with
`EcologyRecorder`s — one global, one per phase — so every diversity number comes from
the same instruments as ADR-015/016, not a parallel implementation. Then it grades
each hypothesis: **✅ CONFIRMED / ❌ REFUTED / ⚠ UNGRADEABLE** (unknown phase — graded
honestly rather than silently dropped). Byte-deterministic: same spec, same report,
same JSON, pinned by test.

Gradle seam: `./gradlew ecologyExperiment` (sample) or
`./gradlew ecologyExperiment -Pspec=path/to/your.eco`.

### 2.3 The theory bench (`TheoreticalModels`)

The textbook calculus, each with a closed form where one exists and a hand-oracle test:

- **Exponential** N(t)=N₀e^rt and **logistic** (exact closed form; the test pins the
  analytic midpoint t = ln((K−N₀)/N₀)/r).
- **Levins metapopulation** dp/dt = cp(1−p) − ep, equilibrium p* = 1 − e/c.
- **Island biogeography** S* = c/(c+e)·pool with the closed-form relaxation
  S(t) = S* + (S₀−S*)e^(−(c+e)t).
- **Lotka–Volterra competition** (sub-stepped Euler; the test pins competitive
  exclusion) and **predation** (the classic cycles, pinned).

### 2.4 The abiotic environment (`TheoreticalModels.Environment`)

`(area, temperature, wind, distance)` with documented conventions, applied uniformly
wherever a rate or capacity enters a model:

- colonization c′ = c · wind · temperature · e^(−distance) — wind and warmth carry
  colonists; distance decays arrival exponentially.
- extinction e′ = e / area — small ponds are riskier.
- growth r′ = r · temperature; capacity K′ = K · area — a half-size pond holds half
  the population.

The sample run shows it end-to-end: `area 0.5, wind 1.3, distance 0.8` turns the
island model's c=0.4 into 0.234 and e=0.1 into 0.2 (S* falls from 80 to 53.9), and
halves both competition capacities. `Environment.NEUTRAL` is the identity, pinned.

### 2.5 The genetics bench (`PopulationGenetics`, `MendelianGenetics`)

- **Hardy–Weinberg**: allele frequencies from a genotype census, expected
  p²/2pq/q² counts, χ² against the df=1 critical value 3.841, heterozygosity
  observed vs expected. Hand oracle: 30/40/30 → χ² = 4.0 exactly.
- **Euler–Lotka**: R₀, generation time T, r ≈ ln R₀/T, and exact r by bisection on
  Σe^(−rx)lₓmₓ = 1 — the test verifies the defining equation directly.
- **Punnett squares** up to three loci, complete or incomplete dominance, with χ²
  ratio grading (df 1–8). The oracles are the famous numbers: Mendel's actual 1866
  seed-shape counts 5474:1850 → χ² ≈ 0.263; his dihybrid 315:108:101:32 → χ² ≈ 0.47;
  chicken combs RrPp × RrPp → walnut 9 : rose 3 : pea 3 : single 1; the blue
  Andalusian Bb × Bb (incomplete) → 1:2:1, the classroom trap that two blue chickens
  never breed an all-blue flock.

### 2.6 The exports (`ExperimentExport`)

`ExperimentLab.runWithExports` produces a bundle (written to `docs/experiment-out/`):

- `report.txt` — the narrated report verbatim.
- `session.json` — drops straight onto the lab page (`docs/ecology-lab.html`).
- `phases.csv`, `drift.csv`, `hypotheses.csv`, `model-series.csv` (long format, ready
  to pivot), `crosses.csv`, `punnett.csv` — RFC-4180 quoted, open directly in
  **Excel**, Google Sheets, or R; round-trip pinned by test.
- `report.html` — self-contained, print-friendly (each section page-breaks), verdicts
  color-coded; prints to PDF or pastes into **PowerPoint** section by section.

**Held with a named trigger:** native `.xlsx`/`.pptx` writers. They would require an
OOXML dependency, and this repo vendors nothing and carries one runtime dependency.
The trigger is an instructor workflow that CSV-into-Excel and print-to-PDF genuinely
cannot serve.

### 2.7 The human seam (lab-page Workbench)

`docs/ecology-lab.html` gains an interactive **Workbench** — no build, no run, works
offline in a browser: paste field counts (name + count per line; junk lines reported,
never guessed) → diversity tiles; quadrat counts → dispersion verdict; a genotype
census → Hardy–Weinberg with the χ² verdict; a Punnett builder with presets (Mendel's
peas with his real counts, dihybrid, blue Andalusian, chicken combs, test cross) and
colored phenotype squares; and a theory-bench with the abiotic sliders mirroring the
Java conventions exactly. The JS mirrors are checked against the Java oracles
(Mendel χ² = 0.263 renders identically in both).

## 3. The graded sample (pinned behavior, not a promise)

`docs/sample-experiment.eco` — three phases (graze/bloom/seasons), a small windy
distant pond, five models, three famous crosses, four pre-registered hypotheses of
which one is **deliberately wrong** so students see what ❌ REFUTED looks like:

```
✅ CONFIRMED  evenness(graze) > 0.9              (observed 0.9944)
✅ CONFIRMED  hill1(bloom) < 20                  (observed 9.1112)
✅ CONFIRMED  brayCurtis(graze, bloom) > 0.5     (observed 0.8505)
❌ REFUTED    evenness(bloom) > 0.9              (observed 0.4947)
```

## 4. Consequences

- The audience seam is now explicit: elementary (chicken types in a colored Punnett
  square) → AP Biology (Hardy–Weinberg problems, χ² grading) → graduate/thesis
  (Euler–Lotka, Lotka–Volterra, abiotic-factor experiments, pre-registered protocol
  files with graded verdicts and a citable export bundle).
- Every number still obeys the house discipline: op-index clocks, seeded streams,
  hand oracles, honest limitation notes. A student's `.eco` run reproduces
  byte-for-byte — which is precisely what makes it usable in a lab report.
- The `expect:` grammar currently exposes 7 metrics; adding one is a one-line switch
  case in the runner plus a parser entry. Deliberately small until a real classroom
  asks for more.
- **Held:** native `.xlsx`/`.pptx` (see §2.6); linked loci / recombination in the
  Punnett engine (independent assortment only — stated in the Javadoc); stochastic
  model variants (the theory bench is deterministic ODE/closed-form by design).
