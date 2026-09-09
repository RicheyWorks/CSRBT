# ADR-165 — The field notebook, recorded whole

**Status:** accepted · **Date:** 2026-09-09 · **The tap-to-tally field notebook counted species, quadrats and captures across three panes but never opened its ethogram or stamped its session: five of its six fields were unentered. Now 6 of 6, an activity budget tallied and the session named.**

## The notebook that never dated a page

`field-notebook.html` is a tally book for the field: tap a species to count
individuals, a quadrat cell to record presence, a "more" counter for captures
and recaptures, and a behaviour to build an **activity budget** — plus a session
header (site, observer, date) that stamps who took the counts and where. Its
task tallied species to ten individuals across three species, worked the
quadrats and the capture counters — but **five of its six value-carrying fields
were never entered**: the whole **ethogram** pane (the scan interval and the
add-a-behaviour box) and the entire **session header**.

A tally book whose pages carry no site, observer or date is a tally book whose
counts can't be attributed — the one thing a field notebook exists to prevent.

## Entered whole, a budget and a session

The existing scenario is kept verbatim — the species counts, the quadrat
dispersion, the capture/recapture counters all hold — and the five untouched
fields are driven: the **scan interval** is set (30 s, the point-sample cadence
fixed before the session starts), a new behaviour "preen" is **added and
tallied** alongside forage to build a real activity budget, and the session is
stamped with a site, an observer and today's date. The activity budget is read
back and held to show the added behaviour, so the ethogram is exercised end to
end rather than merely opened.

## What moved

    field-notebook   1 → 6 of 6 fields entered       (the lowest-covered page
                                                     in the kit, now closed)
    field-notebook  64 → 80 confirmed expectations     0 refuted
    the kit         502 → 507 of 521 fields            (97%), 22 of 27 pages whole

## Held

The ethogram board seeds five behaviours and the added "preen" becomes the
sixth; tallying forage and preen builds a budget the read confirms by name. The
session header is three plain text inputs reached by id. No page was edited: a
task-only slice, the fifteenth page driven end to end.
