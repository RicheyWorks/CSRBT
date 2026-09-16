# ADR-213 — The one artefact this page tells a student to save carried the data, the hypotheses, and none of the answers

**ADR-211 measured 32 figures the ecology lab works out that nothing it hands over carries, and deferred them with a reason: the lab's only export is a `.eco` PROTOCOL — the lines you would RUN — and by design it carries inputs and hypotheses rather than results. That reason was right about what an `.eco` file is and wrong about what follows from it. A reader handed this protocol had every input and no way to tell whether their answer matched the one on the screen. 32 → 19, and the 19 that remain are a different question.**

## 1. Where the numbers were

Five workbench readouts — field diversity, two-site β diversity, quadrat
dispersion, mark–recapture, Hardy–Weinberg — each worked out inside its own
render function and assigned straight into `innerHTML`. There was no value
anywhere: the arithmetic ran, became a string, and became markup.

So *nothing else could read it*. The exporter two hundred lines down rebuilt the
data lines from the same boxes and stopped there, because the only way to get
the answers would have been to do the arithmetic a second time — and a second
copy of a calculation is a second source of truth (ADR-068), which agrees with
the first only until one of them is edited.

## 2. One computation, two readers

Each of the five is extracted to a `stat*` function that returns numbers and
returns `null` when its own inputs are not usable — the same condition the panel
prints its refusal for. The panel renders from it. The exporter reads it.

Nothing is re-derived in the exporter, and `verify_eco` now reads the figures off
the **panel** and requires each of them to appear in the protocol text as the same
digits — so an edit to one and not the other fails on the next run rather than in
six months. That check found the first disagreement immediately: the panel writes
a 95% CI with an en dash and the exporter had written a hyphen. Same numbers,
different string, and a reader diffing the two would have had to squint. The
exporter uses the panel's own dash now.

## 3. Results as comments, and that is the point

A `.eco` file is a **pre-registration**. This page's own instruction, two blocks
above the results block, is *"edit BEFORE you run; that's the discipline"*.
Results written as protocol lines would make the file assert what it is supposed
to be asking.

Written as comments they are **provenance**: legal `.eco`, ignored by the engine,
they survive the copy into a file, and they let anyone re-running the protocol see
at once whether they landed where the workbench landed.

```
# what the workbench got from these entries — provenance, not protocol.
# Re-run the lines above and you should land on these numbers:
#   myfield: 5 species, Shannon H' 1.21, evenness J' 0.75, effective 3.4, Chao1 6
#   siteA vs siteB: 2 of 4 kinds shared, Jaccard 0.50, Sørensen 0.67, Bray-Curtis 0.55
#   mark-recapture: Lincoln-Petersen N 400, Chapman N 379, 95% CI 217–541
#   Hardy-Weinberg: n 100, p 0.590, q 0.410, chi2 (df 1) 0.03, expected 35 / 48 / 17
```

The block is absent when there is nothing to report, rather than a header over
nothing.

## 4. What remains, and why it is a different question

Nineteen figures still reach no file: the nine **stations** — the archipelago's
turnover and Levins occupancy, the island's capacity and mean residence, the
demography table's completed lives and growth rate, the fossil record's inherited
keys, the meadow's second and fourth diversity readings.

Those are not the workbench's. They are rendered from a **session JSON the reader
already loaded**, by nine independent renderers that each build their tiles the
way the five above did. Giving them an export is the same extraction done nine
more times plus a decision about where a run's readings belong — a run record is
not a pre-registration, and putting them in this protocol would make the `.eco`
file assert the results of a *different* experiment from the one it describes.

The ceiling is 19 and may not rise.

## 5. The shape

ADR-141's, once more, in the form this run keeps finding: a quantity computed in
one place and published in one place, with no reader holding the two together.
Here the computation had no reader at all — it went straight into markup — and
the export could not have read it if it wanted to.
