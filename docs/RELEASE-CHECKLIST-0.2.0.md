# Release checklist — v0.2.0 (host-side steps)

Everything the sandbox could verify is done: both modules build and test green
(806), the staging publication produces complete Central-shaped artifacts
(jar + sources + javadoc + POM + md5/sha1/sha256/sha512) for `csrbt-core:0.2.0`
and `csrbt-experimental:0.2.0`, and the POMs carry name/description/url/licenses/
developers/scm with the right inter-module dependency. What remains needs the
host: git, the PGP key, and the Central Portal. Run these from PowerShell at the
repo root.

## 1. Commit and push

```powershell
git status                      # review: sources, tests, docs, README, build files, regenerated sessions
git add -A
git commit -m "0.2.0: ecology program (ADR-015-020), hardening day (26 probe-verified fixes, ADR-021/022), csrbt-experimental published"
git push
```

Wait for CI green on the JDK 17/21 matrix before tagging.

## 2. Tag

```powershell
git tag -a v0.2.0 -m "CSRBT 0.2.0"
git push origin v0.2.0
```

## 3. Sign + stage locally

`SIGNING_KEY` is the ASCII-armored private key (in-memory PGP, per the build files);
signing activates only when it is present, so everyday builds stay unsigned.

```powershell
$env:SIGNING_KEY = Get-Content -Raw path\to\private-key.asc
$env:SIGNING_PASSWORD = "<passphrase>"
./gradlew clean build publishMavenPublicationToStagingRepository
```

Verify: `csrbt-core/build/staging-deploy/...` and
`csrbt-experimental/build/staging-deploy/...` each contain the five files
(`.jar`, `-sources.jar`, `-javadoc.jar`, `.pom`, `.module`) **plus a `.asc`
signature for every one of them**. No `.asc` files = SIGNING_KEY didn't load;
stop and fix before uploading.

## 4. Bundle + upload to the Central Portal

The portal takes one zip per upload rooted at the groupId path. Both artifacts can
go in a single bundle:

```powershell
# from the repo root — merge the two staging trees into one bundle
Copy-Item -Recurse csrbt-core\build\staging-deploy\io bundle\
Copy-Item -Recurse -Force csrbt-experimental\build\staging-deploy\io bundle\
Compress-Archive -Path bundle\io -DestinationPath csrbt-0.2.0-bundle.zip
```

Upload at central.sonatype.com (Publish → Upload Bundle), wait for validation
(it checks signatures, POM completeness, sources/javadoc presence — all verified
present here), then **Release**. First-time note: the `io.github.richeyworks`
namespace must already be verified against the GitHub account (it is, if 0.1.0's
portal setup was completed; otherwise the portal walks through a one-time
repo-proof verification).

## 5. GitHub release

Create a release from tag `v0.2.0` with `docs/RELEASE-NOTES-0.2.0.md` as the body.

## 6. Post-release

- Verify resolution from a scratch project:
  `implementation("io.github.richeyworks:csrbt-core:0.2.0")` (Central sync takes
  a little while after Release).
- Point Brine at `csrbt-experimental:0.2.0` — note the session-format and
  cache-loop changes in the release notes' compatibility section (the promoted
  champion no longer double-processes lookups, so Brine's observed hit rates will
  genuinely change — for the better).
- Roll `version` in both `build.gradle.kts` files to `0.3.0-SNAPSHOT` (or leave
  at 0.2.0 until the next change lands — house call).

## Rollback triggers

Before step 4's **Release** click, everything is reversible (drop the bundle).
After Release, Central is immutable — a bad artifact means shipping 0.2.1, not
unpublishing. So the gate is step 3's verification: signatures present, CI green
on the tagged commit, and the staging jars byte-matching what CI built.
