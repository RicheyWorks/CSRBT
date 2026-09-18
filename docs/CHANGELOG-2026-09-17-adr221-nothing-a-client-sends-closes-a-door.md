# 2026-09-17 — ADR-221: eleven single frames closed a door, one from a caller with no credentials, and on Windows the door heard mojibake

## Fixed

- **`tools/harness_frames.py` (new)**: bytes in, strict UTF-8, one frame of at
  most 1 MiB at a time, strict JSON — `duplicate_key`, `not_finite`, `not_json`,
  `not_utf8`, `too_large`. A refused frame is followed by the next one. All three
  doors read through it.
- **The doors hear UTF-8 whatever the machine's code page is.** Under a cp1252
  stdin `Bear Creek — café` arrived as `Bear Creek â€” cafÃ©`.
- **The token is compared as bytes** (gateway and HTTP bearer). A wrong token
  with an accent raised `TypeError` through every `except HarnessError` and ended
  the stdio door — from a caller holding no credentials.
- **Shapes are checked before they are used** (method, params, tool name, uri,
  arguments, plugin, since, command, action), each refused with the client's
  own code; **a backstop** answers anything else (`failed` / `-32603` with the
  request's id) and serves the next frame.
- **The envelope names its fields**: `COMMAND_FIELDS` on the gateway and a field
  list per op on stdio, both published. `"dry_run": true` used to run for real;
  `"sinse"` used to get the whole snapshot without a word.

## Checked

`verify_frames` 115 (new), `mutate_frames` 37 (new; first run 28 killed, 2
survived, 7 crashed the suite instead of failing it — the suites now turn a
raise into a FAIL, and the two survivors were fixtures too small to reach the
clause). `verify_contract` 180 → 196. `verify_mcp` failed once on a comment
containing the word "page".
