# CSRBT — working notes for agents

## Build & test
- Gradle multi-module build (ADR-013): `./gradlew build` runs everything. Modules: `csrbt-core`
  (the library, publishable), `csrbt-experimental` (arena/ecology/cache-evo; depends on core),
  `csrbt-benchmarks` (JMH; `./gradlew :csrbt-benchmarks:jmh`).
- The suite is JUnit 5 + jqwik; per-module reports land in `<module>/build/reports/tests/test/`.
- Compilation is `options.release = 17` on whatever JDK runs Gradle (no toolchain pin).
  **Gradle 9 itself needs JVM 17+ to run**, so a JRE-11 sandbox can neither build nor test —
  do compilation/test on a host with JDK 17+.
- Dependencies are in `gradle/libs.versions.toml` — one file to audit; nothing is vendored.

## Git is host-side
Agent sandboxes mount the repo but **cannot write `.git`** (commits, staging, `checkout` all fail from the
sandbox). Run every `git` command from your own terminal, not the agent.

**Stale `.git/index.lock`.** Interrupted or sandboxed git can leave a zero-byte `.git/index.lock`; git then
refuses with *"Unable to create '.git/index.lock': File exists."* The sandbox often cannot remove it (and may
show a stale view of it). Fix it host-side, then retry:

```powershell
Remove-Item .git\index.lock -Force -ErrorAction SilentlyContinue   # PowerShell
del .git\index.lock                                                # cmd
```

Prefer **PowerShell** on Windows for these commands.

## Logging in tests
Root logger is WARN (`csrbt-core/src/test/resources/log4j2.xml`; the experimental module carries its own
copy — the published jar deliberately ships no logging config); the engine and control plane log per-op at
INFO/WARN.
Tests that need to read a specific INFO line should raise the level with
`org.apache.logging.log4j.core.config.Configurator.setLevel(name, Level.INFO)` (it forces a context
reconfigure) rather than `core.Logger.setLevel`, which does not refresh an already-exercised logger. Capturing
logs across test classes is order-fragile — prefer asserting on observable state where possible.
