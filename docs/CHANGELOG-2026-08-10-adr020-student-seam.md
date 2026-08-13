# Changelog — 2026-08-10 — ADR-020: the student seam

Data entry and transfer, qualitative tools beside the quantitative ones, and the
rest of the university lab bench: mark–recapture, phylogenies, dichotomous keys,
and a practical trainer. Full suite 767 green (752 prior + 15 new).

## New — `csrbt-experimental` ecology package

- **`FieldData`** — the data bus: token form (`name[=count]`, bare names tally like
  clipboard marks — ethogram-ready) and table form (CSV/TSV/space/bare-name lines,
  spreadsheet paste). Problems reported, never guessed; `toEcoLine`/`toCsv`
  round-trip (pinned).
- **`MarkRecapture`** — Lincoln–Petersen and Chapman estimators with Chapman's
  variance and 95% CI; R=0 handled honestly (LP undefined, Chapman fine). Hand
  oracles: 100/60/15 → 400 and 384.0625 exactly.
- **`PhyloTree`** — Newick parser (names, internal labels, branch lengths),
  leaves/depth, ASCII cladogram, JSON, round-trip serializer. Malformed input
  throws with a reason.

## Changed — the experiment engine

- **`ExperimentSpec`**: new directives `data:` (entered datasets; duplicate and
  phase-colliding names flagged), `note:` / `note(target):` (field notebook;
  unknown targets flagged), `tree:` (label + Newick), `model: markrecapture M C R`.
  New numeric metrics `jaccard`/`sorensen`. New **qualitative hypotheses**
  `expect: metric(args) is word` — evenness/turnover/overlap/fit/survivorship,
  words validated at parse time against the report's bands.
- **`ExperimentLab`**: entered datasets narrated with the same instruments as
  phases + pairwise incidence comparisons; FIELD NOTEBOOK and TREE THINKING report
  sections; mark–recapture on the theory bench; grading unified over phases and
  datasets (phase-vs-dataset comparisons honestly UNGRADEABLE, survivorship without
  a census UNGRADEABLE); UNGRADEABLE verdicts now exported too. New exports:
  `data.csv`, `notes.csv`, `trees.csv`. New session JSON: `entered`, `notes`,
  `trees`, markrecapture stats.
- `docs/sample-experiment.eco` — two pond surveys + an ethogram tally, three
  notebook entries, an animal-phyla phylogeny, the bean lab, and three new
  hypotheses (numeric-on-data, qualitative band, survivorship) — 6 ✅, 1 ❌ (the
  deliberate one).

## Changed — `docs/ecology-lab.html`

- Session cards: 📓 Entered Data (labeled bar charts + tiles), 📔 Field Notebook,
  🌳 Tree Thinking (SVG cladograms from a JS Newick mirror), mark–recapture tiles
  on the theory bench, word verdicts on the hypotheses card.
- Workbench: spreadsheet-paste + tally entry; compare-two-sites station
  (Jaccard/Sørensen/Bray–Curtis, shared kinds); mark–recapture calculator;
  interactive **dichotomous key** (chicken-comb default, build-your-own couplets);
  Newick cladogram drawer; **practical trainer** (seeded flashcards — skeleton,
  model-organism binomials, animal phyla, custom lists; missed cards recycle);
  **transfer box** that rewrites all Workbench entries as ready-to-paste `.eco`
  lines with suggested hypotheses. Zero-JS-error render checks on every station.
- Footer provenance now runs ADR-015 through ADR-020.

## Tests (15 new, all hand-oracle)

- `FieldDataTest` (13) — both entry forms, tally semantics, problem reporting,
  eco-line and CSV round-trips; mark–recapture oracles incl. R=0 and contracts;
  Newick parse/round-trip/ASCII/contracts.
- `ExperimentLabTest` (2 new + extended) — spec parsing of all new directives,
  12-problem bad-spec case, qualitative verdict with band word in report and JSON,
  phase-vs-dataset UNGRADEABLE, survivorship-without-census UNGRADEABLE, entered
  data/notes/trees in report and exports, mark–recapture through the bench,
  export bundle now 11 files.
