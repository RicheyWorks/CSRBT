# The ninth blind trial — provenance (ADR-231)

Four operators, **four more science pages no blind operator had ever driven**
— cell bench, carnivorous-plant bench, deployment log, farm scout — through
the door with ADR-231 in it: `if_stamp` takes a REPORT stamp and guards the
figures. Every operator was asked to work in batches, read the report before
each batch, and guard every act it expected to change a figure with the report
stamp it had last read.

Run **2026-09-18**. Traces are gzipped; `gunzip -c <file>` is the trace exactly
as the server wrote it. `tasks/` holds the four task files as of the run;
`OPERATOR.md` is the manual the operators were handed. The refusals are in the
traces (every `stale` is a row with `code`, `message` and the stamps in the
door's own words); the guard a call carried is NOT — the door started
recording it (`guard`, ADR-231) after this trial, because this trial is what
showed it was missing.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind9/CSRBT` — a copy of the repository with `tools/tasks/`,
`tools/traces/`, `tools/delivery/`, `tools/push/`, every ledger, the board and
its renderer, every `mutate_*.py`, the whole of `tools/verify/` except
`_kit.py`, and every `*.md` **removed from the filesystem** (ADR-136). None of
these four goals ends in an irreversible act, so all ran with the supervised
three rungs. Each had its blind brief (ADR-193) and the manual. One attempt
each. **The trial was run in two halves on purpose** — see below.

## What it measured

| task | reached | of | claims | of | calls |
|---|---|---|---|---|---|
| page-cell-bench-science | **13** | 20 | **33** | 49 | 103 |
| page-cp-bench-science | **14** | 21 | **52** | 71 | 74 |
| page-deployment-log-science | **32** | 50 | **71** | 114 | 145 |
| page-farm-scout-science | **12** | 16 | **28** | 41 | 280 |
| **total** | **71** | 107 | **184** | 275 | **602** |

## What it measured about ADR-231 — and what it found in it

Counted in the traces: every `stale` refusal of a report-stamped guard, and
what had actually moved between the report the operator read and the act it
bound to it (the operator's own `read-report since=<that stamp>` diff where
there is one, the next full read against the issuing read where there is not).

**First half — cell bench and cp bench, on the door as first built.** 11
refusals; **10 of them were the screen chrome**: the keep strip's *"Saved on
this device today 19:09"* rolling over a minute, the outbox strip counting a
first export, a toast fading. Both operators wrote it down unprompted — *"the
report stamp churns on a timer"*, *"5 of the 6 stale refusals were this, each
costing a call"*. The report's stamp was over everything the report served,
and the report serves the chrome. That is a defect in ADR-231 as first built,
and it was fixed before the second half: the report now NAMES its chrome
(`chrome`: keepBox, sendBox, toast), the stamp and the diff leave those boxes
and lines out and say so (`noise`), and a box that contains a strip (the
export pane they are mounted in) is read without it.

**Second half — deployment log and farm scout, on the fixed door.** 131
refusals; **0 chrome**. 99 were figures that had moved, 30 a box that had
moved, and **2 were a pane switch** (`show-pane` moves the report's `route`
and `shown`, and nothing else) — both operators named it, and both are noise
now too: a pane opening is the snapshot's business, and the snapshot diffs it.

**The measurement the slice was for.** Of the 99 figure-moved refusals, **88
were acts where the SNAPSHOT stamp had not moved** since the report was read
— the farm scout's 36 aphid presses and its pollinator taps, where the
operator wrote: *"the snapshot stamp did NOT change (`sf0f00eec2567`
throughout all 35 presses), exactly as the manual says"*. Every one of those
88 would have run under a snapshot-stamped guard. The snapshot guard cannot
see a figure; the report guard did, 88 times, on one page.

| | refusals | chrome | figures | box | pane switch | of the figure ones, snapshot unmoved |
|---|---|---|---|---|---|---|
| first half (as built) | 11 | **10** | 1 | 0 | 0 | 0 |
| second half (chrome fixed) | 131 | **0** | 99 | 30 | 2 | **88** |

## What the trial found in itself

- The farm scout's 127 refusals are the MANUAL's fault, not the door's: it
  said *"guard every act you expect to change a figure with that report
  stamp"*, and the operator did exactly that with a run of 36 presses under one
  stamp — the first ran, the next was refused, read, re-stamped, and so on.
  Every refusal was correct and every one cost a call. The manual now says to
  guard the act that DEPENDS on the figures as read (the first of a batch, the
  one whose subject is a computed value) and not to bind a run of presses to
  one stamp.
- The manual's `if_stamp` example showed `"text": "5"` where the tool takes
  `value`; two operators lost their first call to it. Fixed in the manual.
- The first operator's prescribed opening command carried `--page
  docs/cell-bench.html`; the console prepends `docs/` itself and the door died
  at `docs/docs/`. Two start attempts were lost before any session existed.
  Trial harness, not the door.
- The trace did not record the guard a call carried, so a call that RAN under
  a report stamp reads as a plain call. The MCP door now writes `guard`
  (`if_stamp`, `expires_at`) on the row, only when one was named.

## What they found in the pages (filed, not fixed)

- **cp bench** — `read-control` on a picker lists its options but never says
  which is selected; the only way to confirm a pick took was the verdict text.
  Picker option labels concatenate family and crops (`Solanaceaetomato,
  pepper…`).
- **farm scout** — adding a pollinator card renumbers every later
  `action_btn:N`; ids and labels held. The page opened with `#sDate` already
  set to the clock's date and the scouting fields pre-filled from the demo.
  `spread` in the brief is the page's index of dispersion (var/mean), which
  nothing told the operator.
- **deployment log** — none. The operator noted that returning a control to
  a prior value reproduces the prior report stamp exactly (a content hash), and
  that setting a control to its current value moves neither stamp.
- **cell bench** — the `altered` bucket of a report diff is always empty;
  figure changes land in `fields` as `figures/…` pairs (by design: figures are
  scalars, and `altered` is for keyed-list entries).

## Why these numbers are floors

No blind operator had touched these four pages; `verify_tasks` section F9
holds this run's reached/claims as the floor and holds the two-half
measurement. Graded as a ROUTE all four are FAIL, as always. Twenty of the
21 science tasks now have a blind trace; the ecology lab is the one left.
