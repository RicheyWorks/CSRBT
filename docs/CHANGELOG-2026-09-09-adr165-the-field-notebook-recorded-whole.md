# 2026-09-09 — ADR-165: the field notebook, recorded whole

**The lowest-covered page in the kit (1/6 fields): the ethogram never opened and
the session never stamped. Now 6/6. The kit reaches 97%.**

## Changed — `tools/tasks/page-field-notebook-science.json`

45 → 61 steps, 64 → 80 confirmed expectations. The existing scenario is kept
verbatim (species counts to ten individuals across three species, quadrat
dispersion, capture/recapture counters), so its assertions hold, and the five
never-entered fields are driven: the ethogram scan interval (30 s), a new
behaviour "preen" added and tallied alongside forage to build an activity budget
the read confirms by name, and the session header stamped with site, observer
and date.

## Numbers

    field-notebook.html   1 -> 6 of 6 fields entered    (100%)
                          64 -> 80 confirmed, 0 refuted
    the kit             502 -> 507 of 521 fields          (97%), 22/27 whole

## Held

- The ethogram board seeds five behaviours; "preen" is the sixth, and tallying
  forage and preen builds a budget the read holds by name.
- The session header is three plain text inputs reached by id.
- No page was edited — a task-only slice, the fifteenth page entered whole.
