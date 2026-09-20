# 2026-09-18 — ADR-231: `if_stamp` guards either document (protocol 1.11)

## Changed

- **`if_stamp` takes a REPORT stamp** (`r…`) and guards the figures: the door
  asks the target for its report's stamp now (`Plugin.stamp("report")`, new
  optional hook) and refuses `stale` naming the report, both stamps and
  `read-report since=`. A target with no report is refused `invalid_argument`
  by name; so is a string that is not a stamp of either series. Manifest
  `freshness.ifStampTakes: ["snapshot", "report"]`.
- **The report's stamp ignores the screen chrome and the open pane.** The
  report names `chrome` (`keepBox`, `sendBox`, `toast`); those boxes and
  lines, and `route`/`shown`, are noise for the stamp and the diff — served,
  not compared, named. A box that contains a strip is read without it.
- **The MCP trace records the guard** a call carried (`guard`), only when one
  was named.
- **`docs/OPERATOR.md`** is the canonical blind-operator manual: guard the
  act that depends on the figures, not a run of presses; `value` not `text`.
- **The ninth blind trial** — cell bench, cp bench, deployment log, farm
  scout, one attempt each: 71 / 107 outcomes, 184 / 275 claims, 602 calls.
  Run in two halves: on the door as built, 10 of 11 report-guard refusals were
  the chrome's clock; on the fixed door, 0 of 131 — 99 figures moved, 88 of
  them with the snapshot stamp unmoved. Under `tools/traces/blind9/`.

## Checked

verify_contract 241 → 261, verify_report 252 → 276, verify_mcp 98 → 101,
verify_tasks 446 → 466, verify_walk protocol 1.11; mutate_contract 116 → 126,
mutate_report 153 → 162, all killed.

## Filed

cp bench `read-control` on a picker never says which option is selected; farm
scout's pollinator card renumbers later positional addresses and the page
opens pre-filled with the demo and the clock's date; a guard on both documents
at once is held on a named trigger.
