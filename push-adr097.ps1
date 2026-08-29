$ErrorActionPreference = "Stop"
Set-Location "C:\Users\730ri\projects\CSRBT"

if (Test-Path ".git\index.lock") { Remove-Item -Force ".git\index.lock" }

# staging artifacts the agent sandbox cannot delete
if (Test-Path "_to_delete\adr097.tgz") { Remove-Item -Force "_to_delete\adr097.tgz" }
if (Test-Path "_to_delete\x097")       { Remove-Item -Recurse -Force "_to_delete\x097" }

git add docs/breeding-suite.html docs/collection-sheet.html docs/cp-suite.html
git add docs/ecology-field-card.html docs/ecology-glossary.html docs/ecology-lab-manual.html
git add docs/ecology-lab.html docs/ethogram.html docs/field-season.html
git add docs/releve.html docs/stand-sheet.html
git add tools/published.json tools/verify/counts.json
git add "docs/ADR-097-the-worklist-was-being-worked-in-the-wrong-copy-2026-08-29.md"
git add "docs/CHANGELOG-2026-08-29-adr097-thirty-one-pages-read.md"
git add push-adr097.ps1

git status --short

git commit -m "ADR-097: the worklist was being worked in the wrong copy" -m "Read the remaining 31 published artifacts against the repo, as ADR-096 section 9 required. Eleven had drifted, and in every case the published copy was the newer one: 22 lines replaced by 24 across breeding-suite, collection-sheet, cp-suite, ecology-field-card, ecology-glossary, ecology-lab-manual, ecology-lab, ethogram, field-season, releve and stand-sheet. Ten of the eleven edits are provenance. One is a factual correction: 40-45 C does not sit inside 43-50 C, it overlaps it by two degrees." -m "The eleven pages audit_claims.py had flagged before this slice are the same eleven pages that had drifted, with no page in either list absent from the other. ADR-094 s worklist was not being ignored - it was being worked in the artifact editor, by a session that never wrote back to docs/. Finder: 11 pages / 15 claims / 1 BARE / 14 near, down to 2 pages / 3 claims / 0 BARE / 3 near, with audit_claims.py byte-identical throughout. The fall is entirely content." -m "Each of the twelve cleared flags was read against the edit that cleared it: ten cleared by a phrase in the flagged claim s own sentence, one by a .src span naming where two figures come from, one by inline arithmetic. None by a section-level blanket (ADR-094). collection-sheet was edited three times and still carries both of its flags; micro-bench still carries its one." -m "published.json: 40 current, 40 measured from the live page, 0 stamped at publish time - the first time since the kit had forty pages that no entry rests on a stamp that says nothing about whether the publisher kept the bytes. ADR-096 s five publish-stamped republishes were re-read from the live URL and all five diffed to zero." -m "Suite: 60 of 60 jobs green, 4279 of 4279 checks passing. 4279 rather than ADR-096 s 4278 because verify_engine_sessions had been reporting 24/25 with its engine round-trip UNVERIFIED for a missing log4j-core; resolving the test classpath supplied it and the job now runs the engine at 26/26. Nothing in the suite changed - a check that had been abstaining is now voting." -m "Next: three near claims remain (collection-sheet x2, micro-bench x1). ADR-097 s falsifier is any of the forty drifting again before it is deliberately republished; the cheap check is publish_state.py --verify, run before the next slice edits anything."

git push origin main

git log --oneline -2
Write-Host ""
Write-Host "ADR-097 pushed."
