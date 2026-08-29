$ErrorActionPreference = "Stop"
Set-Location "C:\Users\730ri\projects\CSRBT"

# git is a native command: $ErrorActionPreference does not stop on its exit code,
# so each step is checked. The previous script printed "pushed" after a commit
# that had failed, which is a success line with nothing behind it.
function Step($label) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "FAILED at: $label (exit $LASTEXITCODE). Nothing further was run." -ForegroundColor Red
    exit $LASTEXITCODE
  }
}

if (Test-Path ".git\index.lock") { Remove-Item -Force ".git\index.lock" }

# staging artifacts the agent sandbox cannot delete
if (Test-Path "_to_delete\adr098.tgz") { Remove-Item -Force "_to_delete\adr098.tgz" }
if (Test-Path "_to_delete\x098")       { Remove-Item -Recurse -Force "_to_delete\x098" }

git add docs/collection-sheet.html
Step "git add collection-sheet"
git add tools/audit_claims.py tools/verify/verify_claims_triage.py
Step "git add tools"
git add tools/verify/counts.json tools/published.json
Step "git add state"
git add "docs/ADR-098-a-signpost-is-not-a-claim-2026-08-29.md"
Step "git add ADR"
git add "docs/CHANGELOG-2026-08-29-adr098-the-last-three-claims.md"
Step "git add changelog"
git add push-adr098.ps1
Step "git add script"

git status --short

git commit -m "ADR-098: a signpost is not a claim, and an unknowable quantity has no arithmetic to show" -m "Worked the three near claims ADR-097 handed on, after first running the falsifier check it asked for: the three oldest published versions (tree-proofs, tree-visualizer, greenhouse) re-read from the live URL, zero drift on all three. That is a pass and close to vacuous at a forty-minute interval with nobody editing in between, and the ADR says so rather than banking it." -m "Two of the three were real defects on collection-sheet. The dryer help sent readers to the Method tab for the 50 C discussion; that note is in p-vou, directly under the same log, and p-met has seven cards and none about drying - the pointer named the one tab that does not carry it. The same line asserted that silica beats any drying temperature for sequencing: an unsourced comparative with no number, and therefore something no run of audit_claims.py at any strictness could ever report. It was found by reading the sentence the finder had flagged for a different reason. Also: 40-45 C is now labelled a convention rather than usual, and the 35 C floor a rule of thumb rather than a measured one." -m "The third claim is sound and micro-bench was not edited. Its card names APHA Standard Methods 9215, FDA BAM, USP 1227, ASTM and Breed and Dotterrer 1916. The finder cannot see that, and the reason is worth more than the claim: the derivation exemption is a showable-arithmetic test, not a provenance test. Strip CV = 1 / sqrt N out of the sibling below-30 bullet in a scratch copy and it is reported identically, sourcing untouched. A claim whose content is that a quantity cannot be computed can never take that exit - there is no working to show, and saying so IS the claim. Adding the word conventional would have cleared the flag and told the reader nothing, which is tuning the page to the check." -m "verify_claims_triage 30 to 46 checks: a seeded pair of siblings differing only in showable arithmetic, the same pair on the real page, the provenance the flagged bullet rests on, and the four collection-sheet corrections. audit_claims.py gains a docstring naming both blind spots; no rule changed." -m "A helper that could not see what it was checking. text() strips tags with a bracket regex, so a page JavaScript - which has bare angle brackets - swallows whole spans. Every help string in this kit lives in a script string. An assertion about one written against text() does not fail, it looks elsewhere and passes: the check that the silica sentence is gone would have been green BEFORE the edit. A raw() reader was added with the reason beside it." -m "collection-sheet published repo to live, the first publish in three slices, then re-read from the URL and diffed to zero and re-stamped via read - inside this slice rather than left for the next one. published.json: 40 current, 40 measured from the live page, 0 stamped at publish time." -m "Finder: 2 pages / 3 claims / 0 BARE / 3 near, down to 1 page / 1 claim / 0 BARE / 1 near. The worklist since ADR-094: 71 to 41 to 15 to 3 to 1, and 1 is the correct steady state. Suite: 60 of 60 jobs green, 4295 of 4295 checks passing (4279 before)." -m "Next: sweep every tag-stripping reader in tools/verify for assertions naming a string that occurs only inside a script - decorations passing on text they cannot see. Prediction: at least one exists outside verify_claims_triage."
Step "git commit"

git push origin main
Step "git push"

git log --oneline -2
Write-Host ""
Write-Host "ADR-098 pushed." -ForegroundColor Green
