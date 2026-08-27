# ADR-075: "39 of 39" is a 4% sample

**Status:** Accepted and implemented — `tools/sweep_ledger.py` (`mutants_available`, `mutants_run`,
and a status block that says what the headline means), `tools/verify/verify_sweep_ledger.py` (18 → 23),
`tools/verify/verify_eco.py` (101 → 105).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-041, ADR-047, ADR-069, ADR-074

---

## 1. The headline number claimed twenty times what it had earned

ADR-074 ended **"39 of 39 pages swept. Nothing left to sweep."** True, and read on its own it says
*this kit's suites have been measured against deliberate faults everywhere*. They have not.

A page is swept at a **sample**: `mutants_for(path, limit)` picks four to eight mutants and spreads
them across the operators, precisely so that one run is not eight `>=` from the same function. The kit
has **3036** mutants. The sweep has run **at least 112** of them.

That is a **4% sample**, and the sentence that stood at the end of yesterday's ADR did not say so.

This is the same defect as the tally that opened this arc, one level up: not a number that was wrong,
but a number that meant less than its reader would take it to mean. `--status` carries both figures
now, computed:

```
SAMPLE, not census: a swept page was swept at four to eight mutants,
spread across the operators, and not at every mutant it has.
   at least 112 mutant(s) run, from 30 row(s) that recorded a count
   3036 mutant(s) exist across the 39 page(s) -- so this is a 4% sample
```

"At least", because the twenty-three rows backfilled from the ADRs carry no counts — the tool was not
writing them yet. Reporting a lower bound as exact would be the mistake this ledger exists to stop.

`verify_sweep_ledger` asserts the printed figures are the ones the functions compute, so the numerator
cannot drift from its denominator — which is exactly how *"19 swept, 20 to go"* happened.

**What the sweep has actually earned:** every page has been probed, no page is unprobed, and each
probe found what it found. That is worth having. It is not the same as coverage, and the tool now says
which one it is.

## 2. Ecology Lab: 17% → 67% → 100%

The two survivors ADR-074 named as fresh and untriaged, both measured rather than argued.

### A session is a file somebody sends you

`esc(v)` in the tile builder. The page charts a JSON **dropped onto it**, and its own comment gives the
reason every string from one is escaped: *"a shared protocol would be a script-injection vector for
whoever drops it in."* Nothing tested that escape, and the sweep dropped it twice without a murmur.

`bestFit` is a string straight out of the session and lands in a tile's value. Measured through the
page's own `render()` — the same path the drop handler takes:

| | with the escape | without |
|---|---|---|
| `bestFit: "<b>BROKEN_STICK</b>"` | shown as text | **a real `<b>` element in the tile** |

I did not observe a payload executing — an `<img onerror>` created the element but the handler did not
fire in this offline context — so the claim here is the one that was measured: **markup from a dropped
file becomes DOM.** That is enough; the page's own comment already says what it is for.

### A null is what a missing number looks like

`pts.every(p => isFinite(p[0]) && isFinite(p[1]))` → `||`. A point with a finite x and a **null** y then
passes the filter and gets drawn, when the whole purpose of the guard is that a series with a hole is
dropped so its absence is visible instead of silent.

Counting all paths on the page gave 280 against 281 — true and useless. Counted on the rarefaction
chart, whose curves are one per phase, the difference is a curve that is there or is not: **two phases
give two curves, and nulling one coordinate in one of them gives one.** With the mutant it stays at
two.

Both canaried. Ecology Lab is now **6 of 6**.

## 3. A flake, which is the worst kind of check

The regression run for this slice failed once, on `verify_dwc`, with
`ReferenceError: DWC is not defined` — and passed alone, and passed on a re-run. That is worth chasing
rather than shrugging at: a suite that fails on correct code teaches everyone to re-run it, and after
that a real failure looks like the same noise.

The suite already knew. It has a `ready()` helper whose docstring says, in as many words, that a fixed
sleep *"passed alone and failed under four-way parallel load with 'DWC is not defined'"*. Two of its
navigations — stand-sheet and collection-sheet — kept their 500 ms sleep anyway, and one of them threw
the same error again, from an `evaluate` that patches `DWC.table` on a page whose script had not
finished parsing.

A lesson learned in one place and not applied in the other two is a lesson half-learned. Every
navigation in that file goes through `ready()` now.

## Cost

`verify_eco` 101 → 105, `verify_sweep_ledger` 18 → 23, `sweep_ledger.py` +2 derived figures,
`verify_dwc` two navigations routed through its own wait helper. No page changed.
**55/55 jobs green, 3929 checks.**

**39 of 39 pages probed — at a 4% sample, and the tool says so.**
