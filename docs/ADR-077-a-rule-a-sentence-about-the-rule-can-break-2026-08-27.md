# ADR-077: A rule a sentence about the rule can break

**Status:** Accepted and implemented — `tools/mutate.py` (declared roles, one predicate, two
guards that returned before the cross-cutting suites), `tools/verify/verify_eco.py` (105 → 138),
`tools/verify/verify_mutate.py` (30 → 47), `tools/verify/verify_focus_slice.py` (15 → 22),
role declarations in six suites.
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-039, ADR-041, ADR-046, ADR-052, ADR-061, ADR-072, ADR-076

---

## 1. What this started as

ADR-076 swept `ecology-lab.html` at thirty mutants and killed eighteen. **Sixty percent**, on the
flagship page, and twelve questions to answer. This ADR answers all twelve, and then reports what
answering them turned up about the sweep itself, which is the larger finding.

The page ends the arc at **30 killed of 30 — 100%**, with no survivors to defend. That last figure
took two runs and the second one is the honest one: the first said 29/30, and the mutant it left alive
was alive only because I had wrongly excluded the suite that kills it. See §4.

## 2. The twelve, and what each one was hiding

**The paste path had never been driven.** Three survivors sat in `chipify()`'s `parse()` — the
function behind *"✎ edit as text (paste from a spreadsheet)"*. Everything the kit had ever done to
that widget drove the **add row**: type a name, type a number, click Add. Nobody had ever pasted.
The paste path is the one a person with real data uses, and inverting `if(!line) return;` empties the
whole widget while inverting the bare-number guard silently deletes every species that came without a
count and invents one called `12`. Both now die against a single pasted block that carries a comment
line, a blank line, `name, count` rows, a bare name, a bare number, a trailing `#` comment and a
duplicate name — one paste through every branch.

**Five survivors were chart geometry, and the chart rules only knew about bars.**
ADR-073's rule — *a bar is an assertion about a number, and it has to be inside the picture* — selects
on `path.grow-bar`, and a curve is not a bar. `lineChart` had no geometry check at all. Worse, the bar
rule itself passed a mutant that turned every bar in the kit into a **one-pixel hairline**: still
inside its chart, still using the full height, still a pass. Containment was never the rule. The rule
is that the bars **tile the frame** — measure the pitch between neighbours off the drawing, and the
bar's own width must be that pitch minus the gap — and that curves span the frame axis to margin.

**The axis had to be bound to the data behind it (ADR-052).** `yMax = yMax ?? Math.min(...)` survives
containment *and* span: with the minimum as the ceiling every point above it clamps to the top
gridline, so the curve still fills the frame corner to corner. What breaks is the *axis* —
rarefaction stops labelling 108 species and starts labelling 20. So the top gridline is now checked
against the data maximum plus the 8% headroom the source states, both sides recomputed from the
session on each run.

**A dashed line is a claim, not a decoration.** `if (!s.dash && animate)` guards the draw-on
animation, which works by overwriting `stroke-dasharray`. Drop the `!` and the fitted curve draws
solid — and the growth chart's entire claim is *observed vs fitted*.

**`jSplit` is graded by a real JVM now.** It exists only to make JS's `split` behave like Java's, and
its own comment says what turns on it: whether `model: eulerlotka 1.0:` is reported or silently
accepted. **Nothing in the kit had ever called it.** The oracle is not my belief about Java — the
cases are handed to a JDK on the way past and the JVM's own field counts are what the page is graded
against (ADR-041). No JDK, no verdict: the check says NOT VERIFIED rather than passing blind. It also
covers the second fidelity claim, `J_WS`, which spells out Java's six whitespace characters rather
than reusing `\s`; a no-break space is what tells them apart.

**The escape rule was the instance, not the class (ADR-072 again).** The existing injection check
selects on `.tile`, so it could only ever speak for the tiles — and a sweep then dropped `esc()` from
a reading paragraph, a facet heading and a data-table cell without it noticing any of the three. It is
now stated about the document: every string anywhere in the session is wrapped in a tag that appears
nowhere in the page, and no such element may exist afterwards. New render code is covered the day it
is written.

**Series of unequal length.** Two places say `pts[bi] ?? pts[pts.length - 1]`, and one carries the
comment *"series of unequal length"*. Every fixture in the kit had all its series the same length, so
the fallback was unreachable by construction — ADR-039, exactly. Truncating one phase and hovering
past its end kills all four mutants there, but only once the marker dot's **position** is checked and
not merely its visibility: opacity alone passes a fallback that picks the second-to-last point.

## 3. And then the sweep excluded the suite that does all of it

`verify_eco` — the largest suite in the kit — **did not vote on any of that.** The header said:

```
excluded (builds a scratch tree, so it names this page as a fixture): verify_eco
```

That exclusion was inferred from `"tempfile" in txt and ("shutil" in txt or "mkdtemp" in txt)`, which
is a fact about a suite's **imports** and not about what it does. The moment `verify_eco` needed a
temp dir to compile the JDK oracle, 138 checks on the flagship page stopped voting on that page's
mutants — and one line of output said so, in language that read like a deliberate decision.

I caused that one myself, an hour earlier, and it reported the escapes those checks cover as fresh
survivors.

**The fix is that the role is declared, not sniffed.** A suite that reaches for a temp dir is either
building fixture pages (not coverage) or doing something else, and only its author knows which; the
sweep now demands `MUTATE_ROLE = "fixture-builder"` or `MUTATE_ROLE = "subject"` and **reports the
suites that carry neither** rather than guessing silently. A stale marker is reported too — sitting
out a sweep silently is the ADR-061 failure.

## 4. The joke, and the actual lesson

Declaring the six suites from the sniff's own answer list was the next mistake, and it cost a real
kill. Two of them — `verify_offline_slice` and `verify_claims_triage` — write **one synthetic fixture
file** and assert about the real kit everywhere else. `mutate.py` already knew this: `cross_cutting()`
carried a *second, sharper* predicate (`"shutil" in txt`) chosen specifically because it separated
those two from the genuine tree-builders.

Two text predicates answering one question, in one file. They duly disagreed — and how they disagreed
is the finding:

> The comment I added to `verify_offline_slice` **explaining the `shutil` sniff** contained the word
> `shutil`. That dropped the suite out of the cross-cutting set, and the webfont killer — the one
> mutant that suite exists to catch — went straight back to being reported as a survivor.

Prose about the rule broke the rule. This is the same shape as the pre-escape rule that went blind on
the line it was written for. **A rule a sentence about the rule can break is not a rule.** There is
now one declaration, read in both places, and `verify_mutate` asserts the property rather than the
wording: a globbing suite stays cross-cutting however much prose about shutil and scratch trees it
carries.

## 5. Two guards that returned before the cross-cutting suites ran

Chasing that turned up a latent defect underneath it. *"No suite names this page"* is not the same as
*"nothing covers this page"* — the cross-cutting suites reach every page in `docs/` precisely because
they name none of them. Two guards returned before they were ever consulted, so a page whose only
cover is cross-cutting was reported as having none and its mutants were binned as unrunnable rather
than run. **ADR-061 one more time, in the branch written to report it.**

No page in the kit is in that state today, so nothing was actually mis-scored; the bug was waiting for
the first page written without a suite of its own.

## 6. Where this leaves the numbers

| | before | after |
|---|---|---|
| `ecology-lab.html` sweep | 18/30 — **60%** | 30/30 — **100%** |
| `verify_eco` | 105 checks, **excluded from its own page's sweeps** | 138 checks, voting |
| `verify_mutate` | 30 checks | 47 checks |
| `verify_focus_slice` | 15 checks | 22 checks |

Every check above was canaried: the fault was seeded into a full copy of the tree and the check was
watched to fail. Twenty-two seeded faults, twenty-two failures.

**No survivors to defend this time (ADR-047), and that is worth one caveat rather than a victory
lap.** A hundred percent here means *these thirty mutants, chosen four-to-eight-per-operator across a
page that has 499 of them*. It is a 6% sample of one page, and ADR-075's rule still holds: the
headline is the sample, not the census.

The run before this one reported 29/30 and left `neg-guard` on line 14 alive — the shared webfont
loader. I had a defence written for it: not the page's own code, ADR-055, `verify_offline_slice` owns
it elsewhere. The defence was wrong. That suite kills it here too, and it was silent only because I
had just mis-declared it. **The reason a survivor survives is a claim like any other, and mine was
about to go into an ADR unchecked.**
