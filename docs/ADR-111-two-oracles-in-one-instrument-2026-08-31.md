# ADR-111 — Two visibility oracles in one instrument

**Status:** accepted · **Date:** 2026-08-31 · **Supersedes nothing; closes ADR-110 §7**

## 1. The question ADR-110 left open

ADR-110 ended with three open items, and one of them was written as a question
rather than a defect:

> `ecology-lab`: four Workbench textarea fills time out under the walk while
> working by hand. Either the harness's fill is wrong for that control or the
> control is, and **nobody has measured which** — which is the honest state and
> the next thing worth measuring.

It was the harness's. Measuring it took twenty minutes and changed four
findings from "the page raised" to "we did not reach it", which is a different
sentence about a different thing.

## 2. What was actually there

The four records read:

```
text_in  "robin 34 sparrow 21 wren 8 finch 3 thrush 1"
         why: action raised
         got: ElementHandle.fill: Timeout 2500ms exceeded.
```

Driving the page by hand in a browser, the same textarea fills instantly. So
the timeout was not the page being slow. Playwright's `fill` waits for
*actionability* — visible, enabled, editable, stable — and one of those was
false. Probing each one in turn:

```
#wb-field  rect 300x120   display inline-block   visibility visible
           readOnly false   disabled false   no hidden ancestor
           is_editable True   is_enabled True
           is_visible  FALSE
```

Every property the harness looks at says the control is visible. Playwright
says it is not. The ancestor walk finds why:

```
TEXTAREA#wb-field      300 x 120
DETAILS.fe-raw         300 x  40      <-- open: false
DIV.facet              300 x 1019
```

The textarea is inside a **collapsed `<details>`** — the disclosure labelled
*"✎ edit as text (paste from a spreadsheet)"*. Chromium does not render the
contents of a closed `<details>`, but it does not do it by setting
`display:none` or `visibility:hidden` on the child either. The child keeps its
box and keeps its computed styles. `checkVisibility()` returns false; nothing
the harness was measuring returns anything different.

## 3. The defect: the tool asked two different questions

`tools/harness.py` had two visibility tests and did not know it.

**Discovery** asked its own, hand-rolled one:

```js
vis = r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
```

**The driver** asked Playwright's, which is `checkVisibility()` plus a
non-empty box. For every ordinary control the two agree, which is why this
survived eleven ADRs. For a control inside a closed disclosure they disagree,
and the disagreement had a direction: discovery said *visible*, so the walk
drove it; the driver said *not actionable*, so the press timed out; and the
timeout was filed under `failed`, whose meaning in this harness is **"the page
misbehaved"**.

That is the accusation. The bucket a control lands in is a claim about the
product. `failed` said `ecology-lab.html` had four broken text inputs. It has
none. Four entries sat in `tools/harness_baseline.json` as accepted defect debt
for a page that never had the defect — and being *in* the baseline meant nobody
looked at them again, because that is what a baseline is for.

This is the same shape as ADR-040, ADR-105, ADR-106, ADR-109 and ADR-110: **a
check right about what it matched and wrong about what the match meant.** The
new variant worth naming is that here the tool contradicted *itself*. There was
no external fact to get wrong. Two functions in one file held two definitions of
one word, and the gap between them was reported as news about the page.

## 4. The fix

One oracle, and it is the driver's, because the driver's is the one that
decides whether the press happens:

```js
const rendered = (typeof el.checkVisibility === "function")
  ? el.checkVisibility()
  : (s.visibility !== "hidden" && s.display !== "none");
vis = r.width > 0 && r.height > 0 && rendered;
```

And, separately, the probe now counts collapsed `<details>` ancestors, so the
record can say what is true instead of something vaguer:

- `inside a collapsed disclosure the walk did not open` — the control is fine,
  it was not opened;
- `not visible with its own pane open` — the older, weaker statement, kept for
  everything that is not a disclosure.

Both land in `hidden`, which already means *the harness did not reach this*, and
which the accounting identity already tracks.

## 5. The fix that was built, measured, and thrown away

The obvious next step is to open the disclosure. A closed `<details>` is prior
state a person supplies by clicking a summary — the same category as an unopened
pane, which `show_pane` has handled since the beginning, and the same category as
ADR-110's second chance.

It was built twice.

| approach | ecology-lab driven |
|---|---|
| baseline (before this ADR) | 83 |
| one oracle, no opening | **85** |
| open ancestors just before each press | 55 |
| open every `<details>` once, before discovery | 55 |

Both opening strategies cost **thirty** controls to buy back four, and the two
strategies cost exactly the same, which is the clue: the price is not the
toggling, it is what is *inside* these particular disclosures. The
`edit as text` box rebuilds the whole Workbench widget from its own contents.
Filling it destroys the row editor above it — rows earlier presses had added,
each carrying its own `+`, `−`, `✕`. Affordance ids are positional within a
kind, so once the row count dropped, every id above the break pointed at nothing
and the walk reported *"the page rebuilt it away"*.

Driving the raw box and driving the row buttons are mutually exclusive within
one walk. That is neither a harness defect nor a page defect; it is the
`sequenced` phenomenon of ADR-109 at the scale of an entire widget. The reading
with more coverage wins: leave the box shut, count it `hidden`, say why.

The rejected work is kept as a comment block in `harness.py` with the numbers in
it, because "we tried opening them" is the first thing the next person will
think of.

## 6. What the accounting identity cannot do

Worth recording on its own, because it corrects an impression ADR-104 through
ADR-110 may have left.

Through **both** failed experiments, `discovered == driven + dead + sequenced +
hidden + failed + excluded` held perfectly. Coverage fell 85 → 55 and the
identity did not so much as wobble.

An identity says nothing was lost **track of**. It does not say nothing was
lost. It caught ADR-110's off-by-two because that bug dropped records; it cannot
catch a change that drops *opportunities*, because the affordances that stopped
being driven were still counted, in a different bucket, correctly.

Coverage needs a floor of its own, and it has one — `CONTROL_FLOOR` in
`tools/verify/verify_routes.py`, which exists precisely so coverage cannot be
narrowed while the suite still reports green. On this occasion measurement got
there first. The floor is what would have caught it otherwise, and that is worth
knowing before the day it has to.

## 7. Section K: the contract clause that was asserted by nobody

`tools/verify/verify_harness_matrix.py` gains a tenth section and **nine
checks** (62 → 71):

- **K1** a control in a collapsed disclosure is `hidden`, never `failed`
- **K2** and the reason names the disclosure rather than pointing at the page
- **K3** a control in an **open** disclosure is driven normally — the rule is not
  "details means hidden", and K3 is what stops K1 being satisfied by a harness
  that has quietly stopped testing disclosures at all
- **K4** `display:none` is still hidden, and is **not** relabelled a disclosure
- **K5** rendered but zero-box is still hidden — the other half of the oracle
- **K6/K7** (two fixtures each) the promise stated as the thing that must never
  happen: nothing lands in `failed` carrying an actionability timeout, and the
  identity holds

Two mutants join the catalogue (13 → 15):

- restore discovery's old private visibility test → must be killed by **K1**
- stop counting collapsed disclosures → must be killed by **K2**

`I2` — every mutant's anchor still matches the harness exactly once — **failed
on the first run of this work**, because editing `drive_all` moved the anchor of
the `B3` mutant. That is the check earning its place: without it, `B3` would have
silently stopped testing anything and the catalogue would still have printed
*killed*.

## 8. Results

| | before | after |
|---|---|---|
| kit affordances discovered | 3,699 | 3,699 |
| driven | 2,367 | **2,367** |
| dead | 1 | **1** |
| sequenced | 10 | 10 |
| hidden | 251 | **255** |
| **failed** | **4** | **0** |
| excluded | 1,066 | 1,066 |
| invariant breaks | 62 | **61** |
| accepted debt | 17 distinct / 67 occ / 4 pages | **13 / 63 / 3** |
| matrix checks | 62 | **71** |
| mutants | 13 killed | **15 killed** |

Kit-wide the whole change is four records moving from `failed` to `hidden`, with
**no coverage lost** — the 85 vs 83 gain on `ecology-lab` is offset elsewhere by
the same stricter oracle correctly declining two controls it should never have
counted.

The four baseline entries are **struck, not tolerated**: `verify_findings.py`
refused the run until they were written off, which is the second half of the
ratchet doing the job ADR-109 built it for. `tools/harness_baseline.json` records
why they went.

## 9. Still open

- `selection-log` and `survey-design`: the `row2` flex-chain repair, unchanged
  since ADR-103 and now **all but one** of the accepted debt.
- `stand-sheet`: "📷 Add photos" — the one dead control in the kit, and now
  genuinely the only one.
- The `edit as text` disclosures on `ecology-lab` are untested by the walk and
  will stay that way until the harness can drive a page along more than one
  path. That is a real gap, it is written down, and it is not being called
  anything else.
