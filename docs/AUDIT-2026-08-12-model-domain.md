# Bug audit — 2026-08-12 (post ADR-017…020: heredity seams, classroom & student seams)

**Scope:** adversarial pass over the surface landed *after* the 2026-08-09 ecology
audit — everything modified or created from Aug 9 16:40 onward: the ADR-017 heredity
seams (`PersistentTreeEngine.Snapshot.sharedNodeCount`, `SnapshotLineage`,
`BPlusTreeEngine.leafKeyCounts`), the ADR-018 amortization frontier surface
(`WorkloadTrace`), the ADR-019 classroom seam (`MendelianGenetics`,
`PopulationGenetics`, `TheoreticalModels`, `ExperimentSpec`, `ExperimentLab`,
`ExperimentExport`, `FieldReport`), and the ADR-020 student seam (`FieldData`,
`MarkRecapture`, `PhyloTree`, and the `ExperimentSpec`/`ExperimentLab` additions).
Re-modified-after-audit classes (`CommunityMetrics`, `BetaDiversity`) re-derived too.

**Method:** the house discipline — re-derive each instrument's math/bookkeeping by hand
against a written oracle, hunt degenerate inputs, accounting-invariant breaks, and
parse/grade paths that a student can trip; code defects get a probe test that must FAIL
against the unfixed code before the fix counts, and contract defects get a characterization
test pinning the corrected behaviour. Core engines were additionally differential-tested
against independent oracles (per-op invariant validation over thousands of random op
streams; 249,431 snapshot-pair checks on `sharedNodeCount`). Built and run on JDK 21
(Gradle 8.14.3 / `options.release = 17`). Suite after: **772 green** (617 core +
155 experimental, +5 tests), 0 failures.

**Findings:** two — M-1 (Medium, code, fixed) and M-2 (Medium, contract/doc, corrected).
The core engines (`PersistentTreeEngine`, `BPlusTreeEngine`, including the ADR-017 seam
methods) came back clean under exhaustive differential testing.

---

## Confirmed defect (probe-verified, fixed)

### M-1 (Medium). A parseable-but-out-of-domain `model:` line crashed the entire run.

Every other semantic directive validates its content at parse time and turns a bad one
into a reported problem: `cross:` calls `MendelianGenetics.cross(...)`, `tree:` calls
`PhyloTree.parse(...)`, `data:` calls `FieldData.parseTokens(...)` — each wrapped by
`ExperimentSpec.parse`'s per-line `catch (RuntimeException)`. `model:` was the lone
exception. `parseModel` validated only *structure* (known kind, correct arity, `steps`
range); it never checked that the numbers lay in the model function's domain.

So three model kinds parsed clean and then threw from `ExperimentLab.run` → `appendModel`
(which has no per-model guard), taking the whole report down with a stack trace:

- `model: markrecapture 100 90 95` — R = 95 > min(M, C) = 90 → `MarkRecapture.estimate`
  throws `"recaptured must be in [0, min(marked, caught)]"`.
- `model: hardyweinberg -1 50 25` — negative genotype count → `PopulationGenetics.hardyWeinberg`
  throws `"genotype counts must be non-negative"` (and all-zero → `"no individuals"`).
- `model: eulerlotka 1.0:0 0.8:0 0.5:0` — every mₓ = 0 ⇒ R₀ = 0 → `PopulationGenetics.eulerLotka`
  throws `"R0 must be > 0"`.

This directly contradicts the stated contract of `ExperimentLabTest.badLinesReported`
("bad spec lines become reported problems, never guesses **or crashes**") — that test
only exercised *structurally* bad models (`model: nonsense 1 2 3`), so the domain path
was uncovered. For a student audience this is the sharp edge: one mistyped count in a
theory-bench line erases every phase reading, every graded hypothesis, and every other
model in the report.

All four probes (`markRecaptureOutOfDomain`, `hardyWeinbergNegative`, `eulerLotkaZeroR0`,
`goodModelSurvivesBadNeighbour`) failed against the unfixed code — the invalid model was
accepted (`spec.models().size()` non-zero) and `run` threw — then passed after the fix.

*Fix:* `ExperimentSpec.parseModel` now validates the domain of the value-sensitive models
at parse time by invoking the underlying function (the exact pattern `parseCross` already
uses — call it, discard the result, let the domain exception surface as a reported
problem): `eulerLotka(lx, mx)` in the eulerlotka branch, and a `markrecapture`/
`hardyweinberg` switch in the general branch. A rejected model is dropped from
`spec.models()` and listed in `spec.problems()`, rendered as `⚠ spec:` like every other
malformed line; valid models beside it are untouched and `run` completes.

---

## Confirmed defect (characterization-pinned, contract corrected)

### M-2 (Medium). `EcologyRecorder`'s "Bounded" contract was false for two registers.

The class Javadoc promised: *"**Bounded.** Closed windows are capped at `maxWindows`
(oldest evicted); the cumulative tally and demography registers grow with distinct keys,
the same lifetime discipline as the E2 ancestry map"* — and the class is explicitly
positioned to stand in the long-running ADR-002 §9.2 production seam. But two registers
grow with **events**, not distinct keys, and are never evicted:

- `lifespans` (line 110) appends one entry on every remove of a live key. A single key
  repeatedly re-added and removed contributes one entry per cycle.
- `populationSeries` (line 196) appends one sample at every window boundary, retained even
  after the window it sampled is evicted from the (capped) `closedWindows`.

Demonstrated: `new EcologyRecorder(1000, 4)` driven with 50,000 add/remove cycles on the
**one** key hash `1` yields `cumulativeAbundance().size() == 1`, `aliveBirthOps().size() == 0`,
`closedWindows().size() == 4` (all correctly bounded) — but `lifespans().size() == 50,000`
and `populationSeries().size() == 100`. On a remove-heavy production stream that reuses key
hashes, memory grows without bound, contradicting the stated guarantee → eventual OOM in
exactly the seam the class advertises itself for.

*Fix (contract, not semantics):* the two registers are load-bearing — `lifespans` is the
cohort `LifeTable` consumes and `populationSeries` is the trajectory `LogisticGrowth` fits,
so silently capping them would change demographic and growth output for long runs (the
house's documented-limitation precedent — B-4, EnsembleCommunity's cancelled-cycle
blindness — applies). The Javadoc is corrected to state precisely what is bounded
(closed windows; cumulative tally and `birthOps` by distinct keys) and what grows with
events (`lifespans` with deaths, `populationSeries` with closed windows), with explicit
drain/reconstruct guidance for the production seam. `EcologyRecorderBoundingTest` pins the
true behaviour so the contract stays honest. **If true bounded memory is wanted in the
seam, the alternative is rolling caps on both registers — a deliberate semantic change
that needs a design call, not a silent fix.**

---

## Examined and verified clean (so the next audit needn't re-derive them)

- **`MarkRecapture`** — Lincoln–Petersen `MC/R` (∞ at R=0), Chapman `(M+1)(C+1)/(R+1)−1`
  with the standard variance and 1.96 interval; the first cast to `double` averts long
  overflow; R ∈ [0, min(M,C)] keeps `M−R`, `C−R` ≥ 0 so the variance is non-negative.
  Hand oracle 100/60/15 → 400 / 384.0625 confirmed.
- **`PhyloTree`** — recursive-descent Newick parser rejects `()`, `(A,)`, unbalanced
  parens, and non-tree trailing junk with reasons; internal-label trees, spaces, and
  optional `:length` handled; `newick()`/`json()`/`ascii()` round-trip.
- **`FieldData`** — token and table forms; bare-name tallies, `name=0` reported, the
  three separators normalised; multi-word bare names recover through the hyphenating
  catch. `toEcoLine`/`toCsv` inverses; `Long != 1` unboxes correctly.
- **`PopulationGenetics`** — HW allele counting `p=(2·AA+Aa)/2n`, χ² with the E=0 guard
  (E=0 ⇒ O=0), df=1; Euler–Lotka R₀/T/r with a strictly-decreasing bisection on
  [−5, 5]. **Now domain-guarded at the spec boundary (M-1).**
- **`MendelianGenetics`** — gamete enumeration by bitmask, dominant-first genotype
  normalisation (order-independent keys), complete/incomplete phenotype, χ² ratio fit
  df = classes−1. Mendel 5474:1850 → χ² ≈ 0.263 confirmed; the `Cross`-arity mismatch is
  handled gracefully in `appendCross` (observed counts ignored with a warning, not a
  crash).
- **`TheoreticalModels`** — Levins/logistic/island/exponential closed forms and
  Euler-substep competition/predation; states clamp at 0; `Environment` enforces area>0
  and non-negative temperature/wind/distance. (K=0 in competition/predation yields NaN
  series rather than a throw — cosmetic, no crash; noted, not fixed.)
- **`CommunityMetrics`** — Shannon/Simpson/Hill limits, Chao1 both forms, Hurlbert
  rarefaction in log space (guard ⇒ every factor positive), broken-stick expectations
  sum to N, geometric-k fit, `bestFit` enum-order tie-break.
- **`BetaDiversity`** — Jaccard/Sørensen/Bray–Curtis/Renkonen/Pianka/Whittaker boundary
  conventions (empty-vs-empty, one-empty) re-checked against hand vectors.
- **`PersistentTreeEngine.Snapshot.sharedNodeCount`** — the pruned identity walk is
  correct: a shared node's whole subtree is shared (immutable nodes), so `+= n.count`
  with no descent counts each shared subtree once, no double counting; the
  `structural ≤ content` inheritance invariant holds because shared nodes ⊆ inherited
  keys.
- **`SnapshotLineage`** — contiguous absolute indexing across eviction; content/structural
  inheritance, divergence, and per-generation turnover derive correctly.
- **`ExperimentLab` grading** — the qualitative band words (`qualitativeWord`) match
  `ExperimentSpec.wordsFor` and the `FieldReport` thresholds exactly for evenness /
  turnover / overlap / fit / survivorship; phase-vs-dataset comparisons and
  survivorship-without-census are honestly UNGRADEABLE; JSON braces/brackets balance.
- **`ExperimentExport`** — `csv`/`splitCsv` are RFC-4180 inverses; the printable HTML
  escapes and verdict-styles correctly.
- **`BPlusTreeEngine.leafKeyCounts`** — a read-only leaf-chain walk; trivially correct.
