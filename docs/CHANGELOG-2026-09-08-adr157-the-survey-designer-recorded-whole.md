# 2026-09-08 — ADR-157: the survey designer, recorded whole

**The Event Core / Humboldt page was the kit's worst-covered (5/14 fields) and
its most-unread (6/6 exports). Now 14/14 and all six exports held.**

## Changed — `tools/tasks/page-survey-design-science.json`

28 → 55 steps, 73 confirmed expectations. Types the dataset name, prefix and
effort protocol before the example design loads (so it keeps them), adds an
inventory type and a target taxon, drives the level dial and parent picker
explicitly, builds one site by hand ("South spring" → 15→16 events), and holds
all six things the page hands over: Event Core, Humboldt extension, occurrence
table, readme, print, and the hierarchy's per-row copy-ID. The occurrence
table's per-row UUID is excluded from the assertions; its deterministic columns
(eventID, name, present/absent, the absence note) are held. Row counts come from
an oracle, not by hand.

## Numbers

    survey-design.html   5 -> 14 of 14 fields entered  (100%)
                         6 unread exports -> 0
    the kit              424 -> 433 of 520 fields      (82% -> 83%)

## Held

- The example design is deterministic — no clock freeze needed. The hand-built
  event exercises the manual add path and the id generator.
- One export stays silent (a copy-ID pressed with nothing to copy); silent is
  not unread.
- The occurrence UUID is outside the oracle by design.
