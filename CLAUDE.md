# CSRBT — working notes for agents

## Build & test
- Build + run the full suite: `ant clean test` (the default target is `test`).
- The suite is JUnit 5 (Jupiter) via the console-standalone jar; reports land in `build/test-reports/`.
- Java 17 is required to **compile** (`build.xml` uses `release="17"`). A JRE-only environment can run the
  produced classes but cannot compile — do compilation/test on a host with a JDK 17.

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
Root logger is WARN (`src/main/resources/log4j2.xml`); the engine and control plane log per-op at INFO/WARN.
Tests that need to read a specific INFO line should raise the level with
`org.apache.logging.log4j.core.config.Configurator.setLevel(name, Level.INFO)` (it forces a context
reconfigure) rather than `core.Logger.setLevel`, which does not refresh an already-exercised logger. Capturing
logs across test classes is order-fragile — prefer asserting on observable state where possible.
