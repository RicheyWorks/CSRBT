# ADR-233 — the report says what the numbers say

**Date:** 2026-09-21 · **Status:** accepted · **Chain:** ADR-232 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The standing goal has two halves: the harness must operate every science page,
and it must prove every report is correct. ADR-232 closed the first half's
backlog — all 21 science tasks have a blind trace. The second half had been
accumulating debt the whole time: every blind trial filed page defects and
fixed none of them, because each trial's slice was about the door.

The micro bench's operator (the eighth trial, ADR-230) filed three, and all
three were still live on origin. Each is the page SAYING something the numbers
did not support:

1. **The saturation warning asserted a direction.** With any point above OD
   0.6 in the growth fit, the page said the high points "flatten the line …
   and push µ down". The operator entered four points on the doubling line
   and one at OD 1.5 where the line predicts 0.8: µ went **up**, 0.6931 →
   0.8189, under a sentence saying it went down. Optical saturation makes a
   reading *low*, so a point above the line of the others is exactly what
   saturation cannot produce.
2. **The intermediate band was neither the rule nor the convention.** For
   S ≥ 17 / R ≤ 13 the page printed "13.5–16.5 mm" (R+0.5 to S−0.5). The rule
   it applies is S at ≥ S, R at ≤ R, I strictly between — so 13.2 mm reads I
   and sat outside the stated band — and for whole-millimetre readings the
   convention is 14–16.
3. **Organism and medium went nowhere.** `zOrg` and `zMed` were on the form,
   and not one line of script read them: not the zone list, not the bench
   sheet, not the zone CSV. A zone diameter left the page without the two
   things its interpretation depends on — on a page whose own refusal text
   says S/I/R "depends on the organism, the agent, the disc content, the
   medium and the method".

**The task encoded all three.** `page-micro-bench-science` held
`"13.5–16.5 mm"`, held the bench sheet byte-for-byte with "pushes µ down" and
a zone line with no organism, and held the zone CSV header without the two
columns. The oracle was certifying the defects. Every run of it since the
task was written was green because it agreed with the page, not with the
arithmetic.

## Decision

- **`satEffect(use)`** — the points above OD 0.6 in the fit are separated
  out; with at least three remaining, the fit is recomputed without them and
  the sentence says which way they moved µ, with both slopes and the
  percentage. DOWN: "which is what optical saturation does: the reading is
  low, so the line flattens." UP: "Saturation makes a reading LOW, so a point
  above the line of the others is not saturation: check the reading, the
  blank and the dilution before trusting it." Fewer than three remaining: it
  says the effect cannot be separated out, and names no direction. Box and
  bench sheet read the same function.
- **`bandText(S, R)`** — "Intermediate: above R mm and below S mm", plus
  "— 14–16 mm for whole-millimetre readings" when both breakpoints are whole
  millimetres (a single value when the band is one millimetre wide; "no
  whole-millimetre reading falls between them" when they are adjacent). The
  sentence is the rule the page applies, not a different one.
- **Organism and medium per zone.** Read at Add and kept on the zone — not
  read at export time, so editing the form afterwards does not rewrite a zone
  already recorded. In the zone list, the bench sheet (`… S   E. coli ATCC
  25922   on Mueller-Hinton`) and two new trailing CSV columns `organism,medium`
  (appended, so every existing column keeps its position). A save from before
  this restores with its zones intact.
- **The task says what the page should say.** Its three wrong expectations are
  corrected and it holds two more: the growth box's computed sentence and the
  zone list's organism and medium. Re-run: held.

## Verification

`verify_mb` 65 → 83, a new section on a fresh page per case, held against an
independent Python recomputation (ordinary least squares on ln OD, the page's
half-up rounding): UP (the operator's own data), DOWN (0.65 at 4 h, below
the line), TOO FEW (two points left), NONE (no box); the band at 17/13, 15/13
(one millimetre: "14 mm"), 14/13 (adjacent) and 16.5/13 (not whole: rule only);
13.2 mm reading I against 17/13; organism and medium in list, sheet and CSV,
kept per zone across a later form edit; an old save restoring.

**`tools/mutate_mb.py`**, a new runner (the board lists it): thirteen mutants
of the fix — the direction fixed at DOWN, the refit over the wrong points, the
percentage against the wrong slope, too few points refitted anyway, the old
sentence back in the bench sheet, the band back to R+0.5/S−0.5, off by one,
a one-millimetre band as a range, adjacent breakpoints claiming a reading
between them, the organism not read, the medium read at display time instead
of kept per zone, the CSV and the sheet dropping a value — each on a copy of
the tree against `verify_mb`. 13/13 killed.

## Held

- The other pages' filed defects (the list is in the handoff and in the ninth
  and tenth trials' provenance). One page per slice, oracle first: this slice
  found the task holding the defect, and the next page's task may too.
- `mutate.py --page micro-bench.html` would generate its own mutants of the
  whole page; `mutate_mb`'s thirteen are aimed at the three fixes.

## Lessons

- A task written by reading the page certifies the page. The expectation was
  copied from what the page printed, so it could only ever agree. The band
  was checkable by arithmetic and the saturation direction by a refit; the
  task held neither, it held the text.
- A form field that nothing reads is invisible to every check that reads
  outputs: the audits look at what a page prints, and a field that never
  reaches print leaves no trace to find.
