# ADR-211 — The screen is where the work is done and the export is the only part that survives the tab

**Of the 317 figures the exporting pages of this kit compute and put on the screen, 132 appeared in nothing those pages hand over. The ethogram had three exports of a scored session — the interval CSV, the .eco sheet, the time-budget CSV — and Cohen's κ, the raw agreement and the agreement expected by chance, the entire panel that says whether the session is worth anything, were in none of them. The soil bench exported its mix recipe and not one of the fourteen figures of its compost log. Every audit in this kit was green while this was true, by construction: `read-report` saw the figure, `audit_outputs` saw the button, `audit_readable` saw that the figure was legible, `verify_restored` saw that it came back after a reload. Nobody had ever put the two readings side by side.**

## 1. Two audits about the channel, and none about the envelope

ADR-153 asked whether anything READS what a page hands over — 80 buttons across 19
pages, and one task reading one of them. ADR-208 asked whether a button that is
supposed to hand something over hands anything over at all — eighteen that did
not, none of them named.

Both are questions about the channel. Neither opens the envelope.

The question inside it is the one these pages exist for. A relevé is filled in a
wet field on a phone and then has to become a row in somebody's analysis. An
ethogram session is scored once and argued about for a year. The screen is where
the work is done; the export is the only part that survives the tab. A page that
renders a correct analysis and exports half of it has lost the half it did not
export, and nothing here could see it.

`tools/audit_carried.py` opens each page, replays its own task — the same entry
`entry_reach`, `audit_outputs` and `audit_restored` make, and necessary here for
the same reason: an export pressed on an empty page carries nothing, and every
figure would read as lost for a reason that is about the audit. Then it presses
every control that hands something over, collects the payloads, and asks
`read-report` what the page is showing.

    CARRIED   the number the page shows is in at least one payload
    LOST      it is in none of them — the worklist

**Which controls those are is not decided here.** It is `audit_outputs.candidates`
— a label that says it hands something over, minus whatever the gateway's own
risk ladder calls destructive, minus any kind the door would not press. A second
copy of that rule in this file is the list ADR-204, ADR-205, ADR-207, ADR-208 and
ADR-210 each found drifting out of step with the one reader that read it.

## 2. Most of this file is about what counts as the same number

A figure is matched as a NUMBER, not as a string, and getting that wrong in
either direction ends the audit.

`6.00×10⁵` on the screen is `600000` in a CSV. `1,234` is `1234`. `25%` is `25`.
A minus sign may be U+2212 and an exponent may be superscript digits. A string
comparison reported 171 losses where 135 existed, and an audit that reports a
third more than it should is an audit that gets switched off in a week.

Three corrections were needed after that, each found by a page:

- **The comparison is made at the screen's precision, not the export's.** A file
  carrying `0.7217` has carried the `0.72` on the screen; one carrying `0.7` has
  not.
- **Within the last digit, not by rounding both sides to it.** The greenhouse
  shows g/kWh to two places and exports it to three: 4.8249 is `4.82` on screen
  and `4.825` in the file, which rounds back to 4.83. The figure was exported in
  MORE detail than the page shows it and the audit called it lost. **Double
  rounding** — the shape ADR-087 and `audit_ties` are about — arriving in the
  instrument rather than in a page.
- **And the exponent counts.** `2.83×10²` is written to three significant
  figures, so its last digit is a whole unit, not a hundredth. A tolerance read
  off the mantissa alone called the cell bench's `2.83×10² µM` lost against a
  file carrying `2.834e+2` — the same number, one figure further out.

**The bias is towards CARRIED, on purpose.** A bare `4` matches any `4` anywhere
in any payload, including a row count that has nothing to do with it. So this
under-reports: every LOST is a figure whose value appears NOWHERE in anything the
page hands over. A finder that cries wolf is worse than one that misses, and this
is why the rule is a ratchet on a count rather than a per-figure certificate.

## 3. What was staying on the screen

- **ethogram** — κ, the raw agreement and the agreement expected by chance. The
  reliability panel is the thing that says whether two observers scored the same
  session the same way, and it left with nothing. Neither did the sequences it
  was computed from.
- **soil bench** — fourteen of fourteen. The compost log, the compliance tally
  against the standard, the peak, the blend and the mix ratings. The page's only
  export was the mix recipe: a pile logged for a month left no file at all.
- **selection log** — the differential S, the intensity i, the gradient β, its
  standard error and the mean after selection. The study sheet carried n, mean,
  SD and R per trait: the INPUTS to the analysis and not the analysis.
- **field notebook** — both diversity panels and the whole dispersion panel:
  Shannon, evenness, effective, mean per quadrat, variance-to-mean and Morisita.
  The export carried the raw tallies.
- **cp bench** — the salt left in the pot after a season of top-ups, the mix's
  three ratings, the dormancy tally, the losses.
- **farm scout** — the stop count, the pest total, the pollinator indices and
  the sowing rate the germination test implies.
- **ordination** — the shape of the matrix it was fitted from, the sparsity, the
  number of pairs, and how many random starts agreed. A file of coordinates that
  a reader has to take on trust.
- **collection sheet** — collections per 100 m², grams per m², collections per
  hour: the three figures that make two foragers' sheets comparable at all.
- **relevé** — the effective taxa and the adjusted FQI.
- **stand sheet** — a height measured with the clinometer, in metres and in feet,
  unless somebody remembered to press "use this height" first.
- **pheno tracker** — the run mean and the keeper mean. The export carried the
  differential and not the two numbers it is the difference of.
- **cell bench** — the cells a seeding needs, which is the figure that panel
  exists to work out.
- **food web** — the producer count.

## 4. What was done

Every page above now hands its own analysis over. Most were a line or two in an
export that already existed; the soil bench needed an export that did not — **Copy
the bench sheet**, on the Compost pane, carrying the compliance tally, the
eighteen temperatures in order, the blend and the mix ratings — and its task was
extended to press it and hold the bytes, so it is not one more export nothing
reads (ADR-153).

Three figures are DECLARED right to stay on the screen, each with its reason in
the ledger: the relevé's "taxa in pack" and "families", and the stand sheet's
"known interactions". All three are properties of a reference pack the reader
loaded, not of the site they recorded; the packs travel as their own files.

The breeding bench and the deployment log needed the same treatment as the cp
bench: a `derived` section in the sheet carrying what the page worked out
alongside what was typed into it. The deployment log's four planners — the
acoustic budget, the clock drift, the flight plan, the logger's memory — now
write one planning block read by one function, so the field sheet and the CSV
cannot drift apart.

**132 to 32, and the 32 are one page.** The ecology lab still works out 32
figures that nothing it hands over carries, and that is not the same defect as
the others: its export is a `.eco` PROTOCOL — the lines you would RUN — and by
design it carries inputs and hypotheses rather than results. Giving it a results
block is a real change to what an `.eco` file means and belongs in its own slice,
not smuggled in at the end of this one.

So the count is a CEILING per page, and it may not rise: a page that grows a
figure its exports do not carry fails the day it does, and the ceiling comes down
as they are fixed. The count is not zero and this record does not pretend it is.

## 5. The instrument is broken on purpose

`tools/verify/carried` — 44 checks over six fixtures built from one template, and
the oracle tested on its own: the notation rules, the precision rules, the ratio
rule, and the figure with no number in it that is NOT MEASURED rather than counted
lost (a phenophase is a word, and a rule demanding every figure appear in a CSV
would report every page in this kit as losing most of what it shows).

`tools/mutate_carried.py` — 24 mutants, one known equivalent with its reason
written down (each page measured in its own browser context: these pages autosave,
and a shared context would carry one page's sheet into the next one's export —
ADR-209's defect, found next door — but no fixture here can show it, because the
fixtures deliberately keep nothing).

## 6. The shape, for the seventh time

ADR-141: a rule enforced over a list only one reader reads. This one is its
inverse and the same failure — a QUANTITY computed in one place and published in
one place, with no reader holding the two together. The page's analysis and the
page's export were both correct on their own terms, and correct on their own terms
is what every audit in this kit was measuring.
