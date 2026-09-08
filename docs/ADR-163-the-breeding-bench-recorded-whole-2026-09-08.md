# ADR-163 — The breeding bench, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The vegetable breeder's bench drove all six panes but six of its twenty-one fields were never entered: the breeding goal, the seed-use and rogue-reason chips, the heritability and phenotypic SD behind the selection response, and a third crop picker hidden in the seed-storage pane. Now 21 of 21, every pane driven and the response held against an oracle.**

## The bench that computed a response it never dialled in

`breeding-bench.html` is a home-scale plant breeder's bench: check whether a
**population** clears the published minimum for its mating system and read the
effective size Nₑ; work out an **isolation** distance; compute a **selection
response** R = i × h² × σ_P; run a **variety trial**; and track **seed**
germination and storage. Its task drove every pane and read a response of 6.14 —
but **six of its twenty-one fields were never entered**: the breeding goal dial,
the "my own garden" seed-use chip, the "off-type" rogue-reason chip, the
**heritability and phenotypic SD** that the 6.14 is built from, and a **third
crop picker** tucked into the seed-storage section that no step ever touched.

The response is the telling one: R = i × h² × σ_P, and the task asserted 6.14
while the h² and the σ_P that produce it sat at their defaults, entered by
nobody — the same shape of gap as the cell bench's accumulation figure.

## Entered whole, the response checked

The existing scenario is kept verbatim — bean below its minimum of 20, corn's
Nₑ, the isolation distances, the 6.14 response, the roguing and trial and
germination — so its assertions hold, and the six untouched controls are driven
around it: the goal dial and the seed-use and rogue chips are selected (each at
the value the task already used), the **heritability is set to 0.35 and the
phenotypic SD to 10** — the exact numbers behind the asserted 6.14, now entered
rather than assumed — and the seed-storage crop is picked. A third crop is
selected on the population pane and its published minimum (20, an inbreeder) is
held against the oracle.

## What moved

    breeding-bench   15 → 21 of 21 fields entered    (the largest remaining gap
                                                     among data-entry pages closed)
    breeding-bench  100 → 113 confirmed expectations   0 refuted
    the kit         490 → 496 of 521 fields            (95%), 20 of 27 pages whole

## Held

The page carries **three separate crop pickers** — population, isolation and
seed-storage — and the storage one was the last field standing: the task picked
crops on the first two and never on the third, so the field read as unentered
even though "a crop picker" plainly was driven. Setting the heritability and SD
to the values the assertion already assumed leaves the 6.14 exactly where it was
— the point is that the inputs are now driven, not that the number moved. No
page was edited: a task-only slice, the thirteenth page driven end to end.
