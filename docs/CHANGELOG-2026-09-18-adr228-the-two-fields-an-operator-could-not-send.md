# 2026-09-18 — ADR-228: the two fields an operator could not send

## Added

- **`blind_console` `call` moves may carry `if_stamp` and `expires_at`** — the
  two things ADR-222 gave the gateway and no operator could send. They ride in
  `_meta`, only when named; `OPERATOR.md` documents both.
- **The sixth blind trial** — four pages no blind operator had touched
  (greenhouse, soil bench, survey design, tree visualizer), one attempt each,
  reaching 55 / 78 outcomes and 239 / 285 claims in 171 calls. Every operator
  guarded its irreversible act with `if_stamp`; a stale stamp and a past
  deadline were each refused. Traces + provenance under `tools/traces/blind6/`.

## Checked

`verify_mcp` 93 → 98 (the passthrough, live), `verify_tasks` 392 → 411 (F6),
`mutate_contract` 103 → 105.

## Filed, not fixed

- The report stamp and the snapshot stamp cannot be told apart; `if_stamp`
  guards the snapshot one, and every operator hit it.
- tree visualizer reports 28 nodes after 15 seeded draws where the task holds
  24 — the page draws until a key is new, so no collisions occur.
