# CHANGELOG — 2026-06-11 — ADR-013: Gradle migration (G1+G2 fired)

ADR-009 held G1 (Gradle/JMH/coverage/javadoc) behind "published artifact with external
consumers." The repo went public under MIT and the decision is to ship as a library —
the trigger fired deliberately. ADR-013 converts G1 and G2 in one move.

## What changed

**Build:** Ant → Gradle 9.5.1 (Kotlin DSL, version catalog, Java 17 toolchain). Clean
cutover: `build.xml` and the vendored jars (`junit-platform-console-standalone-1.9.2`,
`junit`, `log4j-api/core-2.17.1`) are gone; dependencies now resolve from Maven Central
and are pinned in `gradle/libs.versions.toml`. log4j 2.17.1 → 2.26.0; JUnit console-jar
1.9.2 → Jupiter 5.14.4 (deliberately not 6.x: jqwik 1.9.3 targets Platform 1.x).

**Modules** (the documented dependency direction, now enforced by the build):

- `csrbt-core` — the library (packages `core.*`), publishable; jacoco + javadoc + sources
  jars + POM metadata wired, signing/Central held to the first release dry-run.
- `csrbt-experimental` — `experimental.*` plus its three tests
  (`CacheTransferExperimentTest`, `ViabilityMapTest`, `TreeContextTesterAdditions`);
  not published.
- `csrbt-benchmarks` — JMH 1.37 via `me.champeau.jmh`; seeded with
  `OrderedSetStrategyBenchmark` (four fixed strategies, shuffled insert + uniform lookup —
  the E5/V5 shapes with forking and statistics). The in-suite printed rows stay until this
  rig reproduces their ordering.

**G2 down payment:** `OrderedSetPropertyTest` (csrbt-core) — the oracle-churn pattern as a
jqwik property across all four strategies, with shrinking.

**Resources:** `log4j2.xml` + `junit-platform.properties` moved from main resources to
*test* resources (duplicated into both tested modules) — the published jar deliberately
ships no logging config.

**CI:** `.github/workflows/ci.yml` now runs `gradle build` (pinned 9.5.1 via setup-gradle,
so green even before the wrapper jar is committed); keeps G0's JDK 17/21 matrix.

**Docs:** CLAUDE.md build section rewritten; README layout/build sections updated.

## Found en route

`TreeContextTesterAdditions.java` declared `package core;` while living in
`src/test/java/test/core/` — Ant's flat fileset compiled it anyway. Relocated to
`csrbt-experimental/src/test/java/core/` to match its declaration.

## Verification

Static checks green in the agent sandbox (package/dir alignment across all 127 sources,
TOML/YAML parse, no stale build references, API usage of new files checked against
source). **`./gradlew build` green host-side 2026-06-11: 583 tests, 0 failures, 0 skipped**
(csrbt-core 577 — includes the new jqwik properties — csrbt-experimental 6) on a JDK 21
host compiling `--release 17`.

Found during the host run and fixed: (1) version-catalog accessors don't resolve inside
the `jmh {}` extension block (hoisted, with `asProvider()` since "jmh"/"jmh-plugin" nest);
(2) the Java-17 toolchain *pin* was dropped for `options.release = 17` — the pin demands
toolchain auto-provisioning on any host whose default JDK is newer, for zero benefit over
the release flag the Ant build already used.

`:csrbt-benchmarks:jmh` exercised same day (10m48s, JDK 21 host): the rig reproduces the
in-suite ordering — insertShuffled n=1e5: RB 37.6ms, AVL 41.4ms, WB(3) 44.4ms, Splay
118.3ms; lookupUniform: WB(3) 16.3ms, RB 16.6ms, AVL 17.1ms, Splay 21.1ms — V5's
steady-state verdict, now with confidence intervals. The benchmark forks log
"Log4j API could not find a logging provider" once each: deliberate — benchmarks ship no
logging backend, so per-op logging is a no-op rather than a cost.

Remaining honest debt: javadoc emits 9 warnings (bare `<` in prose comments, one dangling
`@link`) — cosmetic, fix when curating the public API docs.
