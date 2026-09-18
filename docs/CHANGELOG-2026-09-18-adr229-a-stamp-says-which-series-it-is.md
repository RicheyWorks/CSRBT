# 2026-09-18 — ADR-229: a stamp says which series it is (protocol 1.9)

## Changed

- **Report stamps are `r` + 12 hex; snapshot stamps stay `s` + 12 hex.**
  `if_stamp` handed a report stamp is refused `invalid_argument` naming both
  kinds, before any look. `observe` and `read-report` handed the other kind
  answer the whole document and say which kind they were given. The manifest
  publishes a `stamps` block. Protocol 1.8 → 1.9.
- **The seventh blind trial** — food web, relevé, tree proofs, ethogram, one
  attempt each: 42 / 69 outcomes, 322 / 370 claims, 216 calls. Every wrong-kind
  `if_stamp` was refused as the wrong kind and corrected on the next move;
  zero report stamps answered `stale`. Traces + provenance under
  `tools/traces/blind7/`.
- `mutate_report` gains `--only N` (partial runs do not write the ledger).

## Checked

verify_contract 221 → 230, verify_report 248 → 249, verify_tasks 411 → 429,
mutate_contract 105 → 111, mutate_report 149 → 151.

## Found, next slice

The observe baseline is one slot deep: every act moves it, so a stamp from any
earlier move in a batch is "unknown". All four operators hit it.
