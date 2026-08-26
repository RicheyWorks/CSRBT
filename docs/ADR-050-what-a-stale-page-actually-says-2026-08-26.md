# ADR-050 — What a stale page actually says

**Status:** accepted · 2026-08-26
**Follows ADR-049, which established that reachability is not staleness. This one
establishes that staleness is not harm.**

## The problem ADR-049 left

`publish_state.py` answers "is this page behind?" with a hash. That is the right
question and, alone, a useless answer: BEHIND is a boolean over thirty-nine
pages, and acting on it means republishing at roughly four Read calls each
against the publish gate. Ten pages were BEHIND and twenty-five UNKNOWN.

I had written that the rest was "cosmetic for this defect only". That was a
claim with nothing behind it — the same habit ADR-049 was written about, one
ADR later.

## What was built

`tools/publish_drift.py`. Fetching a live artifact saves its full HTML to disk;
the newest such file per artifact is a real copy of what that URL served. The
tool reads them and **fetches nothing**. It answers: *would a reader of the
stale copy read a different number?*

`tools/verify/verify_publish_drift.py` — 29 checks, nine seeded mutants, all
caught.

## The first version was wrong in the expensive direction

It line-diffed and called any line whose digits changed "numeric". **Twenty-four
of twenty-four pages came back with numeric drift**, which was the tell — the
same shape as `audit_frontend`'s 26 findings for 26 false positives before it
was deleted. It was counting:

- hex colours (`#8B8B7B` → `#6B6B5E` is a contrast fix, not a claim),
- artifact UIDs inside newly added rail links,
- font weights inside a Google Fonts URL,
- and worst, difflib replace-blocks where an **inserted** line was zipped
  against `""` and read as a number appearing from nothing.

Every one of those is now a fixture, because a classifier that cannot tell a
contrast fix from a changed claim is not a weaker classifier — it is measuring
something else.

## What it measures now

Numbers live in three places and only two can mislead a reader:

- **SENTENCE** — a number in rendered prose. A reader reads this.
- **CODE** — a numeric literal in a `<script>`: a midpoint, a threshold, a loop
  bound. Not seen, but the number computed *for* the reader is downstream of it.
- **SURFACE** — colours, weights, sizes, SVG path coordinates, digits inside a
  URL or identifier. Never a claim, and discarded *by construction* rather than
  by a filter, because a filter over line diffs is what produced the false
  positives.

Result: 24 pages → **7 with real numeric drift, 17 clean.**

Then the ranking itself was wrong. `ecology-glossary` topped it with 37, and all
37 were **additions** — the stale page is missing entries, not stating anything
false. CHANGED, WITHDRAWN and ADDED are now three columns, because ranking them
together put a page that says nothing wrong above one that misstates a ratio.

## What it found, verified case by case

- **`fungal-characters` and `collection-sheet`** both publish *"Above about
  50 °C the DNA in the tissue degrades"* — an unsourced figure the repo replaced
  with the sourced one: the Fungal Diversity Survey puts the drying window at
  **43–50 °C** and DNA damage at about **68 °C**, and a 2017 study amplified from
  mushrooms dried at every temperature from 22 °C to 93 °C. A collector reads the
  live page and stays under 50 °C for a reason that is off by nearly twenty
  degrees. **This is the ADR-031 honesty gate applied in the repo and never
  delivered to the reader.**
- **`stand-sheet`** publishes observer error as *"10–20 percentage points"*;
  the repo replaced it with Morrison's 2016 review — 25–50% CV between observers.
- **`soil-bench`** published *"eight-fold"* for a 600/60 ratio that is ten-fold.
- **`food-web`** published a trophic-level fixed point bounded at
  `species.length+1`, one pass short of the repo's `+2`.

## The caveat earned its place immediately

The tool refuses to say "the live page is wrong" — only that the newest copy ON
DISK differs, and it stamps that copy's age on every row.

That caveat fired for real. `food-web` and `soil-bench` both ranked as WRONG
from copies saved 2026-08-24 22:48; fetching them fresh showed **both already
carried the fix**, having been republished in a later slice without being
stamped. Their real drift was two rail links each.

So the workflow this establishes is: **rank cheaply from disk, confirm by
fetching, and only then spend the gate.** A fresh fetch lands on disk and the
next run re-measures automatically. Without the caveat I would have spent four
Read calls each proving a defect that was already fixed.

## What actually shipped

- `food-web` republished and stamped (two rail links; the loop bound was
  already live).
- `soil-bench` confirmed current bar two rail links; not republished.
- **`fungal-characters` could not be republished.** The gate refused: first as
  not-viewed, then as duplicate content, and it stayed in the duplicate branch
  across three fetch-and-read cycles including a full line-by-line read after
  the final fetch. Clearing it needs `force:true`, which the tool reserves for
  the user's explicit confirmation. It is not mine to assume, so the page is
  left stale and named here rather than forced. **This is the one real
  regression this slice leaves open.**

## Still open

- `collection-sheet` (2 changed, 4 withdrawn) and `stand-sheet` (2 withdrawn)
  carry the same class of defect and are unrepublished.
- `fungal-characters`, blocked on the gate as above.
- `ecology-glossary` (37) and `ecology-field-card` (26) are incomplete, not
  wrong.
- **15 pages have no saved copy at all, and nothing can be said about them.**
  That is listed in the tool's own output rather than folded into a total, and
  it is the honest shape of the remaining unknown.

## The rule this adds

> BEHIND is a boolean. Harm is not. Before spending a budget on staleness,
> measure what a reader would actually read differently — and separate "states
> something false" from "is missing something", because they rank differently
> and only one of them is urgent.
