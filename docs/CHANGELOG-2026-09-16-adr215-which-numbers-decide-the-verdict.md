# 2026-09-16 — ADR-215: the board printed "everything is green" beside a reading of 6 / 7

**The Harness Board's headline was not derived from what it displays. `all_green`
was a hand-written conjunction over seven summary fields; the page rendered
eleven tiles and six of them do not gate the verdict — one of which reads
`6 / 7 — clean under load`.**

## Fixed

- **`harness_board.py`** — the verdict is derived from a **named list of seven
  gates**, and the list is rendered in the header beside the verdict, with any
  unmet gate marked `NOT MET`. Two of the gates (the walks, the traces) have no
  tile, so the list is named rather than inferred from what is displayed.
- **Every tile declares which it is** — `counts toward the verdict`, or one line
  saying what kind of number it is instead: a count, a ratchet, a ratio with a
  declared reason on the other side, a reading under contention. The renderer
  refuses to print a tile that does neither.

## Checked

- `verify_board` 102 → 112: the banner is the conjunction of the named gates and
  nothing else; both tile-less gates are named; every tile declares; and — because
  every one of those would pass on a hard-coded green banner — **a gate is broken
  on a copy of the ledgers**, the page re-rendered, and the banner required to go
  red with that gate, and only that gate, named.

## How it was found

A subagent republishing the board read it and said the two statements disagreed.
They did not — and that was the defect.
