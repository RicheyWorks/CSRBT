# Changelog — 2026-08-30 — ADR-107: the first photograph

The kit's first real observation, an evidence pipeline proven end to end, and the
seam the experiment surfaced.

## New — image evidence

- `docs/evidence/` — content-addressed store. Filenames carry the first 8 hex of
  the sha256 of the bytes; `manifest.json` records hash, size, dimensions, site,
  and **whether the file certifies its own origin**.
- `docs/evidence/tahoe-westshore-a42a4047.png` — 510×680, 461,570 bytes. No EXIF,
  no timestamp, no GPS: `self_certifying: false`, site attribution recorded as
  testimony.
- `tools/verify/verify_evidence.py` — **15 checks, all green**: storage hash,
  content-addressing, re-derived dimensions, the self-certification honesty
  clause, and that the `data:` URI embedded in the page decodes byte-identical to
  the stored file.

## New — Douglas Explorer Mode

- `docs/douglas-explorer.html`, published and mapped
  (`tools/artifact_map.json`, stamped). Contains: David Douglas's biography with
  every claim tagged documented or traditional; an original silhouette device
  (**not his likeness** — he died before photographic portraiture) with a
  *Pseudotsuga* cone; the six rules of the mode; the plate; and a full lab report.
- `docs/tahoe-westshore.eco` — the protocol: three data layers, a conifer
  phylogeny in Newick, island and logistic models, four abiotic factors, nine
  notebook entries, five pre-registered hypotheses.

## The lab report

- Site and physiography (graben structure, Sierra Nevada batholith granodiorite),
  the lake (ultraoligotrophic; **69.2 ft Secchi in 2025** against a 97.4 ft
  1967–71 baseline; *Mysis* introduction and the cladoceran collapse), vegetation
  keyed by evidence tier, fauna by the structure that supports it, quantitative
  results, limitations, and a survey of the basin's public numeric data sources
  mapped to the kit instrument that consumes each.
- **Central methodological result, negative:** at this resolution the canopy is
  defensible at genus, the spire crowns at family, the shrub and ground layers at
  growth form, and the snag not at all. Even which range is on the skyline is left
  open, because the photograph does not settle it.

## Found — the seam

- Every field the `.eco` grammar was said to be missing **already exists in the
  kit's own field pages**: coordinates/slope/aspect and Braun-Blanquet and
  Daubenmire cover classes in `releve.html`, `eventDate`/`recordedBy` in all three
  export pages, `basisOfRecord` in `collection-sheet.html`, DBH/basal area/snags
  in `stand-sheet.html`.
- The kit has two halves that do not speak to each other. The field pages emit
  **Darwin Core**; the protocol engine cannot read it. The work to do is one
  reader, not six directives — and it also opens GBIF, iNaturalist, CCH2 and
  MyCoPortal, which publish the same standard.

## Queued

The Darwin Core reader; `site:`/`cover:`/`evidence:`/confidence rank; running the
protocol on a JDK 17 host; and re-entering this observation through `releve.html`,
which is blocked by nothing at all.
