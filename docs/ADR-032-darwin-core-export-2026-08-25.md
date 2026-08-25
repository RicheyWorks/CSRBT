# ADR-032: A Darwin Core export, and the arithmetic of "where"

**Status:** Accepted and implemented — `tools/dwc.py` v1.2.0 inlined into three occurrence-recording pages, `tools/verify/verify_dwc.py` at 101 checks, canaried against three seeded faults.
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** `docs/releve.html`, `docs/stand-sheet.html`, `docs/collection-sheet.html`

---

## Context

The kit's own gap analysis ranked this first, and the evidence was blunt. Grepping all thirty-three pages
for `Darwin Core`, `occurrenceID`, `eventID`, `decimalLatitude`, `basisOfRecord`,
`coordinateUncertaintyInMeters`, `GBIF`, and `DwC` returned **zero occurrences**. The kit could produce a
defensible plot record and then had no way to hand it to anybody. A thesis student who fills a relevé sheet
and is later asked to deposit the occurrences in GBIF has to retype the whole thing into somebody else's
template, and the retyping is where the provenance dies.

Three pages record occurrences — a plant in a plot, a stem in a stand, a fungus on a log. They are the
three that get an export. The other thirty-one record measurements, not occurrences, and giving them an
occurrence exporter would be a category error dressed up as coverage.

## Decision

**Simple Darwin Core, one flat table, 32 terms, emitted by a single shared module.**

The same no-build-step constraint that produced the Field Entry Kit applies here: `tools/dwc.py` holds the
CSS and JS as strings, `tools/dwc_emit.py` inlines them into the three consumers, and `--check` reports
drift. Hand-patching an inlined copy is how the copies diverge, so the regenerator is the only writer.

### The honesty gate, applied to a coordinate

`coordinateUncertaintyInMeters` is the term where this kit's existing rule bites hardest, because the
tempting wrong answer is not a guess — it is a zero, and **zero is not a valid value for this term**. Zero
reads as a claim of perfect precision. Empty means unknown, which is the truth.

Uncertainty is computed by the point-radius method and is the sum of what is actually known:

| Component | Source | Omitted when |
|---|---|---|
| survey extent | plot geometry the page already holds | opportunistic collection — there is no plot |
| GPS accuracy | typed, in metres | not recorded |
| coordinate precision | decimal places actually typed | contributes < 0.5 m |
| unknown datum | 5359 m, the standard worst case | datum is stated |

**No component, no number.** If nothing is known, the field is written empty and the page says so in words.

### What this ADR exists to record: the 55-kilometre bug

The first implementation treated a blank latitude field as a coordinate typed to zero decimal places, and
so reported **55,667 m of uncertainty for a plot nobody had located yet**. The number was not wrong in its
arithmetic — half a degree of latitude really is about 55 km — it was wrong in that it answered a question
nobody had asked. A blank field is not a coarse measurement. It is the absence of one.

The guard is one line, and the suite that protects it is five checks, because this is precisely the class
of error that survives review: internally consistent, plausibly derived, and meaningless.

### Per-page decisions

**Relevé** exports cover as `organismQuantity` with `organismQuantityType: percentageCoverage`. Cover is a
proportion of a plot, not a count of individuals; the term pair exists so that distinction survives export.

**Stand Sheet** exports **one row per stem** — the finest grain the sheet actually recorded — each with
`organismQuantity: 1`. Stems per hectare is a derived rate and does not belong in an occurrence record; the
plot area travels in `sampleSizeValue` so anyone downloading it can recompute the density themselves. Every
stem inherits the plot centre, so the plot's own radius is part of each stem's uncertainty. `samplingProtocol`
states the minimum tallied DBH, because an occurrence dataset without its detection threshold is a
presence list with a silent floor. A snag is `occurrenceStatus: present` with its decay class in the
remarks — the organism was there; it is simply dead.

**Collection Sheet** is the one place where a field decision changes a controlled value: a collection with
a voucher number exports as `PreservedSpecimen`, one without as `HumanObservation`. The sheet will not call
a photograph a specimen. Working names export unaltered — if the name still ends in `sp.` or `cf.`, that is
what a herbarium needs to see, and `taxonRank` follows the name rather than flattering it. `identifiedBy`
stays empty when nobody has made a determination; crediting the collector with an identification they did
not make is a fabrication that would be very hard to notice later.

## The controls are FEK components, not bespoke inputs

The first implementation of the coordinate box hand-rolled a `<select>` for the datum and a bare
`<input type=number>` for the GPS accuracy. Three existing suites assert *no legacy select on this page*
and caught it immediately, which is exactly what ADR-031 built them to do. A bespoke control here would
have been the fifteenth hand-rolled entry widget and would have opted out of the 44 px rule, the focus
ring and the contrast palette that the audits enforce — silently, and only on the newest pages.

The datum is now a `FEK.dial` and the GPS accuracy a **nullable** `FEK.step`. Nullable matters: a GPS
accuracy of 0 m is not something anyone has measured, so an empty stepper means *not recorded* and
contributes nothing, rather than asserting a perfect fix. `dwc.py` refuses to build the box at all where
FEK is absent rather than carrying a fallback path that would never run and would rot unnoticed.

While fixing this, `verify_escaping_slice` turned out to be reading `version:"…"` from anywhere in a page
and so reported every consumer as disagreeing with itself once a second module declared a version. It was
also frozen on `1.2.0` and on *exactly fourteen consumers* — the fifth and sixth frozen constants found
this month. Both are now invariants: the version is read from `tools/fek.py`, and the consumer check is
that a page which **calls** a FEK constructor also **carries** FEK, which stays true as the kit grows.

## Identifiers

`occurrenceID` is a v4 UUID. GBIF discourages IDs derived from institution-collection-catalogue triplets
because they break when a specimen is recatalogued. Where `crypto.getRandomValues` is unavailable the module
falls back to `Math.random` and **says so in the copy confirmation** — unique on that device, not guaranteed
globally. A weak identifier that announces itself is recoverable; one that does not is not.

## Consequences

- Three pages now emit deposit-ready occurrence records. Twenty-nine do not, correctly.
- The term list is read from source by the suite, so adding a term is not a test failure.
- Still open, and named so they are not mistaken for done: Event Core with `parentEventID`, the ratified
  Humboldt Extension (`eco:targetTaxonomicScope`, `eco:isAbsenceReported`), and absence records — none of
  which Simple DwC can carry.
