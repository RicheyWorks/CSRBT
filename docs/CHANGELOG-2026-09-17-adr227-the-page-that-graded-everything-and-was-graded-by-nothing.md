# 2026-09-17 — ADR-227: The page that graded everything and was graded by nothing

## Added

- **`tools/mutate_board.py`** — 43 mutants against `harness_board.py`, each
  re-rendering its own board before `verify_board` runs so the byte-for-byte
  check cannot cover for the arithmetic and rendering checks. The one subject
  in the kit that had no runner.
- **`verify_board` section 9** — a fixture ledger set with every gate broken at
  known numbers; `summary()` held to 39 exact figures and `render()` to the
  bytes of each row. 121 → 204.

## Checked

`mutate_board` 43/43 killed, first honest run. Board 1103/1103 mutants.
