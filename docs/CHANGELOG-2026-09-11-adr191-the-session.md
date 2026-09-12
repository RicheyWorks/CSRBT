# 2026-09-11 — ADR-191: the session

**One door across calls, and a door that remembers what it last showed you.
Every snapshot carries a `stamp`; `observe(since=<stamp>)` answers the CHANGE
instead of the snapshot; every act carries the same change against the
snapshot the client planned it from. The fourth of the seven slices of
`docs/PLAN-operator-api-2026-09-11.md`, and the one that turns a door into an
API. Protocol 1.7.**

## Added — the contract

- `tools/harness_contract.py`:
  - `stamp_of(snapshot, spec)` — a twelve-character digest of everything in a
    snapshot a reader could notice. Paths the plugin calls noise are left out,
    and a keyed list is stamped as a set, so the stamp and the diff can never
    disagree about whether something moved.
  - `diff_of(before, after, spec, cap)` — `fields`, `gained`, `lost`,
    `appeared`, `vanished`, `altered`, `counts`, `capped`, `noise`. Order is
    not change: a keyed list is compared as a mapping from key to entry.
  - `Plugin.identity(snapshot)` — what identity means on this target's own
    snapshot: `keys` (lists with identity, by `/`-joined path) and `noise`
    (paths that move on their own). The plugin supplies the fact only it has;
    the gateway does the diffing, so all five targets diff alike.
  - `DIFF_CAP = 40`, `PATH_SEP = "/"`.
  - `Gateway.observe(token, plugin, since=None)`; one baseline per plugin per
    session, dropped when the plugin is retired; `diff` and `stamp` on every
    execute response; the session's facts in the manifest.

## Changed — the targets

- `identity()` on the page (controls keyed by ADR-188 address, tabs by pane),
  the organism (`jvm` and `replicaLagMs` are noise), the lab, the fixture and
  the session target.
- `tools/harness_plugin_page.py`: a commandable control carries its `value`
  under SENSITIVE_READ and under nothing else — which the redaction line has
  promised since ADR-108, and without which the diff of an act that enters
  data answered `nothing changed`.

## Changed — the transports

- `tools/harness_stdio.py`: the `observe` op takes `since`.
- `tools/harness_mcp.py`: `harness://<plugin>/snapshot?since=<stamp>`, said so
  in `resources/list`; every `tools/call` result carries `stamp` and `diff`
  and still never the snapshot.

## Changed — the console

- `tools/blind_console.py`: `--session NAME` keeps the door open between
  invocations behind a unix socket, `--end` closes it, and a move may carry
  `since`. Both modes interpret a move in one place (`play`).

## Changed — suites

- `verify_contract` 115 → 143: section 14. The stamp is stable, noise-blind
  and order-blind; `since` answers the change and not the snapshot; an
  unknown stamp gets the whole snapshot and says so; a list nobody keyed is
  counted rather than diffed; an entry with no identity is counted, not
  named; the cap says where it bit; the baseline never carries the stamp;
  every act diffs against the last snapshot the session saw and the next act
  against that; a replay answers with the diff it answered with first; a
  retired plugin's baseline goes with it; a plugin that says nothing, or that
  raises while saying it, still gets a stamp.
- `verify_mcp` 73 → 89: section F. `?since=` on the resource, the plain URI
  unchanged, the diff on every tool result and never the snapshot, the
  resource description saying so — and a console whose door outlives the
  invocation, proved by two separate processes and a stamp that spans them.
- `verify_report` 160 → 179: section I. Both stamps on a page snapshot; a page
  nobody touched answers in a line; an act answers in a tenth of the bytes; a
  renumbered control is one field moving rather than a replacement; both tabs
  of a pane switch, keyed by the pane each drives; a field's value as the
  field holds it, under that rung and no other, and never from a control this
  session may not command.
- `mutate_contract` 36 → 56 / 56 and `mutate_report` 104 → 110 / 110.

No page and no task was edited; the 44 science tasks did not move.
