# ADR-121 — One robot for every transport

**Status:** accepted · **Date:** 2026-09-02 · **Completes ADR-115's claim the way ADR-117 completed ADR-114's**

## 1. A transport nobody had walked

ADR-115 built the second transport — MCP over stdio, the one a model
speaks — on the sentence "a transport maps exactly four operations and
decides nothing", and proved it with 31 checks: the mapping, in-process over
a fixture and as a child over the organism, seven requests deep. What it
never did was *operate a target through it*. The robot (`harness_walk.py`)
spoke only the stdio transport; every "operable from the manifest alone"
claim since ADR-114 was a claim about one of the two doors.

"Decides nothing" is a claim with a measurement: the same client, the same
seed, the same target, through either transport, must land every action in
the same bucket the same number of times. Nobody had taken it.

## 2. The decision

`harness_walk.py --transport stdio | mcp`. The walk — forming calls, the
buckets, the identity, the coverage floor, the cross-checks — does not know
which it is on. The only new code is `McpWire`, which speaks JSON-RPC to
`harness_mcp.py` and folds the answers into the shape the walk reads:

| operation | over MCP | read back as |
|---|---|---|
| discover | `initialize` + `notifications/initialized` | ok |
| manifest | `tools/list` + `resources/list` | tools with `pluginId`, `action`, `risk` from each tool's `_meta`; plugins from the snapshot resources; `allowed` always true (the policy hides the rest) |
| observe | `resources/read harness://<plugin>/snapshot` | the snapshot |
| execute | `tools/call` with the request id **as** the JSON-RPC id, then `resources/read` | a JSON-RPC error whose message begins with a gateway code is that code (refused); `isError: true` with a body is the target's no (declined); the snapshot is the resource read after the call |
| quit | close stdin | — |

Two things the server had to say for that to be honest:

- **`_meta` on every tool** — `pluginId`, `action`, `risk`. A tool name is
  a provider-safe slug, and a client that scopes pools by action
  (`set-text.selector`) must not have to guess `set-text` back out of
  `csrbt_page__set_text`. The MCP spec reserves `_meta` on a tool for
  exactly this; the wire reads it and never splits a slug.
- **`snapshotMs` and `requestId` in a call's body** (ADR-120's price,
  carried through).

MCP returns no snapshot with a call, so over MCP **the snapshot is a second
round trip**, and the wire prices it by its own clock — what *this client*
waited, not what the gateway measured. Every execute pays it, refusals
included (over stdio a refusal carries no snapshot). The walk ledger keeps
MCP walks as their own entries, `<plugin>@mcp`, beside the stdio ones.

## 3. Measured: the transport decides nothing

`verify_walk` section **G** (74 → 102):

- the fixture walked over MCP and over stdio, same seed: **identical
  `per_action` counts, totals, commands** — refused, declined, chaos and
  failed all read back through JSON-RPC — and the same unreachable,
  undriven, unschemable and cross-check reports; the fixture counted the
  same calls from either side;
- the organism walked over MCP: 33/33 driven, identity holds, nothing
  broken, and **the same per-action buckets as the stdio walk from the same
  seed** (143 driven, 17 refused in the suite's 2×2 walk);
- over MCP every command paid a snapshot round trip (40 of 40 on the
  fixture; 24 over stdio), priced;
- a target that goes away is the same alarm (`-32002`, `unavailable`);
- the committed ledger carries six entries — three targets × two
  transports — each at the same bar, each naming its transport.

From the committed 8-round walks, the snapshot's price over MCP (client
clock, one extra round trip) against ADR-120's gateway-measured price over
stdio: organism 0 ms median (p95 3) vs 0 (p95 2), lab 0 vs 0, page 91 vs
95 — the loopback round trip is below the millisecond the clock resolves;
the page's DOM read is the cost either way. One correction the MCP walk
forced on the price itself: a refusal runs no action and now contributes
no action price rather than a zero (over MCP every refusal is priced for
its snapshot, and the zeros had halved the page's action median).

`mutate_walk` gained four mutants of the wire — isError not read as the
target's no, a gateway code in a JSON-RPC error not read back, the snapshot
not read after a call, the action guessed from the slug instead of `_meta`
— **21 killed, 0 survived, 2 equivalent**. `verify_mcp` pins `_meta` with a
hyphenated action in-process (`look-twice`, not `look_twice`) and over the
organism (`retain-newest`), and the call body's price; `mutate_mcp` gained
"tools drop their `_meta`" — 7 killed, 0 survived, 1 equivalent.

## 4. What it found

Nothing in the gateway or the plugins, which is the result: the second
transport carried every bucket of every target without a change below its
parser. Two things about the transport itself:

- `tools/list` was **not enough to operate from**. A client could form
  every call but could not scope a pool to an action without guessing the
  action's name from a slug — and `harness_walk` refuses to guess. That is
  the same shape as ADR-114's finding about the stdio manifest (described
  is not operable), one transport over.
- The price of the "observe after every act" design is a second round trip
  over MCP, and now it is a number in the ledger rather than a sentence in
  a doc.

## 5. Held

- A model-driven walk — an actual LLM host planning from `tools/list` — is
  the consumer this transport exists for and is not something this kit can
  run unattended. The robot is the manifest-only client that stands in for
  it; `AUTOMATION-HARNESS.md` carries the host config.
- `listChanged` / progress notifications: still no consumer (ADR-115).
