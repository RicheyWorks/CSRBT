# ADR-051 — The kit contradicting itself

**Status:** accepted · 2026-08-26
**ADR-049: reachability is not staleness. ADR-050: staleness is not harm.
This one: a page being right is not the kit being consistent.**

## The defect

Every suite in this kit is **page-scoped**. Each drives its own page and asserts
that page is correct. Nothing had ever asked whether page A and page B agree.

`ecology-glossary`, under *Trophic transfer efficiency (Lindeman 1942)*, holds
the kit's researched position: the 10% figure is a **teaching convention, not a
constant**; Lindeman's own paper reported 0.1%–37.5%; later measurements run
about 1% to 40%. It ends with an explicit warning:

> "If you are using it to argue that a chain cannot be longer than *n* levels,
> the argument is only as strong as the efficiency you assumed."

Three pages made exactly that argument.

- **`ecology-lab-manual`** — "Use the ~10% energy-transfer figure to estimate how
  much of the producers' energy reaches your top predator." An instruction to a
  student, with no assumption named.
- **`food-web`** — "energy loss (~90% per level) usually caps chains at 4–5",
  inside the tool the glossary is the reference for.
- **`ecology-field-card`** — "nature caps at ~3–5 (≈90% energy lost per step)",
  on the card students carry into the field.

ADR-031's gate was applied on the reference page and never carried to the three
that use the number. Not a stale publish, not an unreachable defect: **the kit
disagreeing with itself, in the repo, today.**

The lab manual now takes 10% as a stated working assumption, asks the student to
redo the estimate at 1% and 40%, and says the sensitivity *is* the result. The
other two name the convention instead of reasoning from it.

## Four failed topic models, and why each looked reasonable

The check needs to know a sentence is *about* what the entry defines. Word
overlap seemed obvious and was wrong four times:

| model | failure |
|---|---|
| entry head words only | too narrow — food-web says "energy loss per level" and never says "transfer" |
| head + whole body | too wide — the body says "the source of the figure", so "use the 10% **slope** figure to estimate runoff" became topical |
| document frequency cap | cannot separate discourse from subject: across 111 entries "figure" appears in five, which any sane cap calls distinctive |
| one hop through the term graph | linked entries on *rather*, *than*, *never*, *cannot*; pulled in 27 entries including one on selection gradients, which handed the fixture the word "slope" |

The claim was never document-level. **"10%" is a defect only where it is a rate
of the thing the entry defines**, and that shows up within a few words of the
figure: "energy-transfer", "per level", "energy lost per step". So the test is
local — a 60-character window around the figure — and its vocabulary comes from
the entry's **first sentence**, a glossary definition being the most reliable
description of a subject there is, rather than from its commentary.

## Three findings about the checker itself

**Fixing the parser lost a true positive, and that was correct.** Before block
scoping, the field-card cell was caught — but only because the sentence splitter
had glued it to two neighbouring table rows and dragged *trophic*, *level* and
*chain* in with them. Correct boundaries lost the finding. A catch that depends
on a parsing accident is not evidence (ADR-039); the fix was a better topic
model, not worse boundaries.

**The hedge scope is the block, not the sentence and not the page.** The lab
manual's rewrite says "take 10% as a working assumption" and explains two
sentences later, in the same list item, that it is a convention. Sentence-scoped,
that reads as bare. Page-scoped, one disclaimer at the top would excuse every
claim below it. The block is what a reader takes in.

**The rule was written twice.** The live loop had one copy and the fixture runner
another. A mutation sweep killed five operators with **no fixture noticing**,
because every fixture went through the copy and every mutation landed in the
original — the connectance defect of ADR-039 exactly. One function, three
callers, and all nine mutants land.

Two further fixtures were themselves too easy and were rewritten: the complement
fixture said "energy **transfer** loss", handing the checker a head word the real
food-web line never contained.

## A narrowing I could not justify, and withdrew

`convention_figures` first took only figures stated *before* the hedge — the
convention (10%) but not the spread offered against it (0.1%, 1%, 37.5%, 40%).
A mutant widened it back and nothing noticed. Going to write the fixture that
justified the narrowing, I could not write an honest one: *"use the 40% transfer
efficiency to estimate…"* is the same error as using 10%. **The spread is the
range of what has been measured, not a menu of better constants.** The narrowing
was a precision tweak dressed as a semantic one; the wider rule is simpler and
more correct, and costs nothing because the locality test, not the figure set,
holds the false-positive rate down.

## Still open

- 33 other entries on the `audit_claims` worklist remain untriaged. Several look
  citable rather than unsourced — Reineke 1933 for the stand density exponent
  1.605, the 30–300 plate-count window, DBH at 1.37 m — and citing them is a
  different job from this one.
- Only one glossary entry currently hedges a percentage, so the check watches
  one subject. It grows with the glossary rather than with a list, but today its
  coverage is one entry wide and this ADR should not imply more.
- The `ecology-lab` claim that "80% of keys survive a generation, but only 57% of
  the physical nodes" is about the engine and is **measurable**. Asserted where
  it should be computed (ADR-041). Not addressed here.

## The rule this adds

> A page being right is not the kit being consistent. Where the kit has done the
> research and written down a position, every page that uses that number is
> bound by it — and nothing page-scoped can check that.
