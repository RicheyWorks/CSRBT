# 2026-08-29 — ADR-103: a crash fixed, and two retractions

Companion to
`docs/ADR-103-the-chaos-was-pressing-buttons-nobody-can-reach-2026-08-29.md`.

## The prediction, and how wrong it was

ADR-102 claimed field-season's 26 uncaught throws and ordination's 2 were the same
defect, and predicted that claim would be wrong. It is wrong twice over: they are
not the same defect, and **field-season has no defect at all.**

## Retraction 1 — chaos was pressing controls no user can reach

field-season's crash reproduces in two actions, and the button lives inside
`<div id="game" style="display:none">`. Measured at load: `gameDisplay: none`,
`markVisible: false`. A user cannot press it.

The cause was mine. ADR-102 found the chaos pass filtering candidates on the
visibility recorded at load — a tenth of the page — and the fix removed the filter
altogether. Neither *trust the snapshot* nor *trust nothing*. It now asks the page,
at the moment it acts, whether this control is visible and enabled.

```
                       before            after
field-season      26 findings      0 findings, 80 of 100 actions skipped
chaos, all pages 151 findings    131 findings, 194 actions skipped
```

That is the ADR-100 defect for the fifth time: a control judged from a state it
cannot be in.

## Retraction 2 — the layout findings had the wrong cause

ADR-102 wrote that a 400-character entry breaking eight pages was "the consequence
of ADR-100's dead `white-space` rule, now measured rather than predicted." It was
not measured. Reproducing it and asking the page:

```
b     w=4005   parent div.verdict   "These records will join xxxx…"
code  w=3065   parent div.verdict   "parentEventID = xxxxxxxxxxxx…"
```

A verdict box echoing the entry back — no `.row2 .g span` involved.

## A seeded random walk is not comparable across a page change

Re-running chaos at the same seed after the CSS fix showed ethogram at 20 → 59
findings. That number means nothing: the seed fixes the choices from the pool, and
the pool is whatever the page is showing. Every before/after here is `edges`,
which drives the same fields with the same values in the same order.

## The crash: guarded on one variable, read another

```js
if(p.err){ M=null; … return; }   // a bad matrix drops M and leaves RES standing
$("copyCoord")… if(!RES){ … return; }   … M.sites[q] …
```

Run an ordination, paste a matrix that will not parse, press **Copy coordinates**.
`copyDis` has the same shape. `clearBtn` clears both together, which is why the
guard looked adequate — `RES` proxies for `M` on one path out of two.

Fixed in both places: a failed parse drops the results with the matrix, and both
handlers guard on what they read. **Chaos at the same seed: 2 → 0.** Three
assertions in `verify_ord`.

## Two CSS fixes, measured

`white-space:nowrap` on `.row2 .g span` was applied to 15 pages **and taken back
off all 15**. With the line unwrapped, releve, micro-bench and soil-bench each run
past a 390px phone *once a record is in the row* — `verify_rv`, `verify_mb` and
`verify_soil` all went red. A fresh page shows nothing; the suites found it because
they put records in first. The repair is a flex-chain change, not a property, and
it is not made here. The 15 pages are byte-for-byte what they were, and
`verify_kit_consistency` now asserts they are **still exactly fifteen**, so the
known-open defect cannot spread to a sixteenth.

That check was wrong on its first run: it read the comment *explaining* that
`white-space` was missing as the declaration itself and reported the defect fixed.
Comments are stripped before the rule is read (ADR-077).

`overflow-wrap:anywhere` on the verdict, code and cell surfaces of the six pages
that echo an entry back. Same fields, same values, before and after:

```
collection-sheet 1→0   stand-sheet 1→0   survey-design 2→0
releve 1→0             ecology-lab 8→7   deployment-log 1→1
                                                   16 → 8
```

## The shrinker

Delta debugging over a chaos replay: drop a step, replay **from a reload**, keep it
if the same invariant breaks. Replaying from a reload is the discipline — a
sequence that only reproduces from wherever the last attempt left the page has not
been shrunk, it has been misread.

```
ecology-lab    12 → 1   1e308 into one field      → a table spills 3006px
survey-design  11 → 1   <script>alert(1)</script> → spills 50px
ethogram        1 → 1   -0.0001                   → a row spills 914px
tree-proofs    12 → 2   a 400-char k, then Walk it → renders NaN
food-web       12 → 3   a 400-char name, then Add → the SVG spills 3662px
farm-scout     12 → 12  NOT CONFIRMED from a reload
selection-log  12 → 12  NOT CONFIRMED from a reload
```

The last two are the honest half: the run says when it could not reproduce rather
than shipping twelve steps as an answer.

## Staleness, owed and stated

ADR-100, 101 and 102 each ended with *no page changed*. This one changed seven,
and **7 published artifacts are now BEHIND**: collection-sheet, deployment-log,
ecology-lab, ordination, releve, stand-sheet, survey-design. Until they are republished a green
audit of `docs/` says nothing about what a reader sees. The stamp command is in
`tools/publish_state.py` and has not been run.

## Suite

```
63 of 64 jobs green, 4461 of 4462 checks passing
verify_ord              111/111  (108 before; three on the crash)
verify_kit_consistency   51/51   (49 before; the count and the wrap)
verify_publish_reach     RED     three injection-reachable pages are behind
```

**The one red job is right.** It is the kit refusing to call itself verified while
a fix exists only in the repository. It clears on republish:

```
python3 tools/publish_state.py --stamp collection-sheet.html deployment-log.html \
  ecology-lab.html ordination.html releve.html stand-sheet.html survey-design.html
```

## Worklist

ecology-lab's `NaN–∞` from `1e308` in a value slot; the `.row2 .g span` repair,
which needs a flex-chain change rather than the property that regressed three
pages, and its untruncated `<b>` sibling;
deployment-log's 41px spill on a nine-digit number; and two findings the shrinker
could not reproduce from a reload — worth more as a question about the shrinker
than as bug reports.
