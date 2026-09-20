# ADR-231 — `if_stamp` guards either document (protocol 1.11)

**Date:** 2026-09-18 · **Status:** accepted · **Chain:** ADR-230 → this ·
**Protocol:** 1.10 → 1.11

## Why

ADR-222 gave a command `if_stamp`: act only if the target is still what I
looked at. ADR-229 made a stamp say which series it is and taught `if_stamp`
to refuse a report stamp as the wrong kind. The eighth blind trial's operators
(ADR-230) wrote down, three trials running, why that was not enough:

> Quadrat and mark-recapture counters, Link parents and the Copy buttons: the
> act changed report boxes and figures and the snapshot stamp — controls only
> — stayed put.

A tally pressed again changes every figure and no control. The snapshot stamp
is a digest of the controls, so it does not move, so a snapshot-stamped guard
lets the second press through. The thing an act on a data-entry page is
*about* — the figures — had no guard at all. `verify_report` J2 now holds the
field notebook to exactly that shape: a quadrat counter pressed a second time
moves the report (`r…` → `r…`) and not the snapshot, and the act's own
control-shaped diff says nothing moved.

## Decision

`if_stamp` takes a stamp of **either** series and guards **that** document.

- A SNAPSHOT stamp (`s…`) guards the snapshot, as before.
- A REPORT stamp (`r…`) guards the report. The gateway asks the target for
  its report's stamp now — `Plugin.stamp(series)`, a new optional hook that
  returns `None` by default — and compares. Moved: `stale`, naming the report,
  both stamps, and `read-report with since=<stamp>` as the way to see which
  figures changed. Unmoved: the act runs. The page plugin reads the report the
  way `read-report` does, stamps it with the same spec, and puts nothing on
  the report ring: a guard is a look the caller did not ask to be served, and
  a baseline it never read would be one it could not name.
- A target with no report series (organism, lab, fixture, session) is
  refused `invalid_argument` by name — *"serves no report: this target has
  only a snapshot series"* — before any look.
- A string that is not a stamp of either series is refused `invalid_argument`
  too. It used to be compared to the snapshot and refused `stale`, which said
  the page had moved about a string that was never a stamp.

The manifest's `freshness.if_stamp` says which document each kind guards,
`freshness.ifStampTakes` lists `["snapshot", "report"]`, and `stamps.mismatch`
says the guard takes either. Old traces grade unchanged.

**The MCP door records the guard.** A trace row carries `guard`
(`if_stamp`, `expires_at`) when the call named one, and nothing otherwise, so
every older trace reads as it did. The ninth trial is why: it could count
refusals but not guards, so an act that RAN under a report stamp read as a
plain call.

## What the ninth blind trial found — in the slice

The trial (`tools/traces/blind9/`, four pages nobody had driven: cell bench,
cp bench, deployment log, farm scout) was run in **two halves on purpose**.

**The first half found a defect in the slice as first built.** 11
report-guard refusals, **10 of them the screen chrome**: the keep strip's
*"Saved on this device today 19:09"* rolling over a minute, the outbox strip
counting a first export, a toast fading. The report's stamp was over
everything the report serves, and the report serves the chrome. Both
operators wrote it down unprompted before the traces were read.

Fixed before the second half, and held by `verify_report` J:

- The report **names its chrome** (`chrome`: `keepBox`, `sendBox`, `toast` —
  the kit's three conventions, matched by class or id). The boxes and lines
  of those ids are **noise** for the report's stamp and diff: served exactly
  as before, left out of both, and named in every diff's `noise`, the way the
  organism names its replica lag (ADR-191).
- A box that **contains** a strip — the export pane the strips are mounted
  in on three pages — is read without it, in `boxes`, `lines` and `rules`, so
  a pane's text does not carry the clock. No task holds those panes' text.
- `route` and `shown` are noise too. Two second-half operators were refused
  right after a `show-pane` that moved no figure and no box; a pane opening
  is the snapshot's business, and the snapshot diffs it (`panes`, `route`).

Each of those has a mutant: no chrome named, chrome named but not made noise,
a nesting box read with the clock in it, `shown` stamped, `route` stamped,
the report's own noise dropped when the chrome is added. All killed.

**The second half measured the slice.** 131 refusals, **0 chrome**; 99 were
figures that had moved, 30 a box, 2 the pane switch. **88 of the 99 were acts
where the snapshot stamp had not moved since the report was read** — the
farm scout's 36 aphid presses and its pollinator taps (*"the snapshot stamp
did NOT change (`sf0f00eec2567`) throughout all 35 presses"*). Every one of
those 88 would have run under a snapshot-stamped guard. `verify_tasks` F9
holds both halves, classifying every refusal from the trace by what had
actually moved.

**The trial found two faults in its own manual.** It told operators to guard
*every* act expected to change a figure with the report stamp, and the farm
scout's operator did exactly that with a run of 36 presses under one stamp:
the first ran, the other 35 were refused, each correctly, each costing a
call. And its `if_stamp` example said `"text": "5"` where the tool takes
`value`; two operators lost their first call to it. `docs/OPERATOR.md` is the
canonical manual now — guard the act that *depends* on the figures as read,
not a run of presses; the chrome and a pane switch do not move the report
stamp — and each trial keeps the copy its operators were handed.

## Numbers

| | before | after |
|---|---|---|
| protocol | 1.10 | **1.11** |
| verify_contract | 241 | **261** (4f) |
| verify_report | 252 | **276** (J: guard, chrome, pane; J2: the field notebook's shape) |
| verify_mcp | 98 | **101** (report stamp through `_meta`; the guard on the trace row) |
| verify_tasks | 446 | **466** (F9) |
| mutate_contract | 116 | **126** (7 guard + 3 trace-guard), 126/126 killed |
| mutate_report | 153 | **162** (3 stamp hook + 6 chrome/noise), 162/162 killed |
| science tasks with a blind trace | 16 | **20** of 21 |

Ninth trial: 71 of 107 outcomes, 184 of 275 claims, 602 calls, one attempt
each; report-guard refusals by chrome 10 of 11 → 0 of 131.

## Held

- **A guard on both documents at once.** One `if_stamp`, one stamp. An act
  that must see neither the controls nor the figures move would pass two.
  Named trigger: an operator asking for it.
- **Report guard on the organism and the lab.** They serve no report; the
  hook returns `None` and the door says so. Trigger: a second document on
  either target.
- **The ecology lab** is the one science task with no blind trace (337
  steps). Trigger: the tenth trial, alone.
- **`read-control` on a picker** does not say which option is selected (cp
  bench operator). Filed on the page reader, not fixed here.

## Lessons

- A stamp over "everything served" is a stamp over the clock. Name the noise
  before an operator pays for it — the first half of a trial is a cheap way
  to find it, and running the second half on the fix is a measurement of the
  fix.
- A manual's instruction is part of the door: "guard every act" produced 120
  correct refusals and one page's operator spending 280 calls.
- A mutant killed by a check other than its `expect` is right about what it
  matched and wrong about what the match meant — three were re-aimed here.
