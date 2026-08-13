# ADR-020: The student seam — data in, qualitative tools, the whole lab bench

**Status:** Accepted (2026-08-10) — landed and green
(`FieldDataTest` + extended `ExperimentLabTest`: 15 new tests, all hand-oracle;
full suite 767 green).
**Date:** 2026-08-10
**Deciders:** Richmond
**Builds on:** ADR-019 (the classroom seam). ADR-019 made experiments pluggable;
this ADR makes them **complete**: real field data flows in and back out, qualitative
tools stand beside the quantitative ones, and the lab covers the exercises an
honors/graduate program actually runs — mark–recapture, tree thinking, keys, and
practical drills — down to the elementary classroom.

---

## 1. The requirements, as stated

- Quantitative **and qualitative** tools available to all students.
- Easy data **entry and transfer**, so an analysis can be run, reused, stored, and
  exported — for classroom and research use.
- Coverage of the experiments university programs run (the intro-bio canon:
  mark–recapture "bean labs", quadrats, life tables, taxonomic keys, phylogenetic
  tree-thinking exercises), plus **bone practicals** and **species-name /
  phylogeny learning** for graduate coursework.

## 2. The decision — six additions, one discipline

### 2.1 The data bus (`FieldData`, the `data:` directive)

One tiny, forgiving entry format with two faces and one result (a name → count
table): token form for protocol files ({@code data: pondA cattail=18 duckweed=44
frogbit}) and table form for spreadsheet paste ({@code name,count} / tab /
space / bare name). Two deliberate classroom touches: a **bare name counts one
sighting and repeats add** — so `peck peck flap peck` is an ethogram tally exactly
as kept on a clipboard — and every malformed token is **reported, never guessed**.
`toEcoLine`/`toCsv` are the inverses, so data round-trips (pinned byte-for-byte).

**Entered datasets are first-class communities.** The runner narrates each one with
the same `FieldReport` instruments the simulated phases get, compares consecutive
datasets (Jaccard, Sørensen, Bray–Curtis, shared-kinds count), exports `data.csv`,
and renders a lab-page card. Hypotheses address datasets by name exactly like
phases — and comparing a simulated phase to an entered dataset is **UNGRADEABLE**,
because the numbers share no species and a grade would be a lie.

### 2.2 The field notebook (`note:` directives)

Qualitative observations travel with the run: `note: <text>` (general) or
`note(bloom): <text>` (attached; unknown targets are spec problems). Notes appear
in the narrated report, the session JSON, `notes.csv`, and a lab-page card. The
principle: numbers say how much, the notebook says what it was like out there —
and both are part of the record.

### 2.3 Qualitative hypotheses (`expect: ... is <word>`)

Pre-registration now works in words, graded against the **same fixed thresholds
the narrated report uses** (`FieldReport`'s public constants — one source of truth):
`evenness(p) is very-even|moderate|uneven|dominated`, `turnover(p,q) is
low|moderate|major`, `overlap(p,q) is high|partial|little`, `fit(p) is
geometric|brokenstick|uniform`, and `survivorship is type1|type2|type3` (reads the
run's census; UNGRADEABLE without one). An unknown band word is a parse-time spec
problem, not a runtime surprise. Numeric grading also gained incidence metrics:
`jaccard(a,b)` and `sorensen(a,b)`.

### 2.4 Mark–recapture (`MarkRecapture`, `model: markrecapture M C R`)

The canonical first field experiment. Lincoln–Petersen (undefined at R=0, and the
code says so instead of printing ∞) and Chapman's small-sample correction with its
standard variance and 95% interval. Hand oracles: M=100, C=60, R=15 → N̂=400
exactly; Chapman 384.0625 exactly. The report states the assumptions (closed
population, no lost marks, equal catchability) because graders look for them.

### 2.5 Tree thinking (`PhyloTree`, `tree:` directive)

A Newick parser — the format every phylogenetics course and paper uses, so trees
**transfer** from any handout — with leaves/depth walks, an ASCII cladogram for the
narrated report, JSON for the lab page's SVG cladogram, and a round-trip
serializer (pinned). Malformed Newick throws with a reason. The materials say
plainly what the repo's two senses of "tree" share and don't: a CSRBT orders keys;
a phylogeny is a hypothesis of descent — same picture, different meaning.

### 2.6 The front end — every station, no build required

The lab page's Workbench grew to cover the full bench, all offline in a browser:

- **Entry everywhere**: the field-data box now takes spreadsheet paste
  (`name,count`, tabs) and bare-name tallies, mirroring `FieldData`.
- **Compare two sites** — Jaccard/Sørensen/Bray–Curtis with shared-species readout.
- **Mark–recapture calculator** — both estimators + CI, live.
- **Dichotomous key** — the classic ID tool as an interactive yes/no walker; the
  default key identifies the four chicken combs, and the couplet format
  (`question | yes | no`) means students build their own keys in the box.
- **Tree thinking** — paste any Newick, get a drawn cladogram (animal-phyla
  default).
- **Practical trainer** — seeded-shuffle flashcards for lab practicals: skeleton
  (bone practical), model-organism binomials, and the animal phyla as presets, plus
  paste-your-own `prompt = answer` study lists (specimen stations, muscle origins,
  anything); missed cards recycle; drills reproduce by seed.
- **Transfer box** — one click rewrites everything typed into the Workbench as
  ready-to-paste `.eco` lines (data, models, crosses, factors, tree, suggested
  hypotheses marked *edit before you run*). That is the store/reuse/export story:
  the Workbench is where data is born, the `.eco` file is where it lives, and the
  export bundle (CSV/JSON/HTML) is how it leaves.

New session cards render `entered`, `notes`, and `trees`; the theory-bench card
renders mark–recapture; the hypotheses card shows word verdicts. All render checks
pass with zero JS errors.

## 3. Grounding

The exercise set matches what intro/honors sequences actually run — mark–recapture
labs, dichotomous keys with phylogenetic trees, skeleton-based practicals, and
"march through the animal phyla" tree-thinking exercises are standard fixtures of
university biology lab courses (e.g. the Berkeley evolution lab-activity
collection, York/OSU intro-bio lab manuals, and the SERC "Skeleton Keys" module).
Flashcard content ships only textbook-level facts (major bones, model-organism
binomials, phylum common-name pairs); everything else is paste-your-own.

## 4. Consequences

- The full student arc is now covered in one deterministic pipeline: observe
  (data:/notes) → hypothesize (expect:, words or numbers, pre-registered) → run →
  grade (✅/❌/⚠, honestly) → export (Excel/CSV, printable HTML, session JSON) →
  drill (practical trainer) — from elementary tallies to thesis-grade protocols.
- Grammar stayed small: five new directives/metric families, every one following
  the house rules (problems reported, bands shared with the narrator, byte
  determinism).
- **Held:** linked-loci genetics, stochastic models, native xlsx/pptx (ADR-019's
  trigger stands); a Workbench "import .eco" reverse path (the forward path —
  Workbench → protocol — is the one classrooms need first).
