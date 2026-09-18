# ADR-228 — The two fields an operator could not send, and the four pages nobody had operated

**ADR-222 gave the gateway `if_stamp` (act only if the target is still what I
read) and `expires_at` (do not run me late). The fifth blind trial's operators
had no way to send either: `blind_console` built a plain call and nothing else,
so an operator who had just read a figure could not say "clear the runs only if
the page is still the one I read". This slice offers both, and spends them on
the thing they were for — the first four science pages no blind operator had
ever touched.**

## The change to the door

A `call` move may carry `if_stamp` and/or `expires_at`; the console puts them in
`_meta`, exactly where the MCP transport takes them (ADR-222), and only when the
move names them, so a move that carries neither is byte-for-byte the call it
always was. `OPERATOR.md` documents both and when to reach for them: guard an
irreversible act against a page that moved between the read and the press.

verify_mcp 93 → 98 holds the passthrough live against the fixture door — a past
`expires_at` and a moved-past `if_stamp` are each refused `stale`, a plain call
still runs — and mutate_contract 103 → 105 breaks the console two ways (strip
both fields; forward the deadline but not the stamp), each killed by the live
check its clause serves.

## The sixth blind trial

Four general-purpose operators, fresh context, a checkout with `tools/tasks/`,
the traces, the ledgers, the board, every `mutate_*`, all of `tools/verify`
except `_kit.py`, and every `*.md` removed from the filesystem (ADR-136). Four
pages **no blind operator had ever driven** — greenhouse, soil bench, survey
design, tree visualizer — each of whose goals ends in an irreversible act, so
each ran with the fourth rung. One attempt each.

| page | outcomes | claims | calls |
|---|---|---|---|
| greenhouse | 18 / 24 | 96 / 107 | 43 |
| soil bench | 11 / 17 | 41 / 53 | 40 |
| survey design | 15 / 22 | 40 / 54 | 35 |
| tree visualizer | 11 / 15 | 62 / 71 | 53 |
| **total** | **55 / 78** | **239 / 285** | **171** |

## What it measured about the two fields

Every operator guarded its destructive act with `if_stamp`, and the door's
refusal is in the trace, not in a claim about it: on all four, a destructive
`activate` bound to a stamp the target had moved past was refused `stale`,
naming the stamp it was bound to and the stamp the target had; the tree
operator also set a 2020 `expires_at` and was refused *expired*, then ran the
same Clear with a fresh stamp and a future deadline. After the guard the act
ran on all four — the greenhouse wipe (runChart removed), the soil undo, the
survey remove, the tree clear. That is the first evidence ADR-222's fields
reach the door in work nobody scripted.

## What it found

- **Every operator confused the two stamps.** `read-report` carries an inner
  content stamp and the door carries an outer snapshot/baseline stamp;
  `if_stamp` guards the outer one. All four first passed the report's inner
  stamp and were (correctly) refused `stale`, then switched and succeeded. It
  never caused a wrong answer — the door fails toward refusal — but it cost
  every operator a guarded retry. The fifth trial filed the same confusion for
  `read-report`'s `since`. This is the clearest next slice: one stamp, or a
  prefix that says which series it belongs to.
- **tree visualizer, filed not fixed** — the task holds `24 nodes after 15
  seeded random draws` and the page produces **28**. The operator reproduced
  the draw sequence exactly (60 first, 19 eleventh) but every press answered
  `inserted`: the page's random button draws until it finds a new key, so 13 +
  15 = 28, and the task's 24 would need four collisions the page never allows.
  The one seeded outcome this trial missed on that page is this divergence.

## Held

The two-stamp collision is a real defect with a name and a cost, held for the
next slice. Thirty-six science tasks remain un-operated blind; the loop that
closes them is a trial like this one each slice, four pages at a time, floors
ratcheted, until every one has a trace.
