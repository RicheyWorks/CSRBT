# ADR-214 — Nine stations charted a morning's run and let you carry away none of it

**ADR-213 took the ecology lab from 32 figures that reach no file to 19, and named what was left: the nine stations, rendered from a session JSON by nine independent renderers, whose readings belong to a RUN rather than to a pre-registration. This is that slice. A reader could see that a run's meadow came back at J′ 0.52 with 11 effective species and a Chao1 of 103.5, and had exactly one way to carry it anywhere: retype it off the screen. 19 → 0, and the kit's carried worklist with it: 0 of 317.**

## 1. The argument that was already refused

The obvious objection is that the reader *has* the session JSON — the stations are
drawn from a file they loaded. Every number is reproducible by loading it back
into this page.

That is the same argument ADR-213 refused for the workbench, and it fails for the
same reason: **having the inputs is not having the answers.** A `.eco` protocol
carried the data and made a reader recompute every result with no way to tell
whether they matched the screen; a session JSON carries a rank-abundance vector
and a survivorship series and makes a reader re-run a page to find out what the
Chao1 estimate was. The file that says what the run *produced* did not exist.

## 2. Read from the session, not from the tiles

`runRecord(S)` takes the same field each tile takes and formats it the same way.
It does not touch the DOM.

That is the whole difference between a record and a transcript. **A record
scraped out of the page would agree with the page by construction** — it could
never catch the page being wrong, and the check holding the two together would be
a check on nothing. Built from `S`, the record and the stations can disagree, and
`verify_eco` reads the figures off the **tiles** and requires each of them in the
record: the one comparison that can fail.

A page with no session carries no record card, rather than a header over nothing.

## 3. What the record says

```
# ecology lab — run record
# read from the session this page charted;
# the stations above show the same numbers.

## The Meadow — diversity
  Even grazing: J' 1, effective species 100, Chao1 est. richness 100, curve uniform
  Hot-patch grazing: J' 0.521, effective species 11, Chao1 est. richness 103.5, curve broken stick
  Pianka overlap 0.259, Bray-Curtis 0.812

## Demography and growth
  completed lives 1,134, mean age at death 228 ops, type ii
  growth rate r (per op) 0.0026, carrying capacity K ≈ 138.5 keys, r² 0.472

## The Archipelago — metapopulation
  local extinctions 3, recolonizations 3, Levins predicted occupancy 83%, observed occupancy 100%

## The Fossil Record — inheritance
  avg turnover per generation 33%, keys inherited / generation 80%, physical nodes inherited 57.5%

## The Island — equilibrium
  capacity (island area) 12, immigrations 54, extinctions 42, turnover / interval 6
```

The page's own task presses the button and holds those bytes, so it is not one
more export nothing reads (ADR-153).

## 4. Six figures declared

The Terrarium's two live demonstrations — the island equilibrium toy and the
meadow's hot-key slider — publish six figures that are now **declared right to
stay on the screen**, with the reason in the ledger: they redraw on every drag, so
the figure is a picture of a parameter you are moving rather than a record of
anything that happened. There is nothing to carry away; the run that produced a
number is the position of a slider. The numbers that *are* a record are the
stations' and the workbench's, and both now leave with their own export.

## 5. Where the count stands

    ADR-211  132 of 317 figures the exporting pages compute reach no file
    ADR-213   19, all on one page
    ADR-214    0

Every page of this kit that hands anything over now hands over what it worked
out, or says in writing why a figure stays on the screen.
