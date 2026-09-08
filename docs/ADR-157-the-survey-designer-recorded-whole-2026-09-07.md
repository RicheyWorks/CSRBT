# ADR-157 — The survey designer, recorded whole

**Status:** accepted · **Date:** 2026-09-08 · **The Event Core / Humboldt page — the one that exists to say the difference between "absent" and "not looked for" — was the kit's worst-covered page and its most-unread: 5 of 14 fields entered, 6 of 6 exports read by nothing. Entered whole against its own example design plus one hand-built event: 14 of 14 fields, all six exports held, and the tables it deposits checked against an oracle for the first time.**

## The page whose product is three files nobody had read

`survey-design.html` builds a Darwin Core **Event Core** deposit: a sampling
hierarchy (survey → site → plot → visit), the **Humboldt Extension** terms that
say what was searched for at every level, and an occurrence table that can
record *absence* — the thing a flat occurrence table structurally cannot say.
Its whole reason to exist is that "we did not record mosses" and "we found no
mosses" produce the same empty cells and mean opposite things.

Its task loaded the example design and checked the on-screen counts, but **five
of its fourteen fields were never entered** — the dataset name and prefix, a
manually built event's name and date, the effort protocol, the inventory type,
a target taxon — and **all six of the things it hands over were unread**: Event
Core, the Humboldt extension, the occurrence table, the readme, the print, and
the tree's per-row *copy ID*. The page deposits three joined files and the
harness had never looked at one of them.

## Entered whole, and the export checked

The demo fills a field only if it is blank, so the dataset name, prefix and
effort protocol are **typed before the example loads** — the design keeps them,
and every id stays as the existing assertions expect. Then an inventory type and
a target taxon are added, the level dial and the parent picker are driven
through explicitly rather than left at their defaults, and **one site is built
by hand** — "South spring", under the survey — taking the design from 15 events
to 16.

Every export is then read and held against an oracle:

    Event Core      16 rows   the added site's row, verbatim and comma-free
    Humboldt        16 rows   its site row: no effort columns (a site is not a
                              search), inventory type free-text, samplingEvents
    Occurrence       3 rows   2 present + 1 absent, all on visit:01
    readme                    target scope, excluded scope, the namespace

**The occurrence table carries a random UUID per row**, so it is asserted on its
deterministic columns only — the eventID, the name, `present`/`absent`, and the
absence note *"searched for within Tracheophyta and not detected"* — never on
the UUID. The row *counts* come from the oracle (15 demo events + 1 = 16;
occurrences unchanged because the new taxon is undecided and an undecided taxon
is no row at all), not from reading them off the page.

## What it closed

    survey-design.html   5 -> 14 of 14 fields entered   (100%)
                         6 unread exports -> 0 (6 emit, 6 held, 1 silent)
    the kit              424 -> 433 of 520 fields (82% -> 83%)

Eight pages are now entered whole. This is the second of the two pages the
ADR-155 instrument fix was about — the one whose spill numbers had been noise —
now driven end to end with its arithmetic pinned.

## Held

- The example design is deterministic, so no clock freeze was needed here; the
  one hand-built event is what exercises the manual add path and the id
  generator (`nextId` gave `SGH2026:site:03`, the third site).
- One export stays **silent**: a `copy ID` on an event with nothing to copy in
  the state it was pressed. Silent is not unread — the button works, it simply
  had nothing to hand over at that moment.
- The occurrence UUID is deliberately outside the oracle. A page that stamps a
  fresh identifier per deposit is behaving correctly, and asserting the UUID
  would be asserting the random number generator.
