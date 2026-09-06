# ADR-145 — The collection sheet, entered whole

**Status:** accepted · **Date:** 2026-09-05 · **ADR-144 measured what the kit's tasks actually enter and found 6 of the collection sheet's 63 fields. This slice enters the rest — the site block, the coordinates, the weather, one specimen described in full, a spore print, four spot tests, a voucher label — and holds what the sheet does with them: 6 → 59 of 63 fields, 9 → 66 confirmed expectations, and the kit from 185 to 237 fields entered. Entering data nobody had entered found four defects, three of them in the harness**

## 1. Why this page

The collection sheet is the kit's flagship data-entry page and ADR-128's
worked example: five collections, and the diversity arithmetic held to a
hand-checked oracle — Chao1 6.5, Shannon 1.359, Pielou 0.845. All of it about
six fields. The other fifty-seven — where you were, when, what the weather had
done, what the specimen smelled like, what the spore print was, what the
reagents did, what the voucher says — were entered by nothing, and the sheet
computes real things from every one of them.

## 2. What is entered now, and what is held

| block | entered | held to |
|---|---|---|
| site & weather | site, collector, date, lat, lon, vegetation, dominant trees, disturbance, elevation, duff depth, stand age, coarse woody debris | the weather verdict: **14 days after a 32 mm event**, inside the 7–21 day window, soil at 10 cm |
| coordinates | GPS accuracy, geodetic datum | `coordinateUncertaintyInMeters` = **36 m**, then **5395 m** with the datum unknown, then 36 m again |
| the specimen | collection number, substrate, habit, hymenophore, two characters, cap width, stipe length and width, fresh mass, odour, colour change, notes, distance to the host stem | the field-sheet export, line by line |
| spore print | colour swatch, print duration, the surface it was taken on | the print note and the export |
| spot tests | four reagents; **four deliberately left blank** | the export |
| voucher | herbarium, accession, determiner, start time, dryer temperature, hours, preparation, DNA subsample | the label: locality with coordinates, habitat, substrate with host, spore print, fresh characters, spot tests |

The coordinate figures are the interesting ones because the page computes them
by a published method (Chapman & Wieczorek's point-radius) and the oracle is a
Python port of the page's own `uncertainty()`: contributions summed, rounded
once — 30 m of GPS plus 5.53 m for four decimal places at this latitude is 36 m;
an unknown datum adds 5359 m. Typed numbers would have been a guess; these are
recomputed.

**Four reagent rows are left blank on purpose.** The sheet's own rule is that
blank means *not tested*, which is not the same as negative, and it keeps them
apart in the export. Filling every row to raise a coverage number would be
inventing observations, which is the one thing a data-entry harness must not do.
So the page reads **59 of 63**, and the four that remain are a decision rather
than a gap.

## 3. What entering it found

**A page coupling, held.** Typing the stand's dominant trees *replaces* the host
picker's regional default with your own stand — so a host that is not in your
stand is refused. The task now enters the stand list and holds both halves:
`Quercus gambelii` is refused, `Pinus contorta` is taken.

That one refusal exposed three defects, all of them in the instrument:

**1. A picker with nothing showing was "not a picker".** `pick` checked for an
option in the DOM *before* typing. This sheet removes non-matching options
rather than hiding them, so after one refused filter the picker had none — and
every later pick answered `not a picker`, including the one that would have
cleared the filter. A single refused pick made the control unusable for the
rest of the session. Whether something is a picker is **structural**; whether it
has options is a fact of the moment. Fixed, and a control cannot stop being a
picker because of what someone typed into it.

**2. A refusal carried no snapshot.** The gateway raises before it observes, so
a refused response has none — and the next `@control:<name>` then resolved
against the last *successful* step's snapshot, which the refusal may have made
stale. It had: the failed filter rebuilt the picker, and the runner blamed the
page for a stale name of its own. The task runner now observes after a refusal.
A refusal is a move too (ADR-126's phrase, one layer down).

**3. An unnamed control's identity was counted across the whole document.** The
audit stamp is `tag#id.class` plus occurrence among identical siblings — and for
a dial's options, which have no id and no distinguishing class, the occurrence
index *was* the whole identity. Adding a collection row anywhere above
renumbered everything below it, so a control measured before the row existed was
a different control after: the stand-age dial came back from ADR-144's
measurement as *never entered* by a task that had just clicked it. The index is
now counted **within the nearest identified ancestor**, which is stable against
the page growing elsewhere — the growth that actually happens. This was ADR-144's
own stated caveat, found biting three days later by the first task that made a
page grow while measuring it.

## 4. The numbers

    collection-sheet.html   6 → 59 of 63 fields   (9 → 66 confirmed expectations)
    the kit               185 → 237 of 517 fields  (36% → 46%)

The kit's total moved by more than this page alone, because the stamp fix
recovered phantom misses on every page whose task makes it grow.

## 5. What is now asserted

`verify_report` **85** (+6): a picker whose filter matches nothing is refused as
*no option matches* and not as *not a picker*; the page really has removed every
option, which is the state the old guard could not tell from "this is not a
picker"; the next pick still works; and each picker's option pool is keyed by
its own search box. `mutate_report` **52** (+2).

`verify_audit_states` **67** (+3): a control with no id keeps its stamp when the
page grows somewhere else; a control **with** an id is keyed by the id alone, so
moving it into another identified ancestor keeps every measurement taken under
it. `mutate_audit_states` **45** (+2).

`verify_tasks` **284** (+2): a refused step carries a snapshot, and is still
recorded as a refusal. `mutate_tasks` **63** (+1).

## 6. Held

- **Nine tasks' worth of pages are still where this one was.** ecology-lab is 7
  of 40, stand-sheet 9 of 50, deployment-log 17 of 37. The method is now a
  worked example rather than a plan: enter the block, find what the page
  computes from it, hold that with an oracle.
- **A held export line is not a held science.** The field sheet echoing "odour
  faintly raphanoid" proves the sheet carries what was entered; it says nothing
  about whether the odour was recorded correctly, which is a question about the
  collector.
- **The four blank reagents are a claim too**, and an unheld one: nothing checks
  that a blank row exports as *not tested* rather than as negative. That is the
  next check on this page, not a gap in this one.
- The coordinate oracle ports the page's own arithmetic, so it catches a change
  in the page but not a shared misunderstanding of the method.

## 7. First reading

    collection sheet     59 / 63 fields entered · 66 expectations confirmed
    the kit             237 / 517 fields entered (46%)
    verify_report        85 · verify_audit_states 67 · verify_tasks 284
