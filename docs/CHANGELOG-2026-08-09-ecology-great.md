# CHANGELOG 2026-08-09 — the "make it great" drop: estimators, trace replay, early warning, terrarium

Five additions in one slice, per the prioritized plan. Suite **705 green**
(608 core + 97 experimental, +11 tests), 0 failures. Byte-deterministic throughout.

## 1. Richness estimation (`CommunityMetrics`)

- **`chao1`** — Chao (1984) estimated true richness from singletons/doubletons, classic
  and bias-corrected forms; "how many keys did the survey miss."
- **`rarefiedRichness` / `rarefactionCurve`** — Hurlbert (1971) exact hypergeometric
  expectation, log-space; the fair richness comparison across unequal effort.
- `FieldReport.richnessEstimateReading` narrates it; every community section now says
  whether the survey looks complete. Hand oracles for both (E[S₁] = 1, E[S_N] = S,
  hypergeometric hand case; Chao1 classic/corrected/complete).

## 2. Your workload as an ecosystem (`WorkloadTrace`)

`./gradlew ecologyTrace -Ptrace=your.csv` — replay any `op,key` trace (aliases:
add/insert/put, remove/delete, search/get/contains…) through the instruments: community
survey with Chao1 + rarefaction, the **drift station** (consecutive-window Bray–Curtis —
workload change over the run), demography, growth, and the survey grid — each emitted
only where the trace carries the signal, malformed lines counted and reported, never
guessed at. Writes a lab-page session; `docs/sample-trace.csv` is a worked example whose
mid-trace hot-set move the drift chart finds on its own. Tests: parser contract,
byte-determinism, schema sanity, graceful station skipping, and the discriminating check
(peak turnover at the planted regime boundary).

## 3. The early-warning experiment (`EarlyWarningExperimentTest`, pre-registered)

The ecology layer put on the bench, ADR-012 style — the perception seam ADR-012's
re-arming triggers were waiting for. Method fixed in advance (50 keys, W = 500, 6-window
regimes, threshold = 2× within-baseline max, 3 seeds), verdicts in hard assertions:

- **Abrupt shifts:** consecutive-window Bray–Curtis crosses exactly at the boundary
  windows — detection lag 0, zero false positives, zero fabricated precursors
  (boundary BC ≈ 0.93–0.97 vs thresholds ≈ 0.20–0.26, all seeds).
- **Gradual drift:** displacement from the baseline community (1 − Renkonen) crosses at
  window 7 of a 6→12 ramp — **5 windows of warning before the new regime establishes**,
  all seeds, with the pre-drift stretch quiet.
- **Method note, pinned by its own test:** consecutive differencing provably smears slow
  drift (ramp max ≈ baseline noise) — displacement is required, not preferred.
- Supporting addition: **`BetaDiversity.renkonen`** (percentage similarity, Renkonen
  1938) — the size-fair companion to Bray–Curtis, added after the experiment's first
  run demonstrated the classic mistake: raw BC between a window and a 5×-larger merged
  baseline reads ≈ 0.67 for *identical* composition. Oracle-tested, motivating contrast
  asserted.

## 4. The terrarium (`docs/ecology-lab.html`)

A live, seeded, pokeable ecosystem at the top of the lab page: drag hot-key share and
hot-set size and watch evenness, effective species, Chao1, and the rank–abundance curve
respond instantly; drag island capacity and watch turnover and residence times move.
Pure in-page simulation (mulberry32, seed fixed — reproducible like everything else).
Plus: the meadow station now draws **rarefaction curves** (species vs effort, per
regime) with Chao1 tiles; a **drift card** renders trace sessions; every station is
schema-optional so field-day and trace sessions both display. Render verified by
headless screenshot, including a slider interaction pass (hot share 95% → J′ 0.43,
Chao1 reporting unseen keys — the lesson, live).

## 5. README

New section **"The ecology layer (2026-08)"** — instrument table, the three ways in,
and the two findings (the constants audit; the early-warning verdicts), linked into the
design history.

## Schema note

Lab-session JSON `meadow` moved from named phase objects to a `phases` array (each with
`name`, `chao1`, `rarefaction`); both generators and the page moved together, and the
embedded session was regenerated — no external consumers existed.
