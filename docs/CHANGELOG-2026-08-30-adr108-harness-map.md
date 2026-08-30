# Changelog — 2026-08-30 — ADR-108: the harness had no map

Routes published, navigation made atomic, coverage ratcheted, and the Darwin Core
seam from ADR-107 closed. Full suite **66 of 66 jobs, 4,507 of 4,507 checks**;
Java **1,127 tests**.

## New — `tools/routes.py`

- Publishes `tools/routes.json`: **128 routes, 41 primary + 87 nested**, derived
  from the pages themselves so the table cannot drift from them.
- `navigate()` opens a route exactly or raises `RouteError`, refusing four ways:
  `MISSING`, `AMBIGUOUS` (a selector matching more than one element is not an
  address), `DISABLED`, and `UNCONFIRMED` — the click that happened and changed
  nothing.

## New — `tools/verify/verify_routes.py` (14 checks)

The app-wide contract: every page routed, ids globally unique, the table matching
what the pages declare, **every routed page covered by the harness ledger**, a
control-count floor, and all 128 routes resolving atomically in a real browser.
All four refusals canaried against seeded faults in a real page.

- Check 4 **went red on its first run**, naming `douglas-explorer.html` — a page
  the harness had never opened while every suite reported green. That is the
  defect the suite was built for, still present when it arrived.

## Fixed — `tools/harness.py` ledger was destructive

- It rewrote `harness_ledger.json` wholesale, so `harness.py one-page.html`
  silently deleted the coverage of every page it did not run. Third instance of
  this defect in the kit (ADR-104's counts ledger was the first). It merges now,
  keeps unrun pages, stamps each entry with its own `at`, and reports
  *"1 page driven, 40 kept from earlier runs"*.
- Per-page totals count list-valued fields correctly.

## New — the Darwin Core seam (closes ADR-107's queue)

- **`DarwinCore.java`** — reads Darwin Core occurrence records, comma- or
  tab-separated, from the kit's own field pages or from a GBIF download.
  Terms: `scientificName`, `organismQuantity` + `organismQuantityType`,
  `individualCount`, `eventDate`, `recordedBy`, `decimalLatitude` /
  `decimalLongitude` / `coordinateUncertaintyInMeters`,
  `minimumElevationInMeters`, `basisOfRecord`, `identificationQualifier`,
  `associatedMedia`, `locality`.
- **The rule:** `abundance()` **refuses** cover data — Chao1 and rarefaction
  estimate unseen species from counts of individuals — and `cover()` refuses
  counts. `proportionalWeights()` is the narrow door letting Shannon, Simpson,
  evenness and Bray–Curtis work on cover honestly.
- An absent coordinate stays absent, never `0`.
- Mixed quantity types in one file are refused, not pooled. Two sites in one file
  are flagged. A non-Darwin-Core table is refused by name.
- **`dwc: <label> <path>`** directive in `.eco`; `ExperimentLab` resolves it,
  narrates cover datasets without a richness estimator, and marks
  `"quantity": "cover", "chao1": null` in the session JSON.
- `ExperimentSpec.Dataset` carries its quantity kind; `dwc:` labels are valid
  targets for `note(...)` and `expect(...)`.
- **15 tests**, including the end-to-end seam and a missing-file case.

## The first ecological experiment, run

`docs/tahoe-westshore.eco` now ingests `docs/tahoe-canopy-dwc.csv` and
`docs/tahoe-understory-dwc.csv` and runs end to end, printing
`cover data: Chao1 and rarefaction withheld` for the two cover datasets while the
counts-based `structure` dataset keeps its Chao1. Five pre-registered hypotheses
graded **3 confirmed, 2 refuted** — both refutations the author's.

## New — `docs/AI_HARNESS.md`

The harness contract: routes, the four refusals, selectors, the observable-trace
oracle, the accounting identity, the ratchet, the merge rule, and the Darwin Core
contract in both directions.

## Credit

- `docs/evidence/manifest.json` and the page now record the photograph as **Morgan
  Linton's** (`@morganlinton`), with `creator`, `credit`, `rights_holder` and
  `source` — and `verify_evidence` **enforces** it: a credited work must name its
  creator on the page a reader sees, not only in a JSON file. 19 checks.

## Conventions honoured

- `verify_claims_slice` and `verify_print_slice` declare `MUTATE_ROLE = "subject"`
  now that they use a temp dir.
- `tahoe-westshore-session.json` is named in `verify_engine_sessions`' unbound
  list rather than appearing silently.
