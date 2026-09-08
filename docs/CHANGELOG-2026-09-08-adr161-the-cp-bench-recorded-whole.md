# 2026-09-08 — ADR-161: the carnivorous-plant bench, recorded whole

**Every tab exercised, but ten of twenty-three fields left at a default nobody
touched. Now 23/23, the media recipe held. The kit reaches 92%.**

## Changed — `tools/tasks/page-cp-bench-science.json`

51 → 65 steps, 85 → 104 confirmed expectations. The existing scenario is kept
verbatim (TDS excellent/usable/too-high; 10 top-ups at 50 ppm → 500 ppm; dormancy
verdicts; a cross's seed set), so its assertions hold, and the ten never-entered
controls are driven explicitly: the RO/DI water source chip, the three
accumulation steppers (TDS, top-ups, volume — the very inputs to the 500 ppm the
task already asserted), the "trap count" observation type, the three dormancy
steppers, and the two free-text fields (a plant's provenance and a cross's note).
The media recipe is copied and held against an oracle — "3 parts: 1 sphagnum
peat, 1 perlite, 1 coconut coir" — built from the Sarracenia·Dionaea preset plus
a coir component, computed from the page's own component table.

## Numbers

    cp-bench.html   13 -> 23 of 23 fields entered   (100%)
                    85 -> 104 confirmed, 0 refuted
                    recipe unread -> held
    the kit        471 -> 481 of 521 fields          (92%), 18/27 whole

## Held

- The first plant is left provenance-less so the "no source recorded" warning
  still fires; the source field is entered afterwards, on its own, not on that
  plant.
- The observation-type and source chips default to the value the task uses, so
  selecting them changes nothing but records that the harness can drive them.
- No page was edited — a task-only slice, the eleventh page entered whole.
