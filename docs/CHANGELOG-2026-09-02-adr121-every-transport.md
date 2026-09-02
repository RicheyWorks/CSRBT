# Changelog — 2026-09-02 — ADR-121: one robot for every transport

## Changed — `tools/harness_walk.py` — `--transport stdio | mcp`

`McpWire` speaks JSON-RPC to `harness_mcp.py` and folds it into the shape
the walk reads: `_meta` for plugin id and action, the request id as the
JSON-RPC id, a gateway code at the head of an error message as the refusal
code, `isError` as the target's no, and a `resources/read` after every call
as the snapshot — priced by the client's own clock. The walk itself does not
know which transport it is on. Results name their transport; the ledger
keeps MCP walks as `<plugin>@mcp`. Regenerated: six entries, 8 rounds each.

## Changed — `tools/harness_mcp.py`

Every tool carries `_meta` (`pluginId`, `action`, `risk`); a call's body
carries `snapshotMs` and `requestId`.

## Changed — `tools/verify/verify_walk.py` (74 → **102**)

Section **G**: the fixture and the organism walked over MCP land every
action in the same bucket the same number of times as over stdio; every
MCP command pays a snapshot round trip; the same alarm for a dead target;
the wire never splits a slug; six ledger entries at the same bar.

## Changed — `tools/mutate_walk.py` (17 → **21 killed**, 0 survived, 2 equivalent); `tools/verify/verify_mcp.py` (31 → **34**); `tools/mutate_mcp.py` (6 → **7 killed**)

## Docs

`docs/ADR-121-one-robot-for-every-transport-2026-09-02.md`;
`docs/AUTOMATION-HARNESS.md`, `docs/AI_HARNESS.md`.
