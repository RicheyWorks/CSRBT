# push-adr225-siblings.ps1 -- two sibling repos, one command (CSRBT ADR-225).
#   WholeHog:   CI checks out Rub and Sizzle (installed from ci/ci.yml by this command).
#   SmokeHouse: get()/range() read under the store lock when eight off-lock tries lose the race.
# Written by hand for sibling repos; CSRBT's own slice is pushed by push-adr225.ps1.
# Run from anywhere:   .\CSRBT\tools\push\push-adr225-siblings.ps1
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$failed = @()
function Land($dir, $paths, $subject, $body) {
  $repo = Join-Path $root $dir
  $lock = Join-Path $repo ".git\index.lock"; if (Test-Path $lock) { Remove-Item $lock -Force }
  $st = git -C $repo status --porcelain -- $paths
  if (-not $st) {
    $ahead = git -C $repo rev-list --count "@{u}..HEAD"
    if ([int]$ahead -gt 0) { Write-Host "$dir is committed but not pushed -- pushing"; git -C $repo push; if ($LASTEXITCODE -ne 0) { $script:failed += $dir; return }; Write-Host "$dir pushed."; return }
    Write-Host "$dir is already pushed -- nothing to do"; return
  }
  git -C $repo add -A $paths
  git -C $repo commit -m $subject -m $body -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_015Ryyc7gWVh4QXAQ9RAFPF1"
  if ($LASTEXITCODE -ne 0) { Write-Host "!! ${dir}: git commit failed ($LASTEXITCODE) -- nothing committed, nothing pushed"; $script:failed += $dir; return }
  git -C $repo push
  if ($LASTEXITCODE -ne 0) { Write-Host "!! ${dir}: git push failed ($LASTEXITCODE) -- the commit is local and the remote does not have it"; $script:failed += $dir; return }
  Write-Host "$dir pushed."
}
# WholeHog: INSTALLED BY THIS COMMAND (ADR-223's rule) -- the bridge will not write a workflow; the operator's own command does.
$wh = Join-Path $root "WholeHog"
if (-not (Test-Path (Join-Path $wh "ci\ci.yml"))) { Write-Error "WholeHog\ci\ci.yml is not there -- the sibling tarball did not land"; exit 1 }
Copy-Item -Force (Join-Path $wh "ci\ci.yml") (Join-Path $wh ".github\workflows\ci.yml")
Land "WholeHog" @("ci/ci.yml", ".github/workflows/ci.yml") "CI: check out Rub and Sizzle -- the build has included them since they joined, and every push has failed at configuration (CSRBT ADR-225)" @"
The composite build in settings.gradle.kts includes thirteen siblings; this workflow checked out eleven. Rub and Sizzle joined the build and never joined this list, so every push failed at configuration -- 'Included build ../Rub does not exist' -- before a test ran. CSRBT's verify_ecosystem now reads every engine's closure off its settings file and its checkouts off its workflow, and holds the two to each other; this is the one engine it named. The file travels as ci/ci.yml and is copied into place by this command, because the delivery bridge refuses to write .github/workflows (CSRBT ADR-202, ADR-223).
"@
Land "SmokeHouse" @("src/main/java/io/github/richeyworks/smokehouse/SmokeHouse.java") "SH-2: a read that loses eight races with compaction is taken under the store lock, not thrown (CSRBT ADR-225)" @"
get() and range() read the log outside the store lock and re-resolve when a compaction commit repoints or reclaims the address they hold -- a bounded eight times, because relentless compaction could otherwise chase a key forever. The bound was the defect: a writer that overwrites the keyset and compacts back to back commits a compaction between EVERY re-resolution and the read that follows it, and eight tries were eight losses on a perfectly healthy store; rangeSurvivesAConcurrentCompactionCommit failed that way about one run in five and threw log/index divergence. The commit runs under the store lock, so the ninth read is now taken under it, where a commit cannot intervene, and settles the question: live at a readable address, gone, or a genuine divergence -- only the last is an error. 82 of 82, three consecutive runs of the probe. Found by CSRBT ADR-225.
"@
if ($failed.Count -gt 0) { Write-Error ("not pushed: " + ($failed -join ", ")); exit 1 }
Write-Host "ADR-225 siblings pushed."
