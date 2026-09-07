# Changelog — 2026-09-06 — ADR-150: assigning a value is not typing

The fifth page taken whole — and the first one that could not be driven.

## The wall

`experiment-guide.html` was the largest gap left at 16 of 52 fields. Three
fields in, the task hit something no earlier page had:

```
lint says "seed must be a whole number"
— and nothing the harness could do would make it say that.
```

`set-text` writes through the `value` setter. That is what a **script** does. A
person presses keys, and for `<input type=number>` the page can tell:

| | `.value` | `validity.badInput` |
|---|---|---|
| assign `"3e"` | `""` | **false** |
| type `"3e"` | `""` | **true** |

A number box the browser cannot parse reads back as the empty string — exactly
what a deliberately blank box reads as. Only `badInput` separates them, and it
reflects a keystroke buffer no assignment fills.

## New action — `type-text`

Clicks the control, clears it, sends real keystrokes. DRAFT rung, same kinds as
`set-text`.

`verify_report` **95** (+10): the table above; typing an empty value **clears**
the control rather than doing nothing; typing into a button is refused the way
`set-text` refuses it. `mutate_report` **57** (+5).

Chromium filters keystrokes on the way in — `many` types as nothing at all,
while `3e` is a number the user started and did not finish. What survives the
filter is the browser's business.

## The defect behind it — `docs/experiment-guide.html`

```js
if ($("e-seed").value !== "" && isNaN(parseInt($("e-seed").value, 10)))
```

The `value !== ""` lets a **blank** seed mean *use 42*. A seed the user typed and
the browser rejected reads as `""` too — so the box showed their text, the
protocol carried `seed: 42`, and the linter said nothing. Fixed with
`validity.badInput`, which is ADR-148's `numField` rule (*reported, never
guessed*) reaching the page next door. Keys and window said **"out of range"**,
which is a different sentence from the true one; they now say *"is not a whole
number"* when that is what happened.

## The task — `tools/tasks/page-experiment-guide-design.json`

42 steps → **165**.

```
experiment-guide.html  16 → 52 of 52 fields  (53 → 220 confirmed expectations)
the kit               349 → 385 of 520 fields (67% → 74%)
```

**The guide's advice is checkable.** Every lint finding is answerable, and
answering it clears exactly that finding: four `MISSING` on the engineering track
cleared one at a time to `CLEAN — pre-registration complete`; a hypothesis naming
a community that does not exist grades `UNGRADEABLE`; one comparing a simulated
phase to entered field data shares no species.

**Two doors, one rule.** The builder refuses a duplicate community name; the
importer accepts a protocol carrying one and the linter reports it — rewriting
someone's record on the way in would be changing it to make it pass.

**A verdict needs a rule *and* numbers.** Half a reading is not a verdict.

**A qualitative hypothesis is graded against a band**, and the emitted line reads
`expect: evenness(graze) is uneven`.

Five pages entered whole: collection-sheet, stand-sheet, ecology-lab, relevé,
experiment-guide.

## Three things the robot found that the task could not

**A click is not a focus.** The first draft clicked to place the caret. The robot
drives every tool at every control, including ones a layout covers, where a click
waits out its whole 30-second actionability timeout and the walk files the wait
as *the page failing* — nine such failures across five pages. Typing needs the
focus; a control that cannot take focus is refused at once, naming the reason.

**An action added to a pool competes for it.** `type-text` claimed `pick_search`,
and pheno-tracker's walk then drove it where it used to drive `pick` — reporting
`pick` undriven on a page that offers one. Out of that pool now.

**Adding a tool re-rolls every seeded walk.** 21 tools → 22 shifted every page's
schedule. Pheno-tracker's pickers have no options until a plant exists, and the
new schedule reached `pick` first: 24 attempts, none driven. Its walk carries an
explicit seed now, and `pick` is counted **unreachable** there — which is what it
is.

`verify_walk` **126**, `verify_mcp` **73**: the page tool count `21` → `22` in
four places.

## Held

- `type-text` is slower and is for where the difference matters; every existing
  task keeps `set-text`.
- It does not reproduce every difference between a script and a person — paste,
  IME, drag-select, autofill and key repeat are still outside it.
- The other number inputs across the kit have not been retyped; the same silence
  is possible anywhere a page treats a blank field as meaningful.

## Docs

`docs/ADR-150-assigning-a-value-is-not-typing-2026-09-06.md`; `docs/AI_HARNESS.md`.
