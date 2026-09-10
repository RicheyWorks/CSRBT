# 2026-09-09 — ADR-176: the deployment log's field sheet and the soil recipes' shopping list, read

**Four exports on two pages, none read, now pressed and held byte for byte.
Unread outputs 9 → 5.**

## Changed — `tools/tasks/page-deployment-log-science.json`

140 → 145 steps, 174 → 183 confirmed. `ecoCopy` (the whole field sheet: three
deployments, GSD 2.10 cm/px, Nyquist 24.0 kHz), `p-log/Print / save PDF` (one
print), the table and sheet read once more.

## Changed — `tools/tasks/page-soil-recipes-scaling.json`

13 → 18 steps, 40 → 49 confirmed. `recCopy` (Coot's quarter batch, whole),
`Print / save PDF` (one print), the export box read once more.

## Changed — `tools/verify/verify_dep.py`

105 → 109: the task's sheet literal held to the suite's GSD and Nyquist ports
and to the logged order.

## Changed — `tools/verify/verify_recipes.py`

238 → 241: a port of the page's scaling/formatting rules applied to the
page's recipe data; Coot's quarter batch export and the task's literal held to
it.

## Changed — `tools/outputs_ledger.json`

deployment-log 3 held (ceiling 2 → 0); soil-recipes 2 held (ceiling 2 → 0).

## Numbers

    the kit    9 → 5 unread of 66
