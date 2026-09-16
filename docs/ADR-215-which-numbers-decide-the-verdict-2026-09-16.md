# ADR-215 — The board printed "everything is green" beside a reading of 6 / 7, and said nothing about which numbers decide

**The Harness Board is the kit's one summary artefact, and its headline was not derived from what it displays. `all_green` was a hand-written conjunction over seven summary fields; the page rendered eleven tiles, and six of them do not gate the verdict. One of those six reads `6 / 7 — clean under load`. A reader with that and "Everything the harness knows how to check is green." on one screen has to distrust one of the two, and the page gave them nothing to decide with.**

## 1. How it was found

Not by an audit. A subagent republishing the board read it, noticed the two
statements side by side, and said so in its report: *"if `verify_board` treats
that tile as a checked value, the green banner and that tile disagree."*

It does not — and that is the whole defect. The board was right and unreadable.

## 2. The shape

ADR-141's, at the top of the kit rather than inside a page: **a rule kept in one
place and published in another, with nothing holding the two together.** The
conjunction could be extended without the page ever mentioning it, and a tile
could be added without anyone deciding whether it gates. The page was the
harness's own summary of itself and it did not summarise its own rule.

## 3. What is measured

The verdict is now DERIVED from a named list, and the list is rendered:

> The verdict is these 7 and nothing else: every suite check passes; every walk
> of every target holds; every task is held; every trace is held; no mutant
> survived; no mutant was inconclusive; no engine suite failed. Every other number
> below is a READING — a measurement with a ratchet or a worklist behind it, which
> moves on its own schedule and does not decide whether this page is green.

**The honest shape is not "every tile gates."** Two of the seven gates have no
tile at all — the walks and the traces — so the list is named rather than inferred
from what happens to be displayed. A gate added to it appears on the page the same
day.

**Every tile then says which it is.** Four carry `counts toward the verdict`. The
other seven say, in one line, what kind of number they are instead:

- *commands walked* — a count of what the robot drove; the walks' own verdicts
  gate, and they are in the table below.
- *entered supervised* — a ratio with a REASON on the other side: the rest declare
  a destructive rung, in writing.
- *fields entered*, *figures readable* — ratchets that only come down, not pass
  marks.
- *files delivered* — a running total; `audit_delivery` is the gate, and it runs
  in `run_all`.
- *clean under load* — readings taken under contention, kept because a flake that
  only shows under load is worth a record; a failed run out of fifty-two is a
  known flake with a ratchet, not a red suite.
- *values handed over*, *engine tests* — counts, with the gating number beside
  them.

The renderer asserts it: a tile that neither gates nor has a reason stops the
render rather than printing an unexplained ratio.

## 4. And the rule fires

Every check above would pass on a page whose banner was hard-coded green. So
`verify_board` breaks a gate on a **copy of the ledgers**, re-renders, and requires
the banner to go red and that gate — and only that gate — to be named `NOT MET`.
A rule with no violator cannot show that it works (ADR-207, ADR-208, ADR-209,
ADR-211), and this one is asserted against a board that is green by construction.

`verify_board` 102 → 112.
