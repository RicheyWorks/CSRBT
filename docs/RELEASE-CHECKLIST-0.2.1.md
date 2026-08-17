# Release checklist — v0.2.1 (host-side steps)

Everything the sandbox could verify is done. What remains needs the host: git, the PGP key,
and the Central Portal. Run these from PowerShell at the repo root.

## 0. Decide this first — is 0.2.0 actually on Central?

**It could not be found.** Checked three ways from the sandbox on 2026-08-17:

| probe | result |
|---|---|
| `repo1.maven.org/maven2/io/github/richeyworks/` | **404** (the namespace directory does not exist) |
| `search.maven.org` — `g:io.github.richeyworks` | `numFound: 0` |
| `central.sonatype.com` component browse — `csrbt` | `0` of 867 700 components |

The control probe (`junit-bom`) returned 200 from the same network, so this is not a
connectivity artifact. `docs/RELEASE-NOTES-0.2.0.md` itself says *"not yet on Maven Central
(signing/portal upload is the release step)"*, which is consistent with step 4 of the 0.2.0
checklist never having been completed — or with the bundle having been uploaded and dropped
rather than Released.

**Confirm on the Portal before tagging**, because it changes two things:

1. **Whether 0.2.1 is the first artifact anyone can resolve.** If so, the "upgrading from
   0.2.0" framing in the release notes is about people building from source (Brine resolves
   through a local repo today), not about Central consumers. Nothing in the notes is false
   either way, but say so in the GitHub release body if 0.2.0 never shipped.
2. **Whether the namespace is verified.** A never-completed 0.2.0 upload may also mean the
   one-time `io.github.richeyworks` namespace verification against the GitHub account was
   never finished. If the Portal asks for repo-proof verification at step 4, that is why —
   it is a one-time gate, not a problem with this bundle.

This does **not** block the release. It only decides the wording and whether to expect a
verification prompt.

## What the sandbox verified

- **Build green:** `./gradlew --no-daemon build -x :csrbt-benchmarks:jmh` → **BUILD
  SUCCESSFUL**, **1063 tests, 0 failures, 0 errors, 0 skipped, 0 javadoc warnings**
  (838 `csrbt-core` + 225 `csrbt-experimental`, counted from the JUnit XML).
  *(The `-x` is defensive: `csrbt-benchmarks` wires only `compileJmhJava` into `check`, so
  `build` compiles the benchmarks but never runs them.)*
- **Version bumped** to `0.2.1` in `csrbt-core/build.gradle.kts:12` and
  `csrbt-experimental/build.gradle.kts:12`, and in the README badge. Those are the only three
  places the version is asserted — verified by grep across `*.kts`, `*.toml`, `*.yml`,
  `*.java`, `*.properties` and the README. (`csrbt-benchmarks/build.gradle.kts:10` still reads
  `0.1.0`; it was `0.1.0` at the 0.2.0 release too and the module is unpublished — see step 6.)
- **Staging publication:** `./gradlew publishMavenPublicationToStagingRepository` succeeds for
  both modules and produces the complete Central-shaped set — **25 files per module** in the
  version directory: `.jar`, `-sources.jar`, `-javadoc.jar`, `.pom`, `.module`, each with
  `.md5`, `.sha1`, `.sha256` and `.sha512`.
- **POMs are complete.** Both carry `name`, `description`, `url`, `licenses` (MIT),
  `developers` (`RicheyWorks` / Richmond) and `scm` (url + `scm:git:` connection).
  `csrbt-experimental`'s POM declares `io.github.richeyworks:csrbt-core:0.2.1` at `compile`
  scope — the inter-module dependency points at the new version.
- **Sample payloads regenerate byte-identical.** All six recorder/lab tasks re-run and diffed:
  `ecology-lab-session.json`, `ecology-experiment-session.json`, `ecology-trace-session.json`,
  `arena-session.json`, `arena-search-session.json`, `viability-map.json`, and all 11 files in
  `docs/experiment-out/`. Zero differences, including `arena-search-session.json`, which was
  regenerated during the seventh pass and is now stable.

**Not verified here — needs the host:** PGP signatures (no key in the sandbox, so no `.asc`
file has ever been produced by this run), CI on the JDK 17/21 matrix, and anything on the
Central Portal.

## 1. Commit and push

```powershell
git status                      # review: sources, tests, docs, README, build files
git add -A
git commit -m "0.2.1: sixth- and seventh-pass fixes (data loss, crashes, ensemble deadlock), ADR-023-026, 1063 tests"
git push
```

Wait for CI green on the JDK 17/21 matrix before tagging.

## 2. Tag

```powershell
git tag -a v0.2.1 -m "CSRBT 0.2.1"
git push origin v0.2.1
```

## 3. Sign + stage locally

`SIGNING_KEY` is the ASCII-armored private key (in-memory PGP, per the build files); signing
activates only when it is present, so everyday builds stay unsigned.

```powershell
$env:SIGNING_KEY = Get-Content -Raw path\to\private-key.asc
$env:SIGNING_PASSWORD = "<passphrase>"
./gradlew clean build publishMavenPublicationToStagingRepository
```

Verify the signatures landed — **this is the gate**:

```powershell
foreach ($m in 'csrbt-core','csrbt-experimental') {
    $d = "$m\build\staging-deploy\io\github\richeyworks\$m\0.2.1"
    "{0}: {1} artifacts, {2} signatures" -f $m,
        (Get-ChildItem $d -File | Where-Object { $_.Name -notmatch '\.(md5|sha1|sha256|sha512|asc)$' }).Count,
        (Get-ChildItem $d -Filter *.asc -File).Count
}
```

Expect **5 artifacts and 5 signatures** for each module (`.jar`, `-sources.jar`,
`-javadoc.jar`, `.pom`, `.module`). **0 signatures = `SIGNING_KEY` didn't load; stop and fix
before uploading** — the Portal will reject the bundle and you will have burned a tag.

## 4. Bundle + upload to the Central Portal

The Portal takes one zip per upload, rooted at the groupId path; both artifacts go in a single
bundle. Build it explicitly rather than copying the `io` trees over each other — PowerShell's
`Copy-Item -Recurse` nests a second `io\` inside an existing one instead of merging, which is
how you get a bundle the Portal silently reads as empty:

```powershell
Remove-Item -Recurse -Force bundle, csrbt-0.2.1-bundle.zip -ErrorAction SilentlyContinue
foreach ($m in 'csrbt-core','csrbt-experimental') {
    $src = "$m\build\staging-deploy\io\github\richeyworks\$m\0.2.1"
    $dst = "bundle\io\github\richeyworks\$m\0.2.1"
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    Copy-Item "$src\*" -Destination $dst
}
Compress-Archive -Path bundle\io -DestinationPath csrbt-0.2.1-bundle.zip
```

This deliberately excludes the `maven-metadata.xml` that Gradle writes one level up in each
staging tree — the Portal generates its own, and the 0.2.0 instruction's wholesale
`Copy-Item -Recurse ...\io` would have swept it into the bundle.

Sanity-check the zip before uploading (expect **50 entries** — 25 per module):

```powershell
(Get-ChildItem bundle -Recurse -File).Count
```

Upload at central.sonatype.com (Publish → Upload Bundle), wait for validation — it checks
signatures, POM completeness and sources/javadoc presence, all of which are verified present
here except the signatures — then **Release**. See step 0 if it asks to verify the namespace.

## 5. GitHub release

Create a release from tag `v0.2.1` with `docs/RELEASE-NOTES-0.2.1.md` as the body. If step 0
established that 0.2.0 never reached Central, add one line saying 0.2.1 is the first artifact
published there.

## 6. Post-release

- Verify resolution from a scratch project:
  `implementation("io.github.richeyworks:csrbt-core:0.2.1")` (Central sync takes a little while
  after Release).
- Point Brine at `csrbt-experimental:0.2.1`. Two things to flag to that consumer: null
  arguments now throw `NullPointerException` uniformly (a B+tree call that previously threw
  `IllegalArgumentException` or returned `false` now throws NPE), and `PolicyBandit.meanCost`
  returns the basis-selected mean, so recorded cost numbers can move. Both are in the release
  notes' behaviour-change section.
- Decide `csrbt-benchmarks/build.gradle.kts:10`, which still reads `version = "0.1.0"`. The
  module is unpublished and build-from-source, so it is cosmetic — but it has now been stale
  across two releases. Either roll it with the others or drop the `version` line entirely so it
  inherits nothing and asserts nothing.
- Roll `version` in both published `build.gradle.kts` files to `0.3.0-SNAPSHOT` (or leave at
  0.2.1 until the next change lands — house call, same as 0.2.0).

## Rollback triggers

Before step 4's **Release** click, everything is reversible (drop the bundle). After Release,
Central is immutable — a bad artifact means shipping 0.2.2, not unpublishing. So the gate is
step 3's verification: signatures present (5 per module), CI green on the tagged commit, and
the staging jars byte-matching what CI built.
