# ADR-198 — The plot everyone calls 400: a printed figure and an exported column have to be the same measurement

**Status:** accepted · **Date:** 2026-09-13 · **ADR-197 closed six page defects and filed a seventh, because closing it moved three figures four tasks claimed. This is that slice. A circle of r = 11.28 m encloses 399.7312 m²; the stand sheet printed `400 m²` and `Expansion factor 25.0` while every column computed from it used the real 25.01681. The two printed figures agreed with each other — 10,000/400 *is* 25.0 exactly — and described a plot nobody measured, which is why nothing on the sheet and nothing in its suite could tell they were wrong.**

## 1. The shape of the error

A rounding you can see is not a defect. Two roundings, one visible and one
not, on numbers a reader is expected to multiply together, are.

    printed:   400 m²      EF 25.0        → 0.070686 × 25.0     = 1.7672
    exported:  399.7312 m²    25.01681    → 0.070686 × 25.01681 = 1.7683

The stem CSV's `ba_m2_ha` column carried the second. The banner, the field
sheet, the Darwin Core `sampleSizeValue` and the `samplingProtocol` string all
carried the first. A reader holding the printed sheet could not reproduce the
downloaded column, and nothing said which to believe.

The page had already made this exact argument about the smaller plot, in its
own fine print: *r = 5.64 m is EF 100.1, not 100.0*. And then printed that
plot's area as `100 m²`, which is the error it was warning about.

## 2. The fix, and what it deliberately does not move

Two decimals, and the trimming differs by term because the terms differ:

- **area** — trailing zeros trimmed to nothing, so a rectangle still reads
  `400` and a circle reads `399.73`, `99.93`.
- **factor** — trimmed to *at least* one decimal, so a rectangle still reads
  `25.0`. `EF 25` reads as a count, and four task claims rest on that decimal.

A 20 × 20 m plot is 400 m² at 25.0 exactly. It was never the bug, and the fix
that took its decimal away would have been a second one. There is a mutant for
precisely that: trimming the circle's zeros with the rectangle's included.

`fmtArea` now feeds the banner, the field sheet's plot line, `sampleSizeValue`
and `dwcProtocol` — one figure in four places, because a record that says 400
in one field and 399.73 in the next is arguing with itself.

## 3. Two more the same trial filed

**`associatedTaxa` was a Darwin Core column this sheet emitted and never
populated** — on a sheet whose Web pane records interactions naming the species
it tallies. The term wants *names of taxa associated with the occurrence*,
which is what an edge is. It is written as a sentence rather than a
`key: taxon` pair, because the pair form cannot say which end of the edge this
occurrence sits at and the page's own verbs do not invert without conjugating
them: `mule deer eats this taxon` is unambiguous read either way. Empty when
the species is in no recorded edge — the honest empty, rather than the
unpopulated one.

**A top height off one measured stem is not a stand figure.** The tile read
`top height m` whether it rested on one height or forty, and the convention it
names — the mean of the tallest fifth — means nothing at n = 1, where it is
just that stem. The sample now travels beside it as *its own tile*, not inside
the label: a figure whose **name** moves when the data moves cannot be followed
across a session, which is the instability the pheno tracker is already filed
for. Both properties have their own check and their own mutant, and the
key-stability one is asserted first so a label that swallows its sample size is
killed by the check that names that, not by the value check downstream of it.

## 4. The oracle is reconciliation, not a pinned string

The defect was that the page's two numbers agreed with each other. A check
recomputing them from the page's own state would have agreed too. So the
figures are read back **off the rendered sentence** and reconciled:

    printed area × printed factor = 10,000 ± 0.005 × (area + factor)

— the bound being what two figures printed to two decimals can carry, not a
tolerance picked to make the current numbers pass. `400 × 25.0` satisfies it
while describing the wrong plot, which is why the geometry check sits beside
it: `|printed area − πr²| < 0.005`, at three radii.

And the CSV column against the printed factor, which is the property that
actually failed:

    |ba_m2_ha − ba_m2 × printed EF| ≤ 0.005 × ba_m2 + …

Under the old `EF 25.0` a 30 cm stem misses that by 0.0012 against a tolerance
of 0.0004. Under `25.02` it lands. That inequality is the whole slice in one
line: *a reader who has only the printed factor recomputes the exported column
to within what that factor's own precision allows.*

## 5. The tasks moved, on purpose, and the trials did not

This is the fix ADR-197 could not make. It moves nine claims in
`page-stand-sheet-science.json` and the goal prose that frames them. The three
blind trials keep the protocols frozen beside them, so their scores are
untouched — which is what freezing them was for, exercised for the first time
on a fix rather than described.

Two of the rewritten claims taught something. `"Expansion factor 25.0"` as a
`contains` claim is satisfied by `"Expansion factor 25.02"`, so tightening the
circle's claim and leaving the rectangle's alone would have left two claims
that pass either way; both rectangle claims now pin the character after the
decimal. And `dwc-50` reads the banner while the design is a **rectangle** —
the same string is the right claim there and the wrong one twelve steps
earlier.

## What moved

    verify_ss           84 → 114     mutate_report    124 → 134 / 134
    verify_report      208 → 223     verify_dwc       147 → 150
    verify_tasks       368 → 371     page defects closed        3

## Held

- The stand sheet's silent no-op exports (`ok: true`, `changed: false`, no
  payload when there is nothing to export) are still filed. So is `Clear trial`
  raising no confirmation dialog — the door raises the call to DESTRUCTIVE on
  the label alone, which is the guard that matters.
- The collection sheet's stale voucher label and its unlabelled guild-spectrum
  percentages, and the pheno tracker's asymmetric exports, are still filed.
- `ba_m2_ha` still carries four decimals off the unrounded factor. That is the
  right number; the defect was never the column, it was that the sheet printed
  a factor you could not get back to it from.
