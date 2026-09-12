# 2026-09-12 — ADR-197: the findings become failures

**Three blind trials found the same page defects and filed all of them, because
fixing one moved a task claim and broke the trials graded against it. Each
trial now keeps the protocol it was run under, and six defects are closed.**

## Added

- `tools/traces/blind{3,4,5}/tasks/` — the four task files as of each run.
- `harness_tasks.protocol_of(dir)` and `protocol_drift(dir)`; `verify_tasks`
  grades each trial against its own protocol (329 → 368).
- `verify_report` section K (194 → 208): the six defects, each against a number
  the suite computes itself, and an export checked as an export.
- `mutate_report` can mutate a **page**: its docs directory is symlinks to the
  real one and a page mutation replaces one link (118 → 124 / 124).

## Fixed

- **breeding bench** — ten generations of inbreeding compound; the breeding
  class is no longer the minimum's provenance (*"this crop is cited for this
  crop"*); a dead seed lot gets no sowing rate.
- **collection sheet** — a reagent's name is decoded once, by the browser that
  encoded it, and the column is as wide as the widest name.
- **pheno tracker** — the `.eco` cross line follows the page's own verdict; the
  header names the traits that were scored; the CSV column says *weighted mean*.
- **`verify_br`** (89 → 90): the breeding bench's own suite asserted the linear
  13.9%. The oracle had been copied from the page rather than from the caption
  above it, which is how a page stays wrong under a green suite.

## Filed, not fixed

The stand sheet's expansion factor (`400 m²`, `EF 25.0` for a 399.72 m² circle)
against a CSV per-hectare column that uses the unrounded factor — three figures
four tasks claim, so it needs its own slice and its own re-grade.
