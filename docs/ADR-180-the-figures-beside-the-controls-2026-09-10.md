# ADR-180 — The figures beside the controls: the readable audit reads an entry host by what remains once its widgets are removed

**Status:** accepted · **Date:** 2026-09-10 · **ADR-146's readable audit skipped any element that holds a control, so a figure a page writes beside a button — a ranked row with a star to keep it, a count on a tally card, a rotation verdict next to its picker, the survey's event tree with a copy button per row — was never on its worklist. The audit now reads such a host by what remains once its controls, the entry kit's widget furniture and its links are subtracted, on both sides of the comparison. Forty-two more written elements are measured; six were blind. The survey's event tree becomes a box, held by its task byte for byte and pinned by a port of the example's ID scheme; five are declared furniture with reasons. Every ceiling is 0 again.**

## The hole, named in ADR-146 and carried since

`audit_readable` measures WRITTEN — the elements whose rendered text changed
while the page's own task ran — against READABLE, what `read-report` returns.
ADR-146 excluded any element holding a control (`data-h`), and for a reason:
the Field Entry Kit mounts its widgets into a div, the div's text then
changes, and forty *Entry hosts across the kit would otherwise read as
"figures the harness cannot see" — true of the string, false of the thing,
since what is inside them is controls and `entry_reach` accounts for those.

But the exclusion was the whole host. ADR-171 named the cost — `rankBoard`
"is read as a box now but still skipped by the audit as an entry host, so a
figure with a button inside it is still not counted as written" — and left
it. Measured now, the shape recurs: the pheno tracker's ranked run (rank,
plant, score, a star), its cross list and score panel and trait chips; the
scout's per-stop counts on their tally buttons and each bed's rotation
verdict beside its picker; the notebook's quadrat counts; the soil bench's
feedstock rows; the survey's event tree, fifteen generated IDs with a
*copy ID* and a *remove* button on every row. Forty-two elements the audit
had never measured, because each holds a button.

## What changed

**The audit reads a host by its remainder.** For an element that holds a
widget — a stamped control, a button, an input, a select, a textarea, a
label, a link, or one of the kit's own widget wrappers (`.fek-row`,
`.fek-step`, `.fek-dial`, `.fek-pick`, `.fek-field`, `.fek-slide`,
`.fek-chip`, `.fek-lab`, `.fek-help`) — the text measured is the text of a
clone with those removed. The same subtraction is applied to the baseline
(the file, rendered by nothing), so a label the kit paints at boot is not a
figure and a count the page writes beside a button is; a static paragraph
with a link in it is read minus the link on both sides and is not written. An
empty remainder is no figure. The rule stays structural: a control is a
control because the swarm stamped it, a widget by the kit's class names, a
link because the robot presses it. The audit still stamps the controls
first, because on a page with no task nothing else does — and the `.kopt`
option divs of a character key are controls only by that stamp.

**Written 270 → 312, blind 6.** Of the forty-two newly measured, thirty-six
were already readable: `rankBoard` and the lists and grids the reader names.
Six were not:

- `survey-design.html` **`tree`** — the event hierarchy: type, generated ID,
  name, date per event. A figure: the IDs are the page's work (`SGH2026:
  visit:08`), and nothing could read them. `read-report` now names `tree` as
  a box by its whole id, beside `journal` and `toast`; the survey task holds
  `boxes.tree` **byte for byte** — fifteen rows in hierarchy order — and
  `verify_sd` pins that literal to a port of the example's own ID scheme
  (one survey; sites 01–02; plots 01–04 across the sites; visits 01–08
  across the plots, zero-padded), so the task cannot transcribe the page.
  `verify_report` gains the fixture and `mutate_report` the mutant; the
  regex line's anchor is widened with it (ADR-140's lesson).
- `collection-sheet.html` `pRg`, `fungal-characters.html` `fkq`,
  `pheno-tracker.html` `scorePanel` and `traitChips`, `releve.html`
  `wEditor` — declared furniture, each with its reason in the ledger: the
  reagent rows painted from the sheet's REAGENTS table (what was seen goes in
  the inputs and the export); the key's question labels (the answers are the
  `kopt` controls, the verdict `fktell` is read); the score panel's heading
  (the scores are dials, the ranked run is `rankBoard`); the trait weights as
  entered (the same weights head the CSV the task holds); the wetland editor
  (taxa from the record list, statuses on dials, the index in the analysis).

## What moved

    written elements measured        270 → 312       blind  0 → 6 → 0
    every page's ceiling             0
    page-survey-design-science       73 → 74         verify_sd         70 → 73
    verify_readable                  33 → 37         mutate_readable   30 → 33 / 33 (+1 recorded equivalent)
    verify_report                   114 → 115        mutate_report     68 → 69 / 69

No page was edited: the audit, the reader's naming, four suites, two runners,
one task, the ledger.

## Held

- A host read whole (controls and all), a host skipped whole (figures and
  all), the kit's furniture counted as a figure, the baseline read whole
  while the entered page is read beside its controls — four mutants, each
  killed by the fixture built for it: a ranked row with a button is written
  and unreadable; the same row in a `*Board` is readable; a kit stepper with
  its label and help line is not written; a static paragraph with a link is
  not written.
- The flag's True/False is a recorded equivalent: since both sides are read
  the same way, only `"whole"` changes the reading, and that mutant is real.
- The event tree's literal carries the two button labels per row (`copy
  IDremove`) because the reader returns the box's text whole; the port
  states them, so a page that renamed a button would move the task.
- Not done here: the through-a-box readings and the furniture list are the
  audit's two soft edges, and both grew by one page this slice. The lab
  importer's own band lists and the undocumented `dwc:` directive stand
  from ADR-179; the unasserted charts stand from ADR-140.
