# ADR-242 — A voucher says nothing it was not told

**Date:** 2026-09-23 · **Status:** accepted · **Chain:** ADR-241 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The seventh blind trial (ADR-229) filed one defect on the relevé: the
voucher's *material* and *phenophase* dials defaulted to **in flower** and
**flowering**, so a voucher recorded without touching them carried
`[in flower, flowering]` onto its label. That is a statement about the
specimen the collector never made, on the one document a herbarium takes as
evidence, and it was written in the collector's name.

The task never saw it. It chose *in fruit* and *dispersing* before recording,
so the default was never on its path.

The occurrence dial on the relevé pane also defaults, to *vegetative*, and
that one is right: most plants in a relevé are vegetative, and the default is
the common case. A specimen's material is different. It is the thing that
decides whether the specimen can be determined at all, and there is no common
case to assume.

## Decision

- **Material and phenophase start unset.** The hidden fields are empty and no
  dial button is lit.
- **A voucher is not recorded until its material is said.** *"Say what the
  specimen is — in flower, in fruit, flower & fruit, or sterile. Nothing
  recorded."* The collection number is kept.
- **A voucher with no phenophase records none.** Its record holds `""`, its
  list row and label read *phenophase not recorded*, the export line reads
  `[fr, phenophase not recorded, 1 sheet]`, and the confirmation says *— no
  phenophase recorded*.
- **`vouNote`, under the dials, says what the next voucher will be recorded
  as:** *"The next voucher will be recorded as: in fruit · dispersing ·
  frequent."* The dials carry forward between specimens, as the selection
  log's do (ADR-238), and the line is how a carried value is seen before it
  is written. With nothing chosen it reads *material not recorded ·
  phenophase not recorded · abundance not recorded* and says a voucher will
  not be recorded until the material is.
- The occurrence dial keeps its vegetative default.

## Held by

- **The task** (`page-releve-science`): 183 → **187** confirmed. Before the
  dials are touched it holds the unset line word for word, presses *Record
  voucher* and holds the refusal, the absence of the number from the sheet
  and *No specimens yet*. After *in fruit*, *dispersing* and *frequent* it
  holds the line, then the record `[fr, dis, 3 sheets]`, the list row, and
  that *in flower* is nowhere on it. **Refuted on the old page** at the first
  new step. The goal says so.
- **`verify_rv`**: 81 → **94**. Against the record KEEP holds, not only the
  sentence: the hidden fields empty and no button lit; the refusal leaves the
  record at zero vouchers with the number kept; a voucher recorded with a
  material and no phenophase holds `phen: ""`; its label, list, export line
  and toast say so; the carried dials are named before the second voucher and
  the second voucher carries exactly that; the occurrence dial still defaults
  to vegetative.
- **New runner `tools/mutate_rv.py`**, 12 mutants, all killed on the second run (the first left two alive: the label check read the list row rather than the label, and the occurrence-dial check read a hidden field that carried the default on its own): each default back, the
  hidden field's old value, recording without a material, toasting but
  recording anyway, an unset phenophase written as flowering, the label and
  the export line calling it by its empty id, the line never saying a
  material is missing, the line not repainted, the toast silent, and the
  occurrence dial's default lost.

## Numbers

| | before | after |
|---|---|---|
| page-releve-science | 183 confirmed | **187** |
| verify_rv | 81 | **94** |
| mutate_rv | — | **12** |

## Held

- **The pheno tracker, stand sheet and ecology lab** filed defects.
- The relevé's line-point entry keeps species and stratum after *+ hit*, so
  repeated presses add repeated hits. Filed as designed (ADR-229); a note of
  the ADR-238 shape would say what the next hit will be. Trigger: an operator
  who adds a hit they did not mean.

## What the first run found

The soil suite hub advertises the relevé suite's count, and the page still said 81/81 after the suite grew to 94; `verify_advertised` caught it, the page edit came after the run, and the tree gate (ADR-241) sent the run round again.

## Lessons

- A default is a statement. Where the common case is real (vegetative), the
  default is right; where there is no common case (a specimen's material),
  the default is the page speaking for the collector.
