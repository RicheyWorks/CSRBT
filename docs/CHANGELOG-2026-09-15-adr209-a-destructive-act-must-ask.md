# 2026-09-15 — ADR-209: the door has called it destructive since ADR-112; the page never asked

**Fifteen controls across this kit took two or more of your records on one tap
and asked nothing. "Clear trial" sat next to "Add plot" on a phone, in a wet
field, under a thumb. The gateway has raised DESTRUCTIVE on that button since
ADR-112 — a task must declare a rung to reach it, the outputs audit refuses to
press it — and none of that ever reached the person doing the tapping.**

## Fixed

- **Eleven bulk clears now ask, naming what goes and how many.** The breeding
  bench's trial, the cell bench's standard curve and mitotic count, the cp and
  soil benches' mixes, the soil bench's pile, the ethogram's two sequences, the
  greenhouse's reading log, the micro bench's growth curve, the ordination
  matrix, the field notebook's quadrats, the survey's target list, and *Start
  over* on both tracks of the experiment guide.
- **Three deletes that cascaded now say so.** Removing a plant from the cp bench
  took nine observations with it; removing a trait from the selection log took
  eighteen typed measurements; removing an individual took its measurements *and*
  its pedigree links. Each row displayed the count and none of them said it was
  attached.
- **The button that removed the backup was removing the original.** *Forget this
  device's copy* on the experiment guide blanked the design on screen as well —
  seventeen records to a button whose label promises only that a saved copy
  stops existing. The copy goes; what you are looking at stays.

## Added

- **`tools/audit_destructive.py`** — the gateway's own `destroys` rule, asked of
  the page. A ratchet downward per page, an exemption that needs a reason, and
  the reason stored word for word.
- **KEEP 1.3.0 — `KEEP.live()`.** A page wires the autosave inside an IIFE and
  keeps the handle in a local, so the one description of its own state that the
  autosave writes and the outbox checksums was reachable from nowhere else.

## The instrument, twice over

- **Rows on the screen are not records.** The first draft counted
  `read-report`'s rows, and a plate shown once in its list and once in the
  results table read as two — so a row remover looked like a bulk delete, while
  a trait delete that emptied a table of eighteen looked the same size as the
  row. A rule that cries wolf on a crossed-off chip is off within a week, and
  then the sheet-clearing ones are invisible again.
- **A record's own fields are not records either.** Counting them made an Undo
  that pops one measurement read as taking five.
- **But a typed field is one.** The ethogram's kappa pane keeps two observers'
  sequences in two textareas and no array at all.

## And the question itself is now watched

- **A question whose answer changes nothing is not a question.** Every control
  that asks is pressed twice — yes and no — and one that takes records on the no
  path is `IGNORES`, on the worklist beside the ones that never asked. No page in
  this kit does it, so the rule is driven against a **defiant fixture**: two
  buttons that both ask, both take three records on yes, and differ only in
  whether the answer means anything.
- **The audit was measuring its own history.** One control per page, one shared
  browser context, and the autosave carried a sheet from each measurement into
  the next — the same button reading three records on one run and six on
  another. Storage is cleared before each page's own scripts run.

## Declared, with a reason

- **`ethogram.html:rUndo`** — it takes its own history entry plus the record
  that entry names: two things leave the autosave and the person loses one.

## Checked

- `verify_destructive` 44 · `mutate_destructive` 30, all killed
- `verify_keep` 282 → 316 · `mutate_keep` 30 → 32, all killed
- Three fixtures: one that keeps its state and shows every row twice, one that
  keeps nothing at all, one that asks and ignores the answer, so the fallback reading is exercised on a page with data
  in it rather than reported clean by silence.
- `before − after == loss` on every row, because a number with nothing behind it
  is what this run of slices keeps finding.

## Standing

**0 of 95** destructive controls take two or more records on one tap and ask
nothing. Twenty-one now ask; thirty-three take exactly one; twenty-five pages carry a
ceiling of zero.
