# 2026-09-08 — ADR-162: the pheno tracker, recorded whole

**The breeder's selection bench computed a differential but never named its run,
noted a plant, or drove the mother/cross controls. Now 16/16, both exports held.
The kit reaches 94%.**

## Changed — `tools/tasks/page-pheno-tracker-science.json`

63 → 80 steps, 77 → 102 confirmed expectations. The existing scenario is kept
verbatim (eight scores, three keepers, run mean 2.41, keeper mean 3.85,
selection differential +1.44, three segregation χ² tests), so its assertions
hold, and the nine never-entered fields are driven around it: the run name /
observer / date, a plant note, a 🌿 mother promotion, two cross-parent pickers +
plan, the trait weight, and the segregation trait. Both exports are then read and
held against an oracle — the field-day report (header, per-plant weighted score
with note, keeper line S=+1.44, the 60:20 cross) and the CSV (weighted-trait
header, #1's row 5,4,4,4 → 4.18 keep) — every figure computed the page's way from
the four dial weights.

## Numbers

    pheno-tracker.html   7 -> 16 of 16 fields entered   (100%)
                         77 -> 102 confirmed, 0 refuted
                         0 -> 2 exports read and held
    the kit            481 -> 490 of 521 fields           (94%), 19/27 whole

## Held

- The mother is promoted on a non-keeper and the cross planned between keepers,
  so neither disturbs the asserted keeper line or plant row.
- The trait name and weight are entered without adding a trait — adding one puts
  an unscored dial on every plant, a field only closeable by scoring it, which
  would move the totals the run is trusted for.
- No page was edited — a task-only slice, the twelfth page entered whole.
