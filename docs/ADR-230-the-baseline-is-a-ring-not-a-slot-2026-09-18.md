# ADR-230 — The baseline is a ring, not a slot

**`observe … since=<stamp>` diffed against exactly one thing: the last
snapshot this session was served. Every act's response serves one. So an
operator who batched six acts into one console call and then asked for the
change since the stamp it read *before* the batch was told the door held no
such snapshot — all ten times the seventh blind trial's operators tried it,
on all four pages. `if_stamp` compares against the target rather than a
baseline, so the same stamps worked there, which is what made it look
inconsistent. ADR-191's "a stamp you read in one call is still the baseline
in the next" was true only when nothing had been served in between, and an
operator batching acts never is.**

## Decision — protocol 1.10

- The gateway keeps, per plugin, an ordered ring of the last **`BASELINE_RING
  = 8`** stamps served, each mapped to its raw snapshot. `since` may name any
  of them; the diff is from that look. A stamp older than the ring is still
  unknown, and the reason says *"among the last 8 it was served"* so a client
  can plan its batches. A stamp served again — a target back at an earlier
  state — is moved to newest, not duplicated, so re-reading an unchanged page
  never pushes real baselines off. An act's own diff is still against the
  newest look. The `if_stamp` guard's look is still not remembered.
- The page plugin's report gets the same ring, `REPORT_RING = 8`; a report
  stamp two reads old diffs instead of being "no longer held" — the check that
  asserted the opposite is inverted.
- The manifest's `session` block gains `baselines: 8` and its `since` sentence
  says so; `stamps.report` now says the report stamp is `output.stamp` and
  that the answer's top-level `stamp` is the snapshot's (two eighth-trial
  operators looked in the wrong place).

verify_contract 230 → 241 (section 7b), verify_report 249 → 252,
mutate_contract 111 → 116, mutate_report 151 → 153. Price: eight snapshots of
memory per plugin, under a megabyte on the science pages.

## The eighth blind trial

Four more pages no blind operator had driven — micro bench, ordination, field
notebook, selection log — supervised rungs, one attempt each, every operator
asked to batch and then ask `since=<the stamp before the batch>`.

| page | outcomes | claims | calls |
|---|---|---|---|
| micro bench | 9 / 18 | 32 / 45 | 76 |
| ordination | 14 / 19 | 43 / 51 | 71 |
| field notebook | 6 / 13 | 22 / 37 | 70 |
| selection log | 6 / 13 | 19 / 42 | 94 |
| **total** | **35 / 63** | **116 / 175** | **311** |

**The measurement**, counted in the traces (`verify_tasks` F8 holds both):
asks for the change since a stamp that was *not* the last one served —
seventh trial, 10 asks, **10 unknown**; eighth trial, 32 asks, **5 unknown**.
Every one of the five was a batch of 8–20 acts, longer than the ring, and
every operator who hit it read the depth off the refusal and kept later
batches under eight. `read-report`'s own `since` with an older report stamp
answered a diff 25 times of 26.

## What it found

- **The snapshot stamp does not move for box-only changes** — quadrat
  counters, Link parents, the Copy buttons — and three operators read
  `changed: false` as "nothing happened" until `read-report` showed otherwise.
  By design (the report has its own stamp), noted by three trials running: an
  `if_stamp` that could name a *report* stamp — guard the act on the figures —
  is the next field worth a slice.
- Filed on the pages: the micro bench's zone read drops the medium and
  organism the operator entered from every output, prints an intermediate band
  of 13.5–16.5 for integer breakpoints, and its saturation warning says "pushes
  µ down" when including the point pushed it up; the ordination page's toast
  is stale after raw data and "1 of 12 starts converged" sits beside stress
  0.000; the selection log's dials toggle *off* on a second press with no
  affordance, which cost one operator a bird's age and most of that page's
  score; the field notebook's tally labels change with every press.

## Held

Ring depth: three batches of 8–20 acts fell off; sixteen would have caught all
three at under two megabytes per plugin — held with that number. Twenty-eight
science tasks remain un-operated blind (44 − 16).
