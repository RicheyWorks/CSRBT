# Changelog — 2026-09-03 — ADR-137: `listChanged`, with a consumer

## Harness — `tools/`

- `harness_plugin_session.py` **(new)**: `csrbt-session`, the session's own
  control surface. `targets` (READ), `attach` (NAVIGATE), `detach` (NAVIGATE).
  Attaching stands a target up through the shared builder and registers it;
  detaching retires it and runs its closers. Refuses an unknown target
  (`invalid_argument`), one already attached or already served (`conflict`),
  one that cannot come up (`failed`), and a detach of something this session
  did not attach (`not_found`).
- `harness_contract.py`:
  - `Registry` is observable and mutable: `watch` / `unwatch` / `retire`, and a
    `register` that announces — except at construction (`quiet=True`), because
    building a session is not a change to it. A watcher that raises does not
    take the registry down.
  - `Gateway` watches the registry, counts changes, re-broadcasts to
    `subscribe`rs, and **forgets a retired plugin's replayable responses** — a
    target detached and attached again is a new target that has done nothing.
  - A duplicate plugin id stays a `ValueError`: no host reaches it, because
    `csrbt-session` checks the ids it is about to add and refuses first.
- `harness_mcp.py`: declares `listChanged` true exactly when the session serves
  `csrbt-session` (derived, not passed); on a change drops its own tool-name
  map and queues `notifications/tools/list_changed`, plus
  `notifications/resources/list_changed` when the plugin set moved. `serve()`
  writes the notices **before** the response that caused them. New
  `--attachable`.
- `harness_stdio.py`: `--attachable` too. No notification: every op re-reads, so
  there is no cached list to go stale.
- `harness_walk.py`: `McpWire.rpc()` reads until its own id comes back and hands
  every id-less message to `on_notification()`, which drops the cache the server
  says is wrong. New `--attach <target>` (MCP only): walk the session's target,
  attach a second one, hear the lists change, re-read, walk it, detach, and
  check the list is exactly what it was.

## Verification

`verify_mcp` 70 (+27) — section **D** (in process, `stand_up` injected: the
declaration honest both ways, the caches dropped, both notices in order, every
refusal by its code, the replay cache forgotten, the registry's contract,
`serve()`'s ordering, the robot's wire as consumer) and section **E** (a real
browser page attached over a real child: 20 tools arrive, its snapshot becomes a
resource, `read-page` answers, the detach puts the list back).

`mutate_mcp` 20 killed, 0 survived (+13). The runner now mutates
`harness_contract.py`, `harness_plugin_session.py` and `harness_walk.py` as well
as `harness_mcp.py`.

Attach walk: `csrbt-page` 256 commands, then `csrbt-organism` 480 commands over
35 tools on the same session, 4 notifications, 0 invariants broken.

## Docs

`docs/ADR-137-list-changed-with-a-consumer-2026-09-03.md`;
`docs/AUTOMATION-HARNESS.md`, `docs/AI_HARNESS.md`.
