# ADR-067 — A sentence disagreeing with itself

**Date:** 2026-08-27
**Status:** accepted
**Extends:** ADR-063/065/066 (the sweeps)

## The one real bug

`breeding-bench` warns about multiple comparisons in a variety trial:

> With **6** entries there are **15** pairwise comparisons. At 5% each you
> should expect roughly **0.8** apparent differences from noise alone.

Both figures come from the same expression, written twice —
`a.t*(a.t-1)/2` for the count and `a.t*(a.t-1)/2*0.05` for the expectation. The
sweep dropped the `/2` from the second one, leaving the banner saying there are
15 pairwise comparisons and that you should expect **1.5** false differences,
which is 15 × 0.10. **One sentence contradicting itself**, on a page about not
being fooled by noise.

Nothing caught it because the banner is guarded by `a.t > 4` and the suite's
demo trial has four entries — it had never been rendered. The suite now builds a
six-entry, three-block trial, reads both halves of the sentence, and asserts the
second is 5% of the first, recomputed from the entry count the page itself
reports rather than pinned.

## Two guards that cannot fire, measured not assumed

Two survivors looked like missing bounds checks and are not:

- **`deployment-log`, `every <= 0` → `every < 0`.** This guards a division, and
  with `every` at zero every reading downstream becomes NaN. But `aOn` and
  `aEvery` are FEK steppers with `min: 1` and no nullable flag: measured, typing
  `0` clamps to 1. Zero is unreachable and the guard is defensive.
- **`breeding-bench`, `esc(c.n)`.** `c` comes from `cropBy()` over the `CROPS`
  literal at line 930; grep finds **0** pushes to it. The constant-table family
  from ADR-064.

## A comment I wrote and had to correct within the hour

The first version of the deployment-log check said the panel was being read
"with nothing entered — which is where the form starts before anyone touches
it". That is wrong twice: the fields start at 60 and 600, and typing zero
clamps to 1. The check itself is still worth having — nothing had ever read that
panel at the bottom of its ranges — but it checks the **floor of the reachable
range**, not zero, and it does not kill the mutant. It now says so.

Writing a comment that flatters the check into covering more than it does is the
same failure as a suite that passes for the wrong reason, and it is easier to
commit because nothing fails when you do.

## Where the sweep stands

| page | fresh survivors |
|---|---|
| breeding-bench | none unexamined |
| deployment-log | none unexamined |

Every survivor on both pages is now recorded with the measurement that settled
it, or fixed.

## Cost

`verify_br` 82 → 90 checks, `verify_dep` 101 → 105, `mutate.py` +3 recorded
equivalents. No page changed — the bug was a missing check, and the two guards
were already right. 52/52 jobs green, 3798 checks.

**Swept: 18 pages. 21 to go.**
