# ADR-042: Transcribing four grower soil recipes without laundering them

**Status:** Accepted and implemented — `docs/soil-recipes.html`, `tools/verify/verify_recipes.py` (238 checks), a false positive fixed in `verify_eco`.
**Date:** 2026-08-26
**Deciders:** Richmond
**Touches:** `tools/nav.py`, `tools/artifact_map.json`, `tools/verify/verify_eco.py`

---

## Context

Requested: SubCool's Super Soil, and the other well-known organic mixes growers pass around — The
Rev's TLO, Clackamas Coot's, BuildASoil's. These live on forums, in a book, and in a High Times
article, and they are copied between threads constantly, which is exactly how the quantities drift.

That drift is the whole problem this kit exists to refuse, so the page had to answer a harder
question than "what is the recipe": **how do you publish someone else's numbers without pretending
they are better evidenced than they are?**

## Decision

**Transcribe, do not improve.** Every quantity is reproduced as its source printed it, including the
ranges (`25–50 lb` of castings, `½–1 cup` of sweet lime), including the units the source chose, and
with the author and a link on every card. No number was rounded, converted or reconciled between
printings. Where printings disagree, the disagreement is stated.

**ADR-031's second gate, applied to a whole page.** The page opens by saying outright that these are
grower conventions with no soil test, no control and no replication behind them, that they are
nonetheless widely used and widely reported to work, and that the page will not tell you which is
best because nothing it has access to could answer that.

**Refuse the calculation that would look most impressive.** The obvious feature is a C:N or NPK total
per recipe. The page declines: these are volumes and weights of materials whose published analyses
vary by a factor of two, so any total would carry an error bar wider than the answer. It points at
Soil Bench instead, which computes C:N on dry mass from figures you supply for your own ingredients.

**The scaler multiplies one recipe; it does not convert between them.** Subcool's is stated per eight
bags of potting soil, the Rev's per 8-gallon batch, Coot's and BuildASoil's per cubic foot. Putting
all four on one denominator would mean inventing a bag volume none of the sources gave — and the page
says so under the control rather than quietly normalising.

## Three things the scaler got wrong first

**It converted at 1×.** `¾ cup` came out as `12 tbsp`. Arithmetically fine, editorially wrong: a
reader checking this page against the original would find a number that is not in it, and matching
the original is the entire point. Conversion now happens only for scaled values, where the published
wording no longer applies.

**It collapsed published ranges.** `25–50 lb` at a quarter batch printed `6.3 lb` — silently halving
the recipe and inventing a precision the source never gave. Both ends scale, or neither does.

**It printed quantities nobody can measure.** A quarter of `2 tbsp` is half a tablespoon, which is
not a spoon anyone owns. Below one tablespoon the answer is now in teaspoons.

All three are the same error in different clothes: **a transformation that is correct as arithmetic
and wrong as a claim about the source.**

## Verification

`tools/verify/verify_recipes.py`, 238 checks. The scaler is checked by **recomputation** — every
printed quantity is parsed back into base units and compared against the recipe's own number times
the multiplier — not against a table of expected strings (ADR-041). Fidelity is checked separately:
at 1× every quantity must equal its published string exactly.

Six seeded faults, six caught: range collapsed to its low end (32 checks fired), scaler off by 10%
(155), 1× no longer verbatim (22), a source URL dropped (2), sub-tablespoon left in tablespoons (2),
export stripped of its source (1).

## A false positive in the kit's own link checker

`verify_eco` failed the new page with `('soil-recipes.html', "'+esc(r.url)+'", 'missing file')`. It
extracts `href="..."` with a regex, and read a **JavaScript template literal** as a relative path.

That is ADR-040's defect class one instrument over: the row is not wrong about what it matched, it is
wrong about what the match *means*. The checker now skips an href carrying concatenation markers, and
that fix was canaried both ways — a genuinely missing file still fails, a templated href no longer
does.

The page was changed too, and would have been anyway: the source link is now set as a DOM property
instead of concatenated into markup. These URLs are page constants, so nothing could be injected
through them, but **an href built by string concatenation is the shape that carries the risk**, and
the safer construction also happens to be the one a static checker can read correctly.

## Consequences

44 of 44 jobs green, 3131 checks. The page is wired into the rail under "At the bench", published,
and stamped.

**The rule this leaves behind:** when you republish somebody else's numbers, every transformation you
apply — rounding, converting, normalising, tidying a range — is a claim that the transformation is
faithful. Most of them are not, and the ones that feel most like housekeeping are the worst offenders.
