# The eighth blind trial — provenance (ADR-230)

Four operators, **four more science pages no blind operator had ever driven**
— micro bench, ordination, field notebook, selection log — through the door
with ADR-230 in it: the observe baseline is a ring of the last eight stamps
served, not the one slot the seventh trial's operators all fell through.
Every operator was asked to work in batches and, after each batch, to ask
`since=<the stamp read BEFORE the batch>` — the exact ask that the one-slot
door answered "unknown" every one of the ten times it was made in the
seventh trial.

Run **2026-09-18**. Traces are gzipped; `gunzip -c <file>` is the trace exactly
as the server wrote it. `tasks/` holds the four task files as of the run;
`OPERATOR.md` is the manual the operators were handed, kept with the trial
for the first time.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind8/CSRBT` — a copy of the repository with `tools/tasks/`,
`tools/traces/`, `tools/delivery/`, `tools/push/`, every ledger, the board and
its renderer, every `mutate_*.py`, the whole of `tools/verify/` except
`_kit.py`, and every `*.md` **removed from the filesystem** (ADR-136). None of
these four goals ends in an irreversible act, so all ran with the supervised
three rungs. Each had its blind brief (ADR-193) and the manual.

## What it measured

| task | reached | of | claims | of | calls | attempts |
|---|---|---|---|---|---|---|
| page-micro-bench-science | **9** | 18 | **32** | 45 | 76 | 1 |
| page-ordination-science | **14** | 19 | **43** | 51 | 71 | 1 |
| page-field-notebook-science | **6** | 13 | **22** | 37 | 70 | 1 |
| page-selection-log-science | **6** | 13 | **19** | 42 | 94 | 1 |
| **total** | **35** | 63 | **116** | 175 | **311** | **4 in 4** |

## What it measured about ADR-230

Counted in the traces: an `observe … since=<stamp>` whose stamp was **not the
last snapshot stamp served** — the ask the one-slot door could not answer.
(The seventh trial's other four `since` asks named the latest stamp and were
answered; they are not in this count.)

| | such asks | answered "unknown" |
|---|---|---|
| seventh trial (one slot) | 10 | **10** (100%) |
| this trial (ring of 8) | 32 | **5** (16%) |

Every one of the five was a batch longer than the ring — eight, ten and
twenty acts between the read and the ask — and the reason said so in the
door's own words: *"this session holds no snapshot stamped '…' for csrbt-page
among the last 8 it was served"*. Every operator who hit it read the depth off
the message and kept later batches under eight; none was sent looking for a
document it had never read. `read-report`'s own `since` with an older report
stamp answered a diff 25 times out of 26 (the one miss was a snapshot stamp
handed over deliberately, named as the wrong kind).

`if_stamp` behaved as documented on all four: a stale snapshot stamp refused
`stale` naming both stamps; the current one let the act run.

## What the operators found in the door (filed; the smaller ones fixed here)

- **A `read-report` answer carries two stamps** — the response's top-level
  `stamp` is the snapshot's, as on every response, and the report's `r…`
  stamp is at `output.stamp`. The manual said "as its `stamp`" and two
  operators looked in the wrong place first. The manifest's `stamps.report`
  and the manual now say `output.stamp` and say what the top-level one is.
- **The snapshot stamp does not move for box-only changes.** Quadrat and
  mark-recapture counters (field notebook), Link parents and the Copy buttons
  (selection log), the Copy presses (micro bench): the act changed report
  boxes and figures and the snapshot stamp — controls only — stayed put, so
  `observe since` answered `changed: false` and three operators read that as
  "nothing happened" until `read-report` showed otherwise. This is by design
  (the report has its own stamp for exactly this) and it is the third trial
  running to note it; an `if_stamp` that could name a *report* stamp — guard
  the act on the figures, not the controls — is the obvious next field.
- Ring depth: three batches of 8–20 acts fell off an 8-deep ring. The depth is
  in the manifest and in every refusal; sixteen would have caught all three at
  under two megabytes per plugin. Held with that number.

## What they found in the pages (filed, not fixed)

- **micro bench** — the zone-of-inhibition read drops the medium and organism
  the operator entered (`Mueller-Hinton`, `E. coli ATCC 25922` held on the
  controls, absent from the result box, the bench sheet and the zone CSV); the
  intermediate band prints 13.5–16.5 mm for integer breakpoints S ≥ 17 / R ≤ 13
  where the convention is 14–16; the saturation warning says a point above OD
  0.6 "pushes µ down" while including it pushed µ *up* (0.6931 → 0.8189) — the
  sentence is generic, not computed.
- **ordination** — the toast box is stale after raw data is entered (still the
  demo's "Simulated: … no gradient at all" until an export overwrites it);
  "1 value could not be read … and *were* taken as zero"; a 4- or 5-site fit
  reports "1 of 12 starts converged" beside stress 0.000 and "every pair sits
  on the monotone fit", which reads as a contradiction.
- **selection log** — a dial re-pressed while selected toggles OFF with no
  affordance saying so: the operator pressed `@adult` for the third bird while
  it was still selected from the second, and A3 was logged with no age, which
  nothing supervised could undo (the row's ✕ and Undo are DESTRUCTIVE). That
  one press is most of this page's miss.
- **field notebook** — tally buttons change label with every press
  (`species-a0` → `species-a1`), so a `@label` address goes stale after one
  press; the report's duplicate-name suffix (`Shannon H′ #2`) swapped which
  H′ was plain once the ethogram gained results.

## Why these numbers are floors

No blind operator had touched these four pages; `verify_tasks` section F8
holds this run's reached/claims as the floor, and holds the ring measurement
against the seventh trial's. Graded as a ROUTE all four are FAIL, as always.
Sixteen of 44 science tasks now have a blind trace.
