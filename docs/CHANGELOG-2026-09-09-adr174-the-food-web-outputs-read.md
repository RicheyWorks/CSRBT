# 2026-09-09 — ADR-174: the food web's outputs, read — and a slash in a label is a label

**Three exports the builder hands over and nothing read — the web export, the
edge-list CSV, the print — are pressed and held byte for byte; and the task
grammar learns that `Print / save PDF` is a label, not `Print ` inside ` save
PDF`. Unread outputs 15 → 12.**

## Changed — `tools/harness_tasks.py`

`find_control`: a name that matches whole (id, label or host) is taken whole;
only a name nothing answers to is read as `host/label`. The builder's hostless
print button becomes nameable; `rCov/4` still scopes.

## Changed — `tools/verify/verify_tasks.py`, `tools/mutate_tasks.py`

292 → 293: a hostless and a hosted print button resolved side by side.
65 → 67 mutants: a slash that always splits, a slash that never does.

## Changed — `tools/tasks/page-food-web-science.json`

15 → 22 steps, 39 → 54 confirmed. On the meadow: `ecoCopy` (the header, the
connectance/chain note, twelve `eats` notes in drawn order), `csvCopy`
(`food,eater` and twelve edges), `Print / save PDF` (one print), then the
tiles read once more.

## Changed — `tools/verify/verify_fw.py`

61 → 64: the export and the edge list built from the suite's own port of the
meadow, and the task's literals held to them.

## Changed — `tools/outputs_ledger.json`

food-web: 3 held, ceiling 3 → 0.

## Numbers

    food-web           0 → 3 of 3 outputs held
    the kit           15 → 12 unread of 66
