# ADR-195 — The report gets a `since` too

**Status:** accepted · **Date:** 2026-09-12 · **ADR-191 gave the *snapshot* a stamp and a diff, and the fourth blind trial (ADR-194) proved it: four operators took the ~100 KB snapshot once and never again. Two of the four then reported the same gap independently — *the diff is control-shaped*. A `read-report` is thirty to a hundred kilobytes, it is the thing a science task is actually **about**, and it had no `since` at all, so an operator watching a computed figure re-read the whole report to learn that one box moved. The stand-sheet operator counted fourteen such calls. `read-report` now carries a `stamp` and takes a `since`: **15,337 bytes become 101 when nothing moved and 1,712 when something did.** It uses the contract's own `stamp_of` and `diff_of`, which needed one new thing — a keyed path may carry a `*`.**

## 1. The gap, in the operators' own words

> *"The diff is control-shaped. A `read-report`'s figures and boxes have no
> `since`, so an operator watching a computed figure must re-read the whole
> report."*

ADR-191's reasoning applies here unchanged and was simply not carried far
enough. A snapshot is taken on every act, so it got a diff. A report is taken
*when the operator wants to know what the page computed* — which, in a science
task, is after nearly every act. It is the larger of the two documents and the
one the task is scored on.

## 2. What it looks like on the stand sheet

| call | bytes |
|---|---|
| `read-report` | **15,337** |
| `read-report since=<current>` | **101** — `changed: false` |
| `read-report since=<one call ago>` | **1,712** — which two boxes moved, and what appeared |
| `read-report since=<a stamp this session never issued>` | **13,433** — the whole report, and why |

The 101-byte answer is not a smaller report. It is `{"stamp", "since",
"changed": false, "diff": null, "route"}` — and an unchanged stamp is
information in its own right, as ADR-194's breeding-bench operator said before
this existed: *"it told me immediately that those three calls were no-ops,
which I would otherwise have mistaken for failed calls."*

## 3. Two documents, one algorithm

The report does **not** get a stamping scheme of its own. It gets
`REPORT_IDENTITY` — a spec saying what identity means on a report — and is
handed to the same `stamp_of` and `diff_of` the snapshot uses. A third
implementation would be a third thing to get wrong, and the suite holds that
the plugin calls the contract's two functions by name.

What the spec says, and why:

- `figures`, `by`, `sources`, `rows` are maps of scalars and diff themselves.
- `boxes` are long strings. A changed box is reported as **that box** changing,
  with the first two hundred characters of each side — enough to say *which*
  box moved without paying for both copies of it.
- `shown`, `headings`, `order` and `lines/*` are keyed by their own text, so a
  line that appeared is **named** rather than counted.
- `tables/*` are **not** keyed. A row of cells has no identity of its own, so a
  table reports that it gained or lost rows, which is true, rather than
  pretending row three is the same row three.

## 4. The one new thing in the contract: `key_for`

ADR-191's key spec could only name a list it could spell out in full. That was
enough for a snapshot, where the lists are `controls`, `tabs`, `panes` — names
the *harness* chose. A report's lists are not: they live under ids the **page**
chose (`lines/kCountOut`, `lines/cwdOut`, `tables/p-method`), and a spec that
had to enumerate them would go stale the first time a page grew a box.

    key_for(path, keys)   an exact path wins; otherwise a pattern whose
                          `*` segments match, segment for segment and
                          length for length

`lines/*` says what the author means — *every list under `lines` is keyed the
same way* — without claiming to know what the page will call them. Both
`stamp_of` and `diff_of` go through it, and the suite holds that they agree:
a stamp that read the wildcard differently from the diff would say "changed"
about a report the diff calls identical.

## 5. It fails toward more

A `since` this session did not issue gets the **whole report** and the reason,
exactly as `observe` does (ADR-191). A diff against a baseline that is not
there would have to be invented, and an invented diff is worse than a large
one: it is a report of change that nobody can check.

The baseline is the last report this session was **served** — one per plugin,
replaced on every read. A stamp two reads old is therefore not held any more,
and the door says so plainly rather than diffing against whatever is nearest.

## 6. The two stamps are about different documents

`version` (ADR-188) is the page's control numbering. The report's `stamp` is
what the page *says*. On the stand sheet, five downed-wood diameters typed into
`#cwdD` recompute two boxes while the page grows and loses no control: the
report moved and the numbering did not. Narrowing the species filter does both
at once. A door with only one of the two stamps could not tell a reader which
had happened, so both are published and the suite holds the distinction with a
change that moves each without the other.

## What moved

    verify_contract    143 → 148      mutate_contract    60 → 65 / 65
    verify_report      179 → 194      mutate_report     110 → 118 / 118

## Held

- One baseline per plugin, and it is the last report **served**, not the last
  one read from the page — the two differ when a read refuses.
- `since` is validated as `^s[0-9a-f]{12}$` at the door, so a malformed stamp
  is an argument refusal and never a silent full report.
- A table's rows stay counted. The day a page gives its rows ids, the spec
  gains `tables/*: ["id"]` and nothing else changes.
- The report's stamp and `version` are published side by side and neither is
  derived from the other.
