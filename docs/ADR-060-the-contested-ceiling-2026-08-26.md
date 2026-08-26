# ADR-060 — The contested ceiling, and the prose the checker could not see

**Date:** 2026-08-26
**Status:** accepted
**Extends:** ADR-031 (the honesty gate), ADR-057 (the policy is the checker's anchor)

## The claim

Soil Bench's compost tracker is careful about the thresholds that are
*published*: 55 °C for 3 days in-vessel, 55 °C for 15 days with 5 turnings for a
windrow, both cited to 40 CFR 503 App. B (PFRP) and the USDA NOP, and both
correctly framed as pathogen-kill requirements rather than as "good compost".

Then it said this, with no source at all:

> The thermophilic organisms doing the work operate to roughly **65–66 °C**;
> above that they begin to die off and the pile cooks itself into a stall.

That figure is load-bearing. `readings.filter(r => r.t > 66)` raises a banner,
the peak tile turns red past it, and the chart draws a band at it. A number that
drives three pieces of UI and cites nothing is exactly what ADR-031 exists for.

## What the sources actually say

Three of them, and they disagree — because they are answering three questions:

| source | figure | what it is |
|---|---|---|
| Cornell Waste Management Institute | keep below about **65 °C**; most microorganisms cannot survive above **60–65 °C**; decomposition fastest at **40–60 °C** | a microbial ceiling |
| Rodale Institute (turn-according-to-temperature) | turn at **160 °F** (71 °C) | an aeration trigger — oxygen is being used faster than it diffuses in |
| USDA NOP | permits up to **170 °F** (77 °C) | a regulatory cap while PFRP is being met |

So the page was stating one convention as if it were the biology. It now names
all three, says which question each answers, and labels its own 66 °C alarm as a
conventional choice sitting one degree above Cornell's band.

**A hypothesis I checked and dropped.** 66 °C is 150.8 °F, and "keep it under
150 °F" is a familiar US composting figure — a tidy story about a converted
threshold, in the shape of ADR-054's breast height. It does not hold: Rodale
turns at 160 °F and NOP allows 170 °F, so there is no single customary
Fahrenheit ceiling to have been converted. ADR-055 is the reason this got
checked before it got written down.

The page also now states the tension the thresholds create: fastest
decomposition ends at 60 °C, *below* the temperature a pile must hold to
certify. A pile hot enough to meet PFRP is already past peak decomposition rate.
Both are true; neither threshold is wrong.

## The rule enforced itself

Adding `the 60–65 °C compost ceiling` to ADR-031's category-2 examples was the
**entire** change needed to start policing it — ADR-057 reads the figures out of
the policy, so the new one was enforced with no edit to any checker. That was
the point of anchoring on the policy, and this is the first time it paid.

## The prose rule 3 could not see

Rule 3 read rendered HTML. These bench pages say most of what a reader actually
reads at **runtime** — the verdict banner after you enter your plates, not the
Method tab you may never open — and every word of it lives in a JavaScript
string. Five such statements carried a category-2 figure with no label.

Runtime statements are now read, with the same cut that exempts headings: a
**label is not a claim**. `'lands in 30-300'` is a tile caption, and demanding
the word "conventional" inside three words is how a checker teaches a page to
get worse. A literal earns the rule when it is a sentence — eight words and the
punctuation of one.

Literals are **joined across `+` first**, because that is what the reader sees.
A first version tested each alone and the very banner that motivated the rule
escaped it: the figure sat in the half with no full stop. The join also cleared
a false positive — Cell Bench's `'...conventional '+n+' 20–50 window...'` is one
sentence on screen, and only looked bare because it is three literals in a file.

## The mistake this slice made, and the check that now catches it

Rewriting the ceiling replaced `65–66` with Cornell's `60–65`. ADR-031 went on
listing 65–66, and **three canary mutants survived** — not because the rule was
weak but because it had nothing left to police. A policy example the kit no
longer states is a rule policing nothing, and it reads exactly like a rule that
is working.

Every figure ADR-031 lists must now be stated somewhere in the kit. Renaming the
entry to a figure no page carries fails the suite.

## A check that was pinned to prose, again

`verify_claims_math` matched `at (\d+) °F \((\d+) °C\)` on Soil Bench. The
rewrite moved "at" to "permits up to" and the check reported the claim *gone*
rather than wrong. Re-pinning it to the new wording buys the same failure at the
next edit — the ADR-041 shape.

What the check is for is that a stated conversion converts, and that is true of
every such pair in the kit. It now finds all of them (three today) and names the
page and the numbers when one is off. The filter is a function so the fixtures
exercise the same code the kit is checked with — inline, disabling the
comparison was an unkillable mutant.

## Canary

Fourteen: runtime statements not read; every literal counted including labels;
the word floor raised past reach; concatenations not joined; everything welded
into one run; the join ignoring `;`; both Soil Bench labels removed in turn;
Micro Bench's verdict label removed; the policy listing a dead figure; the
dead-entry check removed; two shipped conversions made wrong; the conversion
pattern matching nothing; the tolerance widened to nonsense. All caught. One
harmless reword confirms the rule is not hair-trigger.

## Cost

`verify_kit_consistency` 41 → 49 checks; `verify_claims_math` 38 → 43. Prose and
banner rewritten on `soil-bench`, two runtime verdicts labelled on
`micro-bench`, one figure added to ADR-031. 51/51 jobs green, 3598 checks.
