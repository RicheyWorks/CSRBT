# ADR-059 — Regrading the graded run

**Date:** 2026-08-26
**Status:** accepted
**Completes:** ADR-052's unbound list (with ADR-058)

## The last one, and the only one on a published page

ADR-052 named five session artifacts it had not bound to the engine. ADR-058
took the four read by `demo/visualizer.html`. This is the fifth, and its chain
is four links long:

```
docs/sample-experiment.eco              the spec, written before the run
  → ./gradlew ecologyExperiment         the engine grades it
  → docs/ecology-experiment-session.json  the graded output, shipped
  → docs/ecology-lab.html               draws it when you drop it in
  → docs/eco-protocol-reference.html    tells you to
```

Nothing checked any link. The spec could gain a hypothesis the session never
carried; the session could ship a verdict its own numbers contradict; the lab
could ignore a whole section of a file the reference page told you to drop on
it — with every suite in the kit green.

## The verdicts are regraded, not trusted

Each hypothesis ships three fields: the expression, what was observed, and the
engine's verdict. That is enough to grade it again here, in Python, from the
shipped bytes. `evenness(bloom) > 0.9` observed at 0.494749 is REFUTED whoever
does the arithmetic.

**One of the seven is the check with teeth.** `jaccard(pondA, pondB) <= 0.5` was
observed at *exactly* 0.5 — sitting on its own threshold. An engine that read
`<=` as `<` would call it REFUTED, and this file would say so. A boundary case
in shipped data is worth more than any fixture, because it is the case the
engine actually met.

No engine needed to run this, and no expected constants pinned (ADR-041): the
comparison is recomputed from two numbers the file already carries, so it keeps
passing when the engine legitimately produces different data.

## A comment in the spec is a claim

The spec marks one line:

```
expect: evenness(bloom) > 0.9        # deliberately wrong — see what REFUTED looks like
```

That comment predicts what the run will show, so it is checkable: exactly one
hypothesis must be refuted, and it must be that one. Deleting the marker fails
the suite; so does flipping the verdict.

## What the lab was not admitting

`renderStations` reads **fourteen** session keys. Its "nothing to chart" message
named **eight**:

> The JSON parsed, but no known stations (meadow, drift, demography, growth,
> archipelago, fossils, grid, island) were present.

The six it omitted — `models`, `crosses`, `entered`, `notes`, `trees`,
`hypotheses` — are exactly what makes a *graded protocol* worth dropping in, as
opposed to a field-day run. A reader whose file failed to chart was being told
those were unsupported. They were supported all along; the list was written when
only stations existed and never moved.

The message now names all fourteen (and says *sections*, since models and
crosses are not stations), and a check binds it to what the renderer actually
reads. A separate check asserts the shipped session has no top-level key the lab
drops in silence.

## Two fixture gaps the canary found

1. **`>` → `>=` was an equivalent mutant.** No hypothesis in the shipped session
   sits on a `>` boundary, so widening the operator changed nothing observable.
   Every operator now has a fixture *on* its threshold — including `==` and
   `!=`, which this spec does not use at all. An operator no fixture exercises
   is untested code that looks tested.
2. **Four rule-disabling mutants were unkillable by construction.** Forcing
   `spec_n == sess_n` to `True`, or the message/renderer comparison to `True`,
   changes nothing while the tree is clean — both sides already agree. The
   mutants that matter there are on the *data*: removing a hypothesis, adding a
   section the lab ignores, reverting the message to its stale list, deleting
   the spec's marker. All four die.

## Canary

Nine data-and-page mutants plus the operator sweep: grader always CONFIRMED;
`<=` strict; `>`, `<` widened; `==` always true; `!=` inverted; a bool read as a
number; the boundary verdict flipped; a hypothesis dropped; a section the lab
ignores added; the message reverted; the spec's marker deleted. All caught.

## Cost

`tools/verify/verify_eco_experiment.py`, 35 checks, new. One sentence corrected
in `docs/ecology-lab.html`. 51/51 jobs green, 3587 checks.

ADR-052's unbound list is now empty.
