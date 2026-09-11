# ADR-190 — The manual: what the page offers, what to call it, what it says it does

**Status:** accepted · **Date:** 2026-09-11 · **The last four of ADR-187's door findings, and they are one complaint: the door published a figure and withheld what a reader needed in order to act on it. A picker offering sixty-six options published six. `read-control` identified a control without saying what to call it. A box's whole text arrived as one run — `bean, common20you plan to keep20` — so the only clean read was the figures map. And the pheno tracker prints its own scoring rule on the page while the door published the score and nothing about how it was reached, so a blind operator recovered the rule by experiment. Now: a picker's pool is every option it offers and the snapshot says shown-of-how-many per list; `read-control` answers with the address; every box is published split where the page splits it, beside the run of text every task holds; and the prose the page writes about its own arithmetic is handed over as the page wrote it, quoted rather than interpreted. `verify_report` 149 → 160, `mutate_report` 95 → 104.**

## 1. Six of sixty-six

> *The snapshot `pick` pool lists only 6 of 28 crops per picker ("corn, sweet"
> absent), yet `pick` accepted it — the pool undersells what is valid.*
> — the breeding-bench operator, ADR-187

The cap was `slice(0, 6)`, written when a pool was a hint. It is not a hint:
`argumentPools` is the door's answer to "what can I form a call from", and a
pool that publishes 9% of the valid values teaches a client that the pool is
not the answer — which is the opposite of what a pool is for, and exactly what
the operator concluded.

The cap is 80 per list and 600 in all now, and — the part that matters more —
**the cap is reported**. `observe` carries `pickers`: one row per picker and
per select, with its selector, its host, how many options were published and
how many there were. The collection sheet's genus picker says `66 of 66`; a
list longer than the cap says `80 of 105` rather than looking complete. And
`of` is what the picker offers *now*, because a filter takes options out of
the document on these pages — which is the honest number for a client deciding
whether to clear a filter before it picks.

## 2. What to call it

`read-control` gained id, label and host in ADR-141. It still did not say the
one thing a reader identifying a control needs next: the name to call it by.
It carries the ADR-188 `address` now, and the suite holds that the address
`read-control` answers with is the address the snapshot publishes for the same
control — and that `read-control` takes it. The two ends of the loop meet.

## 3. A box, split where the page splits it

    boxes.selOut  "Response10.0%proportion kept1.755intensity i6.14expected R…"

Every task in the kit holds `boxes` exactly as it is, so this is published
**beside** it rather than instead of it: `lines`, the same boxes, each split
into the page's own blocks. The rule is structural, not linguistic — a *leaf
block* is a block element containing no block element, and its text is one
line — so nothing is guessed about what the page meant. `figures` and `by`
remain the precise read for a figure; `lines` is for the prose and the rows
between them.

A line cut at the 300-character cap is trimmed again, because the cut lands
mid-sentence and would otherwise hand back a trailing space that is not in the
page. The suite holds the whole claim: every line of every box is that box's
own text, trimmed, with nothing invented and nothing reworded.

## 4. What the page says it does

> *The scoring formula (weighted mean, not weighted sum, then S from keeper vs
> run means) was not stated anywhere the door shows; I guessed from "1–5 scale"
> and confirmed from the board on attempt 3.*
> — the pheno-tracker operator, ADR-187

It is stated. It is on the page, in a `<p class="fine">`, in the pheno
tracker's own words: an unscored trait is *dropped* from the weighted total
rather than counted as a 1. The door published every figure the page computed
and nothing about how.

`read-report` carries `rules` now: the innermost `.hint` and `.fine` on the
page — the kit's own two conventions for that prose, 21 and 24 pages — each
with the identified thing it sits in, capped at forty pieces of four hundred
characters. Innermost, so a section that wraps another is not handed over
twice. **Quoted, not interpreted**: the door does not know the rule, and it
says so by giving the reader the page's own words for it rather than a summary
it would have had to invent.

## What moved

    verify_report      149 → 160      mutate_report   95 → 104 / 104
    pick pool          6 per picker → every option it offers (66 of 66, 50 of 50, 35 of 35)

One plugin, one suite, one runner. No page and no task was edited; `boxes`,
`figures` and `by` are byte for byte what they were, which is why the 44
science tasks did not have to move.

## Held

- `of` is a count of what is in the document now. A picker whose filter has
  hidden most of its options reports the smaller number, and that is the
  truth about what `pick` would accept at that moment.
- `lines` splits by structure. A page that puts two sentences in one `<p>`
  gives one line, and a page that wraps each figure's label in its own `<div>`
  gives the label and the value as separate lines — which is the page's
  choice showing through, not a reading of it.
- `rules` is `.hint` and `.fine` and nothing else. A page that explains itself
  in a heading or a `<details>` is not covered; extending the convention is a
  page change, and this slice edited no page.
- The snapshot grew: the collection sheet's pools went from twelve entries to
  seventy-nine. That is about five kilobytes on a snapshot already near a
  hundred, and it is the cost of the pool being the answer.
