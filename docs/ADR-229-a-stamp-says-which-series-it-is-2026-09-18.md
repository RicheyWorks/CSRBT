# ADR-229 — A stamp says which series it is

**The snapshot (ADR-191) and the report (ADR-195) each carry a stamp, both were
`s` + twelve hex digits, and nothing on the wire said which was which. All
four operators of the sixth blind trial handed the report's stamp to
`if_stamp`, which guards the snapshot, and were refused `stale` — told the page
had *moved* — about a page that had not. The fifth trial's operators made the
same mistake the other way with `read-report`'s `since`. Never a wrong answer:
the door fails toward refusal. But a wasted guarded retry every time, and a
sentence that was false.**

## Decision — protocol 1.9

- A stamp names its series in its first character: **`s`** + 12 hex is a
  snapshot stamp (`observe`'s `since` and `if_stamp` take it), **`r`** + 12 hex
  is a report stamp (`read-report`'s `since` takes it). One digest algorithm,
  `stamp_of(…, series=)`, one character of difference; `series_of(stamp)`
  reads it back.
- **`if_stamp` handed a report stamp is refused `invalid_argument`, before any
  look, naming both kinds and the fix**: *"if_stamp guards the SNAPSHOT and
  'r…' is a REPORT stamp (read-report's, r...): pass the `stamp` a snapshot or
  a response carried (s...) — nothing was run."* The old `stale` said the page
  had moved; this says what was actually wrong.
- **`observe` handed a report stamp, and `read-report` handed a snapshot
  stamp, still fail toward more** — the whole document — but the reason names
  the kind rather than calling the stamp *unknown*, which sent operators
  looking for a document they had never read.
- The manifest publishes a `stamps` block (both series and what a mismatch
  does at each door); `read-report`'s `since` argument accepts `^[sr]…$` so the
  wrong-kind sentence is reachable rather than a pattern refusal.

verify_contract 221 → 230 (section 4d), verify_report 248 → 249 (report
stamps are `r…`; a snapshot stamp as `since` is named), mutate_contract
105 → 111, mutate_report 149 → 151. The fifth and sixth trials' traces carry
`s…` report stamps and still grade: the fold treats a stamp as opaque.

## The seventh blind trial

Four more pages no blind operator had driven — food web, relevé, tree proofs,
ethogram — one attempt each, the three destructive goals reached and guarded.

| page | outcomes | claims | calls |
|---|---|---|---|
| food web | 7 / 13 | 33 / 43 | 26 |
| relevé | 18 / 31 | 64 / 83 | 92 |
| tree proofs | 10 / 12 | 169 / 176 | 40 |
| ethogram | 7 / 13 | 56 / 68 | 58 |
| **total** | **42 / 69** | **322 / 370** | **216** |

**The measurement.** Each operator was asked to try `if_stamp` with the wrong
kind once. All four were refused `invalid_argument` naming both kinds, and all
four got it right on the very next move. Not one report stamp was answered
`stale … has moved`; the sixth trial's traces carry four such refusals and
this trial's carry zero, and `verify_tasks` F7 holds both numbers.

## What every operator found — the next slice

**The observe baseline is one slot deep.** `observe … since=<stamp>` diffs
only against the *last* snapshot this session served, and every act's
response serves one. All four operators, independently, reported "unknown"
for stamps the session had itself issued — the first read's, or a response's
that was not the last move of a batch. Reproduced after the trial: a response's
stamp is the baseline in the next console call; the one before it is not.
`if_stamp` compares against the *target*, so the same stamps work there, which
is what made it look inconsistent. ADR-191's promise — a stamp read in one call
is still the baseline in the next — holds only when nothing was served in
between, and an operator batching six acts per call is never in that state. A
ring of the last N baselines is the fix; the price is N snapshots of memory
per plugin.

## Filed, not fixed

- tree proofs: the task holds key 63 at 7 actual; the page reports 6. The
  worst-case note says *ascending* for a shape that is descending insertion.
- ethogram: the budget note still calls 06:00 "elapsed" beside the corrected
  in-no-state note; the budget CSV has no out-of-sight row and no event rates.
- relevé: voucher condition/phenology dials default to in-flower/flowering.

## Held

Thirty-two science tasks remain un-operated blind (44 − 12). The one-slot
baseline, above, is the highest-value door change now on the table.
