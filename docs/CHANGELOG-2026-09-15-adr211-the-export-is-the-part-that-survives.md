# 2026-09-15 — ADR-211: the screen is where the work is done and the export is the only part that survives the tab

**Of the 317 figures the exporting pages of this kit compute, 132 appeared in
nothing those pages hand over. The ethogram had three exports of a scored session
and Cohen's κ was in none of them. The soil bench exported its mix recipe and not
one of the fourteen figures of its compost log. Every audit in the kit was green
while this was true: `read-report` saw the figure, `audit_outputs` saw the button,
and nobody had put the two readings side by side.**

## New

- **`tools/audit_carried.py`** — presses every control that hands something over
  (`audit_outputs`' rule, asked rather than copied), collects the payloads, and
  checks every figure `read-report` sees against them. CARRIED or LOST, a ceiling
  per page that may not rise, and an exemption that needs a reason.
- **`tools/verify/carried`** — 44 checks over six fixtures and the oracle on its
  own: notation, precision, ratios, and the figure with no number in it that is
  not measured rather than counted lost.
- **`tools/mutate_carried.py`** — 24 mutants, 1 known equivalent with its reason.

## Fixed — twelve pages now hand their own analysis over

- **`ethogram.html`** — Cohen's κ, the raw agreement and the agreement expected
  by chance now leave with the session they are about.
- **`soil-bench.html`** — a new **Copy the bench sheet** on the Compost pane: the
  compliance tally, the eighteen temperatures in order, the blend and the mix
  ratings. The page's only export had been the mix recipe, so a pile logged for a
  month left no file at all. Its task presses the new button and holds the bytes,
  so it is not one more export nothing reads (ADR-153).
- **`selection-log.html`** — the differential S, the intensity i, the gradient β,
  its SE and the mean after selection. The study sheet had carried n, mean, SD and
  R per trait: the inputs to the analysis and not the analysis.
- **`field-notebook.html`** — both diversity panels and the whole dispersion
  panel.
- **`breeding-bench.html`**, **`cp-bench.html`** — a `derived` section in the
  bench sheet: the selection response, the two inbreeding rates, the isolation
  distance against its citation, the salt left in the pot, the mix ratings, the
  dormancy tally.
- **`deployment-log.html`** — one planning block, read by the field sheet and the
  CSV, carrying what the four planners worked out.
- **`farm-scout.html`**, **`ordination.html`**, **`collection-sheet.html`**,
  **`releve.html`**, **`stand-sheet.html`**, **`pheno-tracker.html`**,
  **`cell-bench.html`**, **`food-web.html`** — the figures each page computes and
  had been keeping to itself.

## Declared

Three figures are right to stay on the screen, each with its reason in the
ledger: the relevé's "taxa in pack" and "families", and the stand sheet's "known
interactions". All three describe a reference pack the reader loaded, not the
site they recorded.

## Open

**132 → 32, and the 32 are one page.** The ecology lab's export is a `.eco`
PROTOCOL — the lines you would run — and by design it carries inputs and
hypotheses rather than results. Giving it a results block changes what an `.eco`
file means, and belongs in its own slice.
