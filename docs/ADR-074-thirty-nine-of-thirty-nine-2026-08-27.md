# ADR-074: thirty-nine of thirty-nine, and a second definition of what the kit is

**Status:** Accepted and implemented — `tools/mutate.py` (`SCRATCH_SKIP` / `SCRATCH_KEEP`),
`tools/verify/verify_mutate.py` (27 → 30), `tools/verify/verify_soil.py` (65 → 70),
`tools/verify/verify_engine_sessions.py` (12 → 18), `tools/verify/verify_eco.py` (98 → 101),
`tools/mutate.py` (+1 recorded equivalent).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-041, ADR-052 (binding the docs to the engine), ADR-072

---

## The sweep is finished

**39 of 39 pages.** The tally that started this arc said *"19 swept, 20 to go"* and was wrong in both
figures (ADR-069); it is now computed, and it reads zero.

## 1. The scratch tree is a second definition of what the kit is

Three times in two slices, a suite has been thrown out of a sweep for being "red" when it was healthy
and the scratch copy was incomplete:

| slice | suite | what was missing | cost |
|---|---|---|---|
| ADR-072 | `verify_eco` | `../README.md`, linked from tree-proofs | 98 checks, every page it names |
| here | `verify_visualizer_sessions` | `demo/visualizer.html` | 32 checks, on ecology-lab |
| here | `verify_engine_sessions` | `FieldReport.java` | the threshold binding, the day it was written |

ADR-072's fix — copy the top-level **files** — was the instance and not the class, and the next sweep
proved it one page later. So the default is inverted: everything at the top level is copied unless it
is named in `SCRATCH_SKIP`, with a reason beside it. A directory added tomorrow comes across without
anybody remembering; leaving something out is a deliberate, visible act. The same lesson KEEP's
`formSnapshot` learned about hand-maintained lists of fields.

The third case did not fit even that. `verify_engine_sessions` reads one 4 KB Java file inside a 6 MB
tree it makes no sense to copy. `SCRATCH_KEEP` names that file, and the reason, and `verify_mutate`
asserts each entry exists on both sides — a stale entry is as bad as a missing one.

Worth saying what went right: `verify_engine_sessions` did **not** fail when the file was absent. It
reported NOT VERIFIED, which is why the sweep recorded a survivor instead of a false kill. A suite that
knows the difference between "did not run" and "passed" is what kept this from being a wrong number
rather than a missing one.

## 2. The page's thresholds now come from the engine

`ecology-lab.html` carries, in a comment, *"same thresholds as FieldReport.java"*. Nothing checked it,
and two mutants walked through: `j >= .85` → `j > .85`, and `i <= 1.5` → `i < 1.5`. At exactly 0.85 a
community stops reading *"very even"*; at exactly 1.5 a distribution stops reading *"random"*.

Both sides are extracted and compared as ordered `(operator, value)` pairs — the Java's named constants
and the comparisons that use them, the page's inline numbers and the operators beside them — for five
readings: evenness, dispersion, overlap, turnover and fill. Canaried three ways: a page-side operator,
a page-side number, and an engine-side constant. All three break the match.

This is ADR-052's shape one layer along. A value generated in one place and inlined in another needs
something binding the two, and here the "value" is a threshold and the "inlining" was a person copying
numbers into JavaScript.

## 3. Soil Bench: the peak was not the peak

`Math.max` over the logged temperatures feeds a tile labelled **peak** and the tone beside it. Replaced
with a min, that tile shows the *coldest* reading and calls it the peak — 32 °C in place of 64 on the
suite's own eighteen-reading fixture. The suite counted how many readings were hot and had never asked
what the hottest one was. Recomputed from the fixture, not written in.

And `last.m <= 2` → `< 2`, the squeeze test. The moisture scale's value 2 is labelled **"Dry"** by the
page itself, and at exactly that reading the mutant drops the dry warning. Every fixture in the suite
ended on 3. Both ends of the scale are asserted now, and 3 in the middle.

## 4. The lab's bars, and a check that was wrong on correct code

`yMax = Math.max(1, ...finite) * 1.05` — the 1 is a floor so an all-zero series still gets an axis.
With a min the bars leave the picture: measured on the page as it loads, **nine charts draw bars, none
outside the frame; with the mutant, six of the nine, the worst at y = −48732 in a 180-high viewBox.**

The first version of that check parsed the path's `d` string and took every second number as a y. Bars
are drawn with rounded corners, so the odd positions also hold arc radii and flags, and it reported a
maxY of 965 in a 170-high chart **on a correct page**. `getBBox()` instead: the browser already knows
where the shape is.

Third page in three days where the arithmetic was checked against independent implementations and the
drawing was not checked at all.

## 5. What is left standing

`collection-sheet` swept **100%** first time — the page ADR-063 parked as needing a longer run than
one command allows.

Two survivors on `ecology-lab` are **fresh and not yet triaged**, and are named here rather than left
implied (ADR-047):

- `pts.every(p => isFinite(p[0]) && isFinite(p[1]))` → `||`. The guard that drops a series with a
  non-finite point so its absence is visible rather than silent.
- `esc(v)` in the tile builder. The page accepts a dropped-in session file, so whether a tile value can
  carry a string from that file is the question, and I have not answered it.

Neither is recorded as equivalent, because neither has been measured.

## Cost

`verify_soil` 65 → 70, `verify_engine_sessions` 12 → 18, `verify_eco` 98 → 101,
`verify_mutate` 27 → 30, one recorded equivalent (soil-bench's `MOIST` label). No page changed.

| page | before | after |
|---|---|---|
| collection-sheet | — | **100%** |
| soil-bench | 50% | **83%** (1 recorded equivalent, 5 of 5 reachable) |
| ecology-lab | 17% | **67%** (2 fresh survivors, named above) |

**55/55 jobs green, 3920 checks. Swept: 39 of 39. Nothing left to sweep.**

`verify_sweep_ledger` fell from 23 checks to 18: five of its checks are one-per-remaining-page, and
there are no remaining pages. A suite about a backlog shrinking to nothing as the backlog empties is
the right behaviour, and it is why that count is derived rather than declared.
