# ADR-108: the harness had no map

**Status:** Accepted (2026-08-30) — landed and green (`verify_routes` 14/14,
`verify_evidence` 19/19, `DarwinCoreTest` 15/15; full suite **66 of 66 jobs,
4,507 of 4,507 checks**; Java **1,127 tests**).
**Date:** 2026-08-30
**Deciders:** Richmond
**Builds on:** ADR-107 (the first photograph, and the Darwin Core seam it found),
ADR-106 (an audit of nothing reports clean), ADR-104 (a hole is not a failure,
and the counts ledger that deleted what it could not measure).

---

## 1. The defect, stated plainly

`douglas-explorer.html` was added to `docs/`. `tools/harness.py` ran over forty
pages. The kit had forty-one. **Every suite was green.**

Nothing in the kit could distinguish a page that passed from a page that was
never opened. Coverage had quietly become *whatever the last run happened to
visit*, and there was no list to check it against. That is ADR-106's audit of
nothing, one level up: not a tool reporting clean having examined no files, but a
whole harness reporting coverage having never heard of a page.

The harness was strong where it looked and blind to where it did not look. It
had an accounting identity — `discovered == driven + dead + hidden + failed +
excluded` — which is a genuinely good property and answers the wrong question. It
accounts for everything **on the pages it visited**. It had no map.

## 2. Routes are published now

`tools/routes.py` generates `tools/routes.json`: every reachable place in the kit
with a name.

```
page.html            a primary route  — the page in its landing state
page.html#pane-id    a nested route   — a pane reached by pressing its tab
```

**128 routes: 41 primary, 87 nested.** The table is derived from the pages
themselves and `verify_routes` fails if it drifts from them, so it cannot become
a second thing to maintain that quietly disagrees with the first.

## 3. Navigation is atomic and refuses four ways

`routes.navigate()` opens a route exactly or raises. It never does its best.

| Refusal | Meaning |
|---|---|
| `MISSING` | nothing matches the selector |
| `AMBIGUOUS` | more than one does — **a selector that is not unique is not an address**, and taking the first match is how a harness silently drives the wrong control |
| `DISABLED` | the target exists but cannot be operated, or is not visible |
| `UNCONFIRMED` | the click happened and the visible pane did not change |

`UNCONFIRMED` is the one worth arguing for. The other three are refusals to act;
this one is a refusal to *believe*. A harness that clicks a tab and assumes it
worked is asserting what it hoped for, and that is the failure this kit has now
found at the reading layer (ADR-099), the auditing layer (ADR-106), the canary
layer (ADR-105) and now the navigation layer.

All four are **canaried** against a seeded fault in a real page — a removed tab,
a duplicated tab, a hidden tab, and a tab whose handler is neutralised — because
a refusal nobody has watched fire is a refusal nobody knows the shape of. The
first run of those canaries reported "no refusal" three times: the seeds had been
written against `<div class="tab">` and the kit uses `<button class="tab">`. The
canaries caught my canaries.

## 4. The ratchet

`tools/verify/verify_routes.py` holds the kit to the list:

1. every page in `docs/` is routed — a new page **fails** until it is listed;
2. route ids are globally unique;
3. every route resolves atomically, in a real browser, all 128 of them;
4. **every routed page appears in the harness ledger** — uncovered fails rather
   than passing by omission;
5. the kit drives at least `CONTROL_FLOOR` affordances, so coverage cannot be
   quietly narrowed while still reporting green;
6. all four refusals are canaried.

Check 4 went red on its first run, naming `douglas-explorer.html`. That is the
whole point of building it: the defect that motivated the suite was still present
when the suite arrived, and the suite said so.

## 5. And building the consumer found the ledger bug, again

`harness.py` wrote its ledger with `json.dump(..., "pages": out)` — the whole
file, every time. So `harness.py one-page.html` **silently deleted the coverage
of the forty pages it did not run**, and the new route contract, which reads that
file, would then have reported forty uncovered pages that had been driven the day
before.

This is ADR-104's counts-ledger defect exactly, in a second ledger, found the
moment something depended on it. It merges now: a run updates only the pages it
drove, keeps the rest, and stamps each entry with its own `at` so a kept reading
can be told from a fresh one. The run says what it did — *"1 page driven, 40 kept
from earlier runs"*.

**The pattern is worth naming, because this is the third time.** A ledger with no
consumer decays without symptoms. Build something that reads it and the decay
becomes a failure the same week. The counts ledger was found by `verify_advertised`
reading it; this one by `verify_routes` reading it. Any remaining ledger in this
kit that nothing reads should be assumed wrong.

## 6. The Darwin Core seam, closed

ADR-107 named the work and queued it. It is done:

- **`DarwinCore.java`** reads the standard the kit's own field pages already
  emit, and that GBIF, iNaturalist, CCH2 and MyCoPortal all publish. 15 tests.
- **`dwc: <label> <path>`** in an `.eco` protocol pulls one straight into the
  analysis engine.
- **The rule that made it worth building:** `organismQuantityType` is
  load-bearing. Cover and individuals are different quantities. Shannon, Simpson,
  evenness and Bray–Curtis are proportional and apply to both; **Chao1 and
  rarefaction are refused for cover data**, in code, with the reason in the
  exception — they estimate unseen species from counts of individuals, and cover
  has none. `proportionalWeights()` is the narrow door that lets the proportional
  indices work on cover without pretending it is a headcount.
- An absent coordinate stays absent. It never becomes `0`, which would read as
  perfect precision at Null Island — the same rule `verify_dwc` already enforced
  on the export side, now enforced on the import side.

**The Tahoe observation ran end to end.** Re-entered as Darwin Core with cover
classes, hedged identifications and a deliberately empty coordinate, it produced:
`dwc canopy: 5 record(s), cover, no coordinate recorded`,
`identification hedged for [...]`, and — the line the whole seam exists for —
`cover data: Chao1 and rarefaction withheld`. The `structure` dataset, which is
genuine counts, still got its Chao1.

Five pre-registered hypotheses graded **3 confirmed, 2 refuted**. Both
refutations were mine: I predicted the canopy would read *uneven* and it read
*moderate* (J′ = 0.76), and I predicted understory Shannon above 1.4 and it came
in at 1.31. Written before the run, graded by the run, wrong.

## 7. Consequences

- New pages cannot arrive uncovered. New controls cannot arrive uncounted.
- The harness is documented, at `docs/AI_HARNESS.md`: routes, refusals,
  selectors, the oracle, the accounting identity, the ratchet, the ledger rule,
  and the Darwin Core contract in and out.
- Three ledgers in this kit have now had the same defect. The next one written
  should merge from the first commit, and anything that keeps a record nobody
  reads should be given a reader or deleted.

## 8. Still open

- `verify_publish_reach` reports one honest hole where there is no build output
  to test containment against — correctly, as `ok--` rather than green.
- `verify_cs_science`'s `DIV.row2` at 401 px in a 390 px phone (ADR-106 §4)
  remains the highest-value item in the worklist: a real defect, on a real user
  platform, needing the flex-chain repair ADR-103 named and deliberately left.
