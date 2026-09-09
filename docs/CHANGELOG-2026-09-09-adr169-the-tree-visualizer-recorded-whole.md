# 2026-09-09 — ADR-169: the tree visualizer, recorded whole

**The order-statistic tree was never asked an order statistic: its select-k-th
and rank-of boxes sat at defaults, read by nothing. Now 3/3. 26 of 27 pages are
whole — only cp-characters is left.**

## Changed — `tools/tasks/page-tree-visualizer-science.json`

24 → 34 steps, 80 → 91 confirmed expectations. The existing scenario is kept
verbatim (the 13-key boot tree at height 4, the 14th key, the ascending 20-key
RB build, the four morphs, the seeded random fill), so its assertions hold, and
the two never-driven order-statistic inputs are exercised on a rebuilt {10, 20,
30} tree: select(2) reads 20, rank(30) reads #3 — the page's own selectK and
rankOf held against the obvious answers.

## Numbers

    tree-visualizer.html    1 -> 3 of 3 fields entered    (100%)
                           80 -> 91 confirmed, 0 refuted
    the kit               518 -> 520 of 521 fields          (26/27 whole)

## Held

- The order-statistic queries do not change the tree, so building a known
  three-key tree and asking select and rank exercises both inputs against
  answers a reader can check by counting.
- The rebuild happens after every earlier assertion has been graded.
- No page was edited — a task-only slice, the nineteenth page entered whole.
