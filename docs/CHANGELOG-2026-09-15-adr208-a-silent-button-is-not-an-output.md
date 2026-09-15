# 2026-09-15 — ADR-208: a silent button is not an output

**The audit that exists to find work a page cannot hand over decided what a
*button* was from the word `save` in a label and from whether a kind's name was
spelt ending in `_in`. A number box captioned "Plants you plan to save seed
from" was pressed as an export, handed nothing over, and was filed `silent` — a
number in a column that nothing named, no ratchet held, and no exit code cared
about. Eighteen stood in this kit; nine were not buttons; one of the nine was
why the breeding bench had never been reported as the data trap ADR-205 was
written to catch.**

## Fixed

- **What a button *is*, read from the door's own `activate` pool** instead of
  from a two-character suffix on a kind's name. `kind.endswith("_in")` catches
  `text_in`, `field_in`, `file_in` — and lets `step_val`, `slider`, `select`,
  `checkbox` and `drop_zone` straight through, which is most of what this kit
  composes. The suite pinned that rule with an `<input>`, the one kind whose
  spelling happens to match, and it read green for fifty-five slices.
- **`breeding-bench.html` had no export at all.** Eighteen typed values across a
  roguing log and a replicated yield trial, and no way to get any of it off the
  screen. Its one false candidate is why the audit never printed the
  no-outputs row ADR-205 added for exactly this.
- **`cp-bench.html` could hand over a soil recipe and nothing else** — not its
  water log, plants, observations, dormancy record or crosses.
- **`ecology-lab.html` built a protocol and left it in a read-only box.** On a
  phone, selecting a 120px textarea by hand is where the morning is lost.
- **A step the door REFUSED, about which the task said nothing, counted as
  held.** This slice's own first draft wrote `collect-output` with a `selector`
  that action does not take; both bench tasks reported PASS with the step that
  was supposed to read the export never run.
- **The outbox suite read one of the two places its ledger is marked from.**
  A download has no clipboard promise to hang the mark on, so the page calls
  `.sent(...)` itself; both new downloads were reported as exports declared and
  impossible.

## Added

- **A second ratchet: `mute_ceiling`.** Per page, may not rise, comes down as
  buttons are fixed, and fails the audit with no flag. A button that is right to
  be silent is declared with `--declare-mute PAGE:KEY --reason "..."`, and the
  reason is stored word for word.
- **Nine written judgements** — *Save to collection* commits a row; *Choose .eco
  file…* is an import; *no print / not applicable* is a key answer about a
  **spore print**.
- **Exports on the two benches**: *Copy the bench sheet* and *Download
  bench.csv*, one section per table, with an outbox ledger beside them. Each is
  **held** — the page's own task presses it and asks what came out, against the
  rows that task entered.
- **`copy the .eco lines`** on the ecology lab, with the build button declared
  silent and that sentence as its reason.
- **A refused or declined step that says nothing about `ok` or `code` fails the
  task**, exactly as an unexpected failure does. All 55 shipped tasks still hold;
  the grammar was already theirs.

## Decided, and written down

- **The CSV downloads are not marked in the outbox.** A hosted viewer refuses a
  page-started download in silence, so a mark there would report a sheet as gone
  from this device that the browser never let leave — ADR-203's defect one layer
  along. The copy is declared and marked; the download carries the sentence the
  experiment guide already carries.

## Checked

- `verify_outputs` 38 → 58 · `mutate_outputs` 31 → 44, all killed
- `verify_tasks` 383 → 392 · `mutate_tasks` 87 → 91, all killed
- `verify_outbox` 316 → 337
- A **scripted door** drives the decline half of the new task rule, because no
  real target in this kit ever answers a step that way — a rule with no
  violators cannot show that it fires, ADR-207's finding one slice later.
- A mutant **survived** the first draft of the mute-ratchet direction check,
  which had been written from a reading that already equalled the ceiling. Same
  lesson, same slice.

## Standing

`0 of 80` outputs leave a page with nothing reading them. `0` buttons hand over
nothing that has not been judged in writing. Twenty-four pages carry a mute
ceiling of zero.
