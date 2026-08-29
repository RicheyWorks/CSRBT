# ADR-097 — The worklist was being worked in the wrong copy

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-055 / ADR-056 / ADR-078 (staleness is a property of the published copy),
ADR-094 (a worklist with a front), ADR-096 (the repository was the stale copy),
ADR-061 (silent exclusion with a plausible face), ADR-069 (a check that cannot fail is not a check),
ADR-031 (the three-way provenance gate)

ADR-096 §9 named this slice in one sentence: *"Thirty-one published pages have still not been read
against the repo… read each remaining artifact, diff, back-merge, `--verify`."* That is what was
done, and the sweep answered a question ADR-096 did not know it had asked.

## 1. The sweep

Thirty-one artifacts read, diffed against `build/publish/`, back-merged where they differed, rebuilt,
re-diffed to zero, and stamped `via "read"`. **Eleven of the thirty-one had drifted.**

| page | lines | what the live copy carried that `docs/` did not |
|---|---|---|
| `breeding-suite` | 1 | the 20/100 floor named as "the seed-savers' rule of thumb" |
| `collection-sheet` | 6→8 | 40–45 °C **straddles** the lower edge of 43–50 °C, "only its top two degrees are inside it" — the repo said it *sits inside*; plus "the distinction is definitional, not a judgement" and "figures indicative, not measured" |
| `cp-suite` | 1 | the top-up equivalence carrying its arithmetic, (10 × 50 = 500) |
| `ecology-field-card` | 3 | "— a rule of thumb" on the 5-transition floor; "Below the **conventional** 80%"; "past the **conventional** >80% confluence it reads long" |
| `ecology-glossary` | 2 | cover over 100% is "correct **by definition**, not an error" |
| `ecology-lab-manual` | 2 | "The methods are Altmann's (**Altmann, 1974**); the window and interval lengths are this manual's convention"; the quadrat size named a convention |
| `ecology-lab` | 2→3 | `<span class="src">Both figures are means over the per-transition table below.</span>`; "the **conventional** ±15-point agreement band" |
| `ethogram` | 1 | "**conventional** starting points, not recommendations" |
| `field-season` | 1 | "a random (Poisson) pattern has ratio 1 **by definition**" |
| `releve` | 1 | cover over 100% is "correct **by definition**, not an error" |
| `stand-sheet` | 1 | breast height given as "**the regional convention**: 1.37 m (4.5 ft) N. America, 1.30 m most elsewhere" |

One of those eleven is a factual correction (`collection-sheet`: 40–45 °C does not sit inside
43–50 °C; it overlaps it by two degrees). The other ten are provenance.

## 2. The finder's worklist and the drift set were the same set

Run `audit_claims.py` against the repository as it stood **before** this slice and it names eleven
pages. Run the diff and it names eleven pages. They are the same eleven pages, with no page in
either list that is not in the other.

| | before | after |
|---|---|---|
| pages flagged | 11 of 40 | **2 of 40** |
| claims to triage | 15 | **3** |
| BARE | 1 | **0** |
| near | 14 | **3** |

Every claim `audit_claims.py` had on its worklist was sitting on a page whose **published** copy had
already been fixed. ADR-094's worklist was not being ignored. It was being worked — in the artifact
editor, one page at a time, by a session that never wrote back to `docs/`. The repository was not
merely stale (ADR-096); it was stale *precisely where the finder was pointing*, which is why the
finder kept pointing there.

This also explains the shape ADR-096 found and could not account for: eight of its nine pages had
drifted because those nine were the pages it had just chosen to edit — and it chose them from the
same worklist.

## 3. What the twelve cleared flags actually got

`near` falling from fourteen to three is the sort of number that should be distrusted before it is
believed. ADR-094 states the failure mode in as many words: *"one citation must not cover every
number under the same heading."* A section-level blanket would produce exactly this graph.

So each of the twelve cleared flags was read against the edit that cleared it:

* **Ten** were cleared by a phrase attached to *that claim's own sentence* — `rule of thumb` on the
  20/100 floor, `by definition` on the two cover sentences, `conventional` on each of the three
  field-card rows separately, `the regional convention` on breast height, `this manual's convention`
  on the sampling windows, `conventional starting points` on the interval, `by definition` on the
  Poisson ratio.
* **One** (`ecology-lab`, the single BARE) was cleared by a `.src` span naming where the two figures
  come from — not by a vocabulary word at all.
* **One** (`cp-suite`) was cleared by the arithmetic being written out inline.

No clearance came from a sentence placed elsewhere in the section to cover several numbers at once.
Twelve for twelve.

## 4. The three that did not clear

`collection-sheet` was edited three times and **neither of its two flagged claims cleared**;
`micro-bench` was back-merged in ADR-096 and its one flag survives. That is the check working. Had
the eleven edits been blankets, `collection-sheet` — the most heavily edited page in the set — would
have gone quiet. It did not.

* `collection-sheet`: the 50 °C figure ("see the Method tab"), and the corrected 43–50 °C sentence.
  The correction fixed the *relationship* between two ranges; it did not source either.
* `micro-bench`: the 300-colony crowding threshold.

These three are the front of the worklist ADR-097 hands on. None is BARE.

## 5. ADR-096's own republishes, measured

ADR-096 republished nine pages and stamped five of them `via "publish"` — the stamp its own §2 calls
blind. Those five were re-read here from the live URL: `breeding-bench`, `cp-characters`,
`eco-protocol-library`, `ecology`, `micro-bench`. **All five diffed to zero.** The republishes landed
exactly as claimed. That is a check ADR-096 could not perform on itself, and it passes.

`published.json` now reads: **40 current, 0 behind, 0 unknown, 0 unmapped — 40 of 40 measured from
the live page, 0 stamped at publish time.** For the first time since the kit had forty pages, no
entry in that file rests on a stamp that says nothing about whether the publisher kept the bytes.

## 6. The prediction ADR-096 made

> I expect the remaining thirty-one to drift at a lower rate than eight-in-nine… **Falsifier: the
> rest drifting at the same rate**, which would say the artifact editor has been the kit's real front
> end for some time and `docs/` is a mirror that nobody has been keeping.

Observed: **11 of 31 (35%)** against **8 of 9 (89%)**. The prediction holds; the falsifier did not
fire. The selection effect ADR-096 guessed at is real and is now named precisely in §2 — the nine
were not merely "pages somebody was reading", they were the finder's own worklist.

## 7. The numbers

```
pages read from the live URL this slice      36   (31 sweep + 5 ADR-096 republishes re-read)
of the 31 sweep pages: drifted               11
of the 31 sweep pages: identical             20
lines back-merged                            22 replaced by 24
published.json  before                       40 current, 18 measured, 22 publish-stamped
published.json  after                        40 current, 40 measured,  0 publish-stamped

audit_claims.py  before   11 pages, 15 claims, 1 BARE, 14 near
audit_claims.py  after     2 pages,  3 claims, 0 BARE,  3 near
```

## 8. What is not done

* **Three `near` claims remain**, listed in §4. Two of them want a source, not a label.
* **No page logic changed.** Every back-merged line is prose or a `.src` span; no tool, no formula,
  no control flow. No mutation sweep is owed.
* **Nothing was published in this slice.** Eleven `docs/` pages now match their live copies exactly,
  so there is nothing to push; the direction of travel was live → repo throughout.
* **The finder was not changed.** `audit_claims.py` is byte-identical to the version ADR-096 left.
  The fall from 15 to 3 is entirely content.

**The next prediction, and its falsifier.** With `docs/` and the forty artifacts now byte-identical
and every entry measured, I expect the *next* sweep of the same 40 pages to find **zero** drift,
because there is no longer a second place for edits to accumulate unseen. **Falsifier: any page
drifting again before it is deliberately republished** — which would say the artifact editor is still
being used as a front end and that the reconciliation here bought a snapshot, not a fix. The cheap
version of that check is `publish_state.py --verify` on a handful of pages, and it should be run
before the next slice edits anything.
