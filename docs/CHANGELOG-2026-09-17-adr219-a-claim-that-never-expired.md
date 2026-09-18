# 2026-09-17 — ADR-219: origin/main was red for ten slices, and the audit built to see that called it "in flight"

**A fresh clone of `origin/main` fails `verify_keep` 270 / 271 while its own
ledger says 316 / 316. ADR-207's change to `tools/keep_emit.py` was never
staged, and `audit_delivery` excused it because ADR-206's manifest — shipped two
slices earlier — still "claimed" the path.**

## Fixed

- **A claim expires when its slice ships.** `audit_delivery.claimed()` reads only
  unshipped manifests. It read all seventy-one, forever: 221 files "in flight",
  every hot file in the kit among them.
- **Where there is git, git is asked** — which bytes are not HEAD's, which
  manifests are in HEAD's tree. No git, no repository, no commit, or a failed git
  is *no evidence*, never *clean*; the audit falls back to the ledger and prints
  which evidence it read.
- **`deliver.py --record` says by name that a slice is over** (`recorded`), which
  is what ends its claim where there is no git.
- **`deliver.py --catch-up`**: a stalled ledger, brought up to what git vouches
  for and nothing else. Here: 217 paths, 71 slices. The ledger had not moved
  since ADR-190.
- **`deliver.py --check` holds the recording step**: committed and never
  recorded is a problem. It named 27 slices.
- **`tools/keep_emit.py` delivered** — the five ADR-207 pages are in the
  emitter's list in origin, where `verify_keep` compares that list against the
  pages that carry the block.
- `_SESSIONS` gains this session; every older script still matches under the
  session it was signed from.

## Found, not fixed

- `docs/AI_HARNESS.md` in origin carries an **ADR-218** paragraph whose slice —
  `tools/exempt.py`, `tools/audit_declared.py`, `verify_declared` — exists
  nowhere. It rode out in ADR-217's commit on four shared paths (this document,
  `harness_board.py`, `mutant_ledger.json`, and `run_all.py`, which runs an
  `audit_declared` that is not there). Held with a trigger in the ADR.

## Checked

`verify_delivery` 50 → 66, `mutate_delivery` 38 → 53 all killed. The first run of
section E failed five older checks: `shipped()` inferred "over" from a path's
`by`, and an adoption writes `by` too.
