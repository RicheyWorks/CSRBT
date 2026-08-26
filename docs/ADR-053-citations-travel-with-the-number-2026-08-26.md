# ADR-053 — Citations travel with the number

**Status:** accepted · 2026-08-26
**Extends ADR-051. Rule 1 anchored on the glossary; the kit proved that anchor
too narrow within a day.**

## The second instance

`stand-sheet` states the stocking measure properly:

> **Stand Density Index (Reineke 1933)** — SDI = N · (QMD/25)^1.605
> Metric form, 25 cm reference. Derived for even-aged single-species stands —
> treat it as indicative in mixed uneven-aged forest.

Citation, unit convention, and the limit of applicability. Gate 1.

`ecology-field-card` — the card that gets printed and carried — shipped the same
formula with **no citation**, and added a threshold stand-sheet never claims:

> N(QMD/25)^1.605 — **>55%** of max means competition-driven mortality has begun

Stated as a universal fact. ADR-051's checker could not see it, because the
researched position lived on a bench page rather than in the glossary. **Only 18
of the kit's 31 citations are in the glossary.**

## What the research actually says

- **Reineke 1933**: log N = −1.605 log D + k, reference diameter 10 inches.
  Reineke presented the −1.605 slope as universal across 14 forest types, while
  himself flagging slash pine as a "possible" and shortleaf pine as a "definite"
  non-conformer.
- **The 25 in the metric form is a convention, not a botched conversion.**
  10 in = 25.4 cm; the literature notes that in metric applications "25 cm is
  conventionally used in the denominator rather than a strict conversion."
  The kit's `25` is right, and now says why.
- **The threshold is species-specific, and 55% is not the general figure.**
  Long & Daniel (1990) put ~25% of SDImax at the onset of competition, ~35% at
  the lower limit of full site occupancy, and ~60% at the lower limit of
  self-thinning. Published onsets of the zone of imminent competition mortality
  run **0.45 for white spruce to 0.55 for lodgepole pine**.

The card now carries the citation, names the 25 cm convention, and gives the
zones as rules of thumb with their species spread instead of one bare number.

## Rule 2: a cited figure must stay cited

Added to `verify_kit_consistency.py`: any figure that carries a citation
somewhere in the kit must not appear uncited on another page.

**A first attempt matched any figure of three or more significant digits and
returned 49 hits, of which one was real.** 100, 180, 225 and 0.05 are slider
maxima, compass bearings, CSS widths and p-value cutoffs — they are everywhere.
Distinctiveness is not magnitude; it is that **nobody writes the number by
accident**. A fingerprint is a decimal carrying three or more decimal places, or
two that do not end in 0 or 5.

On this kit exactly one figure qualifies. That is stated rather than hidden: the
rule is narrow, it asserts it is not vacuous, and it caught the one thing in
range.

## Two decorative alternatives, deleted

The citation matcher was written with three alternatives — `(Author Year)`,
`<span class="who">`, and a bare `after Author Year`. A mutation sweep deleted
the parenthesised one and **nothing noticed**: the bare pattern already matches
the author-year *inside* the parentheses, so the alternative was decoration and
the fixture asserting "all three forms are read" was a tautology, every test
string passing through the bare form.

The span form is not redundant, and now has a fixture that says why: one glossary
entry cites **a year with no author at all**, which the bare pattern — which
requires a capitalised author immediately before the year, so that "the
2026-08-09 audits" is not read as a citation — cannot see.

That bare form was itself added because a fixture failed honestly: "after
Reineke 1933" *is* a citation, and a detector that cannot read it calls a cited
page uncited.

## Still open

- **32 claims remain on the `audit_claims` worklist.** The ones triaged here are
  done; others still look citable rather than unsourced — the 30–300 plate-count
  window, DBH at 1.37 m, the 65–66 °C thermophile ceiling on `soil-bench`.
- Rule 2 sees one fingerprint today. Rule 1 watches one glossary entry. Both
  grow with the kit rather than with a list, but neither is broad yet and this
  ADR should not imply otherwise.
- `collection-sheet` and `stand-sheet` still publish figures the repo
  contradicts (ADR-050); `fungal-characters` is still blocked on the publish
  gate.

## The rule this adds

> Where the kit has paid for a citation, that citation is part of the number.
> A figure that travels to another page without it has become folklore again.

## Sources

- Shaw, *Reineke's Stand Density Index: Where Are We and Where Do We Go From
  Here?* — USDA Forest Service.
  https://www.fs.usda.gov/rm/pubs_other/rmrs_2006_shaw_j006.pdf
- Woodall et al., *Determining maximum stand density index in mixed species
  stands* — USDA Forest Service (Long & Daniel 1990 thresholds).
  https://www.nrs.fs.usda.gov/pubs/jrnl/2005/nc_2005_Woodall_002.pdf
- *FGROW Stand Density Management Diagrams for natural Pl and Sw in Alberta*
  (RDI 0.55 lodgepole pine, 0.45 white spruce).
  https://friresearch.ca/wp-content/uploads/2023/01/FGROW_SDMD_PlSw_20230101.pdf
