# 2026-09-09 — ADR-166: the ordination page, recorded whole

**The kit's worst-covered data-entry page (2/6 fields): the transform, the
distance metric, the dimensions and the random starts were chosen by nobody.
Now 6/6. The kit reaches 98%.**

## Changed — `tools/tasks/page-ordination-science.json`

40 → 48 steps, 61 → 70 confirmed expectations. The existing scenario is kept
verbatim (the 20 × 24 gradient parse, the 2-D NMDS stress and its Clarke band,
the 190-pair Shepard fit, the PCoA axes and negative-eigenvalue share, the
quoted-CSV parse), so its assertions hold, and the four never-driven settings
are exercised: the square-root transform chip (toggled off and back on), the
Bray-Curtis dissimilarity dial (re-selected, non-clearable), and the dimensions
(2) and random-starts (12) steppers — each returned to its default so the seeded
ordination is unchanged.

## Numbers

    ordination.html    2 -> 6 of 6 fields entered    (100%)
                      61 -> 70 confirmed, 0 refuted
    the kit          507 -> 511 of 521 fields          (98%), 23/27 whole

## Held

- The NMDS is seeded (fixed seed 42), so returning every control to its default
  reproduces the exact stress and coordinates the prior assertions hold.
- Transform is a multi-select chip — driven by a toggle-off-then-on, not one
  click; Bray-Curtis is a non-clearable dial that stays on re-activation.
- The steppers are reached as their `step_val` by label; only the dimensions
  change re-runs the ordination, random starts pushes without a run.
- No page was edited — a task-only slice, the sixteenth page entered whole.
