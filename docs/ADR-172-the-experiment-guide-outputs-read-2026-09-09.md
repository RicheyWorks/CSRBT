# ADR-172 — The experiment guide's outputs, read — the .eco, the pre-registration, the skeleton and the print, held

**Status:** accepted · **Date:** 2026-09-09 · **The experiment guide hands over five things — a protocol copied and downloaded, a pre-registration, a JUnit skeleton, a printed checklist — and its task read none of them. It reads all five now, the .eco byte for byte against the grammar, and the kit's unread outputs go 23 → 18.**

## The button is the product

ADR-153's `audit_outputs` measures the other end of the sentence entry_reach
measures: not how much of a page's data its task enters, but how much of what
the page PRODUCES its task reads. The experiment guide was the worst page on
that list — five outputs, none read — and it is the page whose whole point is
the file it hands over. The `.eco` is what `./gradlew ecologyExperiment`
runs; the pre-registration is the paragraph a reviewer grades a claim against;
the skeleton is the test a reader pastes into a repo. A page can render the
protocol correctly in `eco-out` and copy something else, and every suite in
the kit would have stayed green.

## What changed

**The task presses every export and holds what left.** After the existing
scenario (which is kept verbatim, so its 220 expectations hold), in the state it
leaves the page in — the eco track holding the imported "clashing study", the
engineering track holding the two measured rows and the fired verdict:

- `Copy .eco` → one clipboard payload, held **byte for byte** to the
  protocol: the two comment lines (the study's name; the run command under the
  study's slug `clashing-study.eco`), `name`/`keys 200`/`seed 3`/`window 200`,
  the one uniform phase of 1000, the `graze` dataset, the evenness hypothesis
  — groups separated by a blank line, as the grammar has them.
- `Download .eco` → one download payload, named `clashing-study.eco`, the same
  bytes.
- `Copy pre-registration` → one clipboard payload holding the question line,
  the table header, both measured rows exactly (`| 20000 | 12.34 | 5.6 | 2 |
  17.9 | 9× |`, `| 60000 | 100 | 48.6 | 12 | 148.6 | 12× |`), the workload
  line with the seed, the five timed passes, and the fired verdict with its
  note. Not the whole text: it carries today's date, which is the one thing a
  task must not pin.
- `Copy JUnit skeleton` → one clipboard payload held whole: `SEED = 7L`,
  `SIZES = {20000, 60000}`, `TIMED_PASSES = 5`, `median-of-5`, and the
  question and floor in the javadoc.
- `Print this page` on the checklist → exactly one payload, a print, and
  nothing else leaves with it. Then the run command is read once more — still
  the clashing study's — so the last entry is followed by a read, as every
  science task's must be.

Every collect-output also holds that a SECOND payload does not exist: one
press, one product.

**The literals are pinned by the page's own suite, not transcribed.**
`verify_experiment_guide` now builds the expected `.eco` from the grammar
(ExperimentSpec's javadoc: one directive per line, groups blank-line
separated, the slug rule) and the pre-registration rows from the guide's
stated arithmetic (total = the sum of the phases; total/floor whole at 10×
and above, else one decimal) — and holds the TASK's literals to them. A task
literal that merely copied whatever the page emitted is caught: change
`keys: 200` to `201` in the task and two checks fail. That is the same
two-sides-one-arithmetic rule ADR-162 applied to the pheno tracker's exports.

## What moved

    experiment-guide outputs     0 → 5 of 5 held      ceiling 5 → 0
    the kit's unread outputs    23 → 18 of 66         (10 pages still hand something over unread)
    page-experiment-guide-design   220 → 251 confirmed, 0 refuted
    verify_experiment_guide         86 → 92

No page was edited: a task, its page's suite, and the ledger.

## Held

- The prereg's date line is deliberately not held; everything computed is.
- The task returns to the eco track before it leaves the designer, so the
  state walk the three audits make still exposes the chip lists' Remove
  buttons — ending on the engineering track hid them, and audit_contrast,
  audit_focus and audit_targets each named the three as never exposed. The
  audits caught a task shape, not a page fault; the task was reshaped.
- `Download .eco` is caught through the harness's Blob/anchor capture
  (ADR-152), so the download's bytes are the protocol's, not a placeholder.
- The eco track's end state is the *clashing* import (a dataset named like a
  phase), and the `.eco` still emits both — the lint complains, the export
  does not censor. That is the page's behaviour and the task records it as
  such; whether the parser should refuse it is the engine's business.
- Not done here: the other 18 unread outputs — field-notebook (3), food-web
  (3), ordination (3), deployment-log, farm-scout, pheno-tracker, field-season,
  soil-bench, soil-recipes, eco-protocol-library. Same shape, one page a slice.
