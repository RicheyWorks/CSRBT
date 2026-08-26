# ADR-055 — The ranking was stale evidence

**Status:** accepted · 2026-08-26
**Corrects the priority list published in ADR-050.**

## What ADR-050 said, and what was actually true

ADR-050 ranked five pages as *"states a figure the repo contradicts"*, measured
against the newest live copies then on disk. It carried the caveat that a page
republished since a copy was saved would **overstate** its drift.

That caveat has now fired on **four of the five**. Fetching each fresh:

| page | ADR-050 said | actually live |
|---|---|---|
| `food-web` | loop bound one pass short | already `+2`; two rail links behind |
| `soil-bench` | "eight-fold" for a ten-fold ratio | already corrected; two rail links behind |
| `collection-sheet` | 2 changed, 4 withdrawn figures | already correct; two rail links behind |
| `fungal-characters` | unsourced DNA-degradation temperature | **genuinely stale** |
| `stand-sheet` | observer error 10–20 points | **already corrected**; now stale for a different reason |

Four pages were behind by **exactly the same two rail links** — Soil Recipes and
Greenhouse, added to the shared rail after those pages were last published. The
"WRONG" ranking was, in the main, a kit-wide rail update wearing the costume of a
factual defect.

I reported that list to the user as live harm. It was live harm in the evidence I
had; it was not live harm on the pages. **The tool's caveat was load-bearing and
the report around it was not careful enough** — the honest phrasing was always
"the newest copy I hold says", and the summary compressed it to "these pages
state".

## What the fresh measurement shows

Four pages state something the repo contradicts:

- **`stand-sheet`** — 1 changed, 1 withdrawn: breast height fixed at 1.37 m
  (ADR-054).
- **`ecology-field-card`** and **`ecology-lab-manual`** — the trophic-transfer
  argument the glossary names as unsafe (ADR-051). *These two became stale in
  this session, by being fixed in the repo.*
- **`fungal-characters`** — the unsourced DNA-degradation temperature (ADR-050).

`collection-sheet`, `food-web` and `soil-bench` are off the list. `ecology-glossary`
remains incomplete rather than wrong. Fifteen pages still have no saved copy and
nothing can be said about them.

## Two pages cannot be republished

`fungal-characters` and now `stand-sheet` are both stuck in the publish gate's
duplicate-content branch. The sequence that cleared `cp-bench` and `releve`
earlier — fetch, read every line, publish, fetch again, publish — does not clear
these two. Each has now been fetched and read end to end, 662 and 2748 lines
respectively, and each publish is refused as *"identical content already refused
against the newer version, resent unchanged"*.

The gate offers `force:true` and reserves it for the user's explicit
confirmation. **It is not mine to assume, so both pages stay stale and are named
here rather than forced.** That is the cost of the rule and the rule is right;
the decision belongs to Richmond.

## What this changes about how the backlog is reported

The republish backlog is smaller and duller than ADR-050 implied, and the
workflow that produced the correction is the one to keep:

> Rank cheaply from disk. Confirm by fetching. Only then spend the gate — and
> when reporting, say which of the two the claim rests on.

## Still open

- Four pages listed above; two of them blocked on `force`.
- 32 claims on the `audit_claims` worklist.
- Five unbound session artifacts (ADR-052); fifteen published pages with no
  saved copy at all.

## The rule this adds

> A caveat that a measurement can overstate is not a footnote. If the summary
> drops it, the summary is making a claim the measurement did not.
