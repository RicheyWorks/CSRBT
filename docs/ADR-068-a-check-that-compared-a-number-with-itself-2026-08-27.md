# ADR-068 — A check that compared a number with itself

**Date:** 2026-08-27
**Status:** accepted
**Extends:** ADR-039 (fixtures that cannot tell two implementations apart)

## The check I wrote, believed, and had to throw away

`pheno-tracker` seeds its plant grid with

```js
for (var i = 1; i <= 8; i++) S.plants.push(blank(i));
```

The sweep made it `i < 8` — seven plants where there should be eight — and
nothing caught it. The obvious fix looked like an ADR-057 move: don't pin the
number 8, assert that **the grid holds as many plants as the page's own "how
many" control says.** A page agreeing with itself, not a frozen constant.

I wrote it, it passed, and the sweep still reported the mutant alive.

The page **writes `runN` back from the roster length** when it renders. With the
mutant in place both sides read 7 and the check passes. It was comparing a
number with itself.

That is ADR-039 exactly — a fixture that cannot tell two implementations apart —
and the only reason I know is that I ran the sweep again instead of trusting a
green suite. A check written to kill a specific mutant and never tested against
that mutant is a check with no evidence behind it.

## What was left after taking it out

There is **no independent witness** anywhere on the page for the starting count.
Nothing else in the DOM, nothing in the prose. Asserting 8 would pin an
arbitrary UX default, which ADR-041 exists to prevent, so that mutant is
recorded as deliberately left with the measurement that explains why the
tempting check does not work.

What survived the cut is the part with a rule behind it, and it is worth having:
the plant ids run **1..n with no gap**, and asking the page for five plants
gives exactly five rows and says so.

## The other three survivors

The recurring Field Entry Kit pair, and `esc(lastErr)` — all three already
recorded, all three printed under ALREADY EXAMINED. The triage list is doing its
job: on this page it absorbed everything except the one genuinely new question.

## What this costs the score

`pheno-tracker` stays at **0%**, and that is the honest number. Four mutants:
three recorded equivalents and one arbitrary default. Nothing on this page is
under-tested in a way a mutation of this kind can show.

## Cost

`verify_pt` 56 → 60 checks, `mutate.py` +1 recorded entry. No page changed.
52/52 jobs green, 3802 checks.

**Swept: 19 pages. 20 to go.**
