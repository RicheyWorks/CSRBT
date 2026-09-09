# 2026-09-09 — ADR-175: the ordination page's outputs, read

**Three exports the page hands over and nothing read — the coordinates, the
dissimilarity matrix, the print — are pressed and held: the matrix byte for
byte against the suite's Bray-Curtis port, the coordinates by shape and the
page's own arbitrary-axes warning. Unread outputs 12 → 9.**

## Changed — `tools/tasks/page-ordination-science.json`

35 → 42 steps, 70 → 89 confirmed. On the last run (quoted four-site data,
sqrt, Wisconsin, Bray-Curtis): `copyDis` (the 4×4 matrix to six decimals,
whole), `copyCoord` (`site,NMDS1,NMDS2`, a row per site, the warning with
`stress-1 = 0.0000`, no NaN — no position pinned), `Print / save PDF` (one
print), then the parse and verdict read once more.

## Changed — `tools/verify/verify_ord.py`

111 → 114: the matrix recomputed through the suite's own `wisconsin()` and
`bray()` and the task's literal held to it (skipped where numpy is absent);
the coordinates step held to pin no position; the print held.

## Changed — `tools/outputs_ledger.json`

ordination: 3 held, ceiling 3 → 0.

## Numbers

    ordination         0 → 3 of 3 outputs held
    the kit           12 → 9 unread of 66
