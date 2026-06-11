# CHANGELOG 2026-06-10 — consolidation audit: the ecology-turn slices (E1–E3 + addendum)

Fresh-eyes pass over the day's five slices (ship-visibility, E1, E2, E3, the selector
addendum), per the consolidation-audit precedent: when several slices land in one day,
check the seams when the dust settles. Suite **527, green** after.

## Verified (mechanically, not by re-reading)

- **E1 determinism:** `experimental.ViabilityMap` re-run three times —
  `docs/viability-map.json` is **byte-identical** every run (the V5 standard applied to
  the instrument).
- **E2 recorder integrity:** a fresh audit driver ran 4 generations through
  `PolicyEvolutionController` with the recorder attached; the session JSON **parses**,
  carries exactly one `Diversity` decision per generation, and serializes a NaN spread
  as `null` (the Trial-cost convention, kept).
- **Visualizer:** heatmap and Diversity chip/narration paths re-smoke-tested headless
  earlier the same day — 46 cells drawn, 2 viable greens, no NaN/undefined in any frame.
- **Suite:** 527 green after every change below.

## Seam findings

- **One fix: `core.RedBlackTree.remove` logged WARN for a remove of an absent key** — a
  routine no-op, not a fault, and pre-existing (legacy per-op logging, predates the
  E-slices). Under E1's churn probes it flooded **~43k WARN lines per sweep**; the whole
  suite paid similarly. Downgraded to `logger.debug("Remove no-op …")`. No test asserted
  on the line (checked); the viability artifact is byte-identical before/after; sweep
  output went from ~11k lines to 1.
- **Noted, no change — `roots` map growth:** the E2 ancestry map keeps one entry per
  genome value ever bred. Bounded by the parameter space (≤ the structural box), same
  lifetime discipline as the existing `dead` graveyard. Fine at this genome size; revisit
  if E5 widens the genome by orders of magnitude.
- **Noted, no change — event order:** `Diversity` is emitted before a same-generation
  `SELECTED` (selection closes, then promotion). Replay shows the population pulse before
  the throne change; harmless, and arguably the right narrative order.
- **Noted, no change — `endGeneration(0)` tail:** E3's cadence closes a zero-op
  generation at run end when the schedule divides evenly. Legal by the controller's
  contract (`opsElapsed` clamped ≥ 0), judgment runs on the materialized state; benign.
- **Docs cross-check:** ADR-012 items 1–3 ticked with pointers; handoff, changelogs, and
  README links all resolve (link-check re-run).

## Standing residue

`snapshots/` keeps accumulating generated `.rbt` test files when the suite runs from the
repo root — still untracked, still not for committing; clean host-side at will.
