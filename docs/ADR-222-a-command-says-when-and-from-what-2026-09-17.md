# ADR-222 — a command could not say when it stopped being wanted, or what it had been decided from

**ADR-221 made the door refuse a field it does not know, and the two it refused
first were the two a careful client reaches for: `expires_at` and a name for the
look the command was decided from. FlowersForever's gateway requires the first
on every physical command and offers the second on every desktop action. This
gives both a meaning here. Protocol 1.8.**

## 1. Why a name is not enough

ADR-188 stamps a POSITIONAL selector (`kind:index@v<digest>`), so an index cannot
silently mean a different control after the page has been rebuilt. A NAME has no
such guard, and cannot: `@Delete` is still `@Delete` after a dialog has opened
over the page, after the row under it has been swapped, after another client of
the same session has moved the target. The name resolves. What it resolves to is
no longer what the caller looked at.

Every snapshot and every execute response has carried a `stamp` since ADR-191.
`if_stamp` is the caller handing one back: *act only if the target is still
this.* The door takes one look before acting, compares, and refuses `stale` if
they differ — naming the stamp it was bound to, the stamp the target has now,
and `since=<stamp>` as the way to see what moved.

**That look is not served and not remembered.** The first version of this would
have stored it as the session's baseline, which is the obvious thing to do with
a snapshot and is wrong: the caller's next `observe(since=…)` would then diff
against a snapshot the caller never saw and answer *nothing changed*. Held by a
check and a mutant.

**The rung is checked first.** A caller that may not act is not given a look for
asking. A bound command whose target cannot be looked at is refused
`unavailable` and is not run blind.

## 2. Why a deadline

A command waits — in a pipe, behind a slow target, in a client's retry loop —
and the caller that sent it may have timed out, looked again, and decided
something else. Without a deadline the door runs it whenever it arrives.

- An ISO-8601 instant **with an offset**. Not a number, not a number in quotes,
  not a time with no zone: a deadline two machines read differently is worse
  than none. (The strictness is FlowersForever's, learned from a 58,671 A.D.
  timestamp.)
- `now >= expires_at` is expired: the deadline is the first moment the command is
  unwanted, not the last it is wanted.
- **A receipt is served whatever the clock says.** The act it records happened
  and its truth does not expire. The check sits after the replay lookup and
  before validation.
- **Neither field is part of the command's identity.** A retry with a new
  deadline is the same request, not a `conflict`.

Both refusals are `stale` — ADR-189's code for *right when you read it, not right
now: read again*. No new code, so the walk already counts it as a refusal and
the MCP map already carries it.

## 3. Transports

stdio: in the command. MCP and HTTP: in the call's `_meta`, which is where that
protocol puts what a request says about itself; only these two keys are taken
from it (a `progressToken` beside them is not a command field, and with a strict
envelope would have been a refusal). The manifest publishes `commandFields` and
a `freshness` block saying what each field means and what refusing it looks
like.

Both are OPTIONAL. No task, walk or trace written before today carries either;
all of them run unchanged. The clock is injected (`Gateway(..., clock=)`), so the
suite holds *expired*, *at the deadline* and *one second before* to the second
without sleeping.

## 4. Numbers

`verify_contract` 196 → 221. `mutate_contract` 87 → 103. `verify_walk` holds
protocol 1.8.

## 5. Held

- **`blind_console` does not offer either yet.** An operator in a blind trial
  works from the diff and re-reads when told `stale`; whether `if_stamp` lowers
  its call count is a measurement, and a sixth trial is what measures it.
- **No maximum lifetime.** FlowersForever caps a physical command's at thirty
  seconds because its targets are robots. Nothing here is; a cap is a number
  that would need a reason.
- **The kit's own runners do not bind their acts.** The task runner owns its
  page and nothing else moves it. Trigger: the first task that shares a target.
