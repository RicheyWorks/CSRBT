# ADR-073: the middle of every band

**Status:** Accepted and implemented — `tools/verify/verify_cp.py` (81 → 87), `tools/mutate.py`
(+2 recorded equivalents).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-069, ADR-071 (a plot nobody had looked at), ADR-072

---

## Context

Two pages, and the same two shapes as yesterday: a threshold tested only in the middle, and a chart
nobody had ever looked at.

## 1. CP Bench: the bands were tested at 20, 120 and 300

The water page sorts a TDS reading into three bands and names both boundaries in its own prose:
*"comfortably inside the stricter ~50 ppm target"*, *"below **160 ppm**"*. `verify_cp` entered 20, 120
and 300 — the middle of each band, three times, and neither boundary once.

A mutation sweep turned `tds <= 50` into `tds < 50` and nothing noticed. Fifty is not an awkward edge
case here: it is the number the page names, the number a grower reads off a meter, and a value the
stepper lands on going up in fives. At exactly 50 the mutant moves the verdict from *"Excellent —
comfortably inside"* to *"Usable — above the ~50 ppm many growers aim for"*.

The same two comparisons appear a second time, independently, in the row the reading gets in the list.
So both are asserted at both boundaries: a page that agreed with itself only in the middle of a band
would be a page whose list and verdict can disagree exactly where somebody looks. And 51 and 161 are
asserted to have moved, so the boundary checks cannot be passing because the page ignores the number.

## 2. ...and "an svg exists" was the whole of the chart coverage

`ck("trap chart drawn", …svg…length == 1)`. That is all any check in this kit had ever said about that
chart.

`hi = Math.max(series)` → `min`. `hi` then equals `lo`, the `hi === lo` guard bumps it to `lo + 1`, and
every count above that is drawn far above the frame. Predicted and then measured on the suite's own
4 → 6 → 9 series: **y = 134, −102, −456** in a 170-high viewBox. The line leaves the picture entirely.

Three checks now, the same rule as yesterday's ordination plot: a point per observation, every point
inside the frame, and — because a scale that collapsed the line onto one row would satisfy that — a
rising count has to actually rise.

Two pages in two days where the arithmetic was checked against independent implementations and the
drawing was not checked at all. The pattern is worth naming: **a chart is an assertion about numbers,
and the kit had been treating it as decoration.**

## 3. Two survivors left standing, with the measurement

**`esc(s)` on cp-bench's water row.** `s` is a `SOURCES` label; `SOURCES` is a page literal at line
1011 with no push, splice or reassignment anywhere in the file. Nothing in the input to escape. Same
family as the four already recorded.

**`navigator.clipboard && navigator.clipboard.writeText` → `||`** on eco-protocol-library's copy
button. This one is worth the words. With `||`, a truthy `navigator.clipboard` short-circuits and
`writeText` is called even when it is absent — which throws — and the whole expression sits inside a
`try` whose `catch` calls `fallback()`. The `&&` spelling reaches `fallback()` by evaluating to false;
the `||` spelling reaches it by throwing. **Both arrive at the same place in every browser where they
differ at all**, so the mutation cannot be observed from outside the page.

Settled by reading the enclosing `try`, not the condition — which is the general lesson about this
operator: a guard inside a catch-all is not a guard, it is an optimisation.

## Where the sweep stands

| page | before | after | left standing |
|---|---|---|---|
| eco-protocol-library | 50% | 50% | 1 recorded equivalent, 1 of 1 reachable killed |
| cp-bench | 50% | **83%** | 1 recorded equivalent, 5 of 5 reachable killed |

A raw ratio below 100% with every reachable mutant dead is the honest number, and ADR-061 is why this
table has two columns rather than one.

## Cost

`verify_cp` 81 → 87, `mutate.py` +2 recorded equivalents. No page changed. **55/55 jobs green, 3902 checks.**

**Swept: 36 pages, 3 to go — collection-sheet, ecology-lab, soil-bench.**
