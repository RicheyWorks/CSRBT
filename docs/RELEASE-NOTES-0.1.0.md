# CSRBT 0.1.0 — first release

The first versioned release of CSRBT: a Java 17 ordered-set engine with pluggable,
runtime-morphing balancing strategies — and the research program that grew around it,
negative results included.

## Coordinates

```kotlin
// not yet on Maven Central (signing/portal setup pending); until then:
// clone + ./gradlew publishToMavenLocal
dependencies {
    implementation("io.github.richeyworks:csrbt-core:0.1.0")
}
```

Packages live under `io.github.richeyworks.csrbt.*` (relocated from `core.*` for this
release — ADR-013 §3). Only `csrbt-core` is published; `csrbt-experimental` (arena,
ecology, cache evolution) and `csrbt-benchmarks` (JMH) build from source.

## What's in 0.1.0

**The library.** `OrderedSet<K>` over any `Comparable`/`Comparator` key, backed by
interchangeable strategies (Red-Black, AVL, Splay, Hybrid, and the parameterized
WeightBalanced(Δ, Γ)) with health-gated runtime morphing — a failed validation keeps the
incumbent, never loses data. O(log n) order statistics, undo/redo, text-snapshot
persistence, sliding-window eviction, one-writer/many-readers concurrency with
torn-read-free optimistic reads. The multi-tree ensemble makes adaptation an O(1)
primary swap with instant failover and quorum-verified reads; the engine family adds a
persistent path-copying engine (O(1) snapshots) and a B+tree for large n. A
`NavigableSet` adapter makes it a drop-in for `TreeSet` call sites. Adaptation is
observable end to end: structured events, JSON export, a session recorder, and a
zero-dependency replay visualizer.

**The control plane.** Morphs are decided, not requested: a workload monitor, cost-model
scorer, and anti-thrash policy run at the caller's cadence, every decision explainable
from one log line.

**The research record.** ADR-011/012 closed honestly: searched policies do not beat the
fixed four on stationary workloads (V5, deterministic); the calibrated selector ties the
best fixed choice without hindsight; chasing regime blocks is uneconomical at realistic
granularity; and the evolve-under-viability pattern transferred to a second policy space
(cache eviction) with the gate killing the lethal genome on the record.

**Quality.** 583 tests (JUnit 5 + jqwik properties), green on a JDK 17/21 CI matrix.
JMH baselines for the four strategies (insert/lookup, n=1e5) with results in
`docs/CHANGELOG-2026-06-11-adr013-gradle-migration.md`.

## Compatibility notes

- Requires Java 17+ at runtime; build needs JDK 17+ (Gradle 9).
- `.rbt` snapshot files from earlier development builds load unchanged (the text format
  carries no class names).
- Anyone tracking pre-release sources: every `core.*`/`experimental.*` import becomes
  `io.github.richeyworks.csrbt.*` / `io.github.richeyworks.csrbt.experimental.*`.

## Held for later (named triggers)

Maven Central publication (signing + portal credentials), paged file backing for the
B+tree (ADR-008 D2), evolution-loop extraction (third policy space), JUnit 6.x (jqwik
Platform-6 support).
