# ADR-160 — The farm scout, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The farm scout — a grower's field day across four tools: pest scouting, pollinator counts, germination, and rotation — was the kit's most-neglected data-entry page, 5 of 15 fields entered and both its exports read by nothing. Now 15 of 15, every tool driven and both the field-day report and the CSV held against an oracle. The kit crosses 90%.**

## The field day that stopped at germination

`farm-scout.html` walks a grower through a field day: **scout** a pest across
ten stops and get an average and a dispersion (var/mean — is the infestation
patchy or even?) against an action threshold; **tally pollinator visits** and
read the Shannon diversity, effective types and evenness; **test germination**
and compute seeds-to-sow; and **check rotation** — a picker per season per bed,
because soil pests follow plant families, not crop names, and the mistake this
tab exists to catch is not realising that kale and last year's cabbage are the
same family.

Its task tested germination, flagged one rotation conflict, and counted a pest —
but **ten of its fifteen fields were never entered**: the pest's name, the field,
observer and date that stamp the export, the action threshold, every pollinator
tally, the second season on bed one and all three on bed two — and **both files
it hands a grower to take home were read by nothing**.

## Entered whole, both exports checked

The existing scenario is kept verbatim — the ten-stop scout still averages 3.6
pests per plant with a var/mean of 2.54, germination still reads 83% then 65%
then 45% — so its assertions hold, and the rest of the field day is driven
around it. The pest is named, the field stamped with block, observer and date;
five pollinator types are tallied — four defaults plus **one added by hand** —
for eleven visits, and the diversity is held against an oracle:

    Shannon H over [4,3,2,1,1] → effective types 4.3, evenness 0.91

The rotation is completed to both beds, and then both exports are read and held:
the **field-day report** (the pest counts per stop, the scouting note, the
pollinator line, the germination note, and a rotation note per bed) and the
**CSV** (a section/item/value row for every one of them). The generator computes
the diversity, the dispersion, the germination percentage and every export line
the page's own way — Shannon and evenness from the counts, `Math.round` on the
germination, `famLabel` on the rotation keys — so both sides of every claim come
from the same arithmetic.

## What moved

    farm-scout       5 → 15 of 15 fields entered   (the most-neglected page,
                                                    now the tenth entered whole)
    farm-scout      68 → 117 confirmed expectations  0 refuted
    its exports      0 → 2 read and held against an oracle
    the kit        461 → 471 of 521 fields           (90%), 17 of 27 pages whole

## Held

The rotation family selectors count as a field each — a picker per season, named
by their first option — so completing bed two added a rotation line to both
exports, folded into the oracle rather than worked around. The pollinator
tallies are reached by their host index (`@control:poGrid#0`) because a tally
button's label carries its live count and changes as it is tapped. No page was
edited: a task-only slice, the tenth page driven end to end, and the kit's
data-entry coverage crosses ninety percent.
