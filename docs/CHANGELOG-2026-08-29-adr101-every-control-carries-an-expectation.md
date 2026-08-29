# 2026-08-29 — ADR-101: a click is not a result

Companion to `docs/ADR-101-a-click-is-not-a-result-2026-08-29.md`.

## What was wrong with ADR-100's number

The harness asked every affordance one question — *did anything change?* — and
reported 2,357 that answered yes as the kit's working surface. That question is
answered yes by a plus button that subtracts, a filter that keeps the rows that do
**not** match, an option that bumps a counter and refuses to select, and a Copy CSV
that copies an empty string.

## `tools/swarm.py` — the same discovery, a real oracle

```
python3 tools/swarm.py -j 4

discovered 3554 = verified 1966 + wrong 18 + changed 273
                + dead 34 + hidden 204 + failed 4 + excluded 1055   OK
checked against a stated expectation: 1984 of 2257 driven (87%)
```

Twelve expectations, each written in terms of what a user would see: a tab leaves
exactly one pane open and it is the named one; a stepper moves in the direction its
label promises; a field holds what was typed; a slider **displays** the number it
was set to; an option **selects** when clicked, and alone in a radio group; a
filter's survivors all match the query, some were removed, and clearing brings them
all back; an add makes exactly one more row; a clear leaves fewer fields holding
anything; an undo returns to a state the run has been in; an export leaves the page,
**parses**, and contains what was typed into the form.

A control with no expectation is called `changed`, not verified. That is the honest
name for what the old number was.

**The seed makes the questions askable.** Every text field gets a recorded sentinel,
then every add-shaped button is pressed, then every save-shaped one — filling a form
is not the same as having a record, and four exports were called wrong for that
difference before the seed learned to commit.

## Nine defects, all the instrument's

| what it reported | why it was wrong |
|---|---|
| three live exports produced nothing | the verdict used the label from discovery while the action landed on whatever that selector names *now* — an export oracle applied to a quadrat arrow |
| 19 of the first 35 findings | a correct refusal read as a wrong result |
| a live plus button left no trace | the walk had typed a text sentinel into the stepper's value; the next press computed `NaN`, and the one after that computed `NaN` from `NaN` |
| twelve controls wired to nothing | a toast raised while an identical toast is on screen is not a mutation |
| three AI-prompt exports were ragged CSVs | a comma in line one is not a column |
| two filters failed to filter | the query matched every option, or there was only one |
| 54 undriveable controls on experiment-guide | its pane opens by a route the harness insisted was the only one |
| 108 affordances the harness could not drive | an element gone between snapshot and read is a fact about the page, not a failure — now 4 |
| a two-pane page had "no such tab" | `show-pane` asked whether the pane was *the* open one, refusing before the oracle could report |

Two expectations were **retracted**: a *Clear* had been asserted to empty every
field, and breeding-bench's correctly scoped *Clear trial*, field-notebook's
stopwatch *Reset* and its quadrat *Clear* were all reported as defects for not doing
what they never promised.

Four pages, first run: **35 wrong**. After the corrections: **7**.

## `tools/verify/verify_swarm.py` — 28 checks

Ten fixtures. Nine are wired, respond to every click, and would pass the old oracle;
each is asserted to be caught **by its own oracle by name**. The tenth is in order
and must produce nothing. The accounting identity is asserted on all ten. One
fixture failed first time and the fixture was wrong — which is how the `NaN` defect
above was found.

## How the swarm reaches the page

Typed actions rather than clicking at everything: `press-step` with a direction,
`set-text` with a value, `choose-option` with an option. That is what makes the
oracles possible — the harness knows what it asked for, so it can say what it
expected. The layer carries the safety properties that come with letting anything
drive these pages automatically (off unless enabled, a token on every call, values
withheld unless unlocked, generic activation treated as the most consequential thing
a selector can mean, a request id so a retry does not act twice), a ~120-line stdio
adapter, an operator page in `docs/AUTOMATION-HARNESS.md`, and 65 assertions in
`tools/verify/verify_contract.py`.

## The worklist

**18 wrong results**: eleven exports (nine carrying none of the values entered even
after a record was saved; one copying nothing silently; one CSV with a row of the
wrong width), four Adds that add no row and say nothing, two clears that clear
nothing, one Delete that removes nothing. **34 affordances that left no trace**,
headed by fifteen ethogram behaviour buttons and five farm-scout minus arrows.
ADR-100's fifteen-page `white-space` defect is still open.

## Suite

```
63 of 63 jobs green, 4415 of 4415 checks passing   (61 / 4322 before)
verify_swarm     28/28   new
verify_contract  65/65   new
```
