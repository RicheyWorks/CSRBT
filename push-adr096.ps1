# ADR-096 -- the repository was the stale copy.
# CRLF + no here-strings on purpose: the previous version used @"..."@ written with LF
# line endings, which Windows PowerShell 5.1 does not parse as a here-string, so git
# received the message body as arguments and refused with: unknown switch `>'.
$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\730ri\projects\CSRBT'

# A sandboxed git can leave a zero-byte lock behind (CLAUDE.md). Clear it first.
Remove-Item .git\index.lock -Force -ErrorAction SilentlyContinue

# Two paths the agent sandbox created and cannot delete.
Remove-Item _kit_stage.tgz -Force -ErrorAction SilentlyContinue
Remove-Item _to_delete\stage -Recurse -Force -ErrorAction SilentlyContinue

git add -A

# One -m per paragraph. No multiline strings, so nothing depends on line endings.
git commit `
  -m 'ADR-096: the repository was the stale copy' `
  -m 'Working ADR-094 twelve BARE claims meant republishing nine pages, which meant reading each live copy first. Eight of the nine were serving prose the repository never had -- mostly provenance docs/ was missing: a cited Utricularia range (Taylor 1989), The Seed Garden (Colley and Zystro 2015), Falconer and Mackay 1996, three conventional labels and two inline derivations. All eight back-merged into docs/.' `
  -m 'publish_state did not miss this; it was never asked. A publish-stamp says nothing about whether the publisher kept the bytes -- its own ADR-078 docstring -- and 22 of 40 pages were stamped that way. Now 40 current, 0 behind, 0 unknown, 18 measured from the live page.' `
  -m 'Also: ADR-094 section 2 recorded 14 BARE down to 12 without re-running the finder, and only the card naming 40 CFR 503 actually cleared. The finder carried its provenance vocabulary twice and the copies had drifted, so the strict test was WEAKER than the loose one on FDA BAM, AOAC, USP, APHA and Standard Methods; written once now. An empty .cite/.src/.ref exempted the block it sat in; floored and canaried. A .echo exemption was built and withdrawn the same day when the live deployment-log turned out to print its own duty arithmetic, leaving the escape with zero members. Three suites now import a tool probe via _kit.tool() instead of splitting its source -- the coupling ADR-094 named as not-done.' `
  -m 'ADR-094 falsifier fired: cp-characters gave Utricularia bladders as 0.2 to 5 mm, two ranges spliced, and the published card had already been corrected while docs/ had not.' `
  -m 'Claims 29 to 15, BARE 13 to 1. The finder changes clear none of that, measured three ways. run_all: 59 of 60 jobs, 4277 of 4278 checks; the one gap needs ./gradlew classes.'

git push origin main

Write-Host ''
Write-Host 'pushed. To confirm the kit is green on your machine:' -ForegroundColor Green
Write-Host '  python tools\verify\run_all.py -j 4'
Write-Host '  python tools\audit_claims.py        # expect 15 claims, 1 BARE'
Write-Host '  python tools\publish_state.py       # expect 40 current, 0 behind'
