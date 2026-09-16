# 2026-09-16 — ADR-213: the one artefact this page tells a student to save carried the data, the hypotheses, and none of the answers

**ADR-211 found 32 figures the ecology lab works out that nothing it hands over
carries, and deferred them: its only export is a `.eco` PROTOCOL. That was right
about what an `.eco` file is and wrong about what follows from it.**

## Fixed

- **`ecology-lab.html`** — the five workbench readouts (field diversity, two-site
  β diversity, quadrat dispersion, mark–recapture, Hardy–Weinberg) each worked
  out their numbers inside a render function and assigned them straight into
  `innerHTML`, so nothing else could read them. Each is extracted to a `stat*`
  function returning values; the panel renders from it and the exporter reads it.
  **Nothing is re-derived in the exporter** — a second copy of a calculation is a
  second source of truth (ADR-068).
- The `.eco` protocol now ends with a provenance block **written as comments**,
  because the file is a pre-registration and a result written as a protocol line
  would make it assert what it is supposed to be asking. Absent when there is
  nothing to report.

## Checked

- `verify_eco` reads every figure off the **panel** and requires it in the
  protocol text as the same digits. It caught the first disagreement on its first
  run: the panel writes a 95% CI with an en dash and the exporter had a hyphen.

**32 → 19.** The 19 that remain are the nine stations, rendered from a session
JSON by nine independent renderers; a run's readings are not a pre-registration,
and that is its own slice. The ceiling is 19 and may not rise.
