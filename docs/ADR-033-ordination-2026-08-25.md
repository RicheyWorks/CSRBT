# ADR-033: Ordination, and the number that says whether to believe the picture

**Status:** Accepted and implemented — `docs/ordination.html` (the kit's 23rd instrument), engine in `tools/ord.py` v1.0.0, `tools/verify/verify_ord.py` at 82 checks, canaried against five seeded faults. Cross-page navigation moved to `tools/nav.py` in the same slice.
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** `docs/ecology.html`, and the rail on all fifteen instrument pages

---

## Context

The Relevé page has said, in its own words, for several slices: *"It does not do classification,
ordination, or indicator-species analysis — those need many plots and a statistics package."* That was
honest and it was also a hole. The kit could produce a defensible community matrix and then had nothing to
do with it.

Grepped across all thirty-four pages before this slice: **NMDS, PCoA and Bray-Curtis appeared by name in
zero of them.**

## Decision

**One page, both methods, and the diagnostics given equal billing with the picture.**

The engine lives in `tools/ord.py` and is inlined by `tools/ord_emit.py`, the same shape as the Field Entry
Kit and the Darwin Core exporter, so the suite has a source to read a version from rather than a frozen
constant to go stale against.

### Why the diagnostics are not a footnote

A two-dimensional map of a thirty-dimensional dataset **always draws**. It draws for a real gradient and it
draws for random numbers, and the two pictures look equally convincing. That is the whole problem, and it
is why this page gives stress, the Shepard diagram, start agreement and the eigenvalue spectrum their own
tab rather than a line of small print.

The page ships with two demos that make the point without any argument:

| Demo | What it is | Stress | Starts agreeing |
|---|---|---|---|
| Two gradients | 24 species with unimodal responses along two environmental axes | **0.034** | 12 of 12 |
| No structure at all | the same 20 sites and 24 species, counts drawn at random | **0.212** | **1 of 12** |

Same picture-shaped output. One of them means something.

### The honesty gate on the stress bands

The &lt;0.05 / &lt;0.10 / &lt;0.20 bands are Clarke (1993), *Austral Ecology* 18:117–143. They ship under
**gate level 2 — labelled a convention** — and the page says so in the verdict itself, not only on the
method tab, because the verdict is the sentence people screenshot. It also prints the **site count next to
the band**, because stress rises with the number of points for geometric reasons alone: 0.15 from forty
sites is a better result than 0.15 from ten, and a bare band hides that.

Above 0.20 the page stops helping read the picture. That is a refusal, stated as one.

### Things the page will not do

- **It will not run on fewer than four sites.** A two-dimensional ordination of three points is exact by
  construction; its stress of zero is a property of the geometry and says nothing about the data.
- **It draws no axis numbers on an NMDS plot.** An NMDS configuration can be rotated or mirrored freely
  without changing its stress in the fourth decimal. Software that labels the axes `NMDS1`/`NMDS2` is
  naming an arbitrary basis, and "axis 1 represents moisture" is a claim about the arrangement, not the
  axis.
- **It is not a test.** No p-value, and PERMANOVA/ANOSIM/Mantel are named as the tools for that question —
  along with the warning that running one on the data that suggested the grouping is circular.
- **It exposes the two transforms `vegan::metaMDS` applies silently** — square root and Wisconsin double
  standardisation — as switches, because most people who use that function do not know they happened.
- **Euclidean distance is offered and labelled as usually wrong here**, with the trap named: on community
  data it typically gives a *lower* stress than Bray-Curtis, because a dissimilarity that saturates less is
  easier to fit in two dimensions. Lower stress is not a better ordination.

### Negative eigenvalues

Bray-Curtis is semi-metric and PCoA on it produces negative eigenvalues — 8 of 20 on the page's own demo,
holding 4.6% of the total absolute variation. The page counts them, colours them red on the scree plot, and
says that the "83.3% of variation explained" above is computed over positive eigenvalues only. That figure
is not wrong; it means something other than what it looks like, and the difference is the whole point.

## What the verification found

Every number is checked against an independent implementation: Bray-Curtis against **scipy**, the PCoA
eigenvalues against **numpy**'s symmetric solver (the page uses cyclic Jacobi — a different algorithm), and
the NMDS stress against **scikit-learn's SMACOF**, which minimises the same objective by an entirely
different route and lands at 0.0341 against the page's 0.0340. Where a library is absent the suite prints
`SKIP` and says the check *did not run* rather than counting it as a pass.

Two findings came out of canarying, and both were worth more than the canary:

**1. A convergence artefact shipped as a result.** The first NMDS used a fixed step size. It was still
descending after six thousand iterations, which means the stress it reported was a property of the
iteration cap rather than of the data. Replaced with an adaptive step that grows while it helps and halves
when it does not; the same problem now converges to 1e-12 in three hundred iterations.

**2. The eigenvalue check could not have caught a broken PCoA.** Seeding a fault — dropping the column and
grand-mean terms from the double centring — changed nothing the suite was looking at. Investigated rather
than patched: the missing terms remove a rank-one component lying in the constant direction, and **the
spectrum never sees it**. Verified over forty random dissimilarity matrices: eigenvalues agree to 5e-13,
while coordinates move by up to 2.5 units. Eigenvalues are the wrong thing to test. The suite now checks
the **identity** instead — PCoA of a genuinely Euclidean distance matrix must reproduce that matrix exactly
— which catches the fault at 2.1e-01, along with a centroid check. The comment in `ord.py` now tells the
next reader why those apparently redundant terms must stay.

A third change came from the same pass: the suite had asserted *twelve of twelve starts agree*. Multi-start
NMDS is stochastic by design and one start landing in another basin is an ordinary outcome, so that
assertion would have failed on perfectly correct runs. It is a majority test now. An assertion that fails
on non-defects is the frozen-constant failure mode wearing a different hat — this is the seventh instance
found this month.

## The rail, while we were here

Adding a page meant editing the navigation rail in fifteen instrument pages by hand. Measured before
touching it, those rails had drifted badly: **Micro Bench appeared in 4 of the 15**, Cell Bench in 4, and
rail length ranged from 9 chips to 18 — so a student on one bench could not reach the other. Same failure
ADR-031 named for entry controls, one layer up, and the same fix: `tools/nav.py` holds the chip list and
`tools/nav_emit.py` is the only writer. Adding an instrument to the kit is now one line.
