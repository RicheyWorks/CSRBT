# 2026-09-15 — ADR-210: a page with your work already in it is a page nobody had ever looked at

**ADR-207 gave seventeen pages an autosave. It also created a state of every one
of them that nothing in this harness had ever measured: the page as it comes
back. 125 things those pages said before the tab closed, they did not say when
it came back.**

## Fixed

- **`greenhouse.html` kept the saved runs and not the reading log they are built
  from** — nor the yield, rated wattage, tariff, lux reading or photoperiod. The
  environment analysis, light integral, electricity cost and log table all came
  back empty while the strip said the page had been restored.
- **`releve.html` kept records, scale and photographs** — not the vouchers, the
  LPI transect, the wetland indicator per species, or the coordinate uncertainty.
  The wetland analysis said *"no indicator statuses entered"* over a sheet that
  had four; the coordinate came back at 13 m where 43 m had been typed.
- **`stand-sheet.html` did not keep the species packs** a reader had pasted in,
  so the key filter, the tally list and the "species loaded" tile reported the
  kit's own shipped numbers over somebody else's morning.
- **`collection-sheet.html` did not keep the herbarium labels** it had made:
  *"No labels yet."*
- **`breeding-bench.html` kept nothing typed into eighteen FEK controls**,
  because not one of them declared a field.
- **`pheno-tracker.html` kept the run and not the boxes beside it** — the
  segregation counts and the cross being tested.
- **`ordination.html` brought the matrix back and not the ordination** — stress,
  verdict, scree and Shepard notes, blank over a sheet that had them.
- **`cp-bench.html` painted six panes of thirteen**; `field-notebook.html`
  brought the quadrats back and not the Morisita index; `ethogram.html` brought
  two observers' sequences back and not the κ over them; `selection-log.html`
  drew its report card for the wrong trait.

## Added

- **`tools/audit_restored.py`** — open the page, replay its task, flush the
  autosave, reload, and compare what `read-report` said either side of that. A
  loss is a key that went **or a value that changed**. Ratchet downward per
  page; an exemption needs a reason and the reason is stored.
- **FEK 1.7.0 — `FEK.values()`.** The field registry had a way in and no way
  out, so a control that declared a field but had no hidden input behind it was
  invisible to the autosave.
- **KEEP 1.4.0** captures those fields and puts them back through `setField`,
  so a control declares `field:"selN"` and is kept, with no hidden input to
  remember to write to.

## The shape, a sixth time

`verify_keep` checks that *every write-through component declares its field* —
read over the components that already write through. A component that writes to
**nothing** is invisible to it, which is what eighteen breeding-bench controls
were. The answer here is not a better list: it is to stop enforcing the rule
over a list and **measure the outcome**.

## Two orderings

- A restore that runs **before** the boot paint gets repainted over it.
- On a page that rebuilds its entry controls from its own records, a value
  restored **before** that rebuild is one the rebuild replaces with its default.
  Restore, paint, restore again.

## Declared, with a reason

- Kit-wide: the **autosave strip**, the **outbox strip** and the **toast** say
  what just happened, and a reload is a thing that just happened. A **pane** is a
  container and changes when anything inside it does.
- Per page: a pack loader's verdict on the last paste, a session clock, a
  per-plant note editor that needs a plant selected, and a voucher label that
  regenerates from the record and comes back with *more* than it had.

## Checked

- `verify_restored` 25 · `mutate_restored` 19
- Four fixtures from one template, differing only in what they keep and what
  they repaint, plus a fifth whose restore refuses the blob — because a reading
  taken from a page that never came back is about the instrument.

## Standing

**0 of 552.** Every figure and every block these seventeen pages publish before
the tab closes, they publish when it comes back.
