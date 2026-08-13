# The CSRBT Ecology Field Guide

*A plain-language guide to the ecology instruments, written for the reader who thinks
in biology first and Java second.*

The idea behind this whole layer is one sentence: **a data structure under a workload
behaves like a habitat under an ecology**, and the same instruments field ecologists
use — diversity indices, quadrat grids, life tables, island counts — measure real,
varying properties of it. Keys are species. How often the workload touches a key is
that species' abundance. Inserts are births, removes are deaths, and time is counted
in operations, not seconds, so every number reproduces exactly.

The fastest way to see everything at once:

```
./gradlew ecologyFieldDay
```

That prints a narrated six-station survey (below) and writes
`docs/ecology-lab-session.json`, which `docs/ecology-lab.html` turns into charts —
open it in any browser.

---

## Station 1 — The meadow (diversity)

**Instruments:** `EcologyRecorder` + `CommunityMetrics` · **Concept:** species
diversity and evenness (Shannon 1948, Pielou 1966, Simpson 1949, Hill 1973).

Attach a recorder to your tree's operations and it keeps a tally of how often each key
is touched — the abundance distribution. From it:

```java
EcologyRecorder rec = new EcologyRecorder();      // WorkloadMonitor — feed it your ops
rec.recordSearch(key, depth);                      // ... per operation
Map<Integer, Long> abundance = rec.cumulativeAbundance();

CommunityMetrics.shannon(abundance);               // H' — diversity
CommunityMetrics.pielouEvenness(abundance);        // J' — 1.0 = perfectly even
CommunityMetrics.hillNumber(abundance, 1);         // effective species count
CommunityMetrics.bestFit(abundance);               // which rank-abundance model fits
```

**How to read it.** J′ near 1 means traffic is spread evenly ("even grazing"); J′ near
0 means a few hot keys take almost everything (a dominated community). The Hill number
is the friendliest single figure: "100 keys present, but the community behaves like
about 11 equally-common ones" is a hot-key workload in one sentence. `bestFit`
compares your rank–abundance curve against the geometric series (niche preemption),
MacArthur's broken stick, and a flat line.

## Station 2 — The census (life tables and growth)

**Instruments:** `LifeTable` + `LogisticGrowth` · **Concept:** survivorship curves
(Deevey 1947) and logistic population growth (Verhulst 1838).

The recorder also remembers when each key was born (inserted) and died (removed).
Those lifespans build a cohort life table, and the population-size series fits a
logistic growth curve:

```java
LifeTable t = LifeTable.fromLifespans(rec.lifespans(), 6);
t.survivorshipType();                              // TYPE_I, TYPE_II, or TYPE_III
LogisticGrowth.Fit fit = LogisticGrowth.fit(rec.populationSeries());
fit.r();                                           // intrinsic growth rate, per op
fit.carryingCapacity();                            // K
```

**How to read it.** Type I: keys survive long and die together (a batch purge). Type
II: constant turnover risk at every age (songbird-style). Type III: most keys die
almost immediately, survivors persist (oyster-style — think a cache admitting
everything and evicting fast). The growth fit says how fast the structure filled and
what ceiling it approached. Fit the *colonization phase* — the model describes growth
toward K, and plateau noise will otherwise swamp it (the demo shows this practice).

## Station 3 — The archipelago (metapopulation)

**Instrument:** `EnsembleCommunity` · **Concept:** Levins metapopulation dynamics
(1969) — patches, local extinction, recolonization.

The ensemble's members are habitat patches. Quarantine is a local extinction; healing
from the primary is recolonization from the mainland:

```java
EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(ensemble);
eco.sample();                                      // survey the patches, on your cadence
eco.occupancy();                                   // fraction of patches occupied — measured
eco.levinsEquilibrium();                           // p* = 1 − e/c — the model's prediction
eco.strategyDiversity();                           // Shannon over serving strategies
```

**How to read it.** The interesting number is the *disagreement*: the model predicts
occupancy from the event record, and you also measure occupancy directly. When they
differ, either the record is sparse or transitions are happening between surveys —
exactly the conversation a field course wants to have about sampling design. (One
honest limit, pinned by a test: a patch that dies and recovers entirely between two
surveys is invisible. Survey often.)

## Station 4 — The fossil record (descent)

**Instrument:** `SnapshotLineage` · **Concept:** descent with modification, read from
strata.

The persistent engine's snapshots are preserved past states — register each one as a
generation and the record cannot be rewritten by later edits:

```java
SnapshotLineage<Integer> lineage = new SnapshotLineage<>();
lineage.capture(engine);                           // one stratum per capture
lineage.inheritedFraction(g);                      // share of gen g's keys still in g+1
lineage.turnoverPerGeneration();                   // mean composition change per stratum
```

**How to read it.** Inherited fraction near 1 is a stable community; turnover of 0.33
means a third of the community is replaced each generation. Comparing any two strata
gives divergence — how far apart two moments in the structure's history are.

Since ADR-017 the record also carries **physical heredity**: `structuralInheritance(g)`
counts the parent's *nodes* (by identity) that survive into the child, not just its
keys. The gap between the two is the price of path copying — in the demo, 80% of keys
survive a generation but only 57% of physical nodes. A key can be inherited while its
node is rewritten; never the reverse.

## Station 5 — The survey grid (spatial pattern)

**Instrument:** `RangeQuadrats` · **Concept:** quadrat sampling and dispersion — the
literal field method (Morisita 1959).

Lay a grid of equal-width quadrats over the key range of *any* engine and count
individuals per cell:

```java
long[] counts = RangeQuadrats.countsOfInts(engine.inOrder(), 20);
RangeQuadrats.indexOfDispersion(counts);           // variance/mean: ≈1 random, <1 regular, >1 clumped
RangeQuadrats.morisita(counts);                    // same reading, robust to N
```

**How to read it.** Exactly like a field notebook: clumped means your keys arrive in
patches (clustered inserts — timestamps, sequential IDs); regular means deliberate
even spacing; random means no detectable pattern. Works identically over the plain
tree, the ensemble, the persistent engine, and the B+tree — and for the B+tree,
`leafKeyCounts()` (ADR-017) adds the engine's *own* pages as quadrats: leaf-by-leaf
fill with a graded reading (healthy ≈ the ln 2 ≈ 69% random-insertion steady state;
the demo's sequential loading reads 51% — "a split-heavy history left slack").

## Station 6 — The island (turnover at capacity)

**Instrument:** `CacheIsland` · **Concept:** island biogeography (MacArthur & Wilson
1967) — immigration, extinction, and equilibrium turnover on a bounded habitat.

The cache is an island with fixed area. Admissions are immigrations; evictions are
extinctions:

```java
CacheIsland isle = new CacheIsland(cache, capacity);
isle.admit(key);  isle.get(key);                   // route traffic through the island
isle.sample();                                     // sweep for departures, on your cadence
isle.richness();  isle.saturation();               // residents, fullness
isle.lastIntervalTurnover();                       // (immigrations + extinctions) / 2
isle.residenceLifeTable(4);                        // how long residents last → Station 2
```

**How to read it.** The textbook signature — and the demo shows it live — is richness
holding perfectly flat at capacity while composition churns underneath: the island is
"full" yet never the same island twice. Residence lifespans feed straight back into
the life-table instrument, so a cache's eviction policy gets a survivorship curve.

---

## Reading the numbers without memorizing them

`FieldReport` turns every index into the sentence a TA would say, using fixed,
documented thresholds (each one a public constant, each band pinned by a test):

```java
FieldReport.evennessReading(0.52);
// "uneven — a few hot keys carry most of the traffic"
FieldReport.dispersionReading(22.2);
// "clumped — individuals bunched into patches"
FieldReport.survivorshipReading(TYPE_III);
// "heavy early mortality, but survivors persist (think oysters...)"
```

The section builders (`communitySection`, `demographySection`, `spatialSection`,
`metapopulationSection`, `lineageSection`, `islandSection`) assemble whole narrated
blocks — that is what `ecologyFieldDay` prints.

## Design your own experiment (ADR-019)

You do not need to write Java to run an experiment. Write a plain-text `.eco`
protocol — phases, an abiotic environment, theory models, crosses, and hypotheses you
commit to **before** the run — and the engine runs it, grades it, and exports it:

```
name: my pond study
keys: 100
seed: 7
window: 250

phase: spring uniform 2000          # even traffic
phase: bloom  hot 2000 5 90         # 5 keys carry 90% of it
phase: fall   churn 1500 55         # turnover: births and deaths

factor: area 0.5                    # a small pond...
factor: wind 1.3                    # ...with helpful wind
factor: distance 0.8                # ...somewhat far from the mainland

model: logistic 0.15 120 5 60       # r, K, N0, steps (K is scaled by area)
model: island 0.4 0.1 100 0 40      # c, e, pool, S0, steps (c and e feel the wind/area)
model: hardyweinberg 298 489 213    # your genotype census: AA, Aa, aa
cross: Rr x Rr observed 5474 1850   # Mendel's own 1866 seed-shape counts

expect: evenness(spring) > 0.9      # written before the run — the engine grades it
expect: brayCurtis(spring, bloom) > 0.5
```

Your **own observations** ride along (ADR-020) — entered data, notebook entries,
phylogenies, and the bean lab:

```
data: pondA cattail=18 duckweed=44 frogbit=3    # your field counts
data: coop  peck peck flap peck strut           # bare names tally, like clipboard marks
note: sampled after two dry weeks               # the field notebook
note(bloom): five keys took nearly all traffic  # a note pinned to a phase
tree: pondlife (Porifera,(Cnidaria,(Mollusca,Chordata)));   # Newick, drawn + counted
model: markrecapture 120 90 30                  # marked, caught, recaptured

expect: jaccard(pondA, pondB) <= 0.5            # datasets grade exactly like phases
expect: evenness(bloom) is uneven               # hypotheses in words — same bands
expect: survivorship is type3                   #   as the narrated report
```

Entered datasets are narrated by the same instruments as the simulated phases and
compared pairwise (Jaccard, Sørensen, Bray–Curtis). Qualitative `is`-hypotheses
grade against the exact `FieldReport` thresholds — one source of truth — and a
hypothesis that can't be graded honestly (a phase compared to a dataset; a
survivorship claim with no census) is stamped UNGRADEABLE rather than guessed.

Run it with `./gradlew ecologyExperiment -Pspec=path/to/your.eco`. The report prints
each phase's narrated readings, the theory bench, the Punnett squares with their χ²
verdicts, and each hypothesis stamped ✅ CONFIRMED, ❌ REFUTED, or ⚠ UNGRADEABLE.
The run also writes `docs/ecology-experiment-session.json` (drop it onto
`docs/ecology-lab.html` to see it drawn) and a full bundle in `docs/experiment-out/`:
CSVs that open directly in Excel/Sheets/R and a print-friendly `report.html` for
handing in or pasting into slides. A malformed line is reported as a problem, never
guessed at — the run continues with what parsed, and tells you exactly what it
skipped. `docs/sample-experiment.eco` is a complete worked example (with one
deliberately wrong hypothesis, so you can see what REFUTED looks like).

No build at all? The lab page's **Workbench** section runs in any browser: paste
field counts (spreadsheet paste and tally marks both work), quadrat data, or a
genotype census; compare two sites; run the mark–recapture calculator; walk or
build a **dichotomous key**; paste any Newick tree and see the cladogram; build
Punnett squares from presets (Mendel's peas, the blue Andalusian, chicken combs);
turn the abiotic knobs on the theory bench; and drill for lab practicals with the
seeded flashcard trainer (skeleton, model-organism binomials, animal phyla, or your
own study list). When you're done, the **transfer box** rewrites everything you
typed as ready-to-paste `.eco` lines — type once in a browser, store it as a
protocol, re-run and export it forever. Same equations, same conventions, checked
against the Java oracles.

## The honesty rules (why you can cite these numbers)

Everything in this layer follows the house discipline: the clock is the operation
index, never wall time; every random stream is seeded, so every number — and every
sentence — reproduces byte-for-byte; every index was tested against hand-computed
oracles; and where an instrument *cannot* see something (a patch dying and recovering
between surveys; an eviction dated only to the sweep that discovered it), the
limitation is documented and pinned by a test rather than papered over. These instruments have
already done research-grade work: the early-warning experiment proved lag-0 shift
detection with zero false positives, and ADR-018 rode that detector to the
**amortization frontier** — regime blocks must last ≈128k ops before detection-triggered
strategy switching beats the best fixed choice. The whole story, told for reading
rather than reference, is `docs/ESSAY-the-ecology-of-a-tree.md`; the provenance trail
is ADR-015 through ADR-018 and the 2026-08-09 audits and changelogs.
