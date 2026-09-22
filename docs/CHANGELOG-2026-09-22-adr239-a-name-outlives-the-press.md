# 2026-09-22 — ADR-239: a name outlives the press

## Fixed

- **The door:** `_resolve` stamps the page as it stands (DISCOVER) before it
  reads a name. A press that rebuilt a list left its controls unstamped, and a
  name published a moment earlier answered "no control answers to it".
- **Field notebook:** tally cards are named by their category, not
  category+count (`species-a`, not `species-a0` → `species-a1`). Quadrat and
  mark–recapture steppers say what they count (*add one to Q4*, *add one to
  Marked (M)*).
- **Farm scout:** pollinator cards are named by the visitor, not visitor+count.

## Added

- `tools/audit_addresses.py`: presses every addressed control of every page
  through the door and reads its old name back (HELD / GONE / RENAMED /
  SHADOWED). It runs in `run_all` and writes `tools/address_ledger.json`. The
  kit reads 1,632 presses: 1,615 held, 17 gone, 0 renamed, 0 shadowed.
- `verify_addresses` (36 checks) and `tools/mutate_addresses.py` (12/12
  killed), both on the board.

## Changed

- `page-field-notebook-science` (39 steps) and `page-farm-scout-science` (11
  steps) press by name. There are no `host#n` indexes left in either.
