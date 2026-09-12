# ADR-197 — The findings become failures: a trial keeps the protocol it was run under

**Status:** accepted · **Date:** 2026-09-12 · **`findings.py` opens with the sentence this slice is the rest of: *a harness that reports is not a harness that guards*. It has guarded the UI categories since ADR-110. What it never covered is the class of defect a blind OPERATOR finds — arithmetic that disagrees with its own caption, an export that contradicts the screen it was taken from — and three trials running found the same two and filed both. They were not fixed because **fixing them was blocked**: a task claim names a figure and the value the page gave for it, so correcting a page moves the claim and every trace recorded before the fix stops confirming it. The floors fall, the suite goes red, and the honest reading of that red is "you edited the ruler". So each trial now carries `tasks/` — the protocol it was run under — and six page defects are closed against oracles this kit computes itself.**

## 1. The block, which was real

The kit's own measurements made its own pages unfixable. `verify_tasks` holds
the third, fourth and fifth trials to floors counted in confirmed claims; a
claim is `output.by.neOut."after 10 generations" == "13.9%"`. Fix the
arithmetic behind that figure and three trials' traces, recorded against the
page as it was, stop confirming it. Nothing in the kit could tell that apart
from the door getting worse.

A lab keeps the protocol with the data. So does this: `tools/traces/blindN/tasks/`
holds the four task files as of the run, and that trial's traces are graded
against **those**. The live tasks follow the pages. `protocol_drift` names, per
trial, which claims the two now disagree about — empty means the pages that
trial touched have not moved and the copy is ceremony, which is worth being
able to say rather than assume.

The suite holds the whole shape: the frozen protocol exists, it has drifted,
and grading a trace against the live task confirms **fewer** claims than
grading it against the protocol it was run under. That inequality is the
evidence that the freeze is load-bearing rather than decorative.

## 2. Six defects closed

| page | what it did | found by |
|---|---|---|
| breeding bench | `after 10 generations` was `10 × ΔF` under a caption reading *compounding* — 12.5% where compounding gives 11.8% | 3rd, 4th, 5th |
| breeding bench | the breeding class slot printed the minimum's provenance: *"this crop is cited for this crop"*, on sweet corn, the one crop where *outbreeder* carries the argument | 4th, 5th |
| breeding bench | at 0% germination, `1/p` clamped at `p = 1%` read out as *"about 100.0 seeds per plant wanted"* | 5th |
| collection sheet | a reagent's name is HTML; three places stripped its tags and left its entities, so the field sheet printed `KOH 3&ndas` and the voucher label sent `KOH 3&ndash;10%` to a herbarium | 3rd, 4th, 5th |
| collection sheet | the ten-character column cut `Syringaldazine` to `Syringalda` and ran it into the observation with no separator | 3rd, 4th, 5th |
| pheno tracker | the `.eco` export hardcoded `cross: Aa x Aa … vs 3:1` whatever the page had concluded — right by coincidence at 60:20, wrong at 9:7 where the page says *two complementary genes* | 5th |

Two more, smaller, in the same pass: the `.eco` header named every trait while
the scores used only the scored ones, and the CSV column called a weighted
**mean** a weighted **total**.

Each is held by `verify_report` section K against a number the suite computes
itself — `1 − (1 − ΔF)¹⁰` from Nₑ, not a string read off the page — and the
oracle for an export is the **export**: the copy button is pressed and the
payload collected, because a report box collapses its newlines and a check
reading one would have been measuring the reader.

## 3. A page is a subject now

`mutate_report` could only break `tools/`. The code that can undo these fixes
is in `docs/*.html`, so the mutant's docs directory is a directory of
**symlinks** to the real one, and a mutation that lands in a page replaces that
one link with a real file. Nine megabytes are not copied a hundred and thirty
times, and the suite reads the mutated page through `CSRBT_DOCS_DIR`. Six page
mutants, one per fix, each killed by the check that names it.

## 4. The page's own suite held the wrong number

`verify_br` — the breeding bench's own page suite, ninety checks of its
arithmetic — asserted `after 10 generations == "13.9%"`. That is how a page
can be wrong for months with a suite green over it: **the oracle was copied
from the page rather than from the caption above it**, and the caption said
*compounding* the whole time. An oracle that agrees with the code by
construction is not an oracle; it is a second copy of the bug. It now asserts
`13.1%` and says in a comment why.

## 5. What the suite was wrong about first

Two of the six new checks passed for the wrong reason on their first run, and
both were the same mistake: they read `boxes.ecoOut` from a report. A report
box is one string with its newlines collapsed, so `startswith("cross:")`
matched nothing, and a check that finds nothing to examine passes. Right about
what it matched, wrong about what the match meant. Both now press the page's
own copy button and read the payload, and the check that a cross line exists is
separate from the check on what it says.

## What moved

    verify_report      194 → 208      mutate_report     118 → 124 / 124
    verify_tasks       358 → 368      mutate_tasks       80 →  80 / 80
    verify_br           89 →  90      page defects closed        6
    frozen protocols     0 →  12      board            6283 / 6283

## Held

- The trials' numbers are unchanged: 53/169, 82/213 and 80/208. Freezing the
  protocol is what keeps them that way while the pages move.
- `protocol_drift` is allowed to be empty for a trial. The suite requires only
  that at least one trial has drifted, because that is the claim being made.
- The stand sheet's expansion-factor rounding is still filed, not fixed: the
  page prints `400 m²` and `EF 25.0` for a 399.72 m² circle while the CSV's
  per-hectare column uses the unrounded factor. It is a real inconsistency and
  the fix changes three figures four tasks claim; it belongs in its own slice
  with its own re-grade.
- `Clear trial` still raises no confirmation dialog. The door raises the call
  to DESTRUCTIVE on the label alone, which is the guard that matters here.
