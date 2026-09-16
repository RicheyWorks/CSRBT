# 2026-09-16 — ADR-212: three buttons handed the reader a file the published kit cannot deliver, and told them it had arrived

**A published artifact runs in a sandboxed frame that refuses a page-started
download silently — no throw, no return value, nothing to test. Three controls of
this kit handed their payload over by download and by no other route, and all
three raised a message saying the file had gone.**

## Fixed

- **`breeding-bench.html` and `cp-bench.html` — *Download bench.csv*** said
  `"bench.csv downloaded"`. Both handlers already carried a comment explaining
  that a hosted viewer can refuse the download silently — which is why they
  correctly decline to mark the outbox. The ledger was honest and the toast was
  not.
- **`experiment-guide.html` — *Download .eco*** said `"Downloading x.eco"`.
- All three now also put the bytes on the **clipboard**, which reports failure,
  and say which of the two channels the reader can count on. The outbox mark goes
  with the copy, where there is an answer to record.
- `page-experiment-guide-design` holds both payloads — download and clipboard,
  the same bytes — rather than asserting there is exactly one.

## New

- **`tools/audit_takeaway.py`** — presses every control `audit_outputs` counts as
  one that hands something over and reads the payloads by CHANNEL. STRANDED is a
  ratchet per page; CLAIMS fails on sight.
- **`tools/verify/takeaway`** — 28 checks over six fixtures.
- **`tools/mutate_takeaway.py`** — 19 mutants, no known equivalents.

**3 of 81 controls stranded → 0. 3 claims → 0.**
