# ADR-209 — The door has called it destructive since ADR-112; the page never asked, and the question had never been refused

**Fifteen controls across this kit took two or more of your records on one tap and asked nothing. "Clear trial" sat next to "Add plot" on a phone, in a wet field, under a thumb. The gateway has raised DESTRUCTIVE on that button since ADR-112 — a task must declare a rung to reach it, the outputs audit refuses to press it, the risk ladder publishes it in its own argument pool — and none of that classification ever reached the person doing the tapping.**

## 1. The kit's own rule, asked of the page

`harness_plugin_page.destroys()` is the function every layer of the harness
already consults. `tools/audit_destructive.py` presses what it names, with the
page's own data in it, and measures:

| | |
|---|---|
| **ASKS** | a `confirm()` fired, and answering no stopped it |
| **IGNORES** | it asked, and took the records whatever the answer |
| **NOTHING** | the page held the same records afterwards |
| **ONE** | exactly one record went — what an Undo is for |
| **BULK** | two or more went and nothing asked — the worklist |

Not a second list of dangerous buttons kept in the audit. The rule is read from
the gateway, and only controls the door would *press* are candidates — ADR-208's
positive rule, read from the same `activate` pool.

## 2. Rows on the screen are not records

The first draft counted `read-report`'s rows and table rows. It was wrong in
both directions at once:

- a plate shown once in its list and once in the results table built from it is
  **one record counted twice**, so a row remover read as a bulk delete;
- a trait whose eighteen measurements live in a table the remove also empties
  read as the **same size** as the row itself.

A rule that cries wolf on a crossed-off chip gets turned off within a week,
and then the sheet-clearing ones are invisible again — ADR-112's own warning,
arriving on a rule written a hundred slices later.

So the audit asks the page what it is **holding**, through the autosave: the
description the page already writes for every save and the outbox already
checksums. **KEEP 1.3.0** makes that handle reachable from outside the page's
closure (`KEEP.live()`), because a page wires KEEP inside an IIFE and kept the
only description of its own state in a local. One description, read by
everything that needs it. A page with no autosave falls back to the screen and
**says which reading it is** — a rule that silently measured nothing on such a
page would report every one of them clean.

A record is an element of an array the page keeps, or a form field with
something typed in it. Not the fields *inside* a record: counting those made an
Undo that pops one measurement read as taking five, which is the same crying
wolf one layer in. Not an array without the other: the ethogram's kappa pane
keeps two observers' sequences in two textareas and no array at all.

## 3. What one tap was taking

Fifteen, then seven once the instrument was honest, then none:

- **breeding bench** — `Clear trial`, four plots, the button beside Add.
- **cell bench** — the standard curve; the mitotic count.
- **cp bench** — the mix; and **removing a plant removed nine observations of
  it**. The row said *"9 observations"* and did not say they went with it.
- **selection log** — **removing a trait removed eighteen typed measurements**;
  removing an individual removed its measurements *and* its pedigree links.
- **ethogram** — both observers' sequences and the agreement matrix.
- **greenhouse** — the reading log. Its sibling *"Clear every saved run?"* has
  asked since it was written; the one that takes the readings those runs are
  built from did not.
- **micro bench**, **ordination**, **field notebook**, **survey design**,
  **soil bench** — growth curve, matrix, quadrats, target list, pile.
- **experiment guide** — *Start over*, on both tracks, on the page that takes
  more typed values than any other in this kit.

Each confirmation **names what goes and how many**, because "Are you sure?" is
a question nobody reads.

## 4. And the button that removed the backup was removing the original

**Forget this device's copy** on the experiment guide blanked the design on the
screen as well — seventeen records gone to a button whose label promises only
that a saved copy stops existing. Every other page in this kit leaves the
working state alone. The label was the honest half; the code was not. The copy
goes; what you are looking at stays, and the next edit saves it again.

## 5. One exemption, written down

The ethogram's `↩ Undo` keeps an undo stack in its autosave, so a press takes
two things from the description — its own history entry and the record that
entry names — while the person loses one. Declared, with that sentence, in the
ledger where the judgement can be read. Every Undo in this kit that keeps a
stack reads the same way, and a rule that called them bulk deletes is the rule
nobody would keep.

## 5b. A question whose answer changes nothing is not a question

The stub answers `confirm()` with **true**, which is what makes the loss
measurable — the act happens and the records that went can be counted. It also
means the rule above only ever watched the **yes** path. A page can ask a
question, ignore the answer, and destroy anyway. That reads as ASKS, and it is
*worse* than never asking: a question the page does not mean teaches the person
that every question on it is noise.

Every destructive control that asks is now pressed **twice** — once with the
answer yes, once with it no — and one that takes records on the no path is
`IGNORES`, on the worklist beside the ones that never asked at all.

**No page in this kit does this.** All twenty-one that ask honour the answer, so the
rule has no violator anywhere and would read green if it had never been
written. It is driven against a **defiant fixture** instead: two buttons that
both ask, both take three records on the yes path, and differ only in whether
the answer means anything. ADR-127's point about a refusal nobody has watched
and ADR-207's about a rule with nothing left to catch, arriving together on the
confirmations the rest of this slice added.

## 5bb. An Undo cascades too, and the corrected instrument found it

The selection log's `↩ Undo` takes the last individual **and** every measurement
and pedigree link that names it — which is what undoing an add has to mean, but
*Undo* is the word a person presses without reading, and it was taking
measurements typed long after the add it reverses. It read as a one-record
remover right up until the audit stopped carrying the previous page's autosave
into the measurement.

## 5c. And the audit was measuring its own history

One control is pressed per page and every page shared one browser context, so
the autosave ADR-207 gave these pages carried a sheet from the previous
measurement into the next: the same button read as taking three records on one
run and six on another, depending on how many pages had been opened before it.
Storage is cleared before each page's own scripts run — after load would race
the restore. ADR-155's defect, on browser storage instead of on a fill counter.

## 6. What is checked

`verify_destructive` 44, over three fixtures: one that keeps its state and shows
every row twice, one that keeps nothing at all, and one that asks and does it
anyway. It pins that the multiplication
sign in *"Copy host × taxon matrix"* is not a delete; that a text box whose
label says *clear* is not a control anybody taps; that three records are three
and not six; that a typed field is a record; that asking does not stop the loss
being measured, because the stub answers `confirm` with true and a rule that
stopped at *"it asked"* would not know whether asking stopped anything; and that
`before − after == loss` on every row, because a number with nothing behind it
is what this whole sequence of slices keeps finding.

`mutate_destructive` 30, all killed. `mutate_keep` 30 → 32, all killed.
`verify_keep` 282 → 316.

## 7. What stands

**0 of 95** destructive controls across the kit take two or more records on one
tap and ask nothing. Twenty-one **now ask**; thirty-three take exactly one; the rest
take nothing. Twenty-five pages carry a ceiling of zero.
