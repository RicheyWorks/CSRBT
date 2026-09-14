# ADR-205 — A page with no outputs is not measured by the audit that measures outputs

**Two pages in this kit accepted twenty-nine and nineteen typed values apiece — haemocytometer counts, a passage history, a standard curve, plate counts, a growth curve, zone diameters — and offered no way to get any of it out. Not a copy button, not a CSV, not a print block. The audit built to ask exactly *what does this page hand over and does anyone read it* skipped both, silently, for months: it enumerates output buttons, and a page with none produces an empty list, no row, and no ledger entry.**

## 1. The shape the instrument could not see

`audit_outputs` walks every page, finds the controls whose name says they hand
something over, presses each one and asks what came out. It is a good audit. It
has one line in it:

```python
if not r.get("buttons"):
    continue
```

Which means the one page shape it exists to catch — **a page that takes data in
and gives nothing back** — is the one shape it cannot report. Not as "0 held of
0": as nothing at all. The kit's total read *3 of 75 outputs leave a page with
nothing reading them* and was true, and the two worst pages in the kit were not
in the denominator.

**The absence of a row is the loudest thing a ledger can say**, and this one was
saying it into a wall.

## 2. What the two pages were

The **cell bench**: a haemocytometer count with its Poisson CV, a seeding
calculation, a doubling time, a passage log with cumulative population
doublings, a four-point standard curve with an unknown read off it, a
Beer–Lambert concentration, A260/A280/A230 purity ratios, and a mitotic index.
All of it computed, none of it exportable.

The **micro bench**: plate counts with TFTC/TNTC judgements and a mean CFU/mL, a
dilution plan, an exponential growth fit, and disc-diffusion zones interpreted
against breakpoints the user enters. Same.

A morning at either bench ended with a screen you could photograph.

## 3. The exports, and what they carry

Both pages gain the kit's convention: an **Export** pane with a bench sheet and
a CSV per log, copied through one `copyText` that marks on the clipboard's
answer rather than on the click (ADR-203).

**The sheet carries the inputs beside the results.** A concentration without its
chamber factor and dilution, a doubling time without the interval it was
measured over, an unknown without the standards it was read off — each is a
number nobody downstream can check, and a sheet of answers alone would make this
page a worse record than a notebook rather than a better one.

**And it carries the warnings.** Where the page refused a reading on screen — an
absorbance off the end of the standards, a plate outside the countable window,
points above OD 0.6 in an exponential fit — the sheet says so **in the line**. A
caveat that lives only on a screen the reader has closed was never given.

**Every plate is carried, including the rejected ones**, marked TFTC or TNTC. A
CFU/mL reported without the plates that were excluded is a count nobody can
audit, and a series where every plate fell outside 30–300 is a result in itself
rather than an absence of one.

**A zone carries its breakpoint source.** This page deliberately ships no
breakpoint table, because those are revised annually and a stale "susceptible"
is worse than no output; an export that dropped the source would undo that
refusal on the way out of the tab.

## 4. A CSV is an instrument reading, not a float dump

The first version of the plate CSV handed out `147999999.99999997` for a plate
the page displays as `1.480e+8` — eleven significant figures from a hundred and
forty-eight colonies, straight out of binary floating point. Every derived
column is now written at the precision the screen shows. Caught by pinning the
CSV in the page's task, which is the point of pinning it.

## 5. The rule, so it cannot happen again

The skip is gone. A page with no output button now gets a row, and a judgement:

- A page with **fewer than four entry controls** hands nothing over and passes
  quietly. A glossary with a search box is not a data trap.
- A page **at or above four** must either hand something over or be **declared**,
  with a reason, in the ledger — `--declare-page PAGE --reason "..."`. A list of
  pages this audit is choosing not to care about is only useful if each line
  says why.

The bar is a judgement and is written down rather than tuned: four is above a
lone search box and far below the nineteen and twenty-nine that prompted it.
What counts as an entry control is read from `harness.TYPED` rather than
restated, so a kind added tomorrow counts tomorrow — the same ADR-141 rule this
whole slice is an instance of.

## 6. And the exports are held, not just present

Both pages' science tasks press every new button and read what came out, with
the bench sheet pinned against the figures the task's existing oracle already
holds — 6.000×10⁵ live cells/mL, 90.9% viability, a 16.00 h doubling time, a
cumulative PD of 4.0, 9.900×10⁷ CFU/mL from two countable plates of three. The
export is therefore held to the same numbers the screen is, rather than merely
existing. Both pages' ceilings are set to zero, so an export added tomorrow that
nothing reads fails the day it appears.

## 7. What is checked

`verify_outputs` 26 → 38, with **two** new fixtures rather than one: a page that
takes records and hands nothing over, and a page that is right to hand nothing
over. A rule that named both would be switched off within a week, and then the
real ones would be invisible again — so the check that the quiet page is *not*
named carries as much weight as the check that the trap is.

`mutate_outputs` 24 → 31, all killed. The skip reinstated; the bar removed so
every quiet page is named; a declaration that does not exempt; a declaration
that stores no reason; a declaration accepted with no reason; a page with no
outputs given no ledger row; and the entry-kind list restated locally instead of
read from `harness.TYPED`.

## 8. What this does not do

**Neither page keeps your work.** They have no autosave and therefore no outbox:
a tab closed mid-session still loses everything. That is ADR-206's slice, and it
is only possible now — a page that hands nothing over cannot say whether
anything has left.

**The bar is a count, not an understanding.** A page with three entry controls
and a long accumulating log would slip under it. Nothing in the kit has that
shape today; if one arrives, the bar is one number in one file.
