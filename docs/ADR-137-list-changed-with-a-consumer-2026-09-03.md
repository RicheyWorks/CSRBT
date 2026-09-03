# ADR-137 — `listChanged`, with a consumer: a session that can pick up a target it did not start with

**Status:** accepted · **Date:** 2026-09-03 · **The registry can change while a session is open. `csrbt-session` attaches and detaches targets; the gateway hears it and forgets the retired target's replayable responses; the MCP server drops the name map it cached, declares `listChanged` — because now something can — and writes the notice *before* the response that caused it; and the robot, which caches a tool list, is its consumer. One browser session picked up the JVM mid-walk and drove all 35 of its tools**

## 1. What ADR-115 and ADR-121 held, and why they were right

Both transports declared

    "capabilities": {"tools": {"listChanged": false},
                     "resources": {"listChanged": false}}

and ADR-121 held it there with one line: *"still no consumer."* That was the
honest answer to a capability nobody could exercise, and it was true for a
structural reason, not an oversight — **a `Registry` was built once and only
read**. Nothing in the harness could change a list, so `false` was not a
limitation being confessed; it was a fact about the code.

That made the capability true and useless at the same time. The way out is not
to flip the flag. It is to make the sentence false: build the thing that can
change a list, and then find out who was relying on it not changing.

## 2. `csrbt-session` — the session's own control surface

Every other plugin fronts a *target*: a JVM, a browser page, a fixture. This one
fronts the **session**.

    targets   READ      which targets can be attached, and which are attached
    attach    NAVIGATE  stand a target up and put it in this session's registry
    detach    NAVIGATE  take a target out of the registry and close it

`attach` is NAVIGATE, not MUTATE: it changes no record in any target: it changes
what this session can reach. It refuses a target that is not a target
(`invalid_argument`), one already attached or already served by the session
(`conflict`), and one that cannot come up (`failed`, carrying the reason
`stand_up` would have written to stderr). `detach` refuses a target this session
did not attach (`not_found`) — the targets an operator started the session with
are the operator's, not the host's — and runs the target's own closers, so a
browser attached and detached leaves no process.

It is served only when a transport is asked for it (`--attachable`, on both
doors). A transport that does not register it declares `listChanged: false` and
means it.

## 3. What had been relying on the list not changing

Three caches, in three different processes, and every one of them silently
wrong the moment a target arrives:

- **the MCP server's own.** `call()` maps a tool name through `self._tools`,
  filled by the last `tools/list`. After an attach that map has no entry for the
  new target's tools; after a detach it still has the old one's. A server that
  sends the notification without clearing its own cache has been courteous;
  clearing it is the fix.
- **the robot's wire.** `McpWire` keeps a `(pluginId, action) -> tool name` map
  so the walk can speak in the contract's words. It is exactly the client the
  notification is written for.
- **the gateway's replay cache.** Keyed by plugin id and request id. A target
  detached and attached again is a *new* target that has done nothing, and
  answering it with the previous incarnation's response marked `replayed: true`
  is a lie about a machine that no longer exists. `Gateway._changed` drops every
  cached response whose plugin is no longer registered.

And one that was not a cache but an assumption: `McpWire.rpc()` wrote a request
and read **one line**. That was sound while nothing but a response ever came
back. A client that keeps doing it takes the first notification for its answer
and is one line behind for the rest of the session.

## 4. The mechanism

`Registry` gained `watch()`, `unwatch()`, `retire()`, and a `register()` that
announces — except at construction, which is `quiet=True`, because **building a
session is not a change to it**, and a session that opens by announcing a change
it did not make teaches every client to ignore the notice. A watcher that raises
does not take the registry down with it: the change *happened*.

`Gateway` watches the registry (it is the thing that must also forget), counts
changes, and re-broadcasts to whatever subscribed.

`harness_mcp.Server` subscribes only when it can honestly declare the
capability, which it derives rather than being told: `listChanged` is true when
the session serves `csrbt-session`. On a change it drops `self._tools` and
queues `notifications/tools/list_changed`, plus
`notifications/resources/list_changed` when the plugin set itself moved — a
plugin arriving or leaving takes its snapshot resource with it.

**The notice goes out before the answer.** `serve()` drains the queue first and
writes the response second, so there is no window in which a client holds the
response to `attach` — which names the tools it may now call — while the notice
that the list changed is still behind it in the pipe.

The stdio door serves `--attachable` too and sends nothing, for the same reason
it always sent nothing: every op re-reads. There is no cached list there to go
stale, and that is stated rather than left as a gap.

## 5. The consumer

`McpWire.rpc()` now reads until its own id comes back, handing every message
with no id to `on_notification()`, which drops the cache the server just said
was wrong and keeps the method on the record. `harness_walk --attach <target>`
drives the whole round trip:

1. walk the target the session started with, from the manifest alone;
2. attach a second target, and note what arrived **unasked**;
3. re-read the list and walk the new target too, on the same session;
4. detach it, and find its tools gone from the list and its snapshot gone from
   the resources.

Step 3 is impossible without step 2, which is the only claim worth making here.

`csrbt-session` is deliberately kept out of the *generic* walk. A random walk of
`attach` is a random walk of starting processes; the robot drives the control
surface on purpose, in the one order that proves the notification carries its
weight.

## 6. The reading

A browser session, walked, then handed the organism mid-session:

    session started with: csrbt-page
    csrbt-page      4 rounds, 256 commands, invariants broken 0
    attached organism; the server said, unasked: tools/list_changed, resources/list_changed
    the list grew by 35 tool(s)
    csrbt-organism  4 rounds, 480 commands, 35 tools, undriven none, unreachable none
    detached organism; the list is back to 24 tool(s), 4 notification(s) in all

736 commands, two targets, one MCP session, and the second target reachable only
because the robot believed what the server told it without being asked.

## 7. Verification

`verify_mcp` gains **27** checks (**70**), in two new sections:

- **D**, in process, with `stand_up` injected so the mechanics cost nothing: the
  declaration honest in both directions (a plain session says false, an
  attachable one says true, and neither has spoken yet); the server's own cache
  dropped; both notices, tools first; the new tool callable by name on the same
  session; every refusal by its own code; a refused attach announcing nothing;
  detach closing the target it took out; the re-attached target not answered
  from the replay cache; the registry's contract (announce on register and
  retire, silence at construction, a raising watcher survived, `ValueError` for
  a duplicate id and `not_found` for an unknown one); `serve()`'s ordering; and
  the robot's wire dropping each cache on the matching notice.
- **E**, over a real child process: `--target fixture --attachable`, a **real
  browser page attached mid-session** — 20 of the page's 21 tools arriving (the
  DESTRUCTIVE one omitted, because that session never opened that gate), its
  snapshot appearing as a resource, `read-page` answering through it, and the
  list exactly what it was after the detach, with all four notices written
  before the responses that caused them.

`mutate_mcp` gains **13** mutants (**20**), and to carry them the runner now
mutates `harness_contract.py`, `harness_plugin_session.py` and
`harness_walk.py` as well — because `listChanged` is not one file's clause: the
notice is the server's, the change is the registry's, the forgetting is the
gateway's, the attach is the plugin's, and the consumer is the robot's.
**20 killed, 0 survived.**

## 8. Held

- **Policy is still fixed for a session's life.** The other thing that decides a
  tool list is `policy.allow`, and nothing can change it mid-session. A host that
  could tighten a session — drop MUTATE after the data is in — would be the
  second producer of this notification, and it is not built.
- **A target that dies is still listed.** The organism's console can go away
  mid-session; its tools stay in the list and every call answers `unavailable`.
  Unlisting them would be the honest reading, but it would also make `restart`
  unreachable by name, and that trade needs its own slice.
- **`--attach` takes one target.** The robot cannot yet attach two, or attach the
  same target twice under different pages.
- The attach walk writes no walk-ledger entry: it is not a walk of a target but
  a walk of the door. Its numbers live in this ADR and in `verify_mcp`.

## 9. First reading

    verify_mcp   70 / 70   ·  mutate_mcp 20 killed, 0 survived
    verify_contract 89 / 89 (a duplicate plugin id is still a ValueError)
    attach walk  csrbt-page 256 commands, csrbt-organism 480, 4 notifications
