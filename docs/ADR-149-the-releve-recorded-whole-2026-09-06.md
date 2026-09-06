# ADR-149 — The relevé, recorded whole

**Status:** accepted · **Date:** 2026-09-06 · **The fourth page taken whole, and the densest in published method of any in the kit: seven named indices on one sheet. 7 → 44 of 44 fields, 45 → 159 confirmed expectations, and the kit reaches 349 of 520 fields (67%)**

## 1. Why this page

`releve.html` was the largest data-entry gap left after ADR-148 at **7 of 42
fields**, and it is the page that carries the most other people's arithmetic:
Braun-Blanquet and Daubenmire cover classes, Shannon and Pielou over summed
midpoint cover, a growth-form spectrum, Swink & Wilhelm's Floristic Quality
Index, Miller & Wardrop's adjusted FQI, the Corps of Engineers prevalence index
with its 3.0 threshold, line-point intercept cover on a planned denominator, and
Chapman & Wieczorek's point-radius. Seven named methods, one sheet, and the task
drove three cover classes.

## 2. What is held

| block | held to |
|---|---|
| the plot | the header line by line: recorder, date, coordinates, elevation, the method line, the community name, and `# site: aspect 225° · slope 18% · xeric · gravelly loam over limestone colluvium · bare 25% · litter 35%` |
| the records | three taxa → **3 taxa, 2 families, H′ 0.53, J′ 0.48, 1.7 effective taxa**, one non-native, the dominant at **80%**; a fourth at class 1 → 0.67, 0.48, 1.9 and **77%**; an add with no cover class adds no row |
| the spectrum | **80% of cover is shrub** |
| FQA | two of three natives scored → mean C **4.50**, FQI **6.4**, adjusted **31.8**, and the sheet says *partial*; three of three → **4.33**, **7.5**, **37.5**, and the partial sentence is gone |
| wetland | UPL/FACU throughout → prevalence index **4.77**, above threshold, *and a determination still needs hydric soil and hydrology* |
| line-point intercept | 50 m at 1 m in duplicate → **100 points**; at 0.5 m → **200**; five top hits and four bare on the 100-point denominator → **5%** foliar, **4%** bare, *91 points still to read* |
| Darwin Core | 30 m of GPS on a 100 m² plot → **43 m**, of which **7 m is the plot itself**; **5402 m** with the datum unknown |
| packs | a pack missing `sci`, `gf` and `nat` → *Rejected — 3 problems*, and *nothing loaded — your flora is untouched* |

Every figure is recomputed by a Python port of the page's own arithmetic.

## 3. Three claims the sheet makes that nothing was checking

**The scale is a method parameter.** Braun-Blanquet's class 2 and Daubenmire's
class 2 are *both* 5–25% and *both* a midpoint of 15% — the page says so in its
own method notes — so the recorded class alone does not say what was measured.
The sheet writes the scale into the export, and the task now switches to
Daubenmire and back and holds both method lines.

**Blank means unscored, and empty means nothing recorded.** With no taxa the FQA
and wetland boxes hold **nothing at all** — not a zero index, not a default. With
two of three natives scored the FQA reports *"Only 2 of 3 natives have a C-value,
so this is a partial score"* and names the count. The page's own words: *a blank
is honest, a guess is not.*

**Cover comes from the planned denominator, not from what was read.** Five
top-canopy hits on a 100-point plan is **5%** cover, not 100% of the five points
read — and the sheet says *91 points still to read*, so the percentages are
marked partial until the transect is finished. Reporting cover from an unfinished
transect is the standard way to get a confidently wrong number out of this
method, and the page refuses to.

## 4. The oracle grew a second formatter

ADR-148 established that the lab prints through
`Number.toLocaleString`, which rounds half away from zero on the shortest
round-trip decimal. The relevé prints through **`toFixed`**, which keeps trailing
zeros: mean C is `4.33`, and an all-FAC plot's prevalence index is `3.00`, not
`3`. Two formatters, in one kit, in adjacent pages. The oracle now ports both and
each figure is compared against the one its own page uses.

## 5. The numbers

    releve.html         7 → 44 of 44 fields   (45 → 159 confirmed expectations)
    the kit           312 → 349 of 520 fields  (60% → 67%)

Four pages are now entered whole: collection-sheet (59 of 63, four reagent rows
deliberately blank), stand-sheet, ecology-lab and relevé.

## 6. Held

- **A held index is not a validated one.** The FQI is computed from C-values a
  regional expert panel assigns, and the page will not invent them; holding the
  arithmetic says nothing about whether the C-values are right for the region,
  which is a question about the list, not the sheet.
- **The prevalence index is one of three criteria**, and the sheet says so in the
  same box as the number. The task holds that sentence, because a number that
  travels without it is the failure mode of the method.
- **`experiment-guide.html` at 16 of 52 is now the largest gap left**, followed
  by deployment-log at 17 of 37.
