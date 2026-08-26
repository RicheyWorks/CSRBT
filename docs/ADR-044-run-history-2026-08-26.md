# ADR-044: Comparing grow cycles, and the only rigorous thing in that comparison

**Status:** Accepted and implemented — `tools/gh.py` v1.1.0 (run records, `runStats`, `compare`), KEEP wired into `docs/greenhouse.html`, `tools/verify/verify_gh.py` now 131 checks.
**Date:** 2026-08-26
**Deciders:** Richmond
**Touches:** `tools/keep_emit.py`, `tools/verify/verify_emitters.py`

---

## Context

ADR-043 shipped a monitor that answers "what is happening in this room" and "what did this run cost
per gram". The question actually asked at the start of that work was different and larger: *watch the
ratio of plant growth to money spent on electricity* — which is a question about **runs**, plural.
One cycle's g/kWh is a number. Whether it is getting better is the thing worth knowing.

Two follow-ons were on the list — persist runs, and compare them. They are one slice: **you cannot
compare runs you did not keep.**

## The problem with comparing grow cycles

Comparing two cycles is observational data with **n = 1 per condition**, no randomisation, no
control, and every variable moving at once — genetics, technique, plant count, the weather outside,
and where the grower decided the dry-down had finished. A difference between two runs **cannot tell
you what caused it**.

Every grow app in existence draws that chart anyway and lets the reader supply the causal story. It
is the most tempting lie available in this domain, because the chart is real, the numbers are real,
and only the inference is wrong.

## Decision: measure the grower's own repeatability first

There is exactly one rigorous thing available from a grower's own records, and it is what makes every
later comparison mean something: **how much their results move when they change nothing.**

Run three or more cycles at nominally the same settings, mark them **baseline**, and the spread of
those results is the noise floor of the operation. After that:

```
z = (this run − baseline mean) ÷ baseline SD
```

A new run is only news if it lands outside that floor. The page reports the distance in units of the
grower's **own** standard deviation, and reads it back in words — *inside your normal spread, not
news* / *at the edge, watch it, do not conclude from it* / *outside your spread, worth investigating,
still not a cause.*

**There is no p-value, deliberately.** z here is a distance, not a significance test. With a handful
of uncontrolled cycles a significance test would be theatre, and a p-value is the single most
abusable number that could have been put on this page.

Three refusals hold it up:

- **Under three baseline runs, no spread is computed at all.** A standard deviation from two points
  is arithmetic without information. The page shows the runs and refuses the comparison rather than
  printing a z-score that looks like an answer.
- **The sample SD (n−1), not the population form.** The population version divides by n and would
  flatter every small set by shrinking its spread. Every set here is small.
- **A run is excluded from the baseline it is judged against.** Otherwise every run drags its own
  reference point toward itself, and an outlier hides its own outlyingness.

## The worked example is the argument

Five generated runs: four baseline that differ by a few percent for no reason at all, and a fifth
labelled *"new light"* that yields **548 g against a 497 g mean — a 10% improvement**, exactly the
result a grower would post.

Its z on g/kWh is **+1.6**. At the edge. Not outside.

The whole page exists to make that one number visible before the conclusion gets drawn.

## What is stored, and where

A saved run is a **summary** — yield, energy, DLI, mean VPD, time outside band — not the log it came
from. A season of 30-second samples is megabytes and browser storage is a few, and a page that fills
it silently drops the oldest thing the user still needed. The raw log stays in the export, which is
the durable copy. KEEP's own doctrine applies unchanged: browser storage is recovery from a closed
tab, not a backup, and the page says so where it can be read.

## Verification

131 checks, up from 99. The new ones recompute the mean, the sample SD, the CV and z against Python's
`statistics` module — and one of them checks that the SD is **not** the population form, because
those two differ by a few percent on four points and a check that accepted either would test nothing.

**Ten seeded faults; eight caught on the first pass.** Two escaped, and both escapes were the same
error I have now made three times in one week:

- *A run compared against itself* passed, because the fixture used a **non-baseline** run — which the
  baseline filter had already removed, so self-exclusion never bit. Fixed with a baseline run.
- It passed **again**, because the baseline run chosen sat near the mean, where excluding it barely
  moves the answer. Fixed with the low outlier, where the two implementations give z = −1.4 and
  z = −4.9.

*Fixtures that cannot tell two implementations apart are not tests of the difference* (ADR-039). The
lesson keeps arriving because the discriminating case is never the obvious one.

## Consequences

`greenhouse.html` is registered in `keep_emit.py`, so its autosave layer is regenerated with the rest
rather than drifting — the omission this kit has been bitten by before.

**The rule this leaves behind:** before comparing two results, find out how much your results differ
when nothing changed. Without that number every comparison is a story, and with it most of the
stories go away.
