# ADR-153 — What the page hands over

**Status:** accepted · **Date:** 2026-09-07 · **ADR-152 made it possible to read what leaves a page and counted what that had been hiding: 80 buttons, one read. This measures it properly. 63 outputs across 19 pages actually hand something over, and 62 of them left with nothing reading them. A page can render a correct analysis and export a wrong one, and every suite in this kit would be green. Three sheets now read their own exports; 62 → 42, and the ratchet holds.**

## The other end of entry_reach

`entry_reach` asks how much of a page's data its own task **enters**. This asks
the other half of the same sentence: how much of what a page **produces** its
own task **reads**.

Those are not the same question, and the gap between them is where a whole class
of defect lives. Every figure this kit holds is read off the screen. The file is
built by different code — a `cell()` that quotes commas, a Darwin Core row that
maps a cover class to `organismQuantity`, an `.eco` line that writes cover ×10 as
integers — and none of it had ever been looked at. The screen and the file can
disagree and nothing would say so.

    63 outputs across 19 pages hand something over
    62 of them left with nothing reading them
     1 was held -- the one ADR-152 wrote yesterday

## The instrument

`tools/audit_outputs.py`. The page is walked through its states and entered with
its own task — the same replay the other audits make — and then every control
whose **name** says it hands something over is pressed and `collect-output` is
asked what came out.

    EMITS    a payload came back: a copy, a clipboard write, a download, a print
    SILENT   pressed, and nothing left the page
    HELD     it emits, and the page's own task presses it AND then asks what came out
    BLIND    it emits, and no task has ever looked

Four decisions carry the measurement, and each is one a fixture pins.

**A candidate is named, not proved.** A button is a candidate *before* it is
pressed, or there is no experiment. The rule is its label — copy, download,
export, print, save — as whole words, because "Preprint checklist" is not an
export and matching inside a word is where a naive rule starts pressing things.

**"Forget this device's copy" is not pressed.** It matches `copy`, and a verb
list alone would press it; the answer would be a lost autosave. The rule is not
written twice — it is `harness_plugin_page.destroys`, the same rule the
gateway's own risk ladder raises DESTRUCTIVE on, and this audit refuses whatever
that refuses.

**A page with a task is measured with its own data in it.** The states are
walked from rest, and an export pressed on an empty page hands over the
placeholder the page shows when there is nothing to hand over — *"# log a
deployment — the sheet builds itself"*. That **is** a payload. The button would
be recorded as emitting, with the empty page's bytes, and never asked again. So
nothing is pressed until the entry has run.

**Held means pressed *and* read.** Pressing an export is not reading it, and
that distinction is the whole point: the deployment log's Copy button was
pressed by its task for two ADRs before anything asked what came out.

One press each. An earlier draft asked a button again in every later state, on
the theory that one behind a tab could not be pressed until its pane was open.
It can — the plugin's own `_reach` opens the pane before it acts, which is why a
task never has to — and the ladder was measuring nothing: with it removed the
kit's reading is identical to the digit. It is gone.

## What it found, and what was fixed

    the kit    62 -> 42 unread, 1 -> 21 held, of 63 outputs on 19 pages

Three sheets now read what they hand over — the collection sheet, the relevé and
the stand sheet, which are the pages where "the file is the product" bites
hardest, and which between them carry 20 of the 63.

**The claim is agreement, not a second derivation.** Each new step asserts that
the export carries a figure the task **already holds on screen**: the relevé's
`.eco` must say `Shannon H' 0.67`, `FQI 7.5`, `wetland prevalence index 4.77` —
the same numbers ADR-149 pinned against the published methods — and its matrix
must say `WAS-12,62.5,0.5,3.0,15.0`, the Braun-Blanquet midpoints the sheet
shows. The generator **refuses** any figure that is not already in the task; the
one exception it allows is the export's own precision, because a cover of 15% on
screen is 15.0 in a column written to one decimal, and that is the same figure
padded rather than a different one.

Also held now: every one of those files' **schema line**, which is a promise to
whoever reads the file and was checked by nothing; the two sheets' `Print / save
PDF`, on panes their tasks had never opened; and the reference packs and the
prompts they hand over, which are the pages' answer to "how do I get a species
list for somewhere else".

**19 buttons are silent** — pressed after the entry and nothing left the page.
Every one of them refuses honestly: *"Nothing recorded"*, *"Nothing loaded"*.
They are silent because the page's own task never records a session or loads a
log, which is an entry-reach gap and not an export defect. Silent is not on the
worklist: a page with nothing to export is right to export nothing.

`verify_outputs` **26**, `mutate_outputs` **24**, 1 known equivalent.

## The ratchet

Per page, the number of outputs that emit and nothing reads. It may not go up: a
page that grows an export no task looks at fails the day it does, with no flag,
because `run_all` runs an audit with no arguments. It comes down as tasks are
extended. An output that genuinely should not be read is declared in the ledger
**with a reason**; nothing is declared today.

## Held

- **It measures reach, not correctness.** A task that calls `collect-output` and
  asserts nothing about the payload would count as holding the output. That is
  the same bargain `entry_reach` makes, and it is stated rather than hidden.
- **42 outputs are still unread**, on 16 pages. The instrument exists and the
  ceiling holds them; extending the tasks is a worklist.
- **A silent button is not a passing one.** Nineteen exports on this kit have
  never been seen to produce anything, because their pages' tasks never gave
  them anything to produce. Those are the same pages `entry_reach` already
  names, and closing that gap will turn some of them into findings here.
- The candidate rule is a page's own vocabulary. A button that hands a file over
  under a name none of those five verbs covers is invisible to this audit, and
  the rule is in one place so it can be widened when one turns up.
