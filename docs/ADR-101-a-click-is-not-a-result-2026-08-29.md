# ADR-101 — A click is not a result

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-031 (the offline constraint), ADR-061 (silent exclusion with a
plausible face), ADR-065 (a page with no suite), ADR-069 (a check that cannot fail
is not a check), ADR-094 (a worklist with a front), ADR-100 (the instrument was
the first thing it found)

ADR-100 built a harness that discovered 3,684 affordances and drove 2,357 of them.
It asked each one a single question: **did anything change?**

That question is answered *yes* by a plus button that subtracts. By a filter that
keeps exactly the rows that do not match. By an option that bumps a counter and
refuses to select. By a Copy CSV that puts an empty string on the clipboard. The
harness had established that the kit is *wired*. Reporting that as evidence the kit
*works* was the over-claim in ADR-100's headline number, and this document retracts
it.

`tools/swarm.py` keeps that harness's discovery and its accounting and replaces the
oracle.

## 1. Every control now carries an expectation

Each kind is checked against a promise written in terms of what a user would see:

| control | what is asserted |
|---|---|
| tab | exactly one pane is open afterwards, and it is the named one |
| stepper `+` / `−` | the number moved, in the direction the label promises |
| field | what was typed is what the control holds |
| slider | the number the widget *displays* is the number that was set |
| select | the chosen option is the one the box reports |
| option | clicking it **selects** it, and in a radio group it is then the only one |
| picker search | every survivor matches the query, some were removed, and clearing brings all of them back |
| add / remove | exactly one more row / one fewer |
| clear | fewer fields are left holding anything |
| undo | the page is back in a state it was in earlier this run |
| export | a payload left the page, it **parses**, and it contains what was typed into the form |

A control with no expectation attached is **not** called verified. It is called
`changed`, which is the honest name for what ADR-100 was measuring. The split
between those two is the number this slice exists to print:

```
discovered 3554 = verified 1966 + wrong 18 + changed 273
                + dead 34 + hidden 204 + failed 4 + excluded 1055   OK

checked against a stated expectation:  1984 of 2257 driven  (87%)
only observed to change:                273
```

Every one of the 1,966 was asked a specific question and answered it:

```
option 1168   field 321   step 236   tab 87   filter 40   add 29
export 23   remove 20   undo 18   slider 10   print 9   select 3   clear 2
```

## 2. The seed, without which most of those questions cannot be asked

An empty form exports an empty file perfectly correctly, and a spore swatch pressed
before a collection exists is right to do nothing. So a run begins by entering a
recorded sentinel into every text field, pressing every add-shaped button, and then
every save-shaped one — because **filling a form is not the same as having a
record**, and four exports were called wrong for that difference before the seed
learned to commit.

The export oracle can then ask a question worth asking: is what the user typed in
the file the page produced?

## 3. Nine defects, all of them the instrument's

Every one was found by reading a wrong finding, not by reasoning about the design.

1. **The verdict was computed from a label the walk no longer pointed at.**
   Selectors are positional within a kind and these widgets rebuild, so by the time
   `action_btn:30` was driven it was no longer the *Copy .eco lines* button
   discovered under that name. The export oracle was applied to a quadrat arrow and
   three live exports were reported as producing nothing. Every control is now
   re-observed immediately before it is judged. This is ADR-100's rebuild problem
   one layer up: that fix stopped the walk *touching* an element that had vanished;
   it did not stop the walk *judging* one control by another's promise.
2. **A correct refusal read as a wrong result** — an export with nothing saved, a
   swatch pressed too early, an Add with nothing selected. Judging a control from a
   state where its effect could not appear is the ADR-100 defect wearing the
   oracle's clothes. A refusal is now allowed **on one condition, which is the rule
   this kit already holds itself to everywhere else: it has to tell the user.** A
   control that declines with a toast is doing its job; one that declines in silence
   is indistinguishable from one that is broken, and stays a finding. Fifty controls
   sit in `changed` under that rule, each with the words it said.
3. **The harness poisoned the widget it then failed to measure.** A stepper holds a
   number and the walk was typing a text sentinel into it. The next press computed
   `NaN` from that, the press after computed `NaN` from `NaN`, and a live plus
   button reported as leaving no trace. Stepper values are numeric now, and a
   stepper displaying something that is not a number is a *finding* rather than a
   silence.
4. **A toast raised while an identical toast is still on screen is invisible.** The
   class is already there, so adding it again is not a mutation — the same blindness
   that cost ADR-100 twelve live controls. Raises are counted at the call now, not
   hoped for at the result.
5. **Prose with commas in it was read as a ragged CSV.** Three of the kit's
   AI-prompt exports were reported as malformed tables because the reader asked only
   whether line one contained a comma. A payload is a table when most of its rows
   agree on a width of three or more; otherwise it is text.
6. **A filter was judged by a query that separates nothing.** A picker with one
   option cannot be filtered below one, and a query every option matches correctly
   removes none — both were reported as filters that failed to filter. The query is
   now chosen to match some options and not others, and a picker where no query does
   that is unjudged and says so.
7. **A pane that no tab opens was counted as 54 undriveable controls.**
   experiment-guide reveals its designer pane another way; the harness insisted on a
   route the page does not use. Visibility decides now.
8. **An element gone between the snapshot and the read was filed as a failure**,
   inflating the one bucket that means *this tool could not do its job*. It is a
   fact about the page, and belongs in `hidden`. Failed fell from 108 to 4.
9. **`show-pane` refused before the oracle could report.** It first asked "is this
   pane *the* open one", so a page that opens a second pane without closing the
   first came back as *no such tab*. Its job is "did this pane open"; whether it is
   the only one is the oracle's question. A finding had been turned into a failure.

Two expectations were also **retracted as too strong for what a label can carry.**
A *Clear* was asserted to leave no field holding anything, and breeding-bench's
*Clear trial* — correctly scoped to the trial — was reported as a defect for it;
field-notebook's *Reset* resets a stopwatch and its *Clear* empties a quadrat list.
A label says that something is cleared, not what. The expectation retreated to the
part a label supports, and the finding is kept for a clear that clears nothing at
all.

On the four-page pilot the first run reported **35** wrong results. After these
corrections the same four pages report **7**. Twenty-eight of the first
thirty-five findings were mine.

## 4. Showing it fail

`tools/verify/verify_swarm.py` writes ten fixture pages. Nine are wired, respond to
every click, and would pass ADR-100's oracle: a plus that subtracts, a filter that
keeps what does not match, an option that will not select, a field that eats what is
typed, a Copy that copies an empty string, a CSV whose rows disagree about the
column count, a well-formed export of somebody else's data, a tab that opens a pane
without closing the other, and an Add that changes a caption and adds no row. Each
is asserted to be caught **by its own oracle, by name** — not merely to produce some
complaint. The tenth is entirely in order, and the assertion on it is that
**nothing** is reported: an instrument that cannot come back clean is not measuring
(ADR-069). The accounting identity is asserted on all ten.

One fixture failed on its first run and the fixture was wrong, not the swarm: in a
`minus` page whose stepper value the walk had already filled, both buttons computed
`NaN`. That is how defect 3 was found.

## 5. How the swarm reaches the page

The knowledge about what a control *is* on these pages moved behind a typed layer
(`tools/harness_contract.py`, `tools/harness_plugin_page.py`), so the swarm drives
with the action a control deserves — `press-step` with a direction, `set-text` with
a value, `choose-option` with an option — rather than clicking at everything and
inferring afterwards. That is what makes the typed oracles possible: the harness
knows what it asked for, so it can say what it expected.

The layer carries the safety properties that come with letting anything drive these
pages automatically: off unless enabled, a token on every operation, entered values
withheld unless explicitly unlocked, generic activation treated as the most
consequential thing a selector can mean, and a request id so a retried command does
not operate the page twice. `tools/harness_stdio.py` is a ~120-line adapter over it
for a script or a test runner; `docs/AUTOMATION-HARNESS.md` is the operator's page.
`tools/verify/verify_contract.py` holds that boundary to 65 assertions.

None of that is the point of this slice. The point is that 1,966 controls were asked
what they promise and answered.

## 6. The numbers

```
pages driven                            40
affordances discovered                3554
  verified against an expectation      1966
  WRONG                                  18
  changed, no expectation stated        273   (208 unclassified, 50 declined
                                               with a toast, 15 unjudgeable)
  left no trace at all                   34
  never visible                         204
  the harness could not drive             4   (was 108 before defect 8)
  excluded, each with a reason         1055
actions that broke an invariant         68

viewport                         390 x 844   a phone, held in a wet field
commands issued                      15404

suite   63 of 63 jobs green, 4415 of 4415 checks passing   (61 / 4322 before)
        verify_swarm     28/28   new
        verify_contract  65/65   new
```

## 7. What is not done

* **No page changed.** This slice is `tools/`, two new suites and one document.
  Nothing was republished, so no staleness is owed.
* **The swarm is not a gate,** for ADR-100's reason: a red suite nobody can turn
  green gets ignored, and that is how a gate becomes a decoration. `verify_swarm`
  and `verify_contract` gate the instruments; the instruments report on the kit.
* **`changed` is honest, not finished.** 208 affordances are buttons whose label
  carries no verb this slice could turn into an expectation. That bucket is the
  front of the next worklist, not a pass.
* **204 hidden is coarse.** It still does not distinguish *unreachable* from *not
  reached by this walk*.

## 8. The worklist this hands on

**Eighteen results that were not what the control promises.** The shape of them:

* **Eleven exports.** Three on selection-log, two each on collection-sheet, releve
  and food-web produce a well-formed payload containing **none** of the values
  entered into the form, even after the seed committed a record; one on ecology-lab
  copies nothing and says nothing; one on pheno-tracker emits a CSV where one row in
  three is not the width of the others.
* **Four Adds** — ethogram, field-notebook, field-season's *New season*, and
  stand-sheet's *Add photos* — add no row and raise no toast.
* **Two clears** — breeding-bench's *Clear trial* and tree-proofs' *New random
  tree* — change nothing at all.
* **One remove** — tree-visualizer's *Delete*.

**Thirty-four affordances that left no trace,** headed by fifteen of ethogram's
behaviour buttons (*locomote*, *forage*, *vigilant* …) and five of farm-scout's
bespoke minus arrows.

**ADR-100's worklist is still open** and unchanged by this slice: `.row2 .g span`
declares `text-overflow:ellipsis` with no `white-space:nowrap` on fifteen pages, an
ellipsis that can never render.

**The next prediction, and its falsifier.** Everything above is a control answering
wrongly. I claim the kit's *declines* are in better shape than its actions — that
where a control refuses it nearly always says so, because the toast is a house
habit. **I expect that to be wrong: at least five of the thirty-four affordances
that left no trace are guarded controls declining in silence**, doing nothing and
saying nothing, and are being read as unwired when they are in fact refusing. The
fifteen ethogram buttons are where I expect to find them. **Falsifier: reading every
one of the thirty-four against its handler and finding that each either has no guard
at all or raises a toast.** That reading is the next slice.
