# 2026-09-17 — ADR-220: one failed snapshot and the act ran twice; the cache budget read zero while it held 25 MB

**Both rules are FlowersForever's gateway's, learned after this one was copied
from it in ADR-097. Every replay check here retried a command whose first call
had SUCCEEDED, so nothing could have found either.**

## Fixed

- **The receipt is written before the look.** An act that landed is recorded the
  moment it returns. A snapshot that then fails is refused `failed` with
  **LANDED** and the request id; the retry is answered from the receipt,
  completed by looking again and never by acting. Before: the act ran twice.
- **A command that raised keeps a receipt.** The same id is refused `failed`
  again, *NOT run again*; a new id is how to try again. Re-authorised like any
  replay. **A refusal keeps none** — nothing ran.
- **The budget counts what the cache holds**: the retained response as JSON,
  snapshot included. It sized `output` only — 0 of 8,388,608 bytes reported,
  25,807,871 held. On a page-sized target 120 commands now keep 83 receipts.
- **A receipt completed late moves to the newest position before the trim**, so
  the trim cannot evict the receipt it is completing.
- **A response that cannot be sized** is charged the whole budget and kept.
- The manifest states the retry rule (`replay`).

## Checked

`verify_contract` 161 → 180, `mutate_contract` 74 → 87. One mutant survived its
first run — *rewriting a receipt counts its bytes twice* — and it was equivalent
for a reason worth fixing: a receipt waiting for its look was counted as zero
bytes. It is counted at what it holds now, and the mutant dies. One was a bad
mutant (`if False:` fell through to `dict(None)`) and one HUNG the suite: a
budget that had stopped counting kept a fixture loop filling 8 MiB with nothing.
The loop is bounded.
