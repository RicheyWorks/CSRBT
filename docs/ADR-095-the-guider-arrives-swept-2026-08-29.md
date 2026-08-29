# ADR-095 — The guider arrives swept

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-019 (the classroom seam), ADR-022 (battle methodology), ADR-045 (the mutation sweep), ADR-065 (a page with no suite)

## The page

The kit teaches ecology with instruments; nothing taught the *method*. `experiment-guide.html`
is the fortieth page: how to run an experiment in this ecosystem, for scientists and engineers,
built in four slices in one day —

* **Method** — the five commitments, each carrying its receipt: the rule written before the run
  (524× against a 5× bar fired; 191% against 25% priced a workaround dead; 181 B against 1 KB
  stayed held — two of three verdicts said no, and all three were kept), the pinned seed, warm-up
  off the clock (the 3.6× cold-JIT penalty of ADR-022), median-of-3 with decomposition, and
  measuring the realized thing (Splay benchmarked with splaying disabled).
* **Designer** — two tracks that both end runnable. The ecology track emits a `.eco` and its
  gradle line, and *imports* one back (paste, file, or drop — the same reverse path ADR-027 cut
  for the Workbench); a pre-flight lint applies `ExperimentSpec.parse`'s own rules before the
  runner ever sees the file, and warns UNGRADEABLE for a hypothesis naming a community that
  doesn't exist or comparing a phase to entered data. The engineering track emits a
  pre-registration and a JUnit skeleton, then closes its loop: measured rows compute totals and
  the ratio against the floor, and a verdict — FIRES / STAYS HELD / PRICED DEAD — can only be
  declared once a rule and a complete row exist. The page computes; it never decides.
* One parser truth surfaced while mirroring it: `distance`'s neutral value is 0, not 1
  (`parse` defaults `distance = 0`), so the emitter's old drop-if-1 rule silently changed
  `factor: distance 1` into isolation-free. Fixed, with the hint text corrected.
* The day's audit sweep found the page's one print fault — the inactive Designer track was
  `display:none` on paper, losing half the document — fixed; every kit audit now reports zero
  on the page, and the webfont loader is byte-identical to the shared one (ADR-066).

## The sweep

A new page lands in `sweep_ledger.py`'s NOT YET SWEPT column the moment the file exists
(ADR-088's arithmetic, not anyone's memory). So the page was swept on arrival, same day,
before its suite's green had ever been trusted for anything.

First run: **25 mutants, 11 killed, 14 survived** — a 64-check suite measuring less than it
seemed to, which is exactly what the sweep exists to say. Eleven survivors were holes:

* the copy path was never exercised — neither the clipboard branch nor the no-clipboard
  fallback, on a page whose main verb is *copy the protocol*;
* nothing pinned the JUnit skeleton's content — `Math.max(1, floor)` could become
  `Math.min` and every check still passed, in the very text that teaches divide-by-floor;
* checklist box 10 sat outside both `i <= 10` loops' mutated bounds — never wired, never cleared;
* a dataset could take a phase's name if that phase was *first* (`indexOf >= 0` at seat 0 —
  the classic off-by-one, sitting in the one seat the suite never tried);
* a note targeting the first community failed to attach under the same mutation, untested for
  the same reason: the suite's example targeted seat 1;
* the smallest legal `data:` line — label plus one count — was never imported;
* a blank measurement row could print the token `undefined` into the report table, and an
  undeclared verdict could render `**VERDICT: undefined**` — the NaN-in-session.json failure
  class (frontend verification 2026-08-17, J1), reborn in markdown;
* `eulerlotka`'s refusal message could misquote its own rule.

The suite grew 64 → 82, each new check written to kill a named survivor. Re-swept:
**20 killed, 5 survived, 0 fresh — mutation score 80%.** The five are examined and recorded
in `KNOWN_EQUIVALENT` with the measurement that settled each: `fmtRatio`'s boundary operators
agree at the only point they differ (r = 10 renders 10× both ways); `rowComplete`'s
defined/non-empty clauses are subsumed by `isFinite(parseFloat(...))` — kept for readability,
recorded rather than rewritten to dodge a mutant; and `Array.join` renders a pushed
`undefined` as the empty string, one space of markdown padding that markdown renders
identically.

## The column reaches zero

With this row the ledger's NOT YET SWEPT column is empty: every page in the kit has had its
suite's teeth measured at least once. The tally is computed from the rows and the `docs/`
glob, so the next page added re-opens the column by itself — this ADR pins no count.
