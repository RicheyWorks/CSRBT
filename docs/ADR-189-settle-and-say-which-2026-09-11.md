# ADR-189 — Settle before the first act, and say which of the client's problems it is

**Status:** accepted · **Date:** 2026-09-11 · **Two more of ADR-187's findings, and they turn out to be the same finding twice: the door made the client do its bookkeeping. Three of four blind operators opened with a `pick` or an `activate` and were told the page had no control of that kind AT ALL — the kit builds controls in script at load, and nothing had stamped them. The door settles now: it stamps the page and waits for ADR-188's version digest to stop moving, once per document, and it does that in the RISK READ as well as in `execute`, because the gateway asks for the risk first and a plugin that settled only in `execute` would wave a destructive button through on the first call of every session. And `stale` is a refusal of its own (protocol 1.6): a selector that was true when the client read it and is not now is neither malformed nor missing, and only a code of its own says *read again*. `verify_contract` 111 → 115, `verify_report` 140 → 149, `mutate_contract` 31 → 35, `mutate_report` 89 → 95.**

## 1. "This page has no action_btn control at all"

From the third trial's provenance, converging across operators:

> *A fresh page has no controls until something has looked at it. A first move
> of `pick` or `activate` was refused as "no such control at all", and once
> escalated to DESTRUCTIVE because the selector named nothing; a leading
> `observe` fixed it.*

The mechanism is not mysterious. `[data-h]` is not in the kit's HTML; it is
stamped by `harness.DISCOVER`, which `observe` runs. Until a snapshot has been
taken, every selector on the page resolves to nothing, and the door's answer —
truthfully — is that there is no control of that kind. Every operator worked it
out and put a leading `observe` in every moves file. That is the door asking
the client to do its bookkeeping, and after ADR-188 it is worse than that:
a stable name is *supposed* to be usable from the first call, and it was not.

## 2. Settling

`_settle()` stamps the page and then waits for the numbering to stop moving.
ADR-188's version digest is exactly the signal: it changes when a control
appears or an index shifts, so **two consecutive readings that agree mean the
page has stopped building**. Bounded at six rounds of 60 ms, because a page
that rewrites controls on a timer would never settle and a door that hangs is
worse than one that acts a moment early. It is a bounded wait, not a promise;
the suite says so by driving a page that adds a button 40 ms after load and
requiring the first call to find it.

`_ensure_settled()` runs it once per document — per DOCUMENT, not per
session: a plugin that remembered "I have settled" would be right about the
first page and wrong about every page after it, and a session that navigates is
the normal case. The marker is `window.__H_SETTLED`,
set to the version it settled at — so a navigation or a reload takes it with
the old document and the next call settles the new one, and nothing in the
plugin has to remember where the page has been. `open` and `reload` settle the
document they arrive in and answer with its version.

## 3. The part that would have been a hole

The gateway asks a plugin for the risk of a call **before** it executes it
(ADR-141's raise). So settling in `execute` alone would have produced this:

1. first call of a session: `activate @Clear trial`;
2. `risk_for` reads an unstamped page — the name answers to nothing — and,
   since ADR-188, a name that answers to nothing is *not* raised;
3. `execute` settles, the name now resolves to the button that clears the
   trial, and presses it.

A destructive control pressed without a raise, on the first call of every
session, and every check would have stayed green because each half is right on
its own. `risk_for` settles first, and the suite holds exactly that: on a page
nothing has looked at, `@↩ Undo` still reads DESTRUCTIVE.

## 4. `stale`, protocol 1.6

ADR-188 refused a selector stamped with a snapshot the page had moved past, and
carried the refusal as `not_found` with the word "stale" in the message. That
is three instructions spelled one way:

    invalid_argument   the call was malformed        -- fix it
    not_found          no such subject               -- look for another
    stale              your name for it expired      -- READ AGAIN and call with what you find

A client that cannot tell them apart retries the wrong thing, which is what the
blind operators did by hand each time the numbering moved under them. `stale`
is its own code now: the contract makes it, the MCP transport maps it to
`-32602` with the others that are the client's, and `harness_walk` counts it as
a refusal rather than a failure — a selector the page has moved past is the
walk doing its job, not the target misbehaving.

## What moved

    verify_contract    111 → 115      mutate_contract   31 → 35 / 35
    verify_report      140 → 149      mutate_report     89 → 95 / 95
    protocol           1.5 → 1.6

Four files carry the new code (the contract, the transport, the robot, the page
plugin), so `mutate_contract`'s subject list grew to match. No page and no task
was edited.

## Held

- The settle waits out a page that is still building *within its window* — six
  rounds of 60 ms, plus whatever `open` already waits. A control added a second
  later is not waited for, and the door does not pretend otherwise.
- The marker is per document and lives on `window`. A page that replaces its
  own controls without navigating (the key filters, a loaded pack) is not
  re-settled: the version moves, the client's indexes go stale, and *that* is
  what `stale` is for.
- `stale` is only raised for a selector that carried a stamp. An unstamped
  index that has moved still resolves to whatever is at that index — ADR-141's
  raise is the guard there, and a client that wants the stronger answer stamps
  its selectors.
- `forbidden` already distinguished a withheld rung from a missing tool
  (ADR-141); this slice did not touch it.
