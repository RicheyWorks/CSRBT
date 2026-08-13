# CHANGELOG 2026-08-09 — ecology polish: field reports, field guide, and the lab page

The biology-student layer: every instrument now speaks plain English, the whole
ecosystem demos itself in one command, and the results render as an interactive page.
Suite **694 green** (608 core + 86 experimental, +13 tests), 0 failures.

## What landed

- **`FieldReport`** — the interpretation layer: every index gets the sentence a field
  TA would say, graded against fixed public-constant thresholds (each band pinned by a
  test at its boundary). Readings for evenness, effective species, dispersion, niche
  overlap, turnover, survivorship type, island saturation, Levins-vs-observed
  agreement, growth; section builders assemble narrated blocks per instrument.
- **`EcologyFieldDay`** — one seeded, byte-deterministic scenario across all six
  stations: the meadow (diversity under even vs hot-patch access), the census
  (density-dependent births → life table + logistic fit over the colonization phase,
  the standard practice), the archipelago (storm/recovery cycles → occupancy vs
  Levins, including the honest disagreement lesson), the fossil record (20% stratum
  turnover), the survey grid (patchy vs sown B+trees), and the island (all-probation
  cache filling to capacity, then pure turnover). Run: `./gradlew ecologyFieldDay` —
  narrated report on stdout, `docs/ecology-lab-session.json` written for the lab page.
  JSON emission is locale-pinned (Locale.ROOT) and structurally asserted in tests.
- **`docs/ECOLOGY-FIELD-GUIDE.md`** — the plain-language walkthrough: what each
  station measures, the biology it maps to, how to run it, how to read the numbers,
  and the honesty rules that make them citable.
- **`docs/ecology-lab.html`** — self-contained interactive lab page (no dependencies,
  works offline): rank–abundance facets, survivorship and logistic-growth curves,
  occupancy timeline, inheritance strata, quadrat histograms, and the island's
  flat-richness/churning-turnover pair — each with hover tooltips, a data table view,
  and the same plain-English readings. Ships with the current session embedded;
  drag-drop a fresh `ecology-lab-session.json` to reload. Palette is the validated
  dark set (3 categorical slots, all six checks pass via the dataviz validator);
  charts follow the house chart rules (single axis, thin marks, rounded data-ends,
  legend for the one two-series chart, reduced-motion respected).

## Tests (13 new)

`FieldReportTest` (10) — every threshold band at its documented boundary, section
narration (a 90%-one-key community must not read as even; a clumped grid must say
clumped), wording determinism. `EcologyFieldDayTest` (3) — byte-determinism of report
and JSON across runs, all six stations present with interpreted sentences, JSON
structural sanity (balanced, all stations, no dangling commas, no locale-broken
numbers).

## Notes

- The demo's growth fit reports R² ≈ 0.47 — honest for a stochastic population; the
  reading includes it rather than hiding it.
- The spatial reading grades on variance/mean (the classroom index); Morisita is
  printed alongside.
- The archipelago station deliberately shows Levins disagreeing with observation on
  balanced storm cycles — the survey-design lesson, stated in both the report and the
  lab page.
