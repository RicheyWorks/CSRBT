# CHANGELOG — 2026-06-11 — v0.1.0 prep: package relocation (ADR-013 §3 trigger fired)

ADR-013 held the package relocation until "the actual first Central release (the publish
dry-run)". The decision to cut v0.1.0 fires it.

## What changed

**Every package relocated** (128 sources; mechanical, no behavior change):

| Old | New |
|---|---|
| `core.*` | `io.github.richeyworks.csrbt.*` |
| `experimental.*` | `io.github.richeyworks.csrbt.experimental.*` |
| `test.core` (test sources) | unchanged — deliberate: tests stay in a foreign package so they can only exercise the public API |
| `benchmarks` (JMH) | unchanged — never published |

Rewrites covered package/import statements, javadoc `{@link}`s, FQN references in test
code (`PolicySearchControllerTest`'s `instanceof` patterns, `@DisplayName` strings), the
`TreeContext` agent-swarm comment, and README package mentions. log4j's own
`org.apache.logging.log4j.core.*` left strictly alone (the CLAUDE.md "not
`core.Logger.setLevel`" advice refers to log4j's class, not ours).

**Relocation-safety checked before the rename:** no `getClass().getName()`/`Class.forName`
in main sources (snapshot/`.rbt` formats carry no class names — old files load
unchanged); logger names derive from `Class` objects, so they follow automatically;
`log4j2.xml` configures only the root logger.

**Version:** `0.1.0-SNAPSHOT` → `0.1.0` in all three modules.
**Docs:** `RELEASE-NOTES-0.1.0.md` added; README package mentions updated.

## Verification

Sandbox static checks green: package/dir alignment across all 128 sources, leftover scan
for old FQNs empty (org.apache references excluded by design). Build + suite is host-side:
`./gradlew build`, then `./gradlew publishToMavenLocal` as the release dry-run, then tag
`v0.1.0`.
