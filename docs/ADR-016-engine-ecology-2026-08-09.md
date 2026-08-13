# ADR-016: Ecology across the engine family — one faithful model per engine

**Status:** Accepted (2026-08-09) — all four slices landed same day, suite green
(608 core + 70 experimental = 678, 0 failures).
**Date:** 2026-08-09
**Deciders:** Richmond
**Builds on:** ADR-015 (the community-ecology layer: abundance from access, the
generic metric toolkit) and ADR-012's house rules (instruments before mechanisms,
deterministic meters, falsifiable hooks). Extends the ecology program from the
strategy-backed tree to the rest of the engine family.

---

## 1. Context

ADR-015 founded the ecology instruments on the access stream of a single tree. The
ecosystem has three more engines — the ensemble, the path-copying persistent engine,
the B+tree — plus the cache from the E6 transfer experiment. The design question for
each is the one EC-1 taught: **which ecological model is structurally faithful to this
engine?** A model bolted where the structure doesn't carry it produces constants
(EC-1's lesson); a model matched to the engine's real dynamics produces measurements.

## 2. Decision — the model-to-engine map

Four slices in `experimental.ecology`, all additive, all op-clocked/deterministic, all
observing public engine surfaces only (zero core changes):

**E1 — `EnsembleCommunity` (ensemble → metapopulation + community).** The ensemble
literally is a multi-member community. Members are habitat patches; ACTIVE is occupied;
quarantine/retire is local extinction; `healFromPrimary` is recolonization from the
mainland (rescue-effect topology). Caller-sampled state diffs accumulate the event
record; Levins (1969) p* = 1 − e/c (rate ratio from event totals, a documented
simplification) sits next to directly measured occupancy. Community structure: species
= strategy names of active members, so the ADR-015 toolkit applies — Shannon/Pielou
over serving roles, and functional redundancy (mean active copies per role) as the
measured insurance the ensemble buys.

**E2 — `SnapshotLineage` (persistent engine → descent bookkeeping).** Path copying is
the one place the codebase already produces an honest generational record: every O(1)
snapshot is a preserved past. Registered snapshots form the record in generation time;
between generations the instrument reports inherited fraction, gains/losses, Jaccard
divergence between any two retained generations, and mean per-generation turnover (the
uniform-rate drift summary, the null to compare bursts against). Content-based via the
snapshot's public API; bounded retention with absolute numbering.

**E3 — `RangeQuadrats` (whole engine family → quadrat sampling).** The field method
applied literally: a grid of Q equal-width quadrats over the occupied key range, counts
per quadrat from one `inOrder()` pass, then the two classical dispersion statistics —
index of dispersion I = s²/x̄ and Morisita's Iδ — with their textbook readings (≈1
random, <1 regular, >1 clumped). Engine-generic on purpose: one spatial instrument for
strategy-backed, ensemble, persistent, and B+tree alike (generic keys via a position
mapper). Answers "how is the stored data laid out over the key space" — clustered
inserts vs uniform inserts are now a measured distinction.

**E4 — `CacheIsland` (cache → bounded-habitat turnover).** The cache is a bounded
habitat by construction: fixed carrying capacity, `admit` is immigration, eviction is
local extinction. MacArthur–Wilson's signature prediction is directly checkable:
at equilibrium, richness holds flat while composition keeps turning over. The
instrument wraps the cache's public API; evictions (not announced by the cache) are
discovered by non-mutating `peek` sweeps at sample points, so eviction dating resolves
to the sampling cadence — a documented approximation, like a fossil dating to its
stratum. Closed residencies are `LifeTable.Lifespan`s, plugging the eviction record
straight into ADR-015's demography layer.

Supporting change: `CommunityMetrics` and `BetaDiversity` generified from
`Map<Integer, Long>` / `Set<Integer>` to `<T>` — required so strategy names (E1) and
generic keys (E2) flow through the same toolkit. Source-compatible; all ADR-015 tests
unchanged and green.

## 3. Falsifiable hooks (and their verdicts, all 2026-08-09)

- *E1:* quarantine/heal cycles must register as extinction/recolonization with occupancy
  and strategy richness moving in step — **confirmed** (`EnsembleCommunityTest`), including
  the honest negative: state-diff sampling cannot see a cancelled cycle between samples.
- *E2:* the record must be a true past — mutating the engine after capture cannot rewrite
  registered generations — **confirmed**; constant-drift edit sequences reproduce their
  hand-computed turnover (0.4/generation exactly).
- *E3:* clustered vs evenly-spread inserts into a real B+tree must separate on both
  dispersion indices — **confirmed** (clustered I > 1; even spacing I = 0, Iδ < 1); a
  seeded random scatter reads in the Poisson band on both.
- *E4:* a saturated cache under fresh-key pressure must show the equilibrium signature —
  **confirmed**: richness flat at the probation cap across 10 waves while every interval
  shows nonzero turnover; and the protected segment behaves as a refuge (a promoted key
  survives a 20-key probation flood that carries off every probation resident).

## 4. Consequences

**Unlocked:** every engine in the family now has ecological observables matched to its
actual dynamics — the ensemble's health lifecycle is an occupancy record, the persistent
engine's history is a measurable drift rate, any engine's key layout is a dispersion
verdict, and the cache's churn is a turnover-and-residence profile. Cross-layer reuse is
real: E4 feeds E1's demography (`LifeTable`), E1/E2 feed the generified ADR-015 metrics.

**Costs, honest:** all four are caller-driven instruments (nothing records unless wired
— the `WorkloadMonitor` convention); E1's Levins constants are ratio estimates from
event totals, not fitted rates; E4's eviction dating resolves to the sampling cadence;
E2 is content-based lineage, not structural.

**Held, with named triggers:** (a) structural inheritance for E2 — the fraction of
tree *nodes* physically shared between snapshots under path copying — needs core node
exposure; trigger: a question that content-level lineage cannot answer (e.g. pricing
path-copy sharing itself). (b) Leaf-level occupancy for the B+tree — real page-fill
ecology — needs a read-only leaf-counts seam in core; trigger: E3's grid showing a
pattern the engine's own paging plausibly causes, worth confirming at the page level.

## 5. Verification & rollback

All-green gate: `./gradlew build` — 678 tests, 0 failures; 26 new tests across four
suites, hand-oracle throughout (Levins arithmetic, lineage set algebra, both dispersion
indices computed by hand on constructed patterns, cache op-clock lifespans checked to
the exact op). Determinism asserted per instrument. Rollback: the four classes and
their tests delete cleanly; the generification is signature-widening only and stands on
its own.
