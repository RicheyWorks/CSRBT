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

if (Test-Path "_to_delete\adr100.tgz") { Remove-Item -Force "_to_delete\adr100.tgz" }

git add tools/harness.py tools/verify/verify_harness.py
Step "git add harness and its suite"
git add tools/harness_ledger.json
Step "git add ledger"
git add tools/verify/counts.json
Step "git add counts"
git add "docs/ADR-100-the-instrument-was-the-first-thing-it-found-2026-08-29.md"
Step "git add ADR"
git add "docs/CHANGELOG-2026-08-29-adr100-everything-a-user-can-do.md"
Step "git add changelog"
git add push-adr100.ps1
Step "git add script"

git status --short

git commit -m "ADR-100: the instrument was the first thing it found" -m "ADR-099 named its own falsifier: an enumeration of every control, tab, button and export on all forty pages, showing which are driven. That enumeration is tools/harness.py. It runs, and it produces the number: discovered 3684 = driven 2357 + dead 21 + hidden 251 + failed 4 + excluded 1051. The prediction holds and it understates the case. The per-page suites drive a few dozen affordances apiece. Two thousand three hundred and fifty-seven had never been pressed by anything, and until now there was no way to say that in a number." -m "What everything a user can do was taken to mean: nineteen kinds of affordance, discovered by selector in priority order so a stepper value is not also a text box - tabs, stepper values and their plus and minus, FEK fields, text and number and date boxes and textareas, selects, sliders, picker searches and every picker option, dial buttons, chips, the four bespoke chip rows the kit grew before FEK existed, file inputs, every other button, and links. Each is stamped, its owning pane is opened, it is driven with a value new on every pass, and probed before and after in one round trip." -m "A control is driven if pressing it changed what a user could see: the visible text, or WHICH elements carry the on class. Dead if three passes changed nothing. Otherwise hidden, failed, or excluded. Five buckets, exhaustive by construction, and the report adds them up. That identity is asserted on every fixture because the number is a coverage claim: a harness that loses an affordance between discovery and verdict is claiming to have driven what it never saw." -m "Six defects were found in the harness before any were found in the kit, and every one of them was for a while a confident false report. The fingerprint counted on-elements instead of naming them, so a dial whose selection MOVES kept its count and ten dials read dead. A control already selected cannot show its press - and the first fix baselined before the setup click, so setup and target cancelled and it read dead anyway. FEK re-renders subtrees and takes the stamps with them, which made 941 of 1026 hidden mean the page rebuilt it away. Twelve spore swatches all raise the same toast, already on screen. Fields were refilled with the value they already held. A stepper at its bound is a real no-op, not a wiring fault." -m "Three more false invariants were retracted the same way. Spills 15px sideways on two clean pages: the metric was scrollWidth minus window.innerWidth, and innerWidth includes the vertical scrollbar. Junk rendered, the estimate is undefined: the English word, in prose, in a sentence explaining there is nothing to estimate yet - the comparison now tests the matched token, never the sixty characters around it. Console error ERR_INTERNET_DISCONNECTED on field-season: the webfont ADR-031 deliberately loads non-blocking, failing offline by design, and the console text does not carry the URL that identifies it, so the filter reads location.url instead." -m "One pattern runs through all nine: a control judged from a state in which its effect could not appear. That is this harness s version of ADR-069 - not a check that cannot fail, but a check that cannot pass." -m "tools/verify/verify_harness.py writes six pages whose defect is known and asserts the verdict on each: a button wired to nothing, a button that counts and must NOT be reported, a handler leaking NaN into a value element, a 900px row in a 390px phone, a control that exists only behind a closed tab, and a handler that throws. The accounting identity is asserted on all six, and four further assertions pin the measurement corrections so they cannot regress. 22 of 22. One fixture failed on first run and the FIXTURE was wrong: its readout sat in the pane that closes, where a display none ancestor keeps text out of innerText. The harness was right." -m "Exclusion is the hole ADR-061 is about, so there are exactly three and each carries a sentence rather than a label. Rail links and hub cards, 1050 of them, because a click ends the run on a different page - their hrefs are resolved structurally against the artifact map instead. And one readonly box, because a readonly or disabled box is a display, not a control: five of them had been reported as affordances the harness FAILED to drive, when the truth was that nobody can drive them. That is the whole of the 1051." -m "The worklist it hands on, headed by one real defect on fifteen pages. The rule .row2 .g span declares overflow hidden and text-overflow ellipsis with no white-space nowrap - an ellipsis cannot render on wrapping text, so the rule can never fire. It is one rule copied verbatim into fifteen pages, and every other ellipsis rule in the kit carries nowrap and is correct. A rule that cannot fire sitting beside the same rule written correctly is ADR-069 in CSS. Also handed on: 21 dead affordances, unread, a worklist and not a verdict; 4 ecology-lab textareas that time out on fill; selection-log spilling 15 to 37px and survey-design 9px, both of which survived the clientWidth correction; and 2 junk-rendered reports under field-notebook s Copy buttons." -m "Not done, and deliberately. No page changed, nothing was republished, no staleness is owed. The harness is NOT wired into run_all: twenty-one unread dead affordances would make a red suite before anyone has read them, and a red suite nobody can turn green gets ignored, which is how a gate becomes a decoration. verify_harness gates the harness; the harness reports on the kit. And hidden is honest but coarse - it does not yet distinguish unreachable from not reached by this walk." -m "Suite 61 of 61 jobs green, 4322 of 4322 checks passing (60 and 4300 before); verify_harness 22/22 is the new job." -m "Next, and falsifiable: I claim above that the twenty-one dead affordances are MOSTLY correct no-ops. I expect that to be wrong - at least three of the twenty-one are genuinely unwired, a handler never attached or attached to a selector that no longer matches. Falsifier: reading all twenty-one against the page source and finding every one is a legitimate no-op. That reading is the next slice, and it carries the fifteen-page white-space fix, which is one line and can be measured before and after by the harness that found it."
Step "git commit"

git push origin main
Step "git push"

git log --oneline -2
Write-Host ""
Write-Host "ADR-100 pushed." -ForegroundColor Green
