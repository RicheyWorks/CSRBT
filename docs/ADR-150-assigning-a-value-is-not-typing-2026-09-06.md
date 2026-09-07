# ADR-150 — Assigning a value is not typing

**Status:** accepted · **Date:** 2026-09-06 · **The fifth page taken whole — and the first one that could not be driven, because a whole class of real user input was outside what any task in this kit could produce. `set-text` writes through the value setter; a person presses keys, and for `<input type=number>` the page can tell. 16 → 52 of 52 fields, 53 → 220 confirmed, and the kit reaches 385 of 520 (74%)**

## 1. The page, and the wall

`experiment-guide.html` was the largest gap left at **16 of 52 fields**. It is
the kit's design bench: a study builder that emits an `.eco` protocol, a
benchmark pre-registration planner, a ten-item pre-flight checklist, and — the
part worth driving — **two linters** that tell you what is missing or weak in
what you have designed.

Three fields in, the task hit something no earlier page had:

    lint says "seed must be a whole number" — and nothing the harness could do
    would make it say that.

## 2. Assigning a value is not typing

`set-text` writes through the `value` setter. That is what a *script* does. A
person presses keys, and for `<input type=number>` the two are not the same:

| | `.value` | `validity.badInput` |
|---|---|---|
| assign `"3e"` | `""` | **false** |
| type `"3e"` | `""` | **true** |

A number box the browser cannot parse reads its value back as the empty string —
**which is exactly what a deliberately blank box reads as.** Only `badInput`
tells them apart, and `badInput` reflects the user's raw keystroke buffer, which
no assignment fills.

So a page that distinguishes them has a branch **no task in this kit could
reach**, because the harness had only the first way.

**New action: `type-text`** (DRAFT rung), which clicks the control, clears it,
and sends real keystrokes. `verify_report` **95** (+10) holds the table above,
that typing an empty value *clears* the control rather than doing nothing, and
that typing into a button is refused the same way `set-text` refuses it.
`mutate_report` **57** (+5).

**Chromium filters keystrokes on the way in**, so not all text arrives: `many`
types as nothing at all and is not bad input, while `3e` is a number the user has
started and not finished. What survives the filter is the browser's business; the
harness types what a person types.

## 3. The defect that was waiting behind it

`docs/experiment-guide.html`'s linter guarded the seed like this:

```js
if ($("e-seed").value !== "" && isNaN(parseInt($("e-seed").value, 10)))
  no("seed must be a whole number");
```

The `value !== ""` is there so a **blank** seed can mean *use 42*. And a seed the
user typed and the browser rejected reads as `""` too. So: the box showed their
text, the emitted protocol carried `seed: 42`, and the linter said nothing.

Fixed with `validity.badInput` — which is the interactive lab's own rule
(ADR-148's `numField`: *reported, never guessed*) reaching the page next door.
Keys and window were never silent, but they read as **"out of range"**, which is
a different sentence from the true one; they now say *"is not a whole number"*
when that is what happened.

## 4. The guide's advice is checkable

The linters are the page's product, and nothing was checking them. The task now
holds that **every finding is answerable, and answering it clears exactly that
finding and no other**:

- the engineering track opens with four `MISSING` — no question, no floor, no
  decision rule, no sizes — and each field filled removes its own line, ending at
  `CLEAN — pre-registration complete`;
- the ecology track opens with two `WEAK` — no phases, no pre-registered
  hypotheses — and a hypothesis naming a community that does not exist is
  `WEAK … it will grade UNGRADEABLE`, while one comparing a simulated phase to
  entered field data is `WEAK … they share no species`.

## 5. Three more claims, now held

**Two doors, one rule.** The builder **refuses** to add a second community with a
name already taken — the add is declined and the list does not grow. The
**importer accepts** a protocol that has one, and the linter reports it. Rewriting
someone else's record on the way in would be changing it to make it pass.

**A verdict needs a rule *and* numbers.** The base task held that a verdict
without a decision rule is refused. A verdict without a measured row is refused
too, for the same reason: a verdict is a reading against a bar, and half of it is
not a verdict.

**A qualitative hypothesis is graded against a band, not a number.** Choosing
`evenness … is …` puts away the Test and Value boxes and offers a Band list, and
the emitted line reads `expect: evenness(graze) is uneven`. A prediction that
names a band is falsifiable too.

## 6. Three things the robot found that the task could not

A new action goes into the manifest, and the manifest is what the robot walks.
Adding one told us three things:

**A click is not a focus.** The first draft clicked the control to put the caret
in it. The robot drives every tool at every control — including ones a pane
reveals but a layout still covers — and there a click waits out its whole
thirty-second actionability timeout for a hit test that never comes, and the
walk files the wait as *the page failing*. Nine such failures across five pages.
Typing needs the focus, not the pointer, and a control that cannot take focus is
a fact about the page (HIDDEN's family): refused at once, naming the reason.

**An action added to a pool competes for it.** `type-text` claimed
`pick_search`, and the walk of `pheno-tracker.html` then drove it where it used
to drive `pick` — reporting `pick` **undriven on a page that offers one**. It is
out of that pool now: typing into a picker's search box is what `pick` is for.

**Adding a tool re-rolls every seeded walk in the kit.** The page manifest went
21 tools to 22, and every page's seeded schedule shifted with it. That surfaced
a standing fact about `pheno-tracker.html`: its two pickers have no options until
a plant exists, and under the new schedule the robot reached `pick` before any
plant — twenty-four attempts, none driven. Its walk carries an explicit seed now,
recorded in the ledger, and under it the page's `pick` is counted **unreachable**,
which is what it honestly is: a tool the page offers nothing for.

`verify_walk` **126** and `verify_mcp` **73** carried the tool count `21` in four
places; all four now say `22`.

## 7. The numbers

    experiment-guide.html  16 → 52 of 52 fields  (53 → 220 confirmed expectations)
    the kit               349 → 385 of 520 fields (67% → 74%)

Five pages entered whole: collection-sheet (59 of 63, four reagent rows
deliberately blank), stand-sheet, ecology-lab, relevé, experiment-guide.

## 8. Held

- **`type-text` is slower than `set-text`** — it is a click, two key presses and
  one keystroke per character — so it is for the cases where the difference
  matters, not a replacement. Every existing task keeps `set-text`.
- **It does not reproduce every difference between a script and a person.** A
  paste, an IME, a drag-select, an autofill and a keyboard repeat are all still
  outside it. What it buys is one specific, checkable distinction the pages
  themselves already act on.
- **The other number inputs across the kit have not been retyped.** Anywhere a
  page treats a blank field as meaningful, the same silence is possible; nothing
  here has looked. That is a worklist, and it is stated rather than done.
- `deployment-log.html` at 17 of 37 is now the largest gap left.
