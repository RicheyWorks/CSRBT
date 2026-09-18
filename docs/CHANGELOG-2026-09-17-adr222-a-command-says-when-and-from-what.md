# 2026-09-17 — ADR-222: a command may say when it stops being wanted, and what it was decided from

## Added (protocol 1.8)

- **`expires_at`** — an ISO-8601 instant with an offset. A command that has not
  run by then is refused `stale` and is not run. Numbers, quoted numbers and
  zoneless times are refused `invalid_argument`. A receipt is served whatever
  the clock says; a retry with a new deadline is the same request.
- **`if_stamp`** — the stamp of the snapshot the caller decided from. If the
  target has moved, `stale`, nothing run, and `since=<stamp>` says what moved.
  The checking look is not served and not remembered; the rung is checked
  first; a target that cannot be looked at is `unavailable`, not run blind.
- Over MCP/HTTP both ride in `_meta`. The manifest publishes `commandFields` and
  `freshness`. `Gateway(..., clock=)`.

## Checked

`verify_contract` 196 → 221, `mutate_contract` 87 → 103, `verify_walk` protocol
1.8. Both fields are optional; every task, walk and trace runs unchanged.
