# ADR-071: the suite that could not testify, and a plot nobody had looked at

**Status:** Accepted and implemented — `tools/reach.py` (new),
`tools/verify/verify_publish_reach.py` (new, 6 checks, the kit's 55th suite),
`tools/verify/verify_label_escaping.py` (27 → 23, and the four that left are in the new file),
`tools/verify/verify_ord.py` (101 → 108).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-039, ADR-055 (reachability is not staleness), ADR-069, ADR-070

---

## Context

ADR-070's guard does its job by throwing suites out of a sweep, and the first thing it threw out was
worth keeping.

## 1. A suite that had to be excluded, and the half of it that did not

`verify_label_escaping` was excluded from every sweep of all five pages it covers, with the reason
printed: *fails on a comment appended to the page — it is measuring bytes, not behaviour*. That is
true of its section 5, which compares each page against a publish digest. It is not true of sections 1
to 4, which are the actual escaping rules, are properties of the source, and are exactly the witnesses
those five pages most need.

ADR-055 had already had to separate these two ideas once — **reachability is a property of the source,
staleness is a property of the published copy** — and the file kept both anyway. The cost stayed
invisible until something started measuring what a suite can testify about.

Split. The staleness requirement is `verify_publish_reach.py` and stays byte-sensitive, because that
is what it is for. The escaping rules stay where they were and are byte-insensitive again. The
detector they both need — the label scanner, the assignment tracer, the ALL-CAPS-table-that-grows
rule — is `tools/reach.py`, imported by each, because two copies of that tracer would drift and a
drifted tracer fails **open**: it calls typed input a constant.

Measured, on a scratch copy with a comment appended to `selection-log.html`: `verify_label_escaping`
22/22, `verify_publish_reach` 5/6. Which is the split working in both directions.

The tracer's own fixtures stayed with the escaping suite rather than moving with the tracer. They are
checks about whether the detector is right, and `verify_publish_reach` only consumes its answer.

## 2. The rule that went blind on the line it was written for

Re-seeding ADR-069's double escape into `selection-log` to canary the split — and it **passed 22/22**.

The pre-escape rule was a single-line regex anchored with `re.M`. Fixing the page split that return
across three lines and added an explanatory comment, and the rule stopped being able to see it. The
fix defeated the check written to police the defect the fix repaired, and would have gone on doing so
until somebody re-introduced it.

Worse in the other direction: the comment I added *says* `NOT esc()`, so a rule that reads comments
flags the correct code as the defect.

It now matches a brace-bounded **option literal** — an object carrying `value:` beside a `label:` or
`sub:` that calls an escaper — with comments stripped first. `[^{}]*` keeps it inside one literal, and
has the useful side effect that a control's own options never match, because that object has nested
braces. Measured across all thirty-nine pages: **zero hits clean, one hit with the defect re-seeded**,
and the fixture is now the line in the shape it is actually in.

## 3. Ordination: 75% → 100%

Two survivors, both real, and both in the half of the page this suite had never looked at. `verify_ord`
checks Bray-Curtis against scipy, PCoA eigenvalues against numpy, NMDS stress against scikit-learn's
SMACOF — the numbers are checked against three independent implementations. Neither survivor was a
number.

**`n <= k + 2` → `n < k + 2`.** NMDS in k dimensions can place n ≤ k + 2 points to satisfy any ordering
exactly, so a stress of zero there is arithmetic and not a finding — and the page says so, in a
sentence beside the figure. The suite tested the figure and never the sentence. Measured at the
boundary, both sides, **both at stress 0.000**: four sites carry the warning, five do not. So the
check isolates the count, which is the half the mutation touched — a fixture that differed in stress
as well would have proved nothing about the guard.

**`Math.max` → `Math.min` in `scaler()`.** The function that maps a coordinate range onto an axis.
Expecting the plot to collapse, I measured instead: the points are thrown **out of the frame** — cx up
to 1739 in a 680-wide viewBox, cy negative. So the check is that every drawn point is inside its own
frame, plus, because a scale that collapsed everything onto one spot would also satisfy that, the
points must use more than half of each axis.

Nothing in this kit had ever asserted anything about where a point was drawn.

The other six mutants were killed by `fek_emit`, `keep_emit`, `verify_offline_slice` and `verify_ord`
itself — including the shared webfont loader's `if(!l) return`, which ADR-065 recorded as *"appears on
every page in the kit and nothing tests it, which is worth its own look"*. It is tested: ADR-066's
loader work made `verify_offline_slice` a witness for it on every page. That open question is closed,
and it closes the twelve loader-only pages with it.

## Cost

`verify_ord` 101 → 108, `verify_label_escaping` 27 → 23 with 6 in the new file, `reach.py` new. No page
changed. **55/55 jobs green, 3902 checks.**

**Swept: 21 pages, 18 to go — 6 with code of their own, 12 the shared loader.**
