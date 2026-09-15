# ADR-208 — A silent button is not an output

**The audit that exists to find a page whose work cannot leave it decided what a *button* was from the word `save` in a label, and from whether a control's kind was spelt ending in `_in`. So a number box captioned "Plants you plan to save seed from" was pressed as an export, handed nothing over, and was filed `silent` — a number in a column that nothing named, no ratchet held, and no exit code cared about. Eighteen of them stood in this kit. Nine were not buttons. One of the nine was the whole reason the breeding bench, with eighteen typed values and no way out, had never been reported as the data trap ADR-205 was written to catch.**

## 1. The rule that decided what a button is

`audit_outputs` picks its candidates by label: `copy`, `download`, `export`,
`print`, `save`, `.csv`, `.eco`. Every control on every page has a label, so
that regex alone would press half a page. The line that was supposed to stop it
read:

```python
if c.get("kind", "").endswith("_in") or c.get("kind") in ("pick_search",):
    continue
```

**That is a check about how a kind is spelt.** It catches `text_in`,
`field_in` and `file_in`. It lets through `step_val`, `slider`, `select`,
`checkbox`, `drop_zone`, `pick_opt`, `tab` — which is most of what this kit
composes, and every one of those carries a label a person wrote.

`verify_outputs` pinned the rule with a fixture:
`<input id="plans" aria-label="Plants you plan to save">`. An `<input>` is
`text_in`. It is the one kind whose spelling happens to match. The check read
green for fifty-five slices.

The statement the kit could already make is a positive one: **a control the
door does not press is not a button that hands anything over.** The door's own
argument pool for `activate` says which kinds those are, so the audit reads it
from there:

```python
PRESSED = frozenset(PP.POOL_KINDS["activate"])
```

A kind added to that pool tomorrow counts tomorrow. ADR-141's rule, for the
fifth time in five slices.

## 2. What made it invisible: silence was a number in a column

A press that hands nothing over is recorded `silent`. That verdict was counted,
printed as a column total, and **named nowhere, ratcheted nowhere, and never
failed anything**. So three quite different things read identically:

- an export that quietly stopped working,
- a control the audit should never have pressed,
- a page that is right to hand nothing over.

`silent` is now a second worklist with a second ratchet that runs the same way
down: `mute_ceiling` per page, may not rise, comes down as buttons are fixed,
and a button that is right to be silent is **declared with a reason** that goes
in the ledger word for word. Eighteen readings became nine real ones. Nine are
declared. The reasons are worth reading, because between them they are why a
label can never decide this alone:

- **`pSave` / `cSave` / `runSave`** — *Save to collection*, *Save to cross*,
  *Save this run*. Every one commits a row to the page's own list. Entry, not
  handover.
- **`imp-file`, `wb-eco-import`, `srcCtl/Controller export`** — the other
  direction entirely. *Choose .eco file…* opens a picker for a protocol coming
  **in**; *Controller export* is the name of a file this page **reads**.
- **`track-eco`** — a pane chooser that carries `.eco` because that is the
  format the track ends in.
- **`fkq/no print / not applicable`** — a key answer about a **spore print**,
  the deposit a cap leaves on paper overnight. The word is mycology's.
- **`wb-eco-build`** — the one that was a real finding. See §4.

## 3. The data trap ADR-205 was written for, and missed

The breeding bench: eighteen typed values across a roguing log and a replicated
yield trial, and no way to get any of it off the screen. ADR-205 taught this
audit that a page with **no** output button is the loudest row a ledger can
print. The breeding bench had one — the number box — so it never produced that
row. **The false candidate was hiding the true trap**, and neither half was
visible without the other.

It exports now: **Copy the bench sheet** and **Download bench.csv**, one section
per table, with the population and selection figures beside the rows they were
read against, and an outbox ledger so the page can say what has not left this
device. The **cp bench** got the same — its water log, mix, plants,
observations, dormancy record and crosses, where before it could hand over a
soil recipe and nothing else. Both were named as unfixed in ADR-207 §4; both are
fixed here.

Each new export is **held**: the page's own task presses it and then asks what
came out, against the rows the task itself entered.

## 4. The ecology lab built a protocol and left it in a box

`build .eco lines from my entries` writes the protocol the student is told to
save into a read-only textarea — and stopped. On a phone, selecting the contents
of a 120px textarea by hand is the step where the morning is lost. It has a
**copy the .eco lines** button now, which emits and is held; the build button
itself is declared silent, with that sentence as its reason.

## 5. A refusal nobody asked for is a failure

This one came out of the slice's own first draft. ADR-208 added
`collect-output` steps to two bench tasks and wrote them with a `selector`
argument that action does not take. The door refused both. Each task reported
**PASS, 115 confirmed, 0 refuted** — with the one step whose whole job was to
look at what came out never run.

A step that **failed** with nothing said about it has ended the task since
ADR-126. A step the door **refused** did not: it graded nothing, because it
expected nothing, and the runner moved on. So a task could ask the door for
something it will not do and not notice.

The kit already had the grammar for a refusal a task means to provoke —
`expect: {"ok": false}`, or an expectation about `code`; the collection sheet's
`hostgone` types a filter that matches nothing and says so. So the rule reads
off what the task **claimed** rather than a list of steps allowed to be refused,
which would go stale the first time a task grew one:

> a refused or declined step whose expectations say nothing about `ok` or
> `code` fails the task, exactly as an unexpected failure does.

All 55 shipped tasks still hold. **No target in this kit answers a task step
with a `declined`** — the fixture's destructive rung answers `failed`, which is
the other branch — so that half of the rule has no violator anywhere, and
narrowing it back to refusals alone would change nothing a check over the real
targets could see. ADR-207's finding, arriving on the rule written in answer to
ADR-207's finding. It is driven through a **scripted door** instead: a wire that
answers exactly the way a declining gateway does.

## 6. And the ledger is marked from two places

The outbox suite read every export a page can make out of its `copyText(...)`
call sites. A **download** has no clipboard promise to hang the mark on, so the
page calls `SENT.sent("id", bytes)` itself in the path where the bytes went.
Both new downloads were therefore reported as exports declared but impossible —
the rule enforced over one of the two shapes the thing it measures actually has.
It reads both now.

## 6b. The download is not marked in the outbox

The artifact viewer refuses a page-started download **silently** — no throw, no
return value, nothing a page can test. So a `.sent()` beside `a.click()` would
be the exact ADR-203 defect one layer along: the ledger reporting a sheet as
gone from this device that the browser never let leave. Both new CSV buttons
stay, with the sentence the experiment guide already carries — *if your viewer
blocks downloads, use Copy and paste into a file* — and only the **copy** is
declared and marked, because a clipboard write says no.

Which leaves the `.sent` reader of §6 with no violator in the kit. It is driven
over a source written in the suite instead, both shapes in one line, plus the
component's own forwarding call that must not count. ADR-207's answer, applied
to the rule written in the same slice as the reason for it.

## 7. What is checked

`verify_outputs` 38 → 58. The fixture grows a step control, a slider, a select,
a tick box and a drop zone, **every label naming a handover and not one of them
spelt with the two characters the old rule looked for** — checked against the
page's own snapshot, because a check that only asserts an absence passes just as
well when the control was never there.

`mutate_outputs` 31 → 44. And one of the new ones **survived**: the check on the
mute ratchet's direction was written from a reading that already equalled the
ceiling, so inverting the comparison changed nothing. Rewritten from a page that
is **over** its ceiling — ADR-207's lesson, one slice later, on the rule written
to answer ADR-207.

`verify_tasks` 383 → 392, `mutate_tasks` 87 → 91.
`verify_outbox` 316 → 337: a fourth bench driven through a real export button
with the clipboard accepting and then refusing, and the `.sent` call sites read.

## 8. What stands

`0 of 80` outputs leave a page with nothing reading them, and `0` buttons hand
over nothing that has not been judged in writing. Twenty-four pages carry a mute
ceiling of zero.
