# 2026-09-16 — ADR-216: the fix for a reading that looked like a failure asserted a ratchet that did not exist

**ADR-215 gave the board's `6 / 7 — clean under load` tile this line: "a failed
run out of fifty-two is a known flake with a ratchet, not a red suite." There was
no ratchet. The contention ledger had no ceiling, no declaration, and nothing
that ran it.**

## Fixed

- **`tools/contend.py`** — every pairing carries a **ceiling that only comes
  down**. `--raise-floors` records today's count wherever it is lower; a pairing
  above its ceiling fails. `--declare PAIRING --reason` exists and is refused
  without a reason. A pairing with no ceiling yet is not above one.
- **Bare invocation reports**, so `run_all` runs it — a ceiling nothing checks is
  a number, not a ratchet, and this was the only instrument in the kit whose
  readings nothing ran on a schedule. The slow sweep stays opt-in.
- **`harness_board.py`** — the tile's line says what the rule is instead of
  asserting one.
- The known failure is **not declared**: ADR-142's point is that a re-rolled
  flake is a measurement nobody took. It is held where it is and may not rise.

## Checked

- `verify_contend` 36 → 42: the ratchet against a fixture ledger with one pairing
  over, one exactly at, and one with no ceiling; every shipped pairing carries a
  ceiling and none is above it; the failing one is undeclared; bare invocation
  reports; `run_all` runs it.
- `verify_board` requires the tile's line to **name the rule that holds it**.
