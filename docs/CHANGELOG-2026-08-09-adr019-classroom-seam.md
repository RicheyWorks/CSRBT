# Changelog — 2026-08-09 — ADR-019: the classroom seam

Pluggable experiments: a plain-text protocol format, a runner that grades
pre-registered hypotheses against a live tree, a theory bench with abiotic factors,
a genetics bench (Hardy–Weinberg, Euler–Lotka, Punnett squares), an export bundle
(CSV/HTML/JSON), and an interactive Workbench on the lab page. Full suite 752 green
(721 prior + 31 new).

## New — `csrbt-experimental` ecology package

- **`ExperimentSpec`** — parser for `.eco` protocol files: `name/keys/seed/window`,
  `phase:` (uniform / hot / churn), `factor:` (area, temperature, wind, distance),
  `model:` (logistic, exponential, levins, island, competition, predation,
  hardyweinberg, eulerlotka), `cross:` (up to 3 loci, `incomplete`, `observed`),
  `expect:` (richness/shannon/evenness/hill1/chao1 on one phase; brayCurtis/pianka
  across two; ops `< > <= >=`). Malformed lines are reported problems, never guesses;
  duplicate phase names flagged.
- **`ExperimentLab`** — runs the spec's phases on a live `TreeContext` through
  `EcologyRecorder`s (same instruments as ADR-015/016), applies the environment to
  every model, renders Punnett squares, and grades hypotheses
  ✅ CONFIRMED / ❌ REFUTED / ⚠ UNGRADEABLE. Byte-deterministic (pinned).
  `runWithExports` returns the full export bundle.
- **`TheoreticalModels`** — exponential, logistic (closed form), Levins
  (p* = 1 − e/c), island biogeography (closed-form relaxation to S* = c/(c+e)·pool),
  Lotka–Volterra competition and predation (sub-stepped Euler, cycles pinned).
  **`Environment(area, temperature, wind, distance)`** with documented conventions:
  c′ = c·wind·temp·e^(−distance), e′ = e/area, r′ = r·temp, K′ = K·area;
  `NEUTRAL` is the identity.
- **`PopulationGenetics`** — `hardyWeinberg(AA, Aa, aa)` → p, q, expected counts,
  χ² vs 3.841 (df 1), heterozygosity; `eulerLotka(lx, mx)` → R₀, T, r ≈ ln R₀/T,
  exact r by bisection on Σe^(−rx)lₓmₓ = 1.
- **`MendelianGenetics`** — Punnett squares ≤3 loci, complete/incomplete dominance,
  `ratioFit` χ² grading df 1–8. Oracles: Mendel 5474:1850 → χ² ≈ 0.263; dihybrid
  315:108:101:32 → χ² ≈ 0.47; chicken combs 9:3:3:1; blue Andalusian 1:2:1.
- **`ExperimentExport`** — RFC-4180 CSV writer/splitter (round-trip pinned),
  header-on-first-touch row appender, and the self-contained print-friendly
  `report.html`. Native `.xlsx`/`.pptx` held with a named trigger (dependency-free
  policy; CSV-into-Excel and print-to-PDF serve the workflow).

## New — docs and samples

- `docs/ADR-019-classroom-seam-2026-08-09.md` — the decision record.
- `docs/sample-experiment.eco` — the graded sample: three phases, a small windy
  distant pond, five models, three famous crosses, four hypotheses (one deliberately
  wrong so the ❌ REFUTED path is visible).
- `docs/experiment-out/` — the sample's full export bundle (report.txt,
  session.json, 6 CSVs, report.html).
- `docs/ECOLOGY-FIELD-GUIDE.md` — new "Design your own experiment" section.

## Changed

- `docs/ecology-lab.html` — three new session stations (📐 The Theory Bench,
  🌱 The Greenhouse & Coop with colored Punnett squares, 🎯 The Hypotheses with
  verdict badges) and the interactive **Workbench**: field-data paste box, quadrat
  dispersion, Hardy–Weinberg calculator, Punnett builder with famous-cross presets,
  theory bench with abiotic inputs. JS mirrors verified against the Java oracles
  (Mendel χ² = 0.263 in both). Zero-JS-error render checks on all stations.
- `csrbt-experimental/build.gradle.kts` — new task `ecologyExperiment`
  (`-Pspec=path/to/your.eco`, defaults to the sample).

## Tests (31 new, all hand-oracle)

- `TheoreticalModelsTest` (7) — fixed points, closed forms, analytic logistic
  midpoint, competitive exclusion, predation cycles, environment conventions.
- `PopulationGeneticsTest` (8) — 25/50/25 perfect equilibrium; 30/40/30 → χ² = 4.0
  exactly; lx={1,1}, mx={0,2} → r = ln 2 both ways; the defining Euler–Lotka
  equation verified directly; contracts.
- `MendelianGeneticsTest` (9) — the famous ratios and Mendel's actual counts as
  oracles; trihybrid stays drawable (8×8, 27 genotypes); contracts.
- `ExperimentLabTest` (7) — spec contract + honest problem reporting, determinism,
  all three verdicts, JSON schema balance, export bundle presence/consistency,
  CSV round-trip.
