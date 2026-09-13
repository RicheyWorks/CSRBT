# 2026-09-13 — ADR-198: the plot everyone calls 400

**A circle of r = 11.28 m encloses 399.7312 m². The stand sheet printed
`400 m²` at `EF 25.0` — two figures that agree with each other and describe a
plot nobody measured — while every column computed from them used the real
25.01681. Closed, with the three figures four tasks claimed moved.**

## Fixed

- **stand sheet** — the area banner, the field sheet's plot line, the Darwin
  Core `sampleSizeValue` and the `samplingProtocol` string all print the area
  the radius encloses, to two decimals: `399.73 m²` at `EF 25.02`, `99.93 m²`
  at `100.07`. A rectangle still reads `400 m²` at `EF 25.0` — exact, and
  never the bug.
- **stand sheet** — `associatedTaxa` was a Darwin Core column the sheet emitted
  and never populated, on a sheet that records interactions naming the species
  it tallies. It now carries this occurrence's side of each edge
  (`mule deer eats this taxon`), and is empty when there is none.
- **stand sheet** — a top height computed from one measured stem said only
  `top height m`. The sample travels beside it as its own tile, so the figure's
  **name** does not move when the data does.

## Added

- `verify_ss` (84 → 114): the printed figures read back off the rendered
  sentence and reconciled — area × factor = 10,000 within what two decimals
  can carry — at three radii and on a rectangle; the stem CSV's per-hectare
  column recomputed from the **printed** factor; the edges in both directions.
- `verify_report` section L (208 → 223): the same properties through the
  gateway, and the deposit read as a deposit.
- `verify_dwc` (147 → 150): `sampleSizeValue` is the area, the protocol quotes
  the same one, and `associatedTaxa` is empty rather than invented when no edge
  names the species.
- `mutate_report` (124 → 134): ten page mutants, one per property, including
  the fix that would have taken the rectangle's decimal with it.

## Changed

- `tools/tasks/page-stand-sheet-science.json`: nine claims and the goal prose.
  The three blind trials are graded against the protocols frozen beside them
  (ADR-197) and their scores are unchanged — the first time that freeze has
  carried a fix rather than described one.
