# ADR-107: the first photograph, and the seam it found

**Status:** Accepted (2026-08-30) — evidence pipeline landed and proven
(`verify_evidence`, 15/15). The experiment it was built for is **partly queued**,
deliberately.
**Date:** 2026-08-30
**Deciders:** Richmond
**Builds on:** ADR-106 (an audit of nothing reports clean), ADR-031 (the honesty
gate), and the ecology engine of ADR-015 through ADR-020.

---

## 1. What was attempted

The kit had never held a real observation. Every experiment to date has been a
seeded stream with a known answer. Richmond supplied a photograph of a montane
conifer stand above Lake Tahoe and asked for the whole ecosystem to be put to it:
enter everything, prove how the picture is stored, identify what can be
identified, and write it up at thesis density.

The mode is now named: **Douglas Explorer Mode**, after David Douglas, who did
this for eleven years with a notebook and a plant press, wore the wet shirt so
the dry one could wrap the specimens, and died in a bullock pit on Mauna Kea in
1834 at thirty-five. The page carries his biography with each claim tagged
documented or traditional, because a kit with an honesty gate does not get to
repeat a good story as a fact — the roots he is always said to have lived on are
tagged traditional, and the starvation and lost provisions that are documented
are tagged as such.

## 2. What was finished: the evidence chain, proven

A photograph is only evidence if you can say what happened to it. The store is
**content-addressed**: the filename carries the first eight hex of the sha256 of
the bytes, so an altered file no longer matches its own name.
`tools/verify/verify_evidence.py` proves four links from the bytes rather than
from the record, 15 checks, all green:

1. **Storage** — the stored bytes hash to the recorded sha256.
2. **Addressing** — the name matches that hash.
3. **Description** — byte count and pixel dimensions are re-derived from the PNG
   header, never trusted from the manifest.
4. **Publication** — the `data:` URI embedded in the page decodes **byte-identical**
   to the stored file. This is the link that decides what a reader sees, because
   an artifact runs under a policy that blocks external images: the picture
   travels inside the page or not at all.

And one refusal. The file carries no EXIF, no `tIME`, no GPS. It therefore
**cannot certify its own origin**, the manifest must record `self_certifying:
false`, and a site attribution rested on testimony must be labelled as testimony.
Provenance by instrument and provenance by assertion are different evidence and
the suite fails if they are allowed to read the same.

The first draft of that suite computed its root one directory short and looked
for `tools/docs/evidence`. It reported three clean failures instead of an empty
pass — ADR-106's rule firing on the very check that enforces it.

## 3. What the observation actually supports

The report is structured by evidence tier — observed, inferred, regional — and
its central result is negative:

> At this resolution almost nothing is identifiable to species.

Crown silhouette, branch habit and foliage texture are legible. Needle fascicle
count, bark plate colour, cone morphology — the characters that actually separate
*Pinus jeffreyi* from *P. ponderosa*, or *Abies concolor* from *A. magnifica* —
are not. So the canopy is defensible at **genus**, the spire-form crowns at
**family**, the shrub and ground layers at **growth form**, and the snag not at
all. The community call — Sierra Nevada upper montane mixed conifer, Jeffrey
pine–white fir expression — rests on physiognomy and setting, which is legitimate
community-level evidence and does not depend on any uncertain species row.

Even the range on the skyline is left open: from the west shore it is the Carson
Range, from the east shore the Sierra crest, and the photograph does not settle
it. That is one missing datum — a bearing — not a failure of botany.

## 4. The seam, which is the real result

The first pass listed six things the harness could not hold: coordinates,
elevation, aspect and slope; date and observer; the source photograph; cover as
distinct from a count; identification confidence; abiotic variables beyond four.

That list was correct about the `.eco` grammar and **wrong about the kit**.
Every one of those fields already exists in the kit's own field pages:

| Called missing | Already lives in |
|---|---|
| coordinates, slope, aspect | `releve.html`, with `coordinateUncertaintyInMeters` and a rule that unknown stays empty rather than becoming a zero |
| percent cover as its own quantity | `releve.html` — Braun-Blanquet and Daubenmire classes with midpoints |
| date, observer | all three export pages — `eventDate`, `recordedBy` |
| whether a specimen was kept | `collection-sheet.html` — `basisOfRecord` |
| DBH, basal area, snags | `stand-sheet.html` |

So the harness is not missing these concepts. **It has two halves that do not
speak to each other.** The HTML field pages record an observation properly and
emit **Darwin Core**. The `.eco` protocol engine holds the analysis — diversity,
beta diversity, life tables, island biogeography, graded hypotheses, the export
bundle — and cannot read a word of what the field pages produce. This observation
went in through the wrong half.

**The plugin to build is one reader, not six directives:** Darwin Core / relevé
export → `.eco` ingest. And because Darwin Core is the standard GBIF,
iNaturalist, CCH2 and MyCoPortal all publish in, that one reader also opens the
public record for the basin — which is why the data-source survey in the report
can say *direct* against most of its rows.

## 5. Queued, not half-built

Per instruction: what could not be finished is held with its reason rather than
faked.

| Queued | Blocked by |
|---|---|
| The Darwin Core reader (§4) — supersedes the rest | Grammar + ingest work in `ExperimentSpec.java` |
| `site:`, `cover:`, `evidence:`, confidence rank | Same, and better designed against the reader than separately |
| Running `tahoe-westshore.eco` end to end | The engine needs JDK 17 and log4j; assembled from a machine with neither. `./gradlew ecologyExperiment -Pspec=docs/tahoe-westshore.eco` on the host |
| Re-entering the observation through `releve.html` | Nothing — it should simply be done, and would raise the record's quality immediately |

## 6. Consequences

- The kit can hold image evidence, and can prove what it did with it. That was
  not true this morning.
- The exercise cost one photograph and returned an architectural finding that
  years of seeded experiments had not: the two halves of the kit are not
  connected. Real data does that; simulations do not, because a simulation only
  ever offers what the engine already accepts.
- `docs/douglas-explorer.html` is published and mapped; the store is
  `docs/evidence/`, content-addressed, with `manifest.json` as its record.
