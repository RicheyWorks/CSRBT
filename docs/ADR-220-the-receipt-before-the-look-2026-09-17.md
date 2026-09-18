# ADR-220 — one failed snapshot and the act ran twice; the budget that bounds the cache read zero while it held 25 MB

**This gateway was copied from FlowersForever's in ADR-097 and says so in its
docstring. That gateway then spent a week being retried against, and learned two
things. This one had learned neither, and nothing here could have told it: every
check of replay safety in `verify_contract` retries a command whose first call
SUCCEEDED.**

## 1. What was measured, before anything was changed

A plugin whose act lands and whose next `observe()` raises once — a browser that
went away while being looked at, which is the ordinary way a page target fails:

    first call      raised RuntimeError          effect count 1
    retry, same id  replayed=False               effect count 2

`Gateway.execute` ran the act, then took the snapshot that rides the response,
then built the response, then wrote the receipt. Anything that failed between the
first step and the last left an act with no receipt, and the documented remedy
for a lost answer — *send it again under the same id* — did it a second time.

A command that RAISED had the same shape: `boom` under one request id, sent
twice, ran twice. What a command that raised did to its target is the one thing
nobody knows. It is the last one that should run twice under one id.

And the bound on the cache:

    budget says 0 bytes of 8,388,608
    the cache holds 25,807,871 bytes in 256 receipts

`_bytes(output)` sized the action's `output`. The receipt kept the whole
response, and the response carries the snapshot — 77 KB of it on the collection
sheet. The contract's docstring says *"256 commands or 8 MiB of output"*, which
is a true description of a number that bounded nothing.

## 2. The rule

**Retrying a request id never runs anything twice.** One rule; three cases, and
the manifest now states all three, because a client reads the manifest.

- **Landed.** The receipt is written the moment the act returns, before the
  look and before anything is sized. A look that fails is refused `failed` with
  `LANDED` in the message and the request id to send again; the retry is
  answered from the receipt, completed by LOOKING again and never by acting. A
  look that fails twice leaves the receipt where it is.
- **Raised.** A command that raised keeps a receipt carrying what it raised
  with. The same id is refused `failed` again with the original reason and *NOT
  run again — send a new request_id*. Trying again is a decision, and a new id
  is how a client makes it. The replay is re-authorised like any other: a gate
  closed since does not go on saying what happened behind it.
- **Refused.** A refusal keeps no receipt. Nothing ran, and a receipt would make
  the id a client is already holding unusable for the corrected call.

**The budget counts what the cache holds** — the retained response as JSON,
snapshot included. A response that cannot be sized is charged the whole budget
and kept anyway: sizing happens after the receipt is written, so failing there
could only ever lose it.

**A receipt completed late moves to the newest position before the trim.** It was
written when its act landed, so by the time its look succeeds it is the OLDEST
entry in the cache, and completing it is what makes the cache grow. Trimmed in
place, the receipt being completed is the one evicted, and the next retry runs
the act. FlowersForever found that one in its own gateway on 14 September; it is
held here by a fixture that fills the cache to within one receipt of its budget
around a late one.

## 3. What this costs

On a page-sized target the byte bound now bites: 120 commands, 83 receipts
kept, where it used to keep all 256 and count none of them. A client
that retries a command more than eighty calls old gets it run again, which is
what a bounded cache means and what the manifest has always said; the number
was 256 only because the other bound was not measuring.

## 4. Numbers

`verify_contract` 161 → 180. `mutate_contract` 74 → 87, all killed. One SURVIVED
its first run — *rewriting a receipt counts its bytes twice* — and was equivalent
for a reason worth fixing: a receipt waiting for its look was counted as zero
bytes, so there was nothing to count twice. It is counted at what it holds now.
One HUNG the suite: a budget that had stopped counting kept a fixture loop
filling 8 MiB with nothing, and a suite must not be hangable by its own subject
(ADR-192); the loop is bounded. One of the
thirteen was a bad mutant first (`if False:` on the waiting-receipt branch fell
through to `dict(None)` and crashed the suite instead of failing it) and was
re-aimed at the line that does the work. Two of the thirteen are for clauses
that have been in this file since ADR-097 and had no mutant at all: *the second
identical command is answered from the cache*, and *the same id with different
contents is a conflict*.

No page, task, plugin or transport was edited. `failed` is an existing code.

## 5. Held

- **A `receipt` operation** — ask what happened to a request id WITHOUT risking
  that it runs (FlowersForever's `replay()`). A retry is safe now while the
  receipt lives; after eviction it executes. Price: a fifth operation on a
  contract whose three transports are each held to naming four. Trigger: the
  first client that retries across an eviction.
- **A raise inside a page action may have half-landed and the page is not asked.**
  The receipt stops the second run; it does not say what the first one did.
  The diff on the next observe does.
