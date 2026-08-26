# ADR-057 — The policy document is the checker's anchor

**Date:** 2026-08-26
**Status:** accepted
**Extends:** ADR-031 (the honesty gate), ADR-051 (the kit contradicting itself)

## The gap

ADR-031 sorts every displayed number into three gates. Gate 2 reads:

> **Ship it labelled a convention** — widely used, useful, but arbitrary or
> contested. Examples: Landis & Koch κ bands; A260/A280 ≈ 1.8; the 30–300 plate
> window; 20–50 cells per haemocytometer square; 40–45 °C for drying fungal
> vouchers. The word *conventional* must appear beside it.

Nothing checked it. Micro Bench spends a paragraph on whose window 30–300
actually is — *"There is no single countable range"* — and then the glossary,
the field card and the landing page each stated the same figure flatly as
**"the 30–300 rule"**. Six blocks across four pages stated a category-2 figure
with no label at all, including the glossary entry whose own headword is
`30–300 rule`.

This is ADR-051's defect — the kit contradicting itself — in a shape ADR-051's
rule 1 cannot see, because rule 1 anchors on a hedged **percentage** and this is
a hedged **range**.

## The decision

**The figures come out of ADR-031's own category-2 paragraph, not out of a list
in the checker.** A retyped list would be a second copy of the policy, free to
drift from it, which is ADR-039 exactly. Add a figure to the ADR and the rule
starts enforcing it with no edit to the checker.

Enforcement is per **block a reader takes in at once**, with two refinements
that fell out of getting it wrong:

- **A heading is not a claim.** `<h3>The 30–300 window</h3>` names the prose
  under it, and a glossary `<dt>` names its `<dd>`. So a heading's text is
  *prefixed to the following block* rather than judged alone. That is also what
  makes the glossary catchable: the figure is in the `<dt>` and the words are in
  the `<dd>`.
- **A table row is one unit.** `<td>` is deliberately not a block boundary. A
  field-card row is "metric | what it reads"; splitting the cells would leave
  the only satisfying fix as cramming the label into the narrow nowrap metric
  cell — a checker teaching a page to get worse.

A `<div class="card">` holding five paragraphs is **not** one unit. ADR-051
chose block scope over page scope so a disclaimer at the top could not excuse
everything below it; a disclaimer three paragraphs *below* excuses nothing above
it for the same reason. Micro Bench was flagged on that basis and the fix is an
improvement: the label now reaches the reader at first contact, in the heading
and the opening sentence, instead of three paragraphs later.

## Where this deliberately disagrees with ADR-031

ADR-031 asks for a **word**: *"The word conventional must appear beside it."*
What it wants is a reader able to tell a convention from a constant.
`fungal-characters` says 40–45 °C is *"a starting point to adapt, not a
standard"*, which does that job and never says "convention". Enforcing the token
would have forced an edit that made honest prose worse.

So the checker accepts the vocabulary rule 1 already uses, plus the word itself.
**ADR-031's wording is the narrow thing here**, and this ADR records that rather
than letting the checker quietly disagree with the policy it enforces.

## What the fix also fixed

Micro Bench named FDA BAM, USP ⟨1227⟩, ASTM and Breed & Dotterrer — everyone
except the standard its own number comes from. **APHA Standard Methods 9215** is
the pour-plate source of 30–300 (its membrane-filter window is 20–200); it is
now cited on the bench, in the glossary and on the field card, alongside BAM's
25–250 so the reader can see the two disagree.

Both existing attributions were verified against primary sources before the
edit: FDA BAM Chapter 3 gives *"The suitable colony counting range is 25-250"*,
and USP ⟨1227⟩ gives 25–250 for bacteria and 8–80 for *Aspergillus niger*.

## The two block models that were wrong first

1. **Split on every tag.** `<b>20–50</b> cells per square` became a block holding
   just the figure, cut off from the sentence labelling it. Eight of ten
   reported violations were that artefact.
2. **Normalise only the entity.** The kit writes `&ndash;`, a literal en dash
   and a hyphen interchangeably. Reading only `&ndash;` made ADR-031's own
   example list parse as containing **no ranges at all**, and the rule reported
   a clean kit — passing on nothing, which is the ADR-039 failure. Three
   fixtures, one per dash form.

## Canary

Ten mutants, all caught: rule never fires; label ignored; dash normalisation
dropped; category-2 list returns empty; heading text discarded; carry computed
but unused; `td` split restored; policy page no longer exempt; the word
"convention" removed from the vocabulary; and a page regressing to its old bare
wording.

## Cost

`verify_kit_consistency.py` 24 → 41 checks. Six blocks edited across four pages,
plus a `.who` rule for Micro Bench. 49/49 jobs green, 3520 checks.
