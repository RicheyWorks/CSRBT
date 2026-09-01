# ADR-115 — The second transport

**Status:** accepted · **Date:** 2026-09-01 · **Measures ADR-102's "stdio is only the first transport"**

## 1. One of each is a claim

ADR-112 measured "or another target" by building the second target. The
same sentence in `AUTOMATION-HARNESS.md` makes a second promise that had the
same status:

> A client can connect an OpenAI-compatible tool, a local model, an MCP
> server, or an ordinary script without changing the plugin, because a
> transport maps exactly four operations and decides nothing.

One transport existed. "Decides nothing" was a property of a 120-line file
nobody had tried to write a sibling for. And the ask behind this whole
program — *robots and AI get plugged in* — has a concrete meaning in 2026: an
AI plugs in over the **Model Context Protocol**. Until a host could point at
this kit and see tools, the harness was operable by scripts and by the first
robot, and by no model.

## 2. The decision

`tools/harness_mcp.py`: MCP over stdio, JSON-RPC 2.0, one message per line,
**no SDK** — the protocol is small and a dependency would hide exactly the
boundary this file exists to show. The mapping is the whole file:

| MCP | gateway | note |
|---|---|---|
| `initialize` | `discover` | `serverInfo`, capabilities, and instructions naming the plugins |
| `tools/list` | `manifest` | **only tools the policy allows** — `allowed: false` has always meant "omit", and here it is obeyed rather than published |
| `tools/call` | `execute` | **the JSON-RPC id is the request id.** A host that retries a call with the same id gets the replay, not a second write. A call with no id has no request id and is refused rather than run unreplayably |
| `resources/list`, `resources/read` | `observe` | a snapshot is a resource, `harness://<plugin>/snapshot`, redacted under the session's policy |
| `ping` | — | `{}` |

Risk becomes MCP tool annotations so a host can show an operator what it is
being asked: `READ`, `NAVIGATE`, `SENSITIVE_READ` are `readOnlyHint`; `MUTATE`
and `DESTRUCTIVE` are `destructiveHint`; the risk is also the first word of
every description. The gateway enforces policy regardless of what a host does
with a hint.

Refusals are sorted by whose they are. The client's — `invalid_argument`,
`not_found`, `conflict` — are JSON-RPC `-32602` with the gateway's code in the
message. The policy's — `forbidden`, `unauthorized` — are `-32001`. A target
that ran and **said no** is a normal result with `isError: true`, which is
how MCP tells a model "that happened and it was a no" as opposed to "you
asked wrongly". A dead target is `-32002`.

The token never crosses the protocol. It sits in the environment of the
server process, held by the operator who launched it — which is where MCP
puts authentication for a stdio server anyway — and the server refuses to
start without it, exactly like stdio.

**What moved.** Standing a target up — the policy switch, the token length,
which plugins to construct — was in `harness_stdio.main()`. Two transports
need it, so it is `tools/harness_targets.py` now, and it is the *only* file
that names a target. `verify_organism` had pinned that the stdio transport's
`serve()` names no target; it now also pins that the transport file names no
plugin class at all.

## 3. Evidence

`tools/verify/verify_mcp.py`, **31 checks**:

- **A** the `Server` names no target; both transports use the shared builder;
  no SDK is imported; the five methods a host uses are mapped.
- **B** in-process over a fixture plugin: the handshake; a notification
  answered with silence; `tools/list` listing exactly what the policy allows,
  in manifest order; annotations right per risk; a call executing and
  returning its output; **the same id served from the cache with the plugin
  not run again**; the same id with a different body a `conflict`; a target's
  no as `isError`; an out-of-bound argument `-32602` naming `invalid_argument`;
  a hidden tool not callable by name and never reaching the plugin; a call
  without an id refused; unknown method `-32601`; a non-2.0 message `-32600`;
  snapshots as resources, redacted; a foreign URI refused; `serve()` giving
  one line per request and `-32700` for junk.
- **C** the server as a child process over the organism, spoken to in JSON-RPC:
  19 tools listed under `MUTATE`-only (the 14 `SENSITIVE_READ` hidden), a wire
  put landing, its retry replayed, `get` uncallable by name, the snapshot
  resource showing one key and no record, the physical reading.

`tools/mutate_mcp.py`, the same afternoon: **seven mutants, six killed, one
equivalent** (an unchecked resource URI — the registry refuses an unknown
plugin id with the same code either way; recorded with the measurement). The
first version of the replay mutant did not mutate anything — its "fresh" id
was a constant — and would have printed *killed* forever; re-anchored on
`id(object())`, it dies to the replay check, and the catalogue keeps only
mutants that were watched to change something.

Full kit: **71 jobs green**.

## 4. Plugging a model in

```json
{"mcpServers": {"csrbt": {
  "command": "python3",
  "args": ["C:/Users/you/projects/CSRBT/tools/harness_mcp.py", "--target", "organism"],
  "env": {"CSRBT_HARNESS_ENABLED": "true",
          "CSRBT_HARNESS_TOKEN": "<at least 24 random characters>",
          "CSRBT_HARNESS_ALLOW_MUTATE": "true"}}}}
```

That is the whole of it. The host sees nineteen tools with their risks in
the name, forms calls from schemas that carry bounds and examples (ADR-114),
is refused with a code when it forms one badly, is told `isError` when the
organism declines, gets a replay when it retries, and can read the snapshot
as a resource. Open `SENSITIVE_READ` and it sees thirty-three. `--target
page` serves a kit page the same way; `--target both` serves both from one
registry. Nothing in the plugins changed. Nothing in the gateway changed.
**That is the measurement.**

## 5. Held

- **The host's own retries are the only replay protection over MCP.** MCP
  ids are the client's to choose; a host that generates a fresh id per
  attempt gets a fresh write per attempt, and the server cannot tell a retry
  from a new intention. Documented rather than solved: the alternative —
  hashing the arguments into the request id — would make two *deliberate*
  identical writes one write.
- **No `prompts`, no `sampling`, no `listChanged` notifications.** The
  policy is fixed for the life of the process, so the tool list never changes
  and there is nothing to notify. If the policy ever becomes live, the
  notification is the first thing to add.
- **Streaming (`notifications/progress`) is not mapped.** `quiesce` can wait
  thirty seconds; a host sees nothing until it returns.
