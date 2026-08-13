# CSRBT 0.2.0 — the ecology program, the hardening day, and a second artifact

The second versioned release: the ecology research program built on top of the engine
(ADR-015 through ADR-020), a day of adversarial auditing that produced 26
probe-verified fixes and two ADRs (2026-08-12), and `csrbt-experimental` joining
`csrbt-core` as a published artifact — its publication trigger fired when Brine
became the first external consumer (2026-07-18, ADR-013 §4).

## Coordinates

```kotlin
// not yet on Maven Central (signing/portal upload is the release step); until then:
// clone + ./gradlew publishToMavenLocal
dependencies {
    implementation("io.github.richeyworks:csrbt-core:0.2.0")
    implementation("io.github.richeyworks:csrbt-experimental:0.2.0")   // arena, ecology, cache evolution
}
```

Both artifacts ship jar + sources + javadoc with full POMs; `csrbt-benchmarks` (JMH)
stays build-from-source.

## What's new in 0.2.0

**The ecology layer (ADR-015–020).** A community-ecology instrument stack over the
engine's own event stream — abundance/diversity (Shannon, Simpson, Hill, Chao1,
rarefaction), beta diversity and drift, life tables and survivorship, logistic
growth, metapopulation and island models per engine (ensemble, persistent-snapshot
lineage, B+tree occupancy, cache island) — then the classroom on top of it: `.eco`
protocol files with pre-registered, graded hypotheses (numeric and qualitative),
Punnett squares and Hardy–Weinberg, mark–recapture, Newick phylogenies, a field-data
bus, CSV/HTML/print exports, and the interactive lab page (`docs/ecology-lab.html`).
The ADR-017 heredity seams are the program's first core changes: snapshot
node-sharing (`Snapshot.sharedNodeCount`) and B+tree leaf occupancy. ADR-018's
amortization-frontier experiment gave ADR-012's re-arming trigger #1 its number
(B* ≈ 128k-op regime blocks).

**New core API (ADR-021).** `OrderedSet` gains native navigation —
`floor`/`lower`/`ceiling`/`higher`, `countUpTo`, `countBetween` — each answered in
ONE guarded acquisition, atomic under the R1 concurrent-read model. The
`NavigableSet` adapter is rebased on them, closing a real race: its old
count-then-select composition could throw or answer wrong (`floor(k) > k`) under a
concurrent writer. Also new: `OrderedSet.peekOldest()` (the window's next eviction
victim), and `HybridStrategy` now carries its own `samePolicyAs` and
depth-tolerant `validateInvariant`.

**The hardening day (2026-08-12).** Five adversarial audit passes over every
subsystem — ecology, persistence, the public API surface, strategies and control
plane, the ensemble, the evolution machine — with the house discipline throughout:
26 fixes, every one probe-verified (shown failing before the fix counted). The
headlines: the ensemble now masks a divergent member whose queries THROW (and its
health check can no longer heal the honest majority from a content-divergent
primary); persistence refuses truncated snapshots, saves atomically, and
round-trips control-character keys and WeightBalanced snapshots; the health gate's
BST check is range-bounded (a globally-invalid tree can no longer be certified
healthy); dead genomes stay dead in the (μ+λ) selection; three blinded metrics came
back to life (entropy, fragmentation, and the rotation meter feeding stress); the
session recorder emits valid, byte-reproducible JSON. Full accounting in the five
audit docs and changelogs dated 2026-08-12.

**The battle runner benchmarks what it claims (ADR-022).** Searches run through each
strategy's own path (so Splay actually splays), `avgSearchDepth` is the realized
per-search mean rather than the root height, timing is warmed median-of-3, and the
score no longer double-charges self-adjustment (rotations are work the wall time
already prices). With all of it in place the tournament finally agrees with its own
workload design: Splay wins the locality workloads on realized depth, the strict
balancers win uniform/sequential/delete.

**July seams.** The workload-signal seam and ensemble window depth
(CHANGELOG-2026-07-07/08), generic interval endpoints (2026-07-14), scorer
recalibration (2026-07-14), and the 2026-07-08 hardening pass's snapshot gates.

## Compatibility notes

- **Session format**: `Lineage` events now carry the breeding operator as
  `"breedOp"` — previously a second `"op"` key that last-wins JSON parsers resolved
  to the operator string, destroying the op counter. Consumers reading the old
  duplicate key should switch to `breedOp`. Recorded sessions are now
  byte-reproducible (embedded meters are zeroed); the canonical
  `docs/arena-session.json` / `docs/arena-search-session.json` are regenerated.
- **Persistence**: a snapshot whose parsed size disagrees with its header is now
  REFUSED (previously loaded as a smaller, wrong tree); saves are atomic (a failed
  save leaves the previous file intact). Existing well-formed `.rbt` files load
  unchanged. WeightBalanced snapshots, previously unloadable, now round-trip.
- **`TreeContext.getRotationCount()`** now reports the engine's live rotation meter
  (it was a dead field, always 0). The count resets when a morph rebuilds the
  engine; per-window deltas self-heal. `incrementRotations()` is deprecated.
- **Tournament results re-score** under ADR-022 — historical rankings from the old
  runner do not carry over.
- **Undo with a sliding window** now restores a window-evicted key; a redo
  re-executes the add and may evict a different key (the record refreshes so the
  next undo stays exact).
- `EcologyRecorder`'s bounds are documented honestly: `lifespans` grows with deaths
  and `populationSeries` with closed windows — drain or reconstruct in long-running
  deployments.

## Quality

806 tests (JUnit 5 + jqwik), green on the JDK 17/21 CI matrix; every 2026-08-12 fix
carries a probe test that failed against the unfixed code. Staging publication
verified end to end for both artifacts (jar/sources/javadoc/POM + checksums).

## Held for later (named triggers)

Maven Central upload (signing + portal — the release step this note precedes);
paged file backing for the B+tree (ADR-008 D2); the comparator-vs-equals window
seam (D-4 — fires when a custom-comparator key type arrives); JUnit 6.x (jqwik
Platform-6 support); a third evolve-under-viability policy space.
