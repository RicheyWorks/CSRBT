# ADR-013: Build modernization — Gradle migration, module split, benchmark rig

**Status:** Accepted (2026-06-11 — `./gradlew build` green host-side: 583 tests, 0 failures;
see CHANGELOG-2026-06-11-adr013-gradle-migration.md)
**Date:** 2026-06-11
**Deciders:** Richmond
**Builds on:** ADR-009 G1/G2 (held with trigger: "published artifact with external
consumers"). The trigger fired deliberately: the repo went public under MIT and the
decision is to ship as a library. This ADR converts both held items in one move.

---

## 1. Context

The build is a single `build.xml` driving `javac --release 17` and the JUnit Platform
console-standalone jar, with log4j and JUnit jars vendored in the repo root (gitignored,
supplied locally). ADR-009 priced this correctly for a private research codebase: ~16 s
suite, zero plugin surface, nothing to maintain. It priced the migration as zero-feature
churn *until* the project became a published artifact — and that is now the stated goal.

What Ant cannot give us at acceptable cost, and a published library needs:

- **A real benchmark rig.** The in-suite printed rows (E5, V5) kept us honest internally,
  but they run inside JUnit with no forking, no warmup discipline, no statistical output.
  Publishable numbers need JMH.
- **Dependency management.** "Download these jars into the repo root" is not an
  instruction you give external contributors.
- **Publishing machinery.** POM metadata, sources/javadoc jars, signing, Maven Central
  staging — all plugin territory.
- **Coverage and a javadoc site** — the badges and docs a consumer checks before adopting.
- **jqwik (G2)** rides in free once real dependency management exists, as ADR-009
  predicted.

Constraints carried forward: Java 17 (`release=17` stays), JUnit 5 suite as-is (57 test
classes), deterministic tests, no behavior change to the library, and the house rule that
the suite stays fast enough to run on every change.

## 2. Options considered

### Option A: Gradle (Kotlin DSL, version catalog)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — wrapper, settings, catalog, per-module build files |
| JMH support | First-class (`me.champeau.jmh`), dedicated source set, fork/warmup config in-build |
| Multi-module | Natural; convention plugins if it grows |
| Publishing | `maven-publish` + `signing`; Central via the standard portal flow |
| Agent-friendliness | Good once wrapper exists; one command (`./gradlew build`) |

**Pros:** the standard layout for library + benchmark projects; JMH plugin maturity;
toolchains decouple the build JVM from the target JVM; version catalog gives one file to
audit dependencies. **Cons:** the largest plugin surface of the options; Gradle major
versions break plugins on a ~2-year cadence; build scripts are code and can rot.

### Option B: Maven

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low-medium — POMs are declarative and boring |
| JMH support | Second-class — exec/shade workarounds, benchmarks as a separate app |
| Multi-module | Supported, more ceremony |
| Publishing | Mature (it is Maven Central, after all) |
| Agent-friendliness | Good; `mvn verify` |

**Pros:** smallest conceptual surface, slowest-moving target, declarative. **Cons:** the
benchmark rig — the single biggest feature this migration buys — is exactly where Maven
is weakest. JMH's own archetype generates a standalone app you run by hand; integrating
it as a module means shade-plugin plumbing.

### Option C: Stay on Ant + bolt on pieces

Rejected without a table. Ivy for dependencies, hand-rolled JMH runner, no publishing
story. This is the most churn for the least capability — it rebuilds Option A's features
out of parts nobody else uses.

## 3. Decision

**Gradle 9.5.1**, Kotlin DSL, version catalog, `options.release = 17` (the Ant guarantee,
kept; a toolchain *pin* was tried and dropped — it forces auto-provisioning plumbing on
any host whose default JDK is newer, and Gradle 9 already requires 17+ to run), three
modules:

```
csrbt-core/          the library (packages core.*)            — publishable
csrbt-experimental/  arena, ecology, viability, cache evo     — not published
csrbt-benchmarks/    JMH (me.champeau.jmh)                    — never published
```

The deciding factor over Maven is the benchmark rig: JMH-as-a-module is the migration's
marquee feature and Gradle is where it works without plumbing. G1 named Gradle from the
start; the analysis confirms rather than overturns it.

Dependency direction is already clean and the split encodes it: `experimental` depends on
`core`; `core` mentions `experimental` only in comments (TreeContext.java:266 documents
exactly this direction). `benchmarks` depends on both.

**Versions** (verified current 2026-06-11, pinned in `gradle/libs.versions.toml`):

| Dependency | From | To | Note |
|---|---|---|---|
| Gradle | — | 9.5.1 | wrapper, checksum-validated |
| JUnit Jupiter | 1.9.2 console jar | 5.14.4 | staying on 5.x: jqwik 1.9.3 targets Platform 1.x/Jupiter 5.x; JUnit 6.x migration is a separate, later change |
| log4j | 2.17.1 | 2.26.0 | nine minor versions of security fixes; API-compatible |
| JMH | — | 1.37 | plugin `me.champeau.jmh` 0.7.3 |
| jqwik | — | 1.9.3 | G2, test-only, csrbt-core |
| JaCoCo | — | Gradle-bundled | coverage report + badge input |

**Cutover is clean, not parallel:** `build.xml` and the vendored jars are deleted in the
same change that lands the green Gradle build. CLAUDE.md and README build sections are
rewritten in that change. Two builds means two sources of truth and one of them lying.

**Held within this ADR** (named triggers, house style):

- **Package relocation** (`core.*` → `io.github.richeyworks.csrbt.*`): publishing default
  packages to Central is bad citizenship, but the rename touches every file and import.
  **Trigger:** the actual first Central release (the publish dry-run, not before). Until
  then `group = "io.github.richeyworks"` sits in the build with packages unchanged.
- **Signing + Central portal credentials:** host-side secrets, configured at the same
  trigger.
- **JUnit 6.x migration:** trigger — jqwik (or its successor) supports Platform 6.
- **Convention plugins / buildSrc:** trigger — a fourth module.

## 4. Consequences

**Easier:** adding a dependency (one line in the catalog vs. a jar download ritual);
running benchmarks (`./gradlew :csrbt-benchmarks:jmh`); CI (GitHub Actions runs the
wrapper); coverage/javadoc (`jacocoTestReport`, `javadoc`); onboarding an external
contributor (clone, `./gradlew build`, done); shrinking property tests when an invariant
breaks (jqwik).

**Harder:** the build is now code with a dependency of its own (Gradle major upgrades);
the agent sandbox can no longer run the suite (it has a JRE 11 — Gradle 9 requires
JVM 17+ to run, so build verification moves fully host-side, consistent with CLAUDE.md's
existing "compile on a host with JDK 17" rule); test working directory becomes the module
dir, so runtime `snapshots/` strays appear under `csrbt-core/` (already gitignored by
pattern).

**To revisit:** whether `csrbt-experimental` should publish (trigger: an external consumer
asks for the arena); whether the in-suite benchmark rows should be deleted once JMH
reproduces their numbers (keep both until JMH output is trusted, then the rows go).

## 5. Action items

1. [ ] Scaffold: `settings.gradle.kts`, `gradle/libs.versions.toml`, three module build
       files, `.github/workflows/ci.yml`.
2. [ ] Move sources: `core.*` main+test → `csrbt-core`; `experimental.*` main +
       the three tests importing it (`TreeContextTesterAdditions`, `ViabilityMapTest`,
       `CacheTransferExperimentTest`) → `csrbt-experimental`; resources
       (`log4j2.xml`, `junit-platform.properties`) → `csrbt-core/src/test/resources`
       (shared via test fixtures or duplication — see scaffold).
3. [ ] Seed `csrbt-benchmarks` with one JMH benchmark ported from the E5 fanout rows.
4. [ ] Host-side: `gradle wrapper --gradle-version 9.5.1` (or download the dist once),
       then `./gradlew build` green.
5. [ ] Cutover: delete `build.xml` + root jars; rewrite CLAUDE.md build/test section and
       README build instructions. Same commit as the green build.
6. [ ] Add one jqwik property test (G2 down payment): the strategy invariant under
       generated op sequences — the oracle-churn pattern with shrinking.
