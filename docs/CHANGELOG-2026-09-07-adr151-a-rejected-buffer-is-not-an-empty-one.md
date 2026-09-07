# 2026-09-07 — ADR-151: a rejected keystroke buffer is not an empty one

**63 live number boxes across 16 pages could not tell a keystroke buffer the
browser rejected from a box nobody had touched. All 63 are fixed. The kit is at
zero and the ratchet holds it there.**

## New

- **`tools/audit_badinput.py`** — asks every `<input type=number>` in the kit
  the one question no task could ask before ADR-150 built `type-text`. Three
  states per box (a GOOD value assigned, BLANK assigned, `"3e"` **typed** with
  `validity.badInput` confirmed), compared against what the page renders.
  `GOOD != BLANK` is the control that says the box is read live; `BLANK == BAD`
  is the finding. Walks every page state and re-asks until a box tells, keys
  elements by id *or by where they sit* so an unnamed answer still counts,
  drops ids that move on their own, and ratchets **downward** per page.
- **`tools/verify/verify_badinput.py`** — 32 checks on a fixture carrying a
  blind box, one that tells with a sentence, one that tells with a mark and no
  sentence, one that tells in an element with no id, an inert one, a box behind
  a tab, one the entry brings into being, one that only tells once the entry
  has run, one that goes quiet in a later state and keeps its finding, a
  readonly box the token never reaches, a text box holding digits, and a clock.
- **`tools/mutate_badinput.py`** — 24 mutants, 1 known equivalent.
- **`tools/badinput_ledger.json`** — per page: the blind boxes by name, the
  counts, and the ceiling.
- Registered in `run_all`'s audits and on the Harness Board.

## Changed — the pages

- **Field Entry Kit v1.3.0 → v1.4.0** (`tools/fek.py`, re-emitted into 19
  consumers) — 39 of the 63, across ten pages. The stepper and the instrument field check `validity.badInput`
  before they read `.value`, mark the row, and name the box and what happened
  to it. Blur no longer repaints the old value over the reader's characters. A
  new delegated guard covers plain number boxes the kit did not build — seven
  more across three pages — in capture phase and by delegation so boxes added
  later are covered too.
- **`docs/experiment-guide.html`** — twelve. Four factor boxes (a rejected
  factor emitted nothing, which this page reads as the neutral value: silently
  1, or 0 for distance), the grader's seed and passes (blank means 42 and 3),
  and the six measurement cells, which said "waiting for every cell" — what
  they say about a cell nobody filled in. The computed line now carries an id.
- **`docs/ecology-lab.html`** — four. The exporter already knew the difference;
  the Hardy–Weinberg and mark–recapture workbenches beside it did not, and
  answered a rejected buffer with "enter non-negative counts".
- **`docs/tree-visualizer.html`** — two: `select k-th`, and `rank of`, which
  shares its line and shared its bug.

## Numbers

    blind number boxes     63 -> 0        (185 measured, 22 pages)
    boxes that tell        12 -> 75
    inert (read on submit) 107            stated, not measured further
    unreachable              3            releve.html; never asked, not passing
    verify_badinput         32 new
    mutate_badinput         24 new

Both ends of that ratchet were measured with the SAME instrument: the pages at
the ADR-150 commit were checked out and re-measured after the report channel
changed, rather than comparing an old reading against a new one.

## Held

- The audit says a page renders a *different* thing, not a *right* thing. The
  wording is nobody's instrument yet.
- 107 boxes are read only when a button is pressed. The audit does not press
  buttons, so it cannot say whether the reports they feed are blind. That is
  the boundary of this measurement, and the next slice.
- Three boxes on `releve.html` could not be focused in any state the audit could
  reach. Reported as unreachable rather than as passing.
- `type=text` boxes holding numbers have no `badInput` and are out of scope: the
  page is handed the characters.
- The audit costs about eight minutes over the kit — three page states per box,
  one keystroke at a time.
