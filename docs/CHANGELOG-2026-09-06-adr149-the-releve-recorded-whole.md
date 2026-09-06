# Changelog — 2026-09-06 — ADR-149: the relevé, recorded whole

The fourth page taken whole, and the densest in published method of any in the
kit: seven named indices on one sheet, and the task drove three cover classes.

## The task — `tools/tasks/page-releve-science.json`

30 steps → **109**. The plot header, the records with strata and phenology, the
analysis, Floristic Quality Assessment, the wetland prevalence index, the
line-point transect, a voucher, Darwin Core coordinates, and a refused pack.

```
releve.html      7 → 44 of 44 fields   (45 → 159 confirmed expectations)
the kit        312 → 349 of 520 fields  (60% → 67%)
```

Four pages are now entered whole: collection-sheet (59 of 63, four reagent rows
deliberately blank), stand-sheet, ecology-lab and relevé.

## Seven methods, recomputed

Braun-Blanquet and Daubenmire midpoints; Shannon and Pielou over summed midpoint
cover; the growth-form spectrum; **Swink & Wilhelm's FQI** and **Miller &
Wardrop's adjusted FQI**; the **Corps prevalence index** and its 3.0 threshold;
line-point intercept on a planned denominator; and Chapman & Wieczorek's
point-radius.

```
3 taxa, 2 families, H′ 0.53, J′ 0.48, 1.7 effective, dominant at 80%
4 taxa                → 0.67, 0.48, 1.9, 77%
FQA 2 of 3 natives    → mean C 4.50, FQI 6.4, adjusted 31.8, "partial score"
FQA 3 of 3            → 4.33, 7.5, 37.5
prevalence index      → 4.77, above 3.0
50 m at 1 m ×2        → 100 points; at 0.5 m → 200
5 top hits, 4 bare    → 5% foliar, 4% bare, "91 points still to read"
30 m GPS, 100 m² plot → 43 m, of which 7 m is the plot itself; 5402 m unknown datum
```

## Three claims the sheet makes that nothing was checking

**The scale is a method parameter.** Braun-Blanquet's class 2 and Daubenmire's
class 2 are both 5–25% and both a midpoint of 15%, so the recorded class alone
does not say what was measured. The task switches scales and holds both method
lines in the export.

**Blank means unscored, and empty means nothing recorded.** With no taxa the FQA
and wetland boxes hold nothing at all — not a zero index. With two of three
natives scored the FQA says *partial score* and names the count.

**Cover comes from the planned denominator.** Five top-canopy hits on a 100-point
plan is **5%**, not 100% of the five read — and the sheet says *91 points still
to read*. Reporting cover from an unfinished transect is the standard way to get
a confidently wrong number out of this method.

## The oracle grew a second formatter

The lab prints through `toLocaleString` (ADR-148); the relevé prints through
**`toFixed`**, which keeps trailing zeros — mean C is `4.33` and an all-FAC
plot's prevalence index is `3.00`, not `3`. Two formatters, adjacent pages. The
oracle ports both and compares each figure against the one its own page uses.

## Held

- A held index is not a validated one: the FQI is computed from C-values a
  regional panel assigns, and the page will not invent them.
- The prevalence index is one of three criteria, and the task holds that sentence
  as well as the number.
- `experiment-guide.html` at 16 of 52 is the largest gap left.

## Docs

`docs/ADR-149-the-releve-recorded-whole-2026-09-06.md`; `docs/AI_HARNESS.md`.
