# ADR-221 — eleven single frames closed a door, one of them from a caller with no credentials, and on Windows the door heard mojibake

**The doors of this harness read their frames with `for line in sys.stdin` and
`json.loads(line)`, and trusted every value in the result to be the type they
expected. Each of those is a decision nobody made. FlowersForever's harness made
them deliberately a week ago (`McpFrameReader`, strict command bodies, safe
transport errors) after two malformed frames killed its reader. This slice asks
the same questions of these doors, as processes, with bytes.**

## 1. What was measured

Each frame was sent BETWEEN two good frames, to the door as it stood at ADR-217.
Three answers means the door lived.

    MCP    100,000 open brackets        RecursionError       1 answer, exit 1
           "method": 5                  AttributeError       1 answer, exit 1
           "params": ["x"]              TypeError            1 answer, exit 1
           "params": "harness://x"      TypeError            1 answer, exit 1
           tool name a list             TypeError            1 answer, exit 1
           "uri": 7                     AttributeError       1 answer, exit 1
           one malformed UTF-8 byte     UnicodeDecodeError   0 answers, exit 1
             (stdin utf-8, strict)
    stdio  a wrong token with an accent TypeError            1 answer, exit 1
           a bare list                  AttributeError       1 answer, exit 1
           "command": [1]               AttributeError       1 answer, exit 1
           "plugin": ["x"]              TypeError            1 answer, exit 1
    HTTP   a wrong bearer w/ an accent  TypeError            connection dropped

**Zero answers** for the malformed byte: the text decoder reads ahead, so the
door died before answering the GOOD frame in front of the bad one.

**The accented token needs no credentials.** `hmac.compare_digest` refuses to
compare two `str` unless both are ASCII, and says so with a `TypeError` — which
is not a `HarnessError`, so it went through every `except HarnessError` between
`Policy.authenticate` and the top of the process. One line, `{"op":"discover",
"token":"café…"}`, from anyone who can write to the pipe. Over HTTP the same
header was a dropped connection and a traceback where a 401 belonged.

**And the door did not hear what was sent.** With stdin decoded as cp1252 — the
default on the Windows machine this kit is developed on — a host that sends
`Bear Creek — café` as UTF-8, which MCP requires of it, was heard as
`Bear Creek â€” cafÃ©`, and that is what `set-text` would have typed into the
page. No suite could see it: the task runner calls the gateway in-process, and
every suite that did use a pipe sent ASCII. Three machines, three behaviours —
a strict UTF-8 locale dies, a code page garbles, a POSIX locale smuggles the
bytes through as lone surrogates — and the tests passed on all three.

**`json.loads` is a lenient reader.** Through the stdio door, before the fix:

    {"action":"ok","action":"broken"}            ran `broken`, said nothing
    {..., "dry_run": true, "expires_at": "2001-…"}  ok=True, and it RAN
    {"request_id":"A","requestId":"B", …}        filed under A
    {"op":"observe", …, "sinse":"abc"}           whole snapshot, no word about `sinse`

Arguments have been strict since ADR-097. The envelope around them never was.

## 2. What changed

- **`tools/harness_frames.py`** — the wire, before it is a message. Bytes in
  (through `.buffer` when the stream has one), strict UTF-8, one line at a time
  bounded at the HTTP door's 1 MiB (the pipe doors had no bound; a 32 MiB line
  was read whole), strict JSON: a key given twice, `NaN`/`Infinity`, a float
  that overflows to one, a nesting deep enough to raise `RecursionError`,
  trailing input — each refused with a code of its own (`duplicate_key`,
  `not_finite`, `not_json`, `not_utf8`, `too_large`). **A refused frame is
  followed by the next one.** An oversized line is drained in 64 KiB reads and
  refused as ONE frame. A leading BOM is dropped: PowerShell puts one on a pipe.
- **All three doors read through it**, so a body one door refuses no door
  accepts. stdio answers `invalid_argument: <code>: …`, MCP `-32700`, HTTP `400`.
- **The shape is checked before it is used**: method, params, tool name, uri,
  arguments (MCP); the request, plugin, since, command (stdio); command, action,
  plugin (gateway). Each gets the CLIENT'S code, not the backstop's.
- **The backstop**: anything else raised while answering is an answer —
  `failed` on stdio, `-32603` with the request's own id on MCP — and the next
  frame is served. A target that raised while being observed used to end the
  stdio loop.
- **The token is compared as bytes**, in `Policy.authenticate` and in the HTTP
  bearer check (latin-1 back to the bytes the client sent). A right token may be
  non-ASCII.
- **The envelope names its fields.** `COMMAND_FIELDS` is what a command may
  carry and the manifest publishes it; the stdio door holds a field list per op.
  A field the door does not know is a thing the caller believes about the call
  and the door does not, and it is refused by name.

## 3. What the suite's own first run found

`verify_mcp` failed one check on a COMMENT: *"the Server and serve() name no
target"* greps the class body for the word `page`, and the new comment said
"Windows code page". Right about what it matched, wrong about what the match
meant; the comment now says "ANSI encoding" and the check is left as coarse as
it was, because a check that fires on a word it should not is cheaper than one
that misses a target it should.

`verify_contract` had asserted since ADR-097 that *"a command carrying its own
risk claim"* is refused `forbidden`. It was — because `press` happened to be
blocked under that policy. The claim itself was ignored. It is `invalid_argument`
now, and a second check makes the claim on a command that WOULD have been
allowed: refused, and nothing ran.

## 4. Numbers

`verify_frames` 115 (new; six door processes under three stdin encodings, one
HTTP door, no browser). `mutate_frames` 37 (new). `verify_contract` 180 → 196.
`verify_mcp` 93 and `verify_http` 65 unchanged and green.

## 5. Held

- **`blind_console`'s unix-socket session** still reads with `json.loads`. It is
  this kit's own client talking to this kit's own server on a socket only the
  user can open. Trigger: the first foreign client of it.
- **A command cannot yet say when it was decided** (`expires_at`) or what it was
  decided FROM (`if_stamp`). Both are now refused by name rather than ignored,
  which is the precondition for giving them a meaning. That is the next slice.
- **Output is ASCII-escaped JSON on a text stdout**, which every encoding
  carries; on Windows the line ends `\r\n`, which every JSON-lines reader
  accepts. Not moved to bytes because nothing is wrong with it.
