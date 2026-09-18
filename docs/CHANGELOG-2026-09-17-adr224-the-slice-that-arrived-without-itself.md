# 2026-09-17 — ADR-224: thirty written judgements, and whether each is still about anything (ADR-218, rebuilt)

**ADR-218 reached origin as a paragraph, a board row, a ledger entry and a
`run_all` line, and as no code. This is it, rebuilt from those.**

## Added

- **`tools/exempt.py`** — the one place an exemption is granted; it filters and
  records `raw` (flagged before the exemption) and `seen` (everything the reading
  could have flagged) in one call. All six declaring audits use it; `outputs`
  keeps two records and writes its page verdict (`trap`).
- **`tools/audit_declared.py`** — every declaration in every ledger gets
  COVERING, IDLE, STALE or UNREAD; only covering passes; `--forget` prints the
  reason it removes; no `--declare`. Runs last in `run_all`.
- **`verify_declared`** 48, **`mutate_declared`** 45. Two or three checks in each
  of the six audits' suites and four mutants in each of their runners hold the
  shared rule through each audit's own reading.

## Found

See the ADR's §5 for the first reading of the live ledgers.
