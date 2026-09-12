# The first external host — provenance (ADR-192)

`collection-sheet-sdk.jsonl` is the first session this door has ever had with
a client **that is not this kit**.

Every trace in `tools/traces/blind/`, `blind2/` and `blind3/` was taken
through `tools/blind_console.py` — a client written in this repository, by the
same hand as the door it talks to. That is the right instrument for a blind
trial, because the question there is what an operator can work out; it is the
wrong evidence for "an external host can connect", because a client that
shares an author with its server can agree with it about anything.

This one was taken by the **official Model Context Protocol Python SDK**
(`pip install mcp`; `mcp.client.streamable_http.streamablehttp_client` and
`mcp.ClientSession`), which has never seen this repository, implements the
specification rather than this door, and negotiated protocol `2025-03-26` with
it. Nothing in `tools/` was changed to make it work, and one thing in `tools/`
was changed because it did not: see "what it found" below.

## The conditions

- `tools/harness_http.py --target page --page collection-sheet.html --port 0
  --trace tools/traces/http/collection-sheet-sdk.jsonl`, as a child process,
  with `CSRBT_HARNESS_ENABLED=true`, `CSRBT_HARNESS_HTTP=true`, a
  freshly-generated 24-character-plus token, and `SENSITIVE_READ`, `DRAFT` and
  `MUTATE` allowed — `DESTRUCTIVE` withheld, a supervised session.
- Bound to `127.0.0.1` on a port the kernel chose; the server printed the URL
  on stderr and the client read it from there.
- The client sent `Authorization: Bearer <token>` and nothing else this door
  is not documented to take. It managed `Mcp-Session-Id` itself, from the
  header the `initialize` response carried.

## What the host did, and what came back

| # | call | answer |
|---|---|---|
| — | `initialize` | `csrbt-harness 1.7`, protocol `2025-03-26`, session id issued |
| — | `tools/list` | 22 tools (the page's, at the three rungs this session holds) |
| 1 | `resources/read harness://csrbt-page/snapshot` | the sheet, 307 controls, stamp `s31f870317da8` |
| 2 | `tools/call csrbt_page__pick` (`pick_search:0`, `Agaricus`) | ok; **2 067 bytes of diff** where the snapshot is ~100 000 |
| 3 | `resources/read …/snapshot?since=<stamp>` | `changed: false` — the stamp the tool result handed back is the one the resource calls current |
| 4 | `resources/read …/snapshot` | re-read, to pick a text control by address |
| 5 | `tools/call csrbt_page__set_text` (`#cName`, `Meadow edge`) | ok; `changed: true`, `#cName` altered — the value ADR-191 started publishing, moving the stamp, over HTTP, through a client that knows nothing about either |
| 6 | `tools/call csrbt_page__show_pane` (`p-met`) | `route: p-rec → p-met` |
| 7 | `tools/call csrbt_page__read_report` | 15 boxes, 35 rules |

Seven recorded calls. Every one answered on the first attempt; nothing was
refused, and nothing had to be worked around.

## What it found

The first run returned `ready: false` and a Playwright greenlet error —
*"Cannot switch to a different thread"* — where the collection sheet should
have been. `ThreadingHTTPServer` answers each request on a new thread, and
Playwright's synchronous API may only be driven from the thread that created
it. Over stdio there was never a second thread, so nothing had ever exercised
it.

That is a defect this transport revealed rather than caused, and it is fixed
where it belongs: `harness_http.Door` hands every gateway call back to the
thread that stood the target up (`Door.pump`), so the target is driven
serially by one thread whatever the listener does. `verify_http` holds it.

## Reproducing it

The suite does, when the SDK is installed — `verify_http.py` section D runs
this same session and says `NOT VERIFIED` rather than passing if `import mcp`
fails, because a check that silently skips is worse than one that admits it
did not run. To do it by hand:

    pip install mcp
    python3 tools/verify/verify_http.py
