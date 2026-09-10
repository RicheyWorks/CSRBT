# 2026-09-10 — ADR-178: the protocol library's predictions hold

**ADR-177's finding closed: the two ready-made protocols whose predictions the
engine refuted are rewritten to the bands their data sits in, the page is
republished and swept, the task holds the rewritten protocol byte for byte,
and `verify_epl` carries no recorded exceptions.**

## Changed — `docs/eco-protocol-library.html` (republished, `d608dd5a…`)

- `two-ponds.eco`: `evenness(pondA) is uneven # duckweed dominates` →
  `evenness(pondA) is moderate # duckweed leads, 44 of 80, but four others
  hold their share`; `brayCurtis(pondA, pondB) > 0.4` → `turnover(pondA,
  pondB) is moderate # shared duckweed and rush keep the mats closer than they
  look`.
- `activity-budget.eco`: `evenness(morning) is uneven` → `evenness(morning)
  is very-even # five acts, none above half the scans`; `brayCurtis(morning,
  afternoon) > 0.3 # the budget shifted` → `> 0.2 # the budget shifted:
  forage halved, rest nearly doubled`.
- Engine: 3 of 3 and 2 of 2 confirmed. Lab importer: 0 problems.

## Changed — `tools/tasks/page-eco-protocol-library-reference.json`

12 → 17 confirmed: the second `Copy` → `two-ponds.eco` whole, one clipboard
payload and nothing else; the toast read after.

## Changed — `tools/verify/verify_epl.py`

40 → 42: `KNOWN_REFUTED = {}`; no protocol may carry a refuted prediction the
page did not call wrong; the four rewritten lines held by name; the task's
second literal held to the page.

## Numbers

    library predictions refuted and unannounced   4 → 0
    artifacts measured from the live page         42 / 42

## Noted, not done

The `.eco` Reference lists the qualitative bands as `even` / `uneven`; the
engine's words are `very-even` / `moderate` / `uneven` / `dominated`, and
`turnover` has `low` / `moderate` / `major`. A page edit with a republish.
