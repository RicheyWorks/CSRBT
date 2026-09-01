# Changelog — 2026-09-01 — ADR-115: the second transport

An AI can plug in. `tools/harness_mcp.py` serves the gateway over the Model
Context Protocol — JSON-RPC 2.0 on stdio, no SDK — with nothing in the
plugins or the gateway changed.

## New — `tools/harness_mcp.py`

`initialize` → discover; `tools/list` → manifest (only what the policy
allows); `tools/call` → execute with **the JSON-RPC id as the request id**, so
a retry is a replay; `resources/list` / `resources/read` → observe (a
snapshot is `harness://<plugin>/snapshot`); `ping`. Risk → MCP annotations
(`readOnlyHint` / `destructiveHint`) and the first word of each description.
Client errors `-32602`, policy `-32001`, dead target `-32002`; a target's no is
`isError: true`. Token in the server's environment only.

## New — `tools/harness_targets.py`

Standing a target up (policy switch, token length, which plugins) moved out
of `harness_stdio.main()` so both transports share it. It is now the only
file that names a target; `verify_organism` pins that the stdio transport
names no plugin class.

## New — `tools/verify/verify_mcp.py` (**31 checks**) and `tools/mutate_mcp.py` (**6 killed, 0 survived, 1 equivalent**)

The adapter names no target; the full protocol surface in-process over a
fixture; the server as a child over the organism spoken to in JSON-RPC
(NOT VERIFIED ×1 without the build).

## Docs

`docs/ADR-115-the-second-transport-2026-09-01.md`; `docs/AUTOMATION-HARNESS.md`
(the MCP section and a host config); `docs/AI_HARNESS.md` §7d.
