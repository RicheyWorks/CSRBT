# ADR-161 — The carnivorous-plant bench, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The CP bench — water quality, media, plant records, dormancy and crosses across six tabs — had every tab exercised but ten of its twenty-three fields never entered: the chips and steppers left at a sensible default, and the free-text provenance and cross notes left blank. Now 23 of 23, every default driven explicitly and the media recipe held against an oracle.**

## The bench that ran on its defaults

`cp-bench.html` is a carnivorous-grower's bench: judge **water** against the
50/160 ppm TDS conventions and work out how top-ups accumulate solids in a pot;
build a **media** mix from a hobby preset; keep **plant** records with trap
counts; check a genus's **dormancy** need against today's temperature; and log
**crosses** with their seed set. Its task drove every tab — but **ten of its
twenty-three fields were never entered**, and every one of them was a control
sitting at a working default nobody had touched: the RO/DI water source, the
three accumulation steppers, the "trap count" observation type, the dormancy
target temperature and duration and today's reading — plus the two free-text
fields left blank, a plant's provenance and a cross's note.

The accumulation figure is the clearest case: the task asserted that ten 250 mL
top-ups at 50 ppm accumulate to a **500 ppm-equivalent** single watering — and
never once set the TDS, the top-up count or the volume that produce it.

## Entered whole, the recipe checked

The existing scenario is kept verbatim — the three TDS readings still read
excellent/usable/too-high, the accumulation still reaches 500 ppm, the dormancy
verdicts and the cross's seed set all hold — and the ten untouched controls are
now driven explicitly. The water source chip is selected, the three
accumulation steppers set to the values the assertion already assumed, the
observation type chosen, the three dormancy steppers set, and the provenance and
cross note typed. The **media recipe** — the one thing this bench hands a grower
to take to the potting bench — is copied and held against an oracle:

    Carnivorous plant mix — 3 parts
    1 part sphagnum peat · 1 part perlite · 1 part coconut coir

built from the "Sarracenia · Dionaea" preset plus a coir component, the part
counts and names computed from the page's own component table.

## What moved

    cp-bench       13 → 23 of 23 fields entered    (the largest remaining gap
                                                    among data-entry pages closed)
    cp-bench       85 → 104 confirmed expectations   0 refuted
    its recipe      unread → read and held against an oracle
    the kit        471 → 481 of 521 fields           (92%), 18 of 27 pages whole

## Held

The first plant is deliberately left without a provenance so the "no source
recorded" warning still fires — the source field is entered afterwards, on its
own, rather than on that plant, so the existing assertion is untouched. The
observation-type and water-source chips default to the value the task uses, so
selecting them changes nothing but records that the harness can drive them. No
page was edited: a task-only slice, the eleventh page driven end to end.
