$ErrorActionPreference = "Stop"
Set-Location "C:\Users\730ri\projects\CSRBT"

# git is a native command: $ErrorActionPreference does not stop on its exit
# code, so every step is checked. A script that prints pushed after a commit
# it did not make is a success line with nothing behind it (ADR-098).
function Step($label) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "FAILED at: $label (exit $LASTEXITCODE). Nothing further was run." -ForegroundColor Red
    exit $LASTEXITCODE
  }
}

if (Test-Path ".git\index.lock") { Remove-Item -Force ".git\index.lock" }

if (Test-Path "_to_delete\adr099.tgz") { Remove-Item -Force "_to_delete\adr099.tgz" }
if (Test-Path "_to_delete\x099")       { Remove-Item -Recurse -Force "_to_delete\x099" }

git add tools/verify/_kit.py tools/verify/verify_claims_slice.py
Step "git add kit and claims-slice"
git add tools/verify/verify_claims_triage.py tools/verify/verify_engine_sessions.py
Step "git add triage and engine-sessions"
git add tools/verify/verify_kit_consistency.py tools/verify/verify_visualizer_sessions.py
Step "git add consistency and visualizer"
git add tools/verify/counts.json
Step "git add counts"
git add "docs/ADR-099-the-prediction-was-wrong-and-the-reverse-was-true-2026-08-29.md"
Step "git add ADR"
git add "docs/CHANGELOG-2026-08-29-adr099-one-pair-of-readers.md"
Step "git add changelog"
git add push-adr099.ps1
Step "git add script"

git status --short

git commit -m "ADR-099: the prediction was wrong, and the reverse of it was true" -m "ADR-098 predicted at least one assertion passing on text its reader could not see, and named the sweep that would falsify it. The sweep was run. Sixty-six membership tests judged, zero vacuous. The falsifier fired and the prediction is retracted." -m "Method matters here. The first instrument was static analysis over the suites and it reported zero because it could not look: it only matched helpers bound to a constant filename, so every assertion inside a for loop was invisible to it and two suites fell out entirely. An instrument that answers clean because it cannot see is the thing this kit keeps finding in other work, so it was discarded rather than reported. What replaced it logs the membership tests as they happen: each suite runs with its tag-stripper swapped for a str subclass recording every __contains__, with re.sub shadowed so the subclass survives the whitespace pass. Full coverage by construction." -m "The sweep found the reverse defect instead. Eleven live assertions pass ONLY because the mangled JavaScript is still in the haystack - their text is rendered at runtime from a widget help option or a keying table in script. Every one is checking something real; what is not real is the route. Whether any of them is visible is decided by whether an unrelated pair of angle brackets elsewhere in the file happened to close around it. That is the mechanism that hid one sentence from ADR-098 while leaving another four lines away intact. Nothing was broken. Eleven verdicts rested on a coin that has not yet come up tails." -m "_kit now carries one pair of readers and nothing rolls its own: prose(name) and prose_of(src) are what the page shows - a real html.parser parse, script and style dropped, entities left as written, tags joined with a space so assertions across a tag boundary read as before; raw(name) is what the file says. Five suites moved onto them and the eleven assertions moved to raw, where their text lives. verify_claims_slice s absence check for a spliced range moved too: a string gone from the prose but still sitting in a script is not gone." -m "The moves were made from measurement rather than from reading. Swapping the reader and re-running each suite named exactly the eleven, so the refactor was informed before it was made. verify_kit_consistency scored 49/49 with either reader and moved anyway, because a rule with one exception is a rule that erodes. tools/publish_drift.py keeps its stripper and is out of scope for a reason worth stating: it removes script and style BEFORE it strips, so its regex only ever meets markup. It was right all along." -m "The rule: no suite may read a page through a bracket-regex tag stripper, linted across the suites next to the probe-marker rule it resembles. It assembles the forbidden pattern rather than spelling it, because a rule containing what it forbids reports itself (ADR-077, the trap that broke the probe-marker split twice in one hour). Comments are exempt by design - the scan blanks tokenize COMMENT tokens first - so a suite may explain the pattern and may not use one. It is seeded both ways, because a lint nobody has watched fire is a lint nobody knows the shape of." -m "Two silent no-ops of my own, recorded because they are this slice s subject in different clothes. A patch printed patched both having changed nothing - the anchor was indented in the patch and flush-left in the file, str.replace found no match, and the script announced success anyway. And the grep that first confirmed the tree was clean was an over-escaped regex matching nothing. Every edit here now goes through a helper that asserts the replacement changed the file, and the confirming search is fixed-string." -m "Numbers: 72 membership tests logged, 66 attributed to a page, 0 vacuous, 11 script-only. Bracket-regex readers 6 to 1. Suite 60 of 60 jobs green, 4300 of 4300 checks passing (4295 before). No page changed, so the finder is unmoved at 1 near and no mutation sweep is owed." -m "Next: an enumeration of every control, tab, button and export on all forty pages, asserting each is driven by some suite. The defect ADR-099 predicts is an affordance nobody exercises, passing by omission rather than by observation. That enumeration is the harness."
Step "git commit"

git push origin main
Step "git push"

git log --oneline -2
Write-Host ""
Write-Host "ADR-099 pushed." -ForegroundColor Green
