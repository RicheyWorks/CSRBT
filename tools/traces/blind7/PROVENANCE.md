# The seventh blind trial — provenance (ADR-229)

Four operators, **four more science pages no blind operator had ever driven**
— food web, relevé, tree proofs, ethogram — through the door with ADR-229 in
it: a stamp names its series in its first character (`s…` snapshot, `r…`
report), and every door that takes one says so when handed the other. The
sixth trial (ADR-228) found all four of its operators handing the report's
stamp to `if_stamp` and being told the page had *moved* when it had not. This
trial measures whether that is gone.

Run **2026-09-18**. Traces are gzipped; `gunzip -c <file>` is the trace exactly
as the server wrote it. `tasks/` holds the four task files as of the run.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind7/CSRBT` — a copy of the repository with `tools/tasks/`,
`tools/traces/`, `tools/delivery/`, `tools/push/`, every ledger, the board and
its renderer, every `mutate_*.py`, the whole of `tools/verify/` except
`_kit.py`, and every `*.md` **removed from the filesystem** (ADR-136). Each was
handed its blind brief (ADR-193), an `OPERATOR.md` that now has a section
"Two kinds of stamp — the first character says which", and
`blind_console.py --session <name>`; the three whose goals end in an
irreversible act ran with `--rungs SENSITIVE_READ,DRAFT,MUTATE,DESTRUCTIVE`,
the ethogram with the supervised three.

## What it measured

| task | reached | of | claims | of | calls | attempts |
|---|---|---|---|---|---|---|
| page-food-web-science | **7** | 13 | **33** | 43 | 26 | 1 |
| page-releve-science | **18** | 31 | **64** | 83 | 92 | 1 |
| page-tree-proofs-science | **10** | 12 | **169** | 176 | 40 | 1 |
| page-ethogram-science | **7** | 13 | **56** | 68 | 58 | 1 |
| **total** | **42** | 69 | **322** | 370 | **216** | **4 in 4** |

One attempt each. All three destructive goals were reached — the food web's
Undo, the relevé's line-point Undo, the tree proofs' Reset (twice) — each
guarded with `if_stamp`.

## What it measured about ADR-229

The trial's subject, in the traces and not asserted. Every operator was asked
to try `if_stamp` with the *wrong* kind of stamp at least once, so the door's
answer is recorded four times:

- **Handed a REPORT stamp, `if_stamp` refused `invalid_argument` naming both
  kinds and the fix — on all four.** *"if_stamp guards the SNAPSHOT and
  'r7118d0a61de5' is a REPORT stamp (read-report's, r...): pass the `stamp` a
  snapshot or a response carried (s...) … nothing was run."* No look was
  taken; nothing ran. **Every operator got it right on the very next move.**
  In the sixth trial the same mistake was answered `stale … has moved`, and
  every operator spent a guarded retry working out what had "moved".
- **Handed a SNAPSHOT stamp, `read-report`'s `since` answered the whole report
  and named the kind** (ethogram, deliberately): *"the whole report:
  's72a425d34c7d' is a snapshot stamp, not a report stamp."*
- `if_stamp` with a snapshot stamp the page had moved past was still refused
  `stale` naming both stamps (food web, ethogram); a past `expires_at` was
  refused *expired* on all four; a current snapshot stamp let the act run.

Nobody was told a page had moved when it had not.

## What every operator found in the door (new; the next slice)

**The observe baseline is one slot deep.** `observe … since=<stamp>` answers
the diff only against the *last* snapshot this session served, and every act's
response serves one. All four operators — independently, in their own words —
reported "unknown stamp" for stamps the session itself had issued: the stamp
from the first read, or from a response that was not the last move of a batch.
Reproduced after the trial on the food-web page: a stamp from a call's response
is the baseline in the next console call (`changed: false`), and the stamp
before it is not. `if_stamp` compares against the *target*, not a baseline, so
the same stamps work there — which is what made it look inconsistent. The
ADR-191 promise "a stamp you read in one call is still the door's baseline in
the next" is true only if nothing was served in between, and an operator
batching six acts per call is never in that state. A ring of recent baselines
(the last N stamps, each diffable) is the fix; its price is N snapshots of
memory per plugin.

## What they found in the pages (filed, not fixed)

- **tree proofs** — the brief holds `key 63 costs 7 actual / 13.0 amortized`;
  the page reports **6 / 13.0** (five rotations + 1, symmetric with key 1).
  The one balanced-access outcome this trial missed on that page is this
  divergence. And the worst-case note says the 63 keys were inserted in
  *ascending* order while the shape it describes (key 1 at the bottom of a
  left-leaning path) and the page's own prose elsewhere say *descending*.
- **ethogram** — the budget note still reads "percentages are of 05:30
  observed, not 06:00 elapsed": 06:00 is time in a state, elapsed is 06:20; the
  separate "00:20 of the session is in no state" note (which ADR-128's goal
  praises) is right, and this sentence beside it still uses the old word. The
  budget CSV carries the three state rows only — no out-of-sight row, no event
  rates. "1 bouts".
- **relevé** — the voucher's condition/phenology dials default to *in flower /
  flowering*, so a voucher label carries "[in flower, flowering]" the operator
  never chose. Line-point entry keeps species and stratum after `+ hit`, so
  repeated presses add repeated hits (as designed; noted because the brief's
  two picks needed five presses).
- **food web** — the operator read `charts/webSvg/longest` (the reader's
  longest-path-command count) as the chain length and saw 3 beside the page's
  5; not a page defect, a reader field name that invites the misreading. The
  print payload's text is empty (a print event carries no document).

## Why these numbers are floors

No blind operator had touched these four pages; `verify_tasks` section F7
holds this run's reached/claims as the floor a later door may not fall below.
Graded as a ROUTE all four are FAIL, as in every trial before it.
