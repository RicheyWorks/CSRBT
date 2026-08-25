# ADR-036: Event Core, Humboldt, and the difference between absent and not looked for

**Status:** Accepted and implemented — `docs/survey-design.html` (the kit's 25th instrument), `tools/verify/verify_sd.py` at 70 checks, canaried against six seeded faults.
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Extends:** ADR-032 (Simple Darwin Core). **Touches:** `docs/ecology.html`, the rail

---

## Context

This was the last item still open from the kit's own published gap analysis, and it is the one that
completes the deposition story ADR-032 started.

Simple Darwin Core — what the Relevé, Stand Sheet and Collection Sheet export — is one flat table of things
that were found. It is exactly right for that, and there are two things it **structurally cannot say**.

**The first is structure.** Twelve plots visited three times each is thirty-six sampling events nested
inside twelve locations nested inside one season. Flattened, every row repeats the plot and the season, and
nothing records that three particular rows were *the same plot on different days* rather than three plots.

**The second is absence.** A flat occurrence table contains what you found. It cannot say *I looked for
this and it was not there* — which, for anything to do with change over time, is the more valuable half of
the record. A species list from 2016 and one from 2026 tell you nothing about a decline unless both say
what was searched for.

## Decision

**A design page that emits three tables — Event Core, the Humboldt extension, and occurrences — and one
gate.**

### The gate

An occurrence row carrying `occurrenceStatus = absent` and nothing else **is not data**. Absent from what
search? Was the observer looking? Would they have recognised it? With no answer, a reader cannot
distinguish a real absence from a gap in the survey, and the correct thing for them to do is discard the
row. So:

> **Declare `eco:targetTaxonomicScope` and the page writes your absences. Leave it blank and it refuses.**

The refusal is enforced in the data path, not only in prose — the row is never built — and the count of
refused absences is shown beside the count of written ones.

There is a third state, and keeping it distinct is the same principle one level down. A taxon on the target
list that has been marked neither found nor absent reaches **no table at all**. "I did not decide" is not a
presence and not an absence, and writing it as either would be a fabrication. While any remain,
`eco:isTaxonomicScopeFullyReported` is `false`.

### Nothing is inherited

The Humboldt Extension is explicit, and it is the rule an intuitive implementation gets wrong:

> *"A child dwc:Event MUST NOT be assumed to implicitly 'inherit' the value of any property of any of its
> parent dwc:Events; rather, the value SHOULD be provided explicitly."*

So the obvious economy — write the coordinates and the scope once on the site, let the plots below inherit
— produces a file in which the plots have no scope. This page writes every applicable value at **every
level where it applies**. The file is larger and it is readable by something that did not build it. That
redundancy is the Principle of Applicability, and it is the specification rather than laziness.

### What it will not fill in

`eco:inventoryTypes` takes a value from a controlled vocabulary. The published term list defines the term
but **does not publish the value list**, and this page will not guess at one: a controlled value invented
locally validates against nothing while reading as authoritative. The field is free text, the export labels
it free text, and the readme says why.

## What the verification found

**The copy button silently dropped the refused absences.** The counts on the export tab said *1 refused*,
but pressing *Copy Occurrence table* produced a clean-looking presence-only CSV with no warning. A table
that looks complete and has quietly lost its absences is precisely the artefact this page exists to stop
somebody depositing — and a count three tabs away is not a warning anyone sees with a CSV already on their
clipboard. The button now refuses and names how many rows would have been lost.

**The no-inheritance rule had no test.** Seeding a fault that wrote Humboldt rows only for the root event
**passed every check in the suite**: the counts were right, the prose was right, and the file would have
been unreadable at exactly the level anyone joins on. The suite now reads the Humboldt table back through
the page's own copy path and asserts that a child visit carries the scope value explicitly — which catches
both the missing-rows version and the subtler one where the rows exist with the field blank.

**Removing a parent event** was checked to refuse rather than cascade. A cascade deletes work the user
cannot see.

## Consequences

- The kit can now deposit a sampling design, not only a species list.
- Absences are expressible, and only when they can be read.
- The gap analysis published earlier this month is now fully worked through.

## Sources

TDWG — [Humboldt Extension quick reference](https://eco.tdwg.org/terms/),
[term list](https://eco.tdwg.org/list/) (namespace `http://rs.tdwg.org/eco/terms/`, prefix `eco:`;
booleans from the TDWG Boolean Controlled Vocabulary; multiple values pipe-separated),
[properties of hierarchical events](https://eco.tdwg.org/hierarchy/) (the no-inheritance rule, quoted
above).
