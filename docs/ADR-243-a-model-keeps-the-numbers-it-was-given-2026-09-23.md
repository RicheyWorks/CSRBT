# ADR-243 — A model keeps the numbers it was given

**Date:** 2026-09-23 · **Status:** accepted · **Chain:** ADR-242 → this ·
**Protocol:** 1.11 (unchanged)

## Why

The tenth blind trial (ADR-232) filed two defects on the ecology lab, both on
the workbench, both about the page saying something other than what it had
been told.

**The theory bench forgot its numbers.** `buildParams` rebuilt the parameter
boxes from `MODEL_PARAMS` every time the model changed. Type *r* 0.25, *N₀*
10 and 30 steps into the logistic, look at L–V competition, come back: the
boxes read 0.15, 5 and 60 again. The `.eco` line built next — the storage
format, the thing the page tells a student to save — read `model: logistic
0.15 120 5 60`, a protocol of numbers nobody typed. The task certified it:
its `still` step held "the sixty-one-point default curve", and the ADR-186
check in `verify_eco` held the task's literal to the defaults.

**The sites verdict read one figure and spoke for three.** Two sites whose
abundant kinds matched read *"nearly identical communities"* at Bray–Curtis
0.17 — beside *"share 3 of 7 kinds"* and a Jaccard of 0.43. Bray–Curtis
weighs by count; the word did not say so.

## Decision

- **What a model's boxes hold is kept per model.** When the model changes,
  the boxes are read into `GIVEN[model]` — whatever put the numbers there, a
  keystroke or an import — and put back when that model is chosen again.
- **`wb-params-note`, under the boxes, says which numbers the model is drawn
  from:** *"logistic growth is drawn from the numbers you gave it: r 0.25 ·
  K 120 · N₀ 10 · steps 30 — kept while you look at another model."* or
  *"… is drawn from its starting numbers: r 0.15 · K 120 · N₀ 5 · steps 60.
  Change any of them and the change is kept while you look at another
  model."* An imported model line repaints it.
- **The sites verdict says which figure it is reading.** Where the counts
  agree and the membership does not: *"the abundant kinds are nearly the
  same (Bray–Curtis 0.17 weighs by count), and 4 of 7 kinds are at one site
  only (Jaccard 0.43): the turnover is among the scarce kinds."* Identical
  sites are *"identical communities: the same kinds in the same counts"*,
  not nearly so. The moderate and major bands are unchanged.
- The station reading `turnoverR` (the engine's own thresholds, mirrored
  from `FieldReport.java`) is untouched: it is the engine's word, not the
  workbench's.

## Held by

- **The task** (`page-ecology-lab-science`): 345 → **359** confirmed.
  `g243-comp-note` holds competition's starting-numbers line; `g243-back`
  holds the restored line word for word, the thirty-one-point curve in the
  typed habitat and *effective r=0.35, K=300*; `eco` holds `model: logistic
  0.25 120 10 30`; `still` is re-derived from the port for [0.25, 120, 10,
  30] in the neutral habitat the import restores; the three site steps hold
  the verdict. **Refuted on the old page** at `sites-identical`. The goal
  says so.
- **`verify_eco`**: 200 → **227**. The boxes after a round trip, the line at
  boot, after a keystroke, after an import with and without a model line, the
  `.eco` line, each model keeping its own; six site cases against a port of
  `statSites`' word, the figures held to the tiles; the task's literals to
  the same ports. The ADR-186 check that held `still` to the defaults now
  holds it to the numbers the model was given.
- **New runner `tools/mutate_ecolab.py`**, 12 mutants, all killed on the
  first run: rebuilt from the defaults, never kept, the line always or never
  "starting", not repainted on a keystroke, an import unsaid, the `.eco` line
  from the defaults, identical as nearly identical, the two-figure word lost,
  the moderate band moved, *is/are*, Sørensen printed under Jaccard's name.

## Numbers

| | before | after |
|---|---|---|
| page-ecology-lab-science | 345 confirmed | **359** |
| verify_eco | 200 | **227** |
| mutate_ecolab | — | **12** |

## What the first look found

Two of the four filed page defects were already closed: the pheno tracker's
`.eco` header naming every trait was ADR-197's, and the stand sheet refuses
an empty CSV or Darwin Core copy (*"No stems to export"*). The ecology lab's
were the last two open.

The ADR-186 check was the certifying check: right about what it matched
(the task's literal was the default curve), wrong about what the match
meant (that the default curve was the right answer).

## Held

- The relevé's line-point entry keeps species and stratum after *+ hit*
  (ADR-229); a note of the ADR-238 shape would say what the next hit will
  be. Trigger: an operator who adds a hit they did not mean.
- The two-site word for the moderate band reads Bray–Curtis alone, as
  before. Trigger: a case filed where the membership and the counts disagree
  inside it.

## Lessons

- A form that rebuilds itself from its defaults is a form that speaks for the
  user. Keep what was given, and say which it is.
- A verdict that reads one of three figures on the same card must say which
  one, or the reader takes it as all three.
