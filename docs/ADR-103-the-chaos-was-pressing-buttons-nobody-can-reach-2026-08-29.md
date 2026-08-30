# ADR-103 — The chaos was pressing buttons nobody can reach

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-069 (a check that cannot fail is not a check), ADR-094 (a
worklist with a front), ADR-100 (the instrument was the first thing it found),
ADR-101 (a click is not a result), ADR-102 (the harness had never touched the
camera)

ADR-102 closed with a claim and a prediction:

> field-season throws twenty-six times under random pressing and ordination
> twice, and I claim these are the same defect: a handler reading a selection
> that chaos has cleared. **I expect that to be wrong** … **Falsifier: replaying
> both seeds, reading the two handlers, and finding a single shared cause that
> only a random order can reach.**

The replay was run. The claim is wrong, and more completely than predicted: they
are not the same defect, and **field-season has no defect at all.** Twenty-six of
ADR-102's loudest findings were the instrument's.

## 1. Chaos was pressing controls no user can reach

field-season's crash reproduced in two actions — press a stepper, then press
*🐭 Trap & mark voles* — and threw `Cannot read properties of null (reading
'day')`. The page's game state is `var G = null` until a season is started. The
handler has no guard.

But the button lives inside `<div id="game" style="display:none">`, and measuring
the page at load says so plainly:

```
gameDisplay: none    setupDisplay: block    markVisible: false
```

**A user cannot press it.** The harness could, because of a fix I made in
ADR-102. The chaos pass had been filtering its candidates on the visibility
recorded in the snapshot taken at load — which reached a tenth of the page — and
the correction removed the filter altogether. Neither *trust the snapshot* nor
*trust nothing* was right. The pass now asks the page, at the moment it is about
to act, whether this control is visible and enabled.

Re-run at the same seed:

```
                       before            after
field-season      26 findings      0 findings, 80 of 100 actions skipped
chaos, all pages 151 findings    131 findings, 194 actions skipped as unreachable
```

This is the ADR-100 defect for the fifth time and in its purest form: **a control
judged from a state it cannot be in.** The three earlier versions judged a control
from a state where its effect could not *appear*. This one judged a control a user
cannot reach at all.

## 2. And ADR-102 attributed the layout findings to the wrong cause

ADR-102 wrote that a 400-character entry breaking eight pages' layout was "the
consequence of ADR-100's dead `white-space` rule, now measured rather than
predicted." It was not measured. It was two true facts joined by plausibility.

Reproducing the edge value and asking the page which element is over the edge:

```
b     w=4005   parent div.verdict   "These records will join xxxxxxxx…"
code  w=3065   parent div.verdict   "parentEventID = xxxxxxxxxxxxxxxx…"
```

A **verdict box echoing the entry back**, not a `.row2 .g span` anywhere. The
ellipsis rule ADR-100 found dead is real and worth repairing; it is not what
those findings were about. **Retracted.**

## 3. A seeded random walk is not comparable across a page change

The first attempt to show the CSS fixes working re-ran chaos at the same seed and
found ethogram gone from 20 findings to 59. That number means nothing. The seed
fixes the *choices from the pool*, and the pool is whatever the page is showing —
so changing the page changes the walk. A random pass answers *is this still a
page*; it cannot answer *is this better than yesterday*.

The deterministic pass can, because it drives the same fields with the same
values in the same order. Every before/after in this document is `edges`.

## 4. One real crash, found, read, fixed and shown fixed

ordination's two throws are real, on visible controls, and reachable by an
ordinary path.

```js
if(p.err){ M=null; … return; }      // a bad matrix drops M and leaves RES
M=p; RES=null;

$("copyCoord").addEventListener("click", function(){
  if(!RES){ toast("Nothing to copy"); return; }   // guards on RES
  … M.sites[q] …                                  // reads M
});
```

Run an ordination, paste a matrix that will not parse, press **Copy coordinates**:
the guard passes because `RES` survived, and the handler reads `M.sites` off null.
`copyDis` has the same shape. `clearBtn` clears both together, which is why the
guard looked adequate — `RES` is a proxy for `M` on one path out of two.

Fixed in both places, because either alone leaves the other latent: a failed parse
now drops the results with the matrix, and both copy handlers guard on what they
actually read. **Chaos at the same seed: 2 → 0.** Three assertions in
`verify_ord` hold it there.

## 5. Two CSS fixes, and what each is actually worth

**`white-space:nowrap` on `.row2 .g span` — applied to fifteen pages, then taken
back off all fifteen.** ADR-100's finding is real: a truncation rule that can never
fire. The one-line repair regressed three pages. With the line unwrapped, releve,
micro-bench and soil-bench each run past a 390px phone **once a record is in the
row** — `verify_rv`, `verify_mb` and `verify_soil` all went red, naming
`DIV.row2`, `DIV.g`, `SPAN.` and `DIV.cov`. A fresh page shows nothing; the suites
found it because they put records in first.

So the repair is not a property on that rule, it is a change to the flex chain
that rule sits in, and it is not made here. The fifteen pages are byte-for-byte
what they were. What replaces the fix is a count: `verify_kit_consistency` now
asserts that the pages whose ellipsis rule cannot fire are **still exactly
fifteen**, so a known-open defect cannot quietly spread to a sixteenth.

That check was wrong on its first run, in the way this kit keeps finding: it read
the comment *explaining* that `white-space` was missing as though it were the
declaration, and reported the defect fixed on all fifteen pages. Comments are
stripped before the rule is read (ADR-077).

**`overflow-wrap:anywhere` on the verdict, code and table-cell surfaces of the six
pages that echo an entry back.** An entry with no space in it has no break
opportunity.

The `overflow-wrap` fix stands on its own. Measured on the same fields with the
same values, before and after:

```
                       before   after
collection-sheet.html       1       0
stand-sheet.html            1       0
survey-design.html          2       0
releve.html                 1       0
ecology-lab.html            8       7
deployment-log.html         1       1
                       ------  ------
                           16       8
```

Four pages clear. ecology-lab keeps its four `NaN` readouts and two table spills;
deployment-log keeps a 41px spill on `999999999` — a different cause, not touched
here, and named in the worklist rather than quietly folded into the win.

## 6. The shrinker: a story becomes a bug report

A twelve-step sequence ending in a crash is a story. `probe.shrink` is delta
debugging over the replay — drop a step, replay **from a reload**, keep it if the
same invariant still breaks. Replaying from a reload rather than from wherever the
last attempt left the page is the whole discipline: a sequence that only
reproduces from a state nobody reset has not been shrunk, it has been misread.

```
ecology-lab      12 steps -> 1    set-text text_in:28 = 1e308        -> a table spills 3006px
survey-design    11 steps -> 1    set-text text_in:1  = <script>…    -> spills 50px
ethogram          1 step  -> 1    set-text text_in:6  = -0.0001      -> a row spills 914px
tree-proofs      12 steps -> 2    a 400-char k, then Walk it         -> renders NaN
food-web         12 steps -> 3    a 400-char species name, then Add  -> the SVG spills 3662px
farm-scout       12 steps -> 12   NOT CONFIRMED from a reload
selection-log    12 steps -> 12   NOT CONFIRMED from a reload
```

The last two are the honest half. Those findings do not reproduce from a fresh
page, which means they depend on state the shrinker could not reconstruct, and the
run says so rather than shipping twelve steps as though they were the answer.

## 7. The numbers

```
chaos, all pages     151 -> 131 findings   194 of 2784 actions unreachable
                     field-season 26 -> 0
ordination crash       2 -> 0 at the same seed
edges, six pages      16 -> 8 findings, same fields, same values

pages changed                     7   (6 carry overflow-wrap; ordination also
                                         carries the crash fix)
pages changed and then reverted  15   (the nowrap repair, backed out)
published artifacts now BEHIND    7   <- staleness owed, for the first time
                                         in this series

suite   63 of 64 jobs green, 4461 of 4462 checks passing
        verify_ord               111/111  (108 before; three on the crash)
        verify_kit_consistency    51/51   (49 before; the count and the wrap)
        verify_publish_reach      RED     <- and correctly so, see below
```

## 8. Staleness, owed and stated

ADR-100, 101 and 102 each ended with *no page changed, nothing republished*. This
one changed seven. Until they are republished, a green audit of `docs/` says
nothing about what a reader of those artifacts sees (ADR-055/056/078).

**The suite is one job red, and that job is right.** `verify_publish_reach` asserts
that every page where the escaping injection is reachable is published current, and
three of them — collection-sheet, releve, survey-design — are now behind. This is
the first slice in the series to ship red, and the redness is not a defect to route
around: it is the kit refusing to call itself verified while a fix exists only in
the repository. It clears when the seven pages are republished and stamped:

```
python3 tools/publish_state.py --stamp collection-sheet.html deployment-log.html \
  ecology-lab.html ordination.html releve.html stand-sheet.html survey-design.html
```

## 9. What is not done

* **The republish.** Seven pages: collection-sheet, deployment-log, ecology-lab,
  ordination, releve, stand-sheet, survey-design.
* **ecology-lab's `NaN–∞`.** `1e308` into the mark-recapture field produces a
  Lincoln–Petersen estimate of `∞` and a Chapman interval of `NaN–∞`, rendered in
  a value slot. A finite-input guard, not touched here.
* **The `.row2 .g span` repair**, which needs a flex-chain change rather than the
  one-line property that regressed three pages, and its untruncated `<b>` sibling.
* **deployment-log's 41px spill** on a nine-digit number.
* **Two unshrinkable findings**, which are worth more as a question about the
  shrinker than as bug reports: what state does a reload not restore?

## 10. The next prediction, and its falsifier

Five of the seven shrunk repros are a single action into a single field. That
suggests the kit's fragility is concentrated in **what a field accepts**, not in
sequences — and if so, the `edges` pass should already have found every one of
them, because it drives every field with every one of those values.

**I claim it did not.** I expect at least two of the five shrunk chaos repros to be
findings `edges` never reported, because `edges` drives a field from the page's
opening state and chaos reached it with rows already added — the same field, in a
state the deterministic pass never puts it in.

**Falsifier: cross-referencing the five shrunk repros against the `edges` ledger
and finding every one of them already there.** If the falsifier fires, chaos is
buying nothing that edges does not, and should be re-scoped to sequences rather
than values.
