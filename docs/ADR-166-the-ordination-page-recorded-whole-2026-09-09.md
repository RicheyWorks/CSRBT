# ADR-166 — The ordination page, recorded whole

**Status:** accepted · **Date:** 2026-09-09 · **The NMDS/PCoA ordination page ran its whole pipeline but chose none of the four settings that shape it: the transform, the distance metric, the dimensions and the random starts were entered by nobody. Now 6 of 6, each driven and returned to its default so the seeded ordination is unchanged.**

## The ordination nobody set up

`ordination.html` is the community-ecology page: give it a sites × species
matrix and it runs an **NMDS** (Kruskal 1964, rank-order only, iterative) or a
**PCoA** (Gower 1966, eigenanalysis), reads the stress against Clarke's
< 0.05 / < 0.10 / < 0.20 bands, draws a Shepard diagram of the 190 pairs, and
counts the negative eigenvalues Bray-Curtis produces when it violates the
triangle inequality. Its task did all of that — parsed a 20 × 24 two-gradient
demo, ran the ordination in two dimensions, walked PCoA and a row of data edge
cases — but it was the kit's **worst-covered data-entry page**: **two of its six
value-carrying fields had ever been entered**.

The four never driven are the four settings the ordination silently depends on:
the **square-root transform** chip, the **Bray-Curtis dissimilarity** dial, and
the **dimensions** and **random-starts** steppers. An ordination read off
defaults nobody chose is a picture whose transform and distance metric — the two
decisions that decide what "similar" even means for this data — were made by no
one.

## Entered whole, and the picture held still

The NMDS here is seeded — `rng(seed || 42)`, a fixed seed — so it is fully
deterministic: the same matrix and the same settings reproduce the same stress
and the same coordinates, bit for bit. That is what makes this slice honest. The
existing scenario is kept verbatim — the 20 × 24 parse, the 2-D stress with its
Clarke band, the 190-pair (20·19/2) Shepard fit, the PCoA axes and their
negative-eigenvalue share, and the final quoted-CSV parse to 4 sites × 3 species
all hold — and the four untouched controls are driven, each from its own pane
and **returned to its default**:

- the **transform** chip is a multi-select, so it is toggled off and back on —
  ending at the default (square root + Wisconsin);
- the **Bray-Curtis** dial is re-selected (it is non-clearable, so re-activating
  it keeps `bray`);
- the **dimensions** stepper is set to 2 and the **random-starts** stepper to
  12 — the values they already held.

Because every control ends where it began and the seed is fixed, the ordination
is unchanged, and the quoted-data parse is read once more and held to confirm
the page is where it was.

## What moved

    ordination   2 → 6 of 6 fields entered       (the kit's worst-covered
                                                  data-entry page, now closed)
    ordination  61 → 70 confirmed expectations     0 refuted
    the kit     507 → 511 of 521 fields            (98%), 23 of 27 pages whole

## Held

Transform is a multi-select chip, so driving it without changing the result is a
toggle-off-then-on, not a single click. The dimensions and random-starts
steppers are reached as their `step_val` by label
(`@control:methEntry/dimensions`), and only the dimensions change re-runs the
ordination — random starts pushes its value without a run — so each control is
exercised while the picture it feeds stays exactly where it was. No page was
edited: a task-only slice, the sixteenth page driven end to end.
