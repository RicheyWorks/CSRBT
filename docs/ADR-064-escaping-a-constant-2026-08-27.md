# ADR-064 — Escaping a constant, and a claim I got wrong

**Date:** 2026-08-27
**Status:** accepted
**Corrects:** ADR-063 · **Extends:** ADR-062 (the recorded triage)

## The correction first

ADR-063 left one survivor open and said this about it:

> `greenhouse`, `drop-esc` on `esc(lastErr)` — the autosave-failure banner. …
> It **is** testable — force `localStorage.setItem` to throw with markup in the
> message — and it is not tested.

That is wrong, and it is wrong because I asserted testability without reading
the assignment. `lastErr` is **never** the exception's message. It is one of
three strings `keep.py` chooses:

```js
lastErr = "could not read the page state";
lastErr = (e && e.name === "QuotaExceededError")
        ? "this browser's storage is full" : "this browser refused the write";
```

No throw, however crafted, puts markup in the banner. The mutant is
**equivalent**, and no runtime test can reach it.

## What is worth guarding is the next edit

The `esc()` is not pointless — it is what keeps the line safe if the value ever
stops being a constant. And the plausible way that happens is someone reaching
for `e.message` to be more helpful, which turns browser-controlled (and through
a crafted filename or URL, potentially attacker-influenced) text into the
argument of a call the sweep has just shown is unguarded.

So the invariant is asserted where it lives — in the module, statically, once,
rather than in each of the pages that inline it:

- every `lastErr = …` statement is scanned **to its semicolon**, not to the end
  of the line, because the QuotaExceededError ternary spans two lines and a
  line-limited regex reads only its condition;
- none of them may reach `.message`, `.stack` or `.toString`;
- `esc(lastErr)` must still be there.

Three canary mutants — `e.message` in the ternary, `e.message` in the snapshot
catch, and the `esc()` removed — all die.

**Two more fixtures for the two rules that cannot be killed from the tree.** With
`keep.py` clean there is nothing for the leak pattern to match and nothing
spanning a line for the scanner to lose, so forcing either to fail changes no
outcome — the ADR-059 shape. Both are asserted directly instead: the pattern is
shown a leak and a non-leak, and the scanner is required to return the ternary
whole.

## A family, not four coincidences

Four more `drop-esc` survivors turned up across `soil-recipes`, `ethogram` and
`survey-design`, and all of them are the same shape: **an escape whose input is
a constant the page itself wrote.** Each was settled by measurement:

| survivor | measurement |
|---|---|
| `esc(lastErr)` (greenhouse, survey-design) | three literals in `keep.py`; no path from input |
| `esc(it[4])` (soil-recipes) | `rows()` is called only with `r.base` / `r.items` from the `RECIPES` literal; **0** pushes to it anywhere |
| `esc(it[1])` (ethogram) | `chips()` is called only with the `SAMPLE` and `RECORD` literals; **0** pushes to either |

Equivalent *today*, and the escapes stay, because that is what makes them still
right when a table becomes editable.

One more, a different shape: `fmtCup`'s `c <= 0` guard on soil-recipes. Measured
— 51 quantities in `RECIPES` with a minimum of 0.25, and the batch dial's
smallest multiplier is 0.25, so the smallest value `fmtCup` can ever see is
0.0625. Unreachable.

## Where that leaves the sweep

| page | fresh survivors |
|---|---|
| greenhouse | none unexamined |
| soil-recipes | none unexamined |
| survey-design | none unexamined |
| ethogram | none unexamined |

Raw scores stay low — 0% on soil-recipes — and that number now means what it
should: every one of its mutants is recorded as examined, with the measurement
that settled it, and the next sweep will not ask again.

## Cost

`verify_keep` 107 → 112 checks; `mutate.py` +4 recorded equivalents. No page
changed. 51/51 jobs green, 3633 checks.

**Swept: 12 pages. 27 to go.**
