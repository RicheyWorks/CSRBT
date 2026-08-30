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

if (Test-Path "_to_delete\adr103.tgz") { Remove-Item -Force "_to_delete\adr103.tgz" }

git add docs/ordination.html
Step "git add the ordination crash fix"
git add docs/collection-sheet.html docs/stand-sheet.html docs/survey-design.html
Step "git add three echo pages"
git add docs/releve.html docs/ecology-lab.html docs/deployment-log.html
Step "git add three more echo pages"
git add tools/probe.py tools/probe_ledger.json
Step "git add the probe and its ledger"
git add tools/verify/verify_ord.py tools/verify/verify_kit_consistency.py
Step "git add the two suites"
git add tools/verify/counts.json
Step "git add counts"
git add "docs/ADR-103-the-chaos-was-pressing-buttons-nobody-can-reach-2026-08-29.md"
Step "git add ADR"
git add "docs/CHANGELOG-2026-08-29-adr103-two-css-fixes-and-a-crash.md"
Step "git add changelog"
git add push-adr103.ps1
Step "git add script"

git status --short

git commit -m "ADR-103: the chaos was pressing buttons nobody can reach" -m "ADR-102 claimed field-season s twenty-six uncaught throws and ordination s two were the same defect, and predicted that claim would be wrong. The replay was run. The claim is wrong twice over: they are not the same defect, and field-season has no defect at all. Twenty-six of ADR-102 s loudest findings were the instrument s." -m "field-season s crash reproduces in two actions and throws Cannot read properties of null reading day, because the page s game state is null until a season is started and the handler has no guard. But the button lives inside a div whose style is display none. Measured at load: the game card is display none, the button has zero size. A user cannot press it. The harness could, because of a fix I made in ADR-102: the chaos pass had been filtering its candidates on the visibility recorded in the snapshot taken at load, which reached a tenth of the page, and the correction removed the filter altogether. Neither trust the snapshot nor trust nothing was right. The pass now asks the page, at the moment it is about to act, whether this control is visible and enabled. Re-run at the same seed: field-season 26 findings to 0 with 80 of 100 actions skipped; across all pages 151 findings to 131, with 194 actions skipped as unreachable. That is the ADR-100 defect for the fifth time and in its purest form - a control judged from a state it cannot be in." -m "Second retraction. ADR-102 wrote that a 400-character entry breaking eight pages layout was the consequence of ADR-100 s dead white-space rule, now measured rather than predicted. It was not measured. It was two true facts joined by plausibility. Reproducing the edge value and asking the page which element is over the edge gives a bold element 4005 pixels wide and a code element 3065 pixels wide, both inside a verdict box echoing the entry back. No row2 span is involved anywhere. Retracted." -m "A third thing worth writing down: a seeded random walk is not comparable across a page change. The first attempt to show the CSS fixes working re-ran chaos at the same seed and found ethogram gone from 20 findings to 59. That number means nothing - the seed fixes the choices from the pool, and the pool is whatever the page is showing, so changing the page changes the walk. A random pass answers is this still a page; it cannot answer is this better than yesterday. Every before and after in this slice is the deterministic edges pass, which drives the same fields with the same values in the same order." -m "One real crash, found, read, fixed and shown fixed. ordination s two throws are on visible controls and reachable by an ordinary path. A failed parse sets the matrix to null and leaves the results standing, and both copy handlers guard on the results and then read the matrix. Run an ordination, paste a matrix that will not parse, press Copy coordinates: the guard passes because the results survived, and the handler reads sites off null. The Clear button clears both together, which is why the guard looked adequate - the results proxy for the matrix on one path out of two. Fixed in both places, because either alone leaves the other latent: a failed parse now drops the results with the matrix, and both copy handlers guard on what they actually read. Chaos at the same seed: 2 to 0. Three assertions in verify_ord hold it there." -m "Two CSS fixes were attempted and only one stands. white-space nowrap on the row2 span was applied to fifteen pages and taken back off all fifteen: with the line unwrapped, releve, micro-bench and soil-bench each run past a 390 pixel phone ONCE A RECORD IS IN THE ROW, and verify_rv, verify_mb and verify_soil all went red naming the row, the group, the span and the coverage cell. A fresh page shows nothing; the suites found it because they put records in first. So the repair is not a property on that rule, it is a change to the flex chain that rule sits in, and it is not made here. The fifteen pages are byte-for-byte what they were, and what replaces the fix is a count: verify_kit_consistency now asserts that the pages whose ellipsis rule cannot fire are still exactly fifteen, so a known-open defect cannot quietly spread to a sixteenth. That check was wrong on its first run in the way this kit keeps finding - it read the comment EXPLAINING that white-space was missing as though it were the declaration, and reported the defect fixed on all fifteen pages. Comments are stripped before the rule is read." -m "The fix that stands is overflow-wrap anywhere on the verdict, code and table-cell surfaces of the six pages that echo an entry back, because an entry with no space in it has no break opportunity. Measured on the same fields with the same values: collection-sheet 1 to 0, stand-sheet 1 to 0, survey-design 2 to 0, releve 1 to 0, ecology-lab 8 to 7, deployment-log 1 to 1 - sixteen findings down to eight. Four pages clear. ecology-lab keeps its four NaN readouts and two table spills and deployment-log keeps a 41 pixel spill on a nine-digit number; both are a different cause, not touched here, and named in the worklist rather than quietly folded into the win." -m "The shrinker. A twelve-step sequence ending in a crash is a story; the two steps that cause it are a bug report. probe.shrink is delta debugging over the replay - drop a step, replay FROM A RELOAD, keep it if the same invariant still breaks. Replaying from a reload rather than from wherever the last attempt left the page is the whole discipline: a sequence that only reproduces from a state nobody reset has not been shrunk, it has been misread. ecology-lab twelve steps to one: 1e308 into one field spills a table 3006 pixels. survey-design eleven to one: a script tag into a text field spills 50 pixels. ethogram one to one: minus nought point nought nought nought one spills a row 914 pixels. tree-proofs twelve to two: a 400-character k, then Walk it, renders NaN. food-web twelve to three: a 400-character species name, then Add, spills the SVG 3662 pixels. And two - farm-scout and selection-log - NOT CONFIRMED from a reload, which is the honest half: those findings depend on state the shrinker could not reconstruct, and the run says so rather than shipping twelve steps as though they were the answer." -m "Seven pages changed, which is the first time in this series. ADR-100, 101 and 102 each ended with no page changed and nothing republished. Seven published artifacts are now BEHIND: collection-sheet, deployment-log, ecology-lab, ordination, releve, stand-sheet and survey-design. Until they are republished a green audit of docs says nothing about what a reader of those artifacts sees." -m "The suite is 63 of 64 jobs green, 4461 of 4462 checks passing, and the one red job is right. verify_publish_reach asserts that every page where the escaping injection is reachable is published current, and three of them are now behind. This is the first slice in the series to ship red, and the redness is not a defect to route around: it is the kit refusing to call itself verified while a fix exists only in the repository. It clears when the seven pages are republished and stamped with tools/publish_state.py --stamp." -m "Worklist: ecology-lab s NaN to infinity from 1e308 in a value slot; the row2 span repair, which needs a flex-chain change rather than the property that regressed three pages, and its untruncated bold sibling; deployment-log s 41 pixel spill on a nine-digit number; and two findings the shrinker could not reproduce from a reload, which are worth more as a question about the shrinker than as bug reports." -m "Next, and falsifiable. Five of the seven shrunk repros are a single action into a single field, which suggests the kit s fragility is concentrated in what a field accepts rather than in sequences - and if so the edges pass should already have found every one of them, because it drives every field with every one of those values. I claim it did not. I expect at least two of the five to be findings edges never reported, because edges drives a field from the page s opening state and chaos reached it with rows already added: the same field, in a state the deterministic pass never puts it in. Falsifier: cross-referencing the five shrunk repros against the edges ledger and finding every one of them already there. If the falsifier fires, chaos is buying nothing that edges does not, and should be re-scoped to sequences rather than values."
Step "git commit"

git push origin main
Step "git push"

git log --oneline -2
Write-Host ""
Write-Host "ADR-103 pushed." -ForegroundColor Green
Write-Host ""
Write-Host "SEVEN PAGES ARE NOW BEHIND THEIR PUBLISHED ARTIFACTS." -ForegroundColor Yellow
Write-Host "verify_publish_reach stays red until they are republished and stamped:" -ForegroundColor Yellow
Write-Host "  collection-sheet  deployment-log  ecology-lab  ordination" -ForegroundColor Yellow
Write-Host "  releve  stand-sheet  survey-design" -ForegroundColor Yellow
