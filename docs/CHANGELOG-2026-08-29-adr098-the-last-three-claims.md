# 2026-08-29 — ADR-098: the last three claims, and what the finder cannot see

Companion to `docs/ADR-098-a-signpost-is-not-a-claim-2026-08-29.md`.
This slice worked the three `near` claims ADR-097 handed on, having first run the falsifier check
ADR-097 asked for.

## Before editing anything

ADR-097 §8: *"the cheap check is `publish_state.py --verify` on a handful of pages, run before the
next slice edits anything."* Done — the three oldest published versions (`tree-proofs`,
`tree-visualizer`, `greenhouse`) re-read from the live URL, **zero drift on all three**. Weak
evidence at a forty-minute interval with no editing session in between, and ADR-098 §1 says so
rather than banking it.

## Corrected — `docs/collection-sheet.html`

| what | why |
|---|---|
| the dryer help pointed at **the Method tab** for the 50 °C discussion | that note is in `p-vou`, directly under the same log; `p-met` has seven cards and none is about drying. The pointer named the one tab that does not carry it. |
| **"Silica beats any drying temperature for sequencing"** | an unsourced comparative with no number — structurally invisible to `audit_claims.py`, which tests for a number with a unit or a comparison written with a digit. Replaced with what the page supports. |
| 40–45 °C was **"the usual working compromise"** | "usual" is an observation; the note below it argues at length that the figure is a *convention*. Now says so. |
| 35 °C carried no label | now "a rule of thumb rather than a measured floor". |

Four lines. No page logic changed.

## Not corrected — `docs/micro-bench.html`

The remaining flag is the above-300 crowding bullet, and it is **sound**. Its card names APHA
Standard Methods 9215, FDA BAM, USP <1227>, ASTM and Breed and Dotterrer (1916), and calls the
window "a convention rather than a constant". Adding the word "conventional" to the bullet would
clear the flag and tell the reader nothing — tuning the page to the check (ADR-094). Left alone,
triaged, and asserted instead.

## Tools

* **`tools/audit_claims.py`** — docstring only, no rule changed. Names the two blind spots: a claim
  with no number, and a claim whose content is that a quantity cannot be computed.
* **`tools/verify/verify_claims_triage.py`** — **30 → 46 checks**.
  * a seeded pair of sibling claims, identical but for showable arithmetic: exactly one is reported,
    and it is the one that cannot show its working;
  * the same pair on the real `micro-bench` page;
  * the provenance that bullet rests on, plus the fact that it carries no `=`, `÷` or `√`;
  * the four `collection-sheet` corrections;
  * a `raw()` reader, because `text()` strips tags with `<[^>]+>` and therefore **cannot see script
    content at all** — a page's JS has bare `<` and `>` and the regex swallows whole spans. Two new
    assertions failed on that before they failed on anything real; the same assertion written against
    `text()` would have been green *before* the edit it was checking.

## Published

`collection-sheet` published repo → live (the first publish in three slices), then **re-read from the
URL and diffed to zero** and re-stamped `via "read"` — inside this slice rather than left for the
next one.

## The numbers

```
audit_claims.py  before   2 pages, 3 claims, 0 BARE, 3 near
audit_claims.py  after    1 page,  1 claim,  0 BARE, 1 near
the worklist since ADR-094:  71 -> 41 -> 15 -> 3 -> 1

suite          60 of 60 jobs green, 4295 of 4295 checks passing  (4279 before; +16)
publish_state  40 current, 40 measured from the live page, 0 stamped at publish time
```

## Verification

* `python3 tools/audit_claims.py` — 1 page, 1 claim, 0 BARE, 1 near.
* `python3 tools/verify/verify_claims_triage.py` — 46/46.
* `python3 tools/verify/run_all.py` — 60/60 jobs, 4295/4295 checks.
* `python3 tools/publish_state.py` — 40 current, 40 measured from the live page.
* The mutation behind §4 is reproducible: delete `CV = 1 ÷ √N` from micro-bench's below-30 bullet in
  a scratch copy and the finder reports it identically to its sibling.

## Next

ADR-098's falsifier: a sweep of every `re.sub(r"<[^>]+>"` reader in `tools/verify/` for assertions
that name a string occurring only inside a `<script>` — passing on text they cannot see. The
prediction is that at least one exists outside `verify_claims_triage`.
