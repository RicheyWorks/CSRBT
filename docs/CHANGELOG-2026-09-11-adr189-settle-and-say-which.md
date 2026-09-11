# 2026-09-11 — ADR-189: settle before the first act, and say which

**The door stamps a page and waits for it to stop building before the first
call touches it — in the risk read as well as the act — and `stale` becomes a
refusal of its own. The second of the seven slices of
`docs/PLAN-operator-api-2026-09-11.md`.**

## Changed — the contract

- `tools/harness_contract.py`: protocol **1.5 → 1.6**; `Stale = _err("stale")`.
- `tools/harness_mcp.py`: `CODE["stale"] = INVALID_PARAMS` — the client's, and
  re-readable.
- `tools/harness_walk.py`: `REFUSAL` gains `"stale"`, so a selector the page
  has moved past is counted as a refusal and not as a failure of the target.

## Changed — the door

- `tools/harness_plugin_page.py`:
  - `VERSION` (the numbering's digest alone), `_settle()` and
    `_ensure_settled()`. The settle stamps with `DISCOVER` and waits for two
    consecutive readings of the version to agree, at most six rounds of 60 ms,
    then marks the document with `window.__H_SETTLED = <version>`.
  - `execute` settles any action that is about the page as it stands; `open`
    and `reload` settle the document they arrive in and answer with its
    version; `observe` settles before it re-stamps.
  - `risk_for` settles **first** — the gateway asks for the risk before the
    act, so a plugin that settled only in `execute` would read the risk of an
    unbuilt page and then press what the name turned out to mean.
  - the stale refusal is raised as `Stale`, not `NotFound`.

## Changed — suites

- `verify_contract` 111 → 115: the manifest states 1.6; every refusal carries
  its own code and renders as one a transport can map; `stale` is not a
  spelling of `invalid_argument` or `not_found`; the transport leaves no code
  unmapped; the robot counts it as a refusal.
- `verify_report` 140 → 149: section G. On a page nothing has looked at, the
  first call's risk read still says DESTRUCTIVE; an act can be a session's
  first move, by name, with no observe; the marker is the version the snapshot
  then reports; a reload re-settles and answers with its version; the first
  call after it needs no observe either; a stamped selector the page has moved
  past refuses `stale`; a session that navigates settles the page it lands on
  and not only the one it started on; and a control the page adds 40 ms after
  load is there for the first call.
- `mutate_contract` 31 → 35 / 35 (and its subject list grew to the four files
  that carry the code); `mutate_report` 89 → 95 / 95.

No page and no task was edited.
