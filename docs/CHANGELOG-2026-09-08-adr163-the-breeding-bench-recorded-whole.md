# 2026-09-08 — ADR-163: the breeding bench, recorded whole

**All six panes driven, but six of twenty-one fields never entered — including
the heritability and SD behind an asserted selection response, and a third crop
picker hidden in the storage pane. Now 21/21. The kit reaches 95%.**

## Changed — `tools/tasks/page-breeding-bench-science.json`

62 → 73 steps, 100 → 113 confirmed expectations. The existing scenario is kept
verbatim (bean below its minimum, corn's Nₑ, isolation distances, response 6.14,
roguing, trial, germination), so its assertions hold, and the six never-entered
controls are driven around it: the breeding-goal dial, the "my own garden"
seed-use chip, the "off-type" rogue chip, the heritability (0.35) and phenotypic
SD (10) that the asserted 6.14 is built from, and the seed-storage crop picker.
A third crop is picked on the population pane and its published minimum (20, an
inbreeder) held against the oracle.

## Numbers

    breeding-bench.html   15 -> 21 of 21 fields entered   (100%)
                          100 -> 113 confirmed, 0 refuted
    the kit             490 -> 496 of 521 fields            (95%), 20/27 whole

## Held

- The page has three separate crop pickers (population, isolation, storage); the
  storage one was the last field standing, since the task picked crops on the
  first two and never the third.
- The heritability and SD are set to the values the assertion already assumed,
  so the 6.14 is unchanged — the inputs are now driven, not the number moved.
- No page was edited — a task-only slice, the thirteenth page entered whole.
