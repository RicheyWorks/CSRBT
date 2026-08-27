# ADR-061 — The survivor that was already dead

**Date:** 2026-08-27
**Status:** accepted
**Extends:** ADR-045/046/047 (the mutation sweeps)

## What the sweep said

`micro-bench.html` had never been swept. Five mutants, and the report:

```
mutation score: 0%
```

Five for five surviving, including `drop-esc` — `esc(z.drug)` becoming
`z.drug`, an escaping call removed from a value the user types into the disc
diffusion form. That is the ADR-031 defect, seeded, on a published page, and
nothing caught it.

## Except something did

`audit_escaping` kills that mutant outright: run it against the seeded tree and
it reports **two element injections** on micro-bench.

`mutate.py` never ran it. Its `suites_for()` globs `verify_*.py` and keeps the
ones whose source **names the page** — and a cross-cutting audit names no page,
because it globs them all. So every audit was excluded from every sweep by
construction, and every `drop-esc` mutant on every page has been reported as
surviving while the kit killed it.

ADR-047 wrote the rule this breaks: *a survivor list padded with garbage is a
worklist nobody finishes.*

## The fix, and how narrow it is

`audit_escaping.py` gains `--page NAME`, and `mutate.py` gains one mapping:

```python
AUDITS_FOR_OP = {"drop-esc": ["audit_escaping.py"]}
```

The audit runs only for the kinds it demonstrably kills, and only after the
verify suites have already failed to catch the mutant — so the cost is three
seconds on a seventy-second sweep.

There is **no entry for the other four audits**. Contrast, offline, print and
focus are not reachable from any mutation this file generates, and adding them
on a hunch buys a slower sweep for no kills. A mapping that fires on everything
is the same mistake in the other direction.

## A hypothesis that was wrong, and cost nothing because it was checked

Before finding the real cause I had a better story: the audit probes only the
page's **first tab**, because a hidden pane's inputs have a zero bounding rect
and the fill loop skips those. Measured at load, `cell-bench`, `cp-bench` and
`ethogram` show **zero** visible text inputs, and `collection-sheet` shows seven
of thirty-one. It looked like a large, general coverage hole.

It is not one. `audit_escaping` already does this, eleven lines before the fill:

```python
"()=>{const p=[...document.querySelectorAll('.pane')];"
" p.forEach(x=>x.classList.add('on')); return p.length;}"
```

My measurement was of the page *without* the step the audit performs. ADR-055 is
why this got tested against the code before it got written up as a finding.

## Triaging the rest, which is the part that matters

Three survivors remained. All three are **equivalent mutants**, and each was
confirmed by measurement rather than by reading:

| survivor | why it cannot fire |
|---|---|
| `>=` → `>` in the picker's filter | `FEK.picker` is used **zero** times on this page |
| `&&` → `\|\|` in `reg(o, h)` | all **six** call sites pass the constructor's own `o`, which every constructor has already defaulted to `{}` |
| `<=` → `<` on the plated volume | the stepper clamps: typing `0` yields `0.001`, typing `-5` yields `0.001` |

So the page's honest score is **2 of 2 reachable mutants killed**, not 40%, and
certainly not 0%. The raw ratio was wrong in both directions at once — it
counted a mutant the kit kills as a survivor, and three that cannot fire as
failures to detect.

## The one real gap, now closed

`hi = Math.max.apply(null, vals)` → `Math.min.apply`. That makes `hi === lo`, so
`hi/lo` is always 1 and the adjacent-dilution warning can never fire again. The
Method tab promises exactly that behaviour — *"If they disagree by more than
about a factor of two, something is wrong with the series rather than with the
organism, and the page says so"* — and nothing checked that it does.

`verify_mb` now adds a third plate at the same dilution and volume as the first,
so the ratio of computed CFU/mL is just the ratio of the counts, and asserts the
warning fires and states that ratio. Recomputed from the inputs, not pinned
(ADR-041).

## Cost

`verify_mb` 61 → 65 checks; `audit_escaping` +`--page`; `mutate.py` +1 mapping.
51/51 jobs green, 3603 checks. micro-bench swept.

**Still unswept at page level: 38 pages.** The number that matters for each is
not the ratio but the triage under it, and this slice took an hour for one page.
