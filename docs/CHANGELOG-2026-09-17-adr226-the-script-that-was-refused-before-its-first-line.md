# 2026-09-17 — ADR-226: The script that was refused before its first line

## Fixed

- **`push-adr225-siblings.ps1` parses.** `"!! $dir: ..."` is a drive-qualified
  variable to PowerShell and a parse error; both lines are `${dir}:` now.
  ADR-225's main script pushed; the sibling one had not run.

## Added

- **`deliver.ps_parse_faults(text)`** — every `$name:` that is not a
  PowerShell scope, with its line.
- **`deliver.py --check`** reads every script under `tools/push/`, hand-written
  ones included, and refuses one with a parse fault, naming the line and the fix.

- **The board is stamped in UTC.** Rendered in local time, the committed page
  was a different page on every machine in a different zone, and `verify_board`
  failed on the operator's VM with identical ledgers. The footer names the zone.

## Checked

`verify_delivery` 76 → 82. `mutate_delivery` 60 → 63, all killed. `verify_board` 118 → 121 (the same
ledgers render the same bytes in three time zones).
