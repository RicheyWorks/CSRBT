# CSRBT 0.3.0 — release checklist (host-side)

Everything below runs in PowerShell from `C:\Users\730ri\projects\CSRBT` unless noted.
Prepared 2026-08-20; the working tree at this point is verified green (1100 tests, javadoc
clean, `publishToMavenLocal` produces jar + sources + javadoc + POM for both modules at
0.3.0).

## 0. The 0.2.x decision, settled

`v0.2.0` is tagged in git (`f1de06f`) but **never reached Maven Central** — the portal
upload step was never completed. Decision recorded here: **skip backfilling 0.2.x**; 0.3.0
is the first Central release. The old tags stay as history; nothing is rewritten.

## 1. Commit and tag

```powershell
git add -A
git commit -m "0.3.0: eighth pass + ADR-029/030 + correction; version alignment"
git tag -a v0.3.0 -m "CSRBT 0.3.0 - ScoreCard 8-structure break (ADR-029), B+ registry slot, native Office exports (ADR-030), eighth pass"
git push
git push origin v0.3.0
```

## 2. Sign and stage the Central bundle

Requires your PGP key in the environment (same convention as 0.2.0's prep):

```powershell
$env:SIGNING_KEY = Get-Content path\to\private-key.asc -Raw
$env:SIGNING_PASSWORD = "<key passphrase>"
.\gradlew publishMavenPublicationToStagingRepository
```

This stages both modules, signed, under:
- `csrbt-core\build\staging-deploy\`
- `csrbt-experimental\build\staging-deploy\`

## 3. Bundle and upload to the Central Portal

The portal takes one zip whose internal layout is the maven repo path
(`io/github/richeyworks/...`). Both modules can go in a single bundle:

```powershell
# Merge the two staging trees into one bundle
Remove-Item -Recurse -Force central-bundle -ErrorAction SilentlyContinue
New-Item -ItemType Directory central-bundle | Out-Null
Copy-Item -Recurse csrbt-core\build\staging-deploy\* central-bundle\
Copy-Item -Recurse csrbt-experimental\build\staging-deploy\* central-bundle\
Compress-Archive -Path central-bundle\io -DestinationPath csrbt-0.3.0-bundle.zip -Force
```

Then: https://central.sonatype.com → sign in (the account that owns
`io.github.richeyworks`) → **Publish** → upload `csrbt-0.3.0-bundle.zip` → wait for
validation to pass → **Release**. This is the step that was skipped for 0.2.0 — it is not
optional; nothing is public until the portal's Release button is pressed.

## 4. Verify — the step that would have caught 0.2.0

Within ~30 minutes of the portal showing "released":

```powershell
curl.exe -s -o NUL -w "%{http_code}" https://repo1.maven.org/maven2/io/github/richeyworks/csrbt-core/0.3.0/csrbt-core-0.3.0.pom
# 200 = actually released. 404 = the portal step didn't finish - go back to 3.
```

(Search indexing on central.sonatype.com lags repo1 by hours; trust the repo1 URL, not the
search box.)

## 5. GitHub release (optional but cheap)

```powershell
gh release create v0.3.0 --title "CSRBT 0.3.0" --notes-file docs\RELEASE-0.3.0.md
```

## Ecosystem versions (context, no action required today)

The sibling engines were version-aligned in the same change set: SmokeHouse, SmokeSignal,
DryAge, Jerky, and WholeHog moved to **0.2.0** (each grew public API since birth: the tail
sidecar exports, the Write/Batch routes + WireStats, generationPath/retention/scan-runs,
targeted extraction, and the composed organism respectively); Rub and Sizzle stay 0.1.0
(newborn); Twine, Carver, Renderer, Brine, PitBoss, SuperBeefSort stay 0.1.0 (unchanged
API). Every cross-repo dependency coordinate now states the real version, so the day any
engine goes to Central its POM is already honest. Releasing the engines to Central is its
own campaign (one bundle each) — deliberately out of scope for this checklist.
