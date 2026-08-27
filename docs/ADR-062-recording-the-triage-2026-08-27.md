# ADR-062 — Recording the triage, and one rule I could not get right

**Date:** 2026-08-27
**Status:** accepted
**Extends:** ADR-047 (the sweeps), ADR-061 (the excluded audits)

## Two more pages, and the same three survivors

`fungal-characters` swept clean at **4/4**. `cell-bench` reported **25%** — and
its three survivors were, line for line, the three that survived on micro-bench
in ADR-061:

- `>=` → `>` inside `FEK.picker`'s filter
- `&&` → `||` inside `FEK.reg(o, h)`
- `<=` → `<` on a `<= 0` guard

Every page in this kit inlines the Field Entry Kit whole, so these three will
come back on all thirty-nine. Re-triaging the same three rows thirty-nine times
is precisely how a worklist teaches you to skim, which ADR-047 named as the
failure mode.

Each was settled by measurement, not by reading:

| survivor | measurement |
|---|---|
| picker filter | `FEK.picker` appears **0** times on either bench page |
| `reg(o, h)` | all **6** call sites pass the constructor's own `o`, which every constructor has already defaulted to `{}` |
| `sq <= 0` on cell-bench | typing `0` or `-3` into the stepper both yield hidden `cSq = 1` |
| `v <= 0` on micro-bench | typing `0` or `-5` both yield `plV = 0.001` |

So cell-bench's honest score is **1 of 1 reachable**, and micro-bench's is 2 of
2. The raw ratios — 25% and 40% — are true and useless on their own.

`mutate.py` now carries `KNOWN_EQUIVALENT`: operator plus a context fragment
plus the measurement that settled it. Matched survivors print under **ALREADY
EXAMINED** with their reason; anything else prints as a fresh question. Both
halves have to match, so the same operator elsewhere is still a survivor.

## The rule I could not get right, and withdrew

The tempting version was automatic: *a mutation inside a module function the
page never calls cannot change what the page does.* That is a fact, not a
heuristic — the module publishes its constructors in a `return { … }`, and if
the page never writes `FEK.picker(` then picker is dead code in that copy.

Getting from a mutation's **position** to the function that **contains** it needs
JavaScript braces matched properly, which needs regex literals told apart from
division. The first cut attributed every FEK mutation to `esc()`, because the
escaper's own `/[&<>"']/g` contains a quote, the matcher read it as a string
opening, and the brace depth never came back to zero.

"Nearest preceding declaration" was tried and is unsound in both directions: the
picker mutation sits inside a nested `paint()`, and walking back to the nearest
*published* declaration would attribute a mutation inside the private `reg()` to
`escv()` — marking a real survivor unreachable, which is the expensive
direction.

**A rule that cannot be got right is worse than a list that is honest about
being a list.** The detector is withdrawn and the reason is written where the
next person will reach for it.

## The second silent exclusion

ADR-061 fixed one systematic exclusion in `suites_for()`. The other is still
there: a suite that builds a scratch tree is dropped, on the grounds that it
names pages as fixtures. Two suites match, and only one is a pure fixture-user.
`verify_claims_triage` **asserts about three real pages** and also builds a
canary.

Measured before deciding: seeded two real mutants into `fungal-characters` and
ran it. It passed both — it asserts on rendered *text*, and these mutants change
interactive behaviour. The exclusion costs nothing today.

It was still happening **in silence**, which is exactly what let ADR-061 hide.
The sweep now prints what it excluded and why, so the judgement is reviewable
instead of buried in a predicate.

## Cost

`tools/mutate.py`: `suites_for` returns what it skipped, the sweep reports it,
and survivors split into fresh versus already-examined. No page changed.
51/51 jobs green, 3603 checks.

**Swept so far:** micro-bench (2/2 reachable), cell-bench (1/1), fungal-characters
(4/4). **36 pages to go**, and `collection-sheet` needs a longer timeout than a
single command allows — its four suites run about 100 s per mutant.
