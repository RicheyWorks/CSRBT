# ADR-098 — A signpost is not a claim, and an unknowable quantity has no arithmetic to show

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-031 (the three-way provenance gate), ADR-051 (the kit contradicting itself),
ADR-061 (silent exclusion with a plausible face), ADR-069 (a check that cannot fail is not a check),
ADR-077 (a sentence about the rule can break the rule), ADR-094 (a worklist with a front),
ADR-097 (the worklist was being worked in the wrong copy)

ADR-097 handed on three `near` claims and one instruction: run `publish_state.py --verify` on a
handful of pages **before** the next slice edits anything. This slice did that, then worked the three.
Two were real defects on one page. The third is sound, and the reason the finder cannot see that it is
sound turns out to be worth more than the claim.

## 1. The falsifier check, and why it is weak evidence today

ADR-097's falsifier: *any of the forty drifting again before it is deliberately republished.* The
three oldest published versions — `tree-proofs`, `tree-visualizer` (both 2026-08-25) and `greenhouse`
(2026-08-26) — were re-read from the live URL before anything was edited. **All three: zero drift.**

That is a pass, and it is close to vacuous, which is worth saying rather than banking. ADR-097
finished its sweep roughly forty minutes earlier and nobody opened the artifact editor in between, so
the check could only have fired on an edit nobody made. Its value is as a habit for a slice that
starts a day or a week later, not as evidence today. **The falsifier that had teeth in this slice is
in §6**, where a page was published repo → live for the first time in three slices and the publish
was measured rather than assumed.

## 2. The signpost that was read as a claim

`collection-sheet`'s dryer log carries a help line under the DNA-subsample dial. It read:

> Take it before the dryer. Silica beats any drying temperature for sequencing; see the Method tab on
> where the 50 °C figure comes from and who disagrees with it.

The finder flagged it for the `50 °C`. Remove the number — "the drying-temperature figure" — and the
flag disappears. The sentence makes no claim about 50 °C; it points at where the claim is discussed.
A sentence *about* provenance was being asked for provenance, which is ADR-077's shape.

Except the pointer was wrong. The 50 °C discussion — the Wang, Liu and Xu (2017) paragraph, the
practitioner rule, the disagreement — is in `p-vou` (lines 584–639), the Vouchers tab, in the note
**directly under that same log**. The Method pane `p-met` (639–808) has seven headed cards and not one
of them is about drying. The help line sent the reader to the one tab that does not carry what it
promised.

So the flag was a true positive by accident: the finder pointed at a number, and the number was
sitting in a broken cross-reference. Corrected to *"The note under this log says where the 50 °C
ceiling comes from and who disagrees with it."*

## 3. The claim with no number, which no run of this finder could ever report

The same help line asserted **"Silica beats any drying temperature for sequencing."** That is a
comparative, it is load-bearing — it tells a collector what to do with their only DNA subsample — and
it is unsourced. The finder's two tests are a number carrying a unit, and a comparison written with a
digit. A comparative in words takes neither. **No run of `audit_claims.py`, at any strictness, would
ever have reported it.** It was found by reading the sentence the finder had flagged for a different
reason.

Replaced with what the page can actually support: silica is the conventional choice for a DNA
subsample, and its virtue is that it takes the dryer out of the question entirely.

This is now named in the tool's own docstring. A blind spot a reader can find in the docstring is a
different object from one they discover by trusting a clean run (ADR-061).

## 4. The exemption that rewards arithmetic, not sourcing

The third claim was `micro-bench`:

> **Above 300** colonies merge, crowd, and compete for nutrients, so you undercount by a growing and
> unknowable amount. This is a **bias**, not noise, and more plates will not fix it.

Its card is the best-sourced passage in the kit: `APHA Standard Methods 9215` named in the lead-in and
again below, `FDA BAM`, `USP <1227>`, `ASTM`, and Breed and Dotterrer's 1916 measurement, with the
window called "a convention rather than a constant" in as many words. Its sibling bullet, **Below
30**, is not flagged.

The two differ in one respect, and it is not sourcing. Strip the arithmetic out of the Below-30 bullet
in a scratch copy — leave "thirty colonies carry about 18% relative error and ten carry about 32%",
delete `CV = 1 ÷ √N` — and the finder reports it, identically, with its provenance untouched.

**The derivation exemption is a showable-arithmetic test, not a provenance test.** The consequence is
sharper than the observation: a claim whose content is that a quantity *cannot be computed* can never
take that exit. "You undercount by a growing and unknowable amount" has no working to show, and saying
so is the claim. The finder rewards the bullet that can do a sum and penalises the one whose honest
content is that no sum exists.

**`micro-bench` was not edited.** Adding the word "conventional" to that bullet would have cleared the
flag and told the reader nothing the card does not already say twice. That is tuning the page to the
check, which is ADR-094's failure mode in miniature. The claim is triaged sound; the asymmetry is now
asserted instead.

## 5. What was asserted instead

`verify_claims_triage` gains sixteen checks (30 → 46):

* **A seeded pair.** Two sibling list items, neither carrying a provenance token and neither near one,
  differing only in whether the arithmetic can be written down. Exactly one is reported, and it is the
  one that cannot show its working. If that ever changes, the suite says so.
* **The same pair on the real page.** `micro-bench`'s above-300 bullet is reported; its below-30
  sibling is not.
* **The provenance the flagged bullet rests on**, held in place: APHA 9215, the convention wording,
  Breed and Dotterrer 1916 — and that the bullet itself carries no `=`, `÷` or `√`, which is *why* it
  cannot take the exit.
* **The four corrections** on `collection-sheet`.

`audit_claims.py` gains a docstring section naming both blind spots. **No rule changed.** The finder
behaves exactly as it did; it now says what it cannot see.

## 6. A helper that could not see what it was checking

Two of the new assertions failed on first run for a reason that had nothing to do with the page. The
suite's `text()` helper strips tags with `<[^>]+>`. A page's JavaScript contains bare `<` and `>` —
comparisons, arrows — so the regex pairs them off and swallows whole spans of script. Every claim this
kit renders from a widget's `help:` option lives in a script string.

An assertion about one of those, written against `text()`, does not fail. It looks somewhere else and
passes. `ck("Silica beats any drying temperature" not in cs, ...)` would have been **green before the
edit** — the string was there and the helper could not see it. A `raw()` reader was added, with the
reason written beside it, and the four script-string assertions moved onto it.

This is the ADR-069 shape in a helper rather than a check: a predicate that cannot observe its subject
is not a weak check, it is a decoration.

## 7. The publish, measured

`collection-sheet` was published repo → live — the first publish in three slices, after ADR-096 and
ADR-097 both ran live → repo. The live copy was then re-read from the URL and diffed: **zero drift**,
and the entry re-stamped `via "read"`. `published.json` still reads **40 current, 40 measured from the
live page, 0 stamped at publish time.**

That is ADR-097 §5's check applied to this slice's own work, inside the same slice, rather than left
for the next one to discover.

## 8. The numbers

```
audit_claims.py  before this slice   2 pages, 3 claims, 0 BARE, 3 near
audit_claims.py  after               1 page,  1 claim,  0 BARE, 1 near

the worklist, since ADR-094      71 -> 41 -> 15 -> 3 -> 1

suite                            60 of 60 jobs green, 4295 of 4295 checks
                                 (4279 before; +16, all in verify_claims_triage, 30 -> 46)
publish_state                    40 current, 40 measured from the live page, 0 publish-stamped
pages read from the live URL     5   (3 falsifier spot-checks, collection-sheet before and after)
pages edited                     1   docs/collection-sheet.html, 4 lines
pages published                  1   collection-sheet, verified at the URL afterwards
```

## 9. What is not done

* **One `near` remains, and it should.** `micro-bench`'s above-300 bullet is sourced. The number 1 is
  the correct steady state for this finder on this kit, not a residue to be driven to zero — and
  driving it to zero is available at the cost of one redundant word, which is precisely why it should
  not be spent.
* **The no-number blind spot is named, not closed.** Nothing in the kit finds an unsourced comparative
  written in words. That is a reading problem, and pretending a regex will solve it would be worse
  than the gap.
* **No page logic changed.** Four prose lines on one page; no formula, no control flow. No mutation
  sweep is owed.

**The next prediction, and its falsifier.** The `text()` defect in §6 was found because two assertions
failed loudly. I expect there are assertions elsewhere in `tools/verify/` that read script content
through the same tag-stripping helper and are quietly passing on text they cannot see — the
**decorations**, not the checks. **Prediction: at least one such assertion exists in a suite other than
`verify_claims_triage`. Falsifier: a sweep of every `re.sub(r"<[^>]+>"` reader in the suite showing
that no assertion built on one names a string that only occurs inside a `<script>`.** The sweep is
cheap, it is mechanical, and it is the next slice.
