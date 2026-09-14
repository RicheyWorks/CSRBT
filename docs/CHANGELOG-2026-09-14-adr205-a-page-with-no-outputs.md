# 2026-09-14 — ADR-205: a page with no outputs is not measured by the audit that measures outputs

**Two pages accepted twenty-nine and nineteen typed values apiece and offered no
way to get any of it out. The audit built to ask exactly *what does this page
hand over and does anyone read it* skipped both, silently, for months: it
enumerates output buttons, and a page with none produces an empty list, no row,
and no ledger entry.**

## Fixed

- **`cell-bench.html` and `micro-bench.html` produced nothing.** Not a copy
  button, not a CSV, not a print block. A haemocytometer count with its Poisson
  CV, a passage log with cumulative population doublings, a four-point standard
  curve and an unknown read off it, plate counts with TFTC/TNTC judgements, an
  exponential growth fit, disc-diffusion zones — all computed, none exportable.
  A morning at either bench ended with a screen you could photograph.
- **`audit_outputs` skipped a page with no output buttons** on a bare
  `continue`. That is the one shape it exists to catch. A page with no export
  now gets a row, and a judgement: under four entry controls it passes quietly
  (a glossary with a search box is not a data trap); at or above four it must
  hand something over or be **declared with a reason** in the ledger. What
  counts as an entry control is read from `harness.TYPED`, not restated, so a
  kind added tomorrow counts tomorrow.

## Added

- An **Export** pane on both benches: a bench sheet carrying the **inputs beside
  every result** and the page's own warnings **in the line** — an extrapolation
  outside the standards, a plate outside the countable window, points above
  OD 0.6 in a fit — plus a CSV per log. Every plate is carried **including the
  rejected ones**, because a CFU/mL without the plates that were excluded is a
  count nobody can audit. Every zone carries its **breakpoint source**, because
  this page ships no breakpoint table on purpose.
- `audit_outputs --declare-page PAGE --reason "..."`.
- `verify_outputs` 26 → 38, with two new fixtures: a page that takes records and
  hands nothing over, and a page that is right to hand nothing over. A rule that
  named both would be switched off within a week, and then the real ones would
  be invisible again.
- `mutate_outputs` 24 → 31, all killed.
- Both benches' science tasks press every new button and read what came out,
  with the sheet pinned against the figures their existing oracle already
  holds — 6.000×10⁵ live cells/mL, a 16.00 h doubling time, a cumulative PD of
  4.0, 9.900×10⁷ CFU/mL from two countable plates of three. **The kit is now at
  0 of 75 outputs that nothing reads**, with both ceilings at zero.

## Changed

- **A CSV is an instrument reading, not a float dump.** The first plate CSV
  handed out `147999999.99999997` for a plate the page displays as `1.480e+8` —
  eleven significant figures from a hundred and forty-eight colonies. Every
  derived column is written at the precision the screen shows. Caught by
  pinning the CSV in the page's task, which is the point of pinning it.
- Two new routes (`cell-bench.html#p-out`, `micro-bench.html#p-out`).

## Noted, not fixed

- **Neither bench keeps your work.** No autosave, so no outbox: a tab closed
  mid-session still loses everything. That is the next slice, and it is only
  possible now — a page that hands nothing over cannot say whether anything
  has left.
- **The bar is a count, not an understanding.** A page with three entry
  controls and a long accumulating log would slip under it. Nothing in the kit
  has that shape today.
