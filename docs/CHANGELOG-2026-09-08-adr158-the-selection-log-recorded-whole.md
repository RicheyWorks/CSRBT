# 2026-09-08 — ADR-158: the selection log, recorded whole

**The page that measures selection on marked individuals was the kit's
worst-covered data-entry page (10/25 fields). Now 26/26, with all three exports
read and held against an oracle.**

## Changed — `tools/tasks/page-selection-log-science.json`

54 → 92 steps, 77 → 123 confirmed expectations. The existing scenario is kept
verbatim — six birds, bill depths 8–13, two deaths — so every selection-analysis
assertion (mean before 10.500, differential 1.000, intensity 0.586, gradient
0.586) still holds, and the fifteen never-entered fields are driven around it:
cohort, sex and age dials, natural-history note, episode, fitness component, the
measurement's occasion and observer, the add-a-trait fields, the parent-linking
pickers, and the Selection/Heritability trait selectors. A wing-chord trait is
added, a seventh bird A7 is entered with a full record, given a tarsus
measurement, marked a survivor and linked to A1 and A2 as parents — A7 has no
bill depth, so it enters the pedigree and the exports without moving one figure
in the analysis. The measurements CSV, the individuals CSV and the study sheet
are read and held against a Python oracle that re-implements the page's own
`mean` / `sd` / `sdPop` / `reg` and JavaScript `toFixed`; the generator refuses
to emit unless its figures reproduce the six the page already asserted.

## Numbers

    selection-log.html   10 -> 26 of 26 fields entered   (100%)
                         0 -> 3 exports read and held
                         77 -> 123 confirmed, 0 refuted
    the kit             433 -> 449 of 521 fields          (86%), 15/27 whole

## Held

- The seventh bird is outside the selection analysis by design — a tarsus, no
  bill depth — so the differential, intensity and gradient are untouched.
- Cohort is entered on A7 alone: it shows in the pickers' sub-line, and setting
  it on A1–A6 would change the label the six existing measurement picks match.
- No page was edited — a task-only slice, the eighth page entered whole.
