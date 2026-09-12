# 2026-09-12 — ADR-195: the report gets a `since` too

**The gap ADR-194's fourth blind trial left open, reported independently by two
of its four operators: the diff was control-shaped. `read-report` now carries a
`stamp` and takes a `since`.**

## What it costs now

| call | bytes, stand sheet |
|---|---|
| `read-report` | 15,337 |
| `read-report since=<current>` | **101** |
| `read-report since=<one call ago>` | **1,712** |
| `read-report since=<unknown stamp>` | 13,433 — the whole report, and why |

## Added

- `harness_contract.key_for(path, keys)`: a keyed path may carry a `*`. An
  exact path wins; otherwise a pattern matching segment for segment and length
  for length. `stamp_of` and `diff_of` both go through it, so they cannot
  disagree about whether a list moved.
- `PagePlugin.REPORT_IDENTITY` and `PagePlugin._report()`: one baseline per
  session, `changed: false` when nothing moved, a diff when something did, the
  whole report with `sinceUnknown` for a stamp this session never issued.
- `read-report` gains a `since` argument, validated `^s[0-9a-f]{12}$`.
- `verify_contract` 143 → 148 (section 15, the wildcard).
- `verify_report` 179 → 194 (section J, the report's stamp and `since`).
- `mutate_contract` 60 → 65 / 65, `mutate_report` 110 → 118 / 118.

## Not changed

Nothing about a report's contents. `figures`, `by`, `sources`, `boxes`,
`lines`, `rows`, `tables`, `headings`, `order`, `rules` and `route` are what
they were; a call without `since` answers exactly as before, plus a stamp.
