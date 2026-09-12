# 2026-09-12 — ADR-192: HTTP

**The third transport, and the first one anything else can reach. The official
MCP Python SDK — which has never seen this repository — now drives the
collection sheet through it, and its trace is kept. The fifth of the seven
slices of `docs/PLAN-operator-api-2026-09-11.md`.**

## Added

- `tools/harness_http.py`: MCP over streamable HTTP. `POST /mcp` for messages
  and batches, `GET /mcp` for the SSE notification stream, `DELETE /mcp` to end
  the session. It imports `harness_mcp.Server` and names none of the four
  operations — the one method name it knows is `initialize`, because that is
  where the specification puts the session id.
  - `CSRBT_HARNESS_HTTP=true` **as well as** the kit's own switch.
  - Binds `127.0.0.1`; anywhere else takes `CSRBT_HARNESS_HTTP_BIND` and says
    on stderr that it did.
  - `Origin` checked on the parsed hostname, so `http://127.0.0.1.evil.example`
    is refused; no Origin at all is a non-browser client and is allowed.
  - `Authorization: Bearer <token>`, compared with `hmac.compare_digest`.
  - One session: the first `initialize` claims it, a second is 409, an id this
    door did not issue is 404.
  - `Door.pump()` — every gateway call runs on the thread that stood the target
    up, because Playwright's synchronous API is bound to it and an HTTP server
    is not.
- `tools/traces/http/collection-sheet-sdk.jsonl` and its `PROVENANCE.md`: the
  first session this door has had with a client this kit did not write.
- `tools/verify/verify_http.py` (65) and `tools/mutate_http.py` (26 / 26).

## Changed

- `tools/harness_board.py`: `verify_http` and `mutate_http` join the harness
  suites and the runner table.

## Found

The SDK's first request returned `ready: false` and a Playwright greenlet
error — *"Cannot switch to a different thread"*. `ThreadingHTTPServer` answers
each request on a new thread; Playwright's sync API may only be driven from the
thread that created it. Over stdio there was never a second thread, so nothing
had ever exercised it in ninety ADRs. Fixed in the transport, held by
`verify_http` section C with six concurrent requests against a target that
raises if touched from any thread but the first.

No page, no task and no plugin was edited; the gateway, the contract and the
two existing transports are byte for byte what ADR-191 left.
