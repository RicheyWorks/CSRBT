# ADR-173 — The field notebook's outputs, read — and the notebook gets a suite

**Status:** accepted · **Date:** 2026-09-09 · **The notebook hands over three things — its .eco lines, a CSV, a print — and nothing read them; and it was the one data-entry page in the kit whose arithmetic no suite held. Both are closed: the task reads all three byte for byte, and a new `verify_fn` holds the page's figures and exports to independent statements, then holds the task's literals to the same.**

## A page with a task and no suite

ADR-153's `audit_outputs` listed the field notebook next after the experiment
guide: three exports, none read. Looking for the suite to pin the literals in
(ADR-172's rule: the page's own suite states what the export must be, from the
grammar, and holds the task to it) turned up that there was none. Every other
data-entry page has a `verify_<page>`; the notebook's Shannon, Morisita and
Lincoln–Petersen figures were held only by the task, to literals a reader was
asked to check by hand.

## What changed

**The task presses every export and holds what left**, in the state ADR-165
leaves the page in (three species to ten individuals, quadrats 0 1 2 9, five
marked / four caught / two recaptured, forage ×4 and preen ×2, the session
stamped `oak ridge, plot 3 — R. Ellison — 2026-09-09`):

- `Copy .eco lines` → one clipboard payload, held **byte for byte**: the two
  comment lines, `data: focal forage=4 preen=2`, `data: site species-a=6
  species-b=3 clover=1`, the quadrat comment, `model: markrecapture 5 4 2`,
  the note.
- `Copy CSV` → one clipboard payload, held byte for byte: fifteen rows under
  `section,item,count` — and the site, which carries a comma, comes out
  quoted (`"oak ridge, plot 3"`), so a spreadsheet reads one field and not
  two. That is the one claim on this page a reader could not check by
  looking at the screen.
- `Print / save PDF` → exactly one payload, a print.
- Then the counters and the `.eco` box are read once more, unchanged.

**`tools/verify/verify_fn.py` (new, 21 checks).** It drives the notebook to
the same state through its own controls and holds, from formulas stated
independently of the page's JavaScript: Shannon H′ = −Σ p ln p, Pielou J′ =
H′/ln S, Hill N1 = e^H′, the quadrats' sample variance/mean and Morisita's
n·Σx(x−1)/(N(N−1)), the "clumped" reading above 1.4, and Lincoln–Petersen
N = M·C/R, with the R = 0 case saying *undefined* in words. Then the exports:
the `.eco` lines from the grammar, the CSV from RFC 4180, the print counted
once. Then the **task's** literals — the `.eco`, the CSV, the print, and the
figures N̂ ≈ 10, H′ 0.90, Morisita 2.24 — held to those same statements:
change `Q4,9` to `Q4,8` in the task and the suite fails.

## What moved

    field-notebook outputs      0 → 3 of 3 held        ceiling 3 → 0
    the kit's unread outputs   18 → 15 of 66           (9 pages still hand something over unread)
    page-field-notebook-science   80 → 95 confirmed, 0 refuted
    verify_fn                   new, 21 / 21           (the kit: 75 → 76 suites)

No page was edited: a task, a new suite, and the ledger.

## Held

- The date is entered by the task (`2026-09-09`), so both exports are fully
  deterministic and are held whole — unlike the experiment guide's
  pre-registration, which stamps today.
- The notebook's `holdable` buttons fire once per click and repeat on a long
  press; the suite clicks, as the task activates, and each tap counts one.
- Not done here: food-web (3), ordination (3), deployment-log (2),
  soil-recipes (2), farm-scout, pheno-tracker, field-season, soil-bench,
  eco-protocol-library. Same shape, one page a slice.
