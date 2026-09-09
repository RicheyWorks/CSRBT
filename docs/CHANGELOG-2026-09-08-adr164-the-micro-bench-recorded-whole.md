# 2026-09-08 — ADR-164: the micro bench, recorded whole

**A CFU/mL and a dilution plan computed, but six of eighteen fields never
entered — every one a volume or label the result depends on. Now 18/18. The kit
reaches 96%.**

## Changed — `tools/tasks/page-micro-bench-science.json`

50 → 60 steps, 74 → 86 confirmed expectations. The existing scenario is kept
verbatim (plate counts to 9.90×10⁷ CFU/mL across the countable plates, the
dilution stepping 1:10 at 1.00 log₁₀, the growth curve, the zone
interpretation), so its assertions hold, and the six never-entered fields are set
to the values those results already assumed: the plated volume (0.1 mL), the
transfer and diluent volumes (1 mL into 9), and the zone medium
(Mueller-Hinton) and organism (E. coli ATCC 25922). The count and dilution plan
are re-read and held against the oracle with the volumes now driven.

## Numbers

    micro-bench.html   12 -> 18 of 18 fields entered   (100%)
                       74 -> 86 confirmed, 0 refuted
    the kit           496 -> 502 of 521 fields           (96%), 21/27 whole

## Held

- The "mean of countable" CFU is 9.90×10⁷ (the average of plates inside the
  30–300 window), not the 1.48×10⁸ of the single best plate; the confirming read
  holds the average.
- Each volume is set to the value the calculation already used, so no figure
  moved — the settings are now driven.
- No page was edited — a task-only slice, the fourteenth page entered whole.
