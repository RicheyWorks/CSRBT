# ADR-158 — The selection log, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The selection log — the page that measures natural selection on marked individuals — was the kit's worst-covered data-entry page: 10 of 25 value-carrying fields ever entered. It is now entered whole, 26 of 26, and its three exports are read and held against an oracle for the first time.**

## The page that measures selection, half its fields never touched

`selection-log.html` is where selection stops being a story and becomes a
number. You mark individuals, measure a trait on each — with replicates, so the
page can tell you your own measurement error — record who survived or bred, and
it computes the **selection differential S** (the fitness-weighted trait mean
minus the mean), the **intensity i = S/σ**, and the univariate **gradient β**
(Lande & Arnold's regression of relative fitness on the standardized trait), and
then tells you what each one is and is not entitled to say.

Its task entered six birds, measured bill depth on each, let two die, and
checked the analysis — mean before 10.500, differential 1.000, intensity 0.586.
Good arithmetic, but **fifteen of its twenty-five fields were never entered**:
the cohort, the sex and age-class dials, the natural-history note, the episode
name, the fitness component, the measurement's occasion and observer, the
add-a-trait fields, the parent-linking pickers, and the two trait selectors on
the Selection and Heritability tabs. And **all three of the files it exports —
the measurements CSV, the one-row-per-individual CSV that is the input to a
multiple regression, and the study sheet — were read by nothing**. The page
whose entire product is a dataset you take away and analyze had never had that
dataset looked at.

## Entered whole, and every export checked

The existing scenario is kept intact — same six birds, same bill depths, same
two deaths, so **all of its selection-analysis assertions still hold** — and the
missing fields are driven around it. The sex and age dials are set once and
persist across the adds; the episode and fitness component are named; each
measurement now carries an occasion and an observer. A **wing-chord trait** is
added, a **seventh bird A7** is entered with a full cohort/sex/age record, given
a tarsus measurement, marked as a survivor, and **linked to A1 and A2 as its
parents** — A7 carries no bill depth, so it enters the pedigree and the exports
without disturbing a single figure in the bill-depth selection analysis.

Then all three exports are read and held against an oracle:

    measurements CSV   7 rows   individual,cohort,sex,age,trait,unit,value,
                                occasion,measurer,fitness,episode
    individuals  CSV   7 rows   one row per bird, trait columns to 3 dp, the
                                A7 row carrying dam A1 and sire A2
    study sheet                 the episode line, the fitness definition, and
                                per-trait n / mean / SD, bill depth n=6 and
                                the new tarsus n=1

**Nothing in the oracle is typed by hand.** A Python re-implementation of the
page's own statistics — `mean`, sample and population `sd`, the `reg` slope, and
JavaScript's `toFixed` reproduced with round-half-up on the Decimal of each
float — computes every differential, intensity, gradient, CSV cell and study-
sheet line, and the generator refuses to emit the task unless its selection
figures reproduce the six the page had already been asserting. The numbers on
both sides of every claim come from the same arithmetic; the test is that the
page and the oracle agree.

## What moved

    selection-log      10 → 26 of 26 fields entered      (the last worst-covered
                                                          data-entry page closed)
    selection-log      77 → 123 confirmed expectations    0 refuted
    its exports         0 → 3 read and held against an oracle
    the kit           433 → 449 of 521 fields              (86%), 15 of 27 pages
                                                          now entered whole

## Held

The seventh bird is deliberately outside the selection analysis: it has a tarsus
but no bill depth, so the trait's rows are unchanged and the differential,
intensity and gradient are exactly what they were — A7 exists to exercise the
pedigree, the second trait and a fresh measurement's metadata, not to move a
number that a reviewer is trusting. Cohort is entered on A7 alone and not on
A1–A6, because the cohort shows in the individual pickers' sub-line and setting
it on a bird changes the label the measurement picker matches — entering it
early would have broken the six picks the existing scenario depends on. And no
page was edited: this is a task-only slice, the eighth page driven end to end
with its arithmetic pinned.
