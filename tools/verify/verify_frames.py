# -*- coding: utf-8 -*-
"""Nothing a client can send closes a door, and the door hears what was sent (ADR-221).

Measured before this suite existed, against the doors as they stood at ADR-217.
Each frame below was sent BETWEEN two good frames, to a real process:

    MCP    100,000 open brackets           RecursionError         door gone
           "method": 5                     AttributeError         door gone
           "params": ["x"]                 TypeError              door gone
           "params": "harness://x"         TypeError              door gone
           tool name a list                TypeError              door gone
           "uri": 7                        AttributeError         door gone
           one malformed UTF-8 byte        UnicodeDecodeError     door gone, and the GOOD
                                           (utf-8 strict stdin)   frame before it unanswered
    stdio  a wrong token with an accent    TypeError              door gone  -- NO CREDENTIALS
           a bare list                     AttributeError         door gone
           "command": [1]                  AttributeError         door gone
           "plugin": ["x"]                 TypeError              door gone
    HTTP   a wrong bearer with an accent   TypeError              connection dropped, no answer

and, on a machine whose code page is not UTF-8 (every Windows machine this kit
is developed on), the door HEARD `Bear Creek â€” cafÃ©` where a host had sent
`Bear Creek — café`, and would have typed that into the page.

  A. loads()   strict UTF-8, strict JSON: duplicate keys, NaN, Infinity, 1e999,
               depth, trailing input -- each refused with a code of its own.
  B. frames()  bounded, and it CARRIES ON: a refused frame is followed by the
               next one. Bytes, a stream with .buffer, a plain text stream.
  C. THE DOORS, AS PROCESSES, under three stdin encodings. Every frame in the
               table above gets a TYPED refusal -- not the backstop's -- and the
               frame after it is answered.
  D. the token is compared as BYTES, on both doors that take one per call.
  E. the backstop: a target that raises while being observed is an answer.
  F. the stdio envelope names its fields; a misspelt one is refused, not ignored.

Run:  python3 tools/verify/verify_frames.py
"""
MUTATE_ROLE = "subject"
import http.client, io, json, os, re, subprocess, sys, threading, time

import _kit

TOOLS = _kit.TOOLS_DIR.rstrip(os.sep)
sys.path.insert(0, TOOLS)
import harness_contract as C
import harness_frames as FR
import harness_stdio as STDIO
import harness_mcp as MCP
from harness_plugin_fixture import FixturePlugin

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


def err(fn):
    try:
        fn()
    except FR.FrameError as e:
        return e
    except Exception as e:                      # a leak: the wrong kind of exception
        return e
    return None


def val(fn):
    """What fn returns, or the exception it raised -- a check then FAILS on the wrong answer
    instead of the suite crashing on it, which a mutant runner cannot score (ADR-191)."""
    try:
        return fn()
    except Exception as e:
        return e


TOKEN = "t" * 32
SAID = u"Bear Creek — café"

# ---- A. loads() -----------------------------------------------------------------
ck(FR.loads(json.dumps({"v": SAID}, ensure_ascii=False).encode("utf-8")) == {"v": SAID},
   "UTF-8 bytes are read as UTF-8: %r" % SAID)
ck(val(lambda: FR.loads(FR.BOM + b'{"a":1}')) == {"a": 1},
   "a byte-order mark in front of a frame is not part of it -- PowerShell puts one on a pipe, "
   "and it is not an error a person piping a file in could do anything about")
e = err(lambda: FR.loads(b'{"a":"\xff"}'))
ck(isinstance(e, FR.FrameError) and e.code == "not_utf8" and "0xff" in e.message and "offset 6" in e.message,
   "a byte that is not UTF-8 is refused `not_utf8`, naming the byte and where: %s" % e)
e = err(lambda: FR.loads(u'{"a":"\udcff"}'))
ck(isinstance(e, FR.FrameError) and e.code == "not_utf8",
   "and so is TEXT carrying a lone surrogate -- bytes that were not UTF-8, smuggled through a "
   "lenient decoder upstream: %s" % e)
e = err(lambda: FR.loads(b'{"action":"ok","action":"clear-all"}'))
ck(isinstance(e, FR.FrameError) and e.code == "duplicate_key" and "'action'" in e.message,
   "A KEY GIVEN TWICE IS NOT ONE MESSAGE. json.loads keeps the last silently, so a logger that "
   "reads the first and a door that reads the last are handed two different commands: %s" % e)
e = err(lambda: FR.loads(b'{"c":{"arguments":{"n":1,"n":2}}}'))
ck(isinstance(e, FR.FrameError) and e.code == "duplicate_key",
   "...at any depth: %s" % e)
ck(FR.loads(b'{"a":{"k":1},"b":{"k":2}}') == {"a": {"k": 1}, "b": {"k": 2}},
   "the same key in two DIFFERENT objects is not a duplicate")
for lit in (b"NaN", b"Infinity", b"-Infinity", b"1e999", b"-1e999"):
    e = err(lambda: FR.loads(b'{"n":' + lit + b"}"))
    ck(isinstance(e, FR.FrameError) and e.code == "not_finite",
       "%s is refused `not_finite`: json.loads accepts the first three though they are not JSON, "
       "and turns the last two into them: %s" % (lit.decode(), e))
ck(FR.loads(b'{"n":1.5,"m":-2,"k":1e3}') == {"n": 1.5, "m": -2, "k": 1000.0},
   "ordinary numbers are untouched")
e = err(lambda: FR.loads(b"[" * 100000))
ck(isinstance(e, FR.FrameError) and e.code == "not_json",
   "100,000 open brackets are refused `not_json`. json.loads raises RecursionError for them, "
   "which is not a ValueError, and it went through the MCP door's `except ValueError` and out "
   "of the process: %s" % type(e).__name__)
e = err(lambda: FR.loads(b'{"op":"manifest"} {"op":"quit"}'))
ck(isinstance(e, FR.FrameError) and e.code == "not_json", "trailing input is refused: %s" % e)
e = err(lambda: FR.loads(b'{"a":'))
ck(isinstance(e, FR.FrameError) and e.code == "not_json", "and so is a frame cut short: %s" % e)
ck(set(FR.CODES) == {"too_large", "not_utf8", "not_json", "duplicate_key", "not_finite"},
   "the refusals a frame can get are published: %s" % (FR.CODES,))

# ---- B. frames() ------------------------------------------------------------------
got = list(FR.frames(io.BytesIO(b'{"a":1}\n\n   \n{"a":\xff}\n{"a":2}\n{"a":3}')))
ck([g[0] for g in got] == [{"a": 1}, None, {"a": 2}, {"a": 3}]
   and got[1][1].code == "not_utf8" and all(g[1] is None for i, g in enumerate(got) if i != 1),
   "A REFUSED FRAME IS FOLLOWED BY THE NEXT ONE: good, bad, good, and a last line with no "
   "newline -- four answers in order, blank lines skipped: %s"
   % [(g[0], getattr(g[1], "code", None)) for g in got])
big = b'{"pad":"' + b"x" * 200000 + b'"}\n'
got = list(FR.frames(io.BytesIO(b'{"a":1}\n' + big + b'{"a":2}\n'), cap=256))
ck(len(got) == 3 and got[0][0] == {"a": 1} and got[2][0] == {"a": 2}
   and got[1][1] is not None and got[1][1].code == "too_large"
   and str(len(big)) in got[1][1].message and "256" in got[1][1].message,
   "AN OVERSIZED LINE IS DRAINED AND REFUSED AS ONE FRAME, saying how big it was and what the "
   "bound is, and the frame after it is read from where it starts -- not from the middle of "
   "the big one: %s" % [(g[0], getattr(g[1], "message", None)) for g in got])


class Counting(io.BytesIO):
    most = 0

    def readline(self, n=-1):
        b = io.BytesIO.readline(self, n)
        Counting.most = max(Counting.most, len(b))
        return b


list(FR.frames(Counting(b'{"pad":"' + b"x" * 400000 + b'"}\n'), cap=1024))
ck(0 < Counting.most <= 65536,
   "and it is never held whole: the largest single read of a 400,000-byte line under a 1 KiB "
   "cap was %d bytes" % Counting.most)
exact = b'{"p":"' + b"x" * (256 - 8) + b'"}'
ck(len(exact) == 256
   and [g[1] for g in FR.frames(io.BytesIO(exact + b"\n"), cap=256)] == [None]
   and [getattr(g[1], "code", None) for g in FR.frames(io.BytesIO(exact[:-2] + b'x"}\n'), cap=256)] == ["too_large"],
   "the bound is exact: a frame of cap bytes passes, one of cap+1 does not")
ck(FR.FRAME_CAP == 1 << 20,
   "the bound is the HTTP door's 1 MiB (ADR-192), so a command that fits one door fits them all; "
   "the two pipe doors had none, and read a 32 MiB line whole")
ck([g[0] for g in FR.frames(io.StringIO(u'{"a":1}\n{"a":2}\n'))] == [{"a": 1}, {"a": 2}],
   "a plain text stream is read too -- the suites hand these doors a StringIO")


class Pipe(object):
    """What sys.stdin is: a text face that would mis-decode, over the bytes."""

    def __init__(self, b):
        self.buffer = io.BytesIO(b)

    def __iter__(self):
        raise AssertionError("the text face was read")

    def readline(self, *a):
        raise AssertionError("the text face was read")


ck(val(lambda: [g[0] for g in FR.frames(Pipe(json.dumps({"v": SAID}, ensure_ascii=False).encode("utf-8") + b"\n"))])
   == [{"v": SAID}],
   "a stream with a .buffer is read THROUGH it: the bytes, not the machine's opinion of them")

# ---- C. the doors, as processes ---------------------------------------------------
ENV = dict(os.environ, CSRBT_HARNESS_ENABLED="true", CSRBT_HARNESS_TOKEN=TOKEN,
           CSRBT_HARNESS_ALLOW_DRAFT="true")
ENCODINGS = (None, "utf-8:strict", "cp1252:strict")


def door(script, payload, enc):
    env = dict(ENV)
    env.pop("PYTHONIOENCODING", None)
    if enc:
        env["PYTHONIOENCODING"] = enc
    pr = subprocess.Popen([sys.executable, os.path.join(TOOLS, script), "--target", "fixture"],
                          env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    try:
        o, er = pr.communicate(payload, timeout=60)
    except subprocess.TimeoutExpired:
        pr.kill()
        o, er = pr.communicate()
        return "hung", [], er.decode("utf-8", "replace")
    lines = []
    for l in o.splitlines():
        try:
            lines.append(json.loads(l.decode("utf-8")))
        except Exception:
            lines.append({"unreadable": repr(l[:80])})
    return pr.returncode, lines, er.decode("utf-8", "replace")


def j(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n"


PING = lambda i: j({"jsonrpc": "2.0", "id": i, "method": "ping"})
MCP_BAD = [
    ("100,000 open brackets", b"[" * 100000 + b"\n", MCP.PARSE_ERROR),
    ("a malformed UTF-8 byte", b'{"jsonrpc":"2.0","id":9,"method":"pi\xffng"}\n', MCP.PARSE_ERROR),
    ("a key given twice", b'{"jsonrpc":"2.0","id":9,"method":"ping","method":"tools/list"}\n', MCP.PARSE_ERROR),
    ("a bare number", b"7\n", MCP.INVALID_REQUEST),
    ("method is a number", j({"jsonrpc": "2.0", "id": 5, "method": 5}), MCP.INVALID_REQUEST),
    ("params is a list", j({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": ["x"]}), MCP.INVALID_PARAMS),
    ("params is a string", j({"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": "harness://x"}), MCP.INVALID_PARAMS),
    ("the tool name is a list", j({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": ["a"]}}), MCP.INVALID_PARAMS),
    ("the uri is a number", j({"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": 7}}), MCP.INVALID_PARAMS),
    ("arguments is a list", j({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                               "params": {"name": "csrbt-fixture_ok", "arguments": [1]}}), MCP.INVALID_PARAMS),
]
DISC = j({"op": "discover", "token": TOKEN})
STDIO_BAD = [
    ("a wrong token with an accent", j({"op": "discover", "token": u"café-is-not-the-token-at-all-no"}), "unauthorized"),
    ("a token that is a number", j({"op": "discover", "token": 5}), "unauthorized"),
    ("a bare list", b"[1,2]\n", "invalid_argument"),
    ("a command that is a list", j({"op": "execute", "token": TOKEN, "plugin": "csrbt-fixture", "command": [1]}), "invalid_argument"),
    ("a plugin that is a list", j({"op": "observe", "token": TOKEN, "plugin": ["x"]}), "invalid_argument"),
    ("a since that is an object", j({"op": "observe", "token": TOKEN, "plugin": "csrbt-fixture", "since": {"a": 1}}), "invalid_argument"),
    ("an action that is a list", j({"op": "execute", "token": TOKEN, "plugin": "csrbt-fixture",
                                    "command": {"request_id": "x", "action": ["ok"]}}), "invalid_argument"),
    ("100,000 open brackets", b"[" * 100000 + b"\n", "invalid_argument"),
    ("a malformed UTF-8 byte", b'{"op":"discover","token":"\xff\xfe"}\n', "invalid_argument"),
    ("a key given twice", ('{"op":"execute","token":"%s","plugin":"csrbt-fixture","command":'
                           '{"request_id":"d1","action":"ok","action":"broken"}}\n' % TOKEN).encode(), "invalid_argument"),
]
HEAR = j({"op": "execute", "token": TOKEN, "plugin": "csrbt-fixture",
          "command": {"request_id": "hear", "action": "reached", "arguments": {"thing": SAID}}})

for enc in ENCODINGS:
    tag = "stdin %s" % (enc or "as the machine has it")
    # -- MCP: good, bad, good, bad, ... good
    payload = PING(100)
    for i, (_n, frame, _c) in enumerate(MCP_BAD):
        payload += frame + PING(101 + i)
    rc, out, er = door("harness_mcp.py", payload, enc)
    ck(rc == 0 and len(out) == 2 * len(MCP_BAD) + 1,
       "[%s] THE MCP DOOR OUTLIVES EVERY FRAME: %d bad frames between %d good ones, %d answers, "
       "exit %s  %s" % (tag, len(MCP_BAD), len(MCP_BAD) + 1, len(out), rc, er.strip().split("\n")[-1][:120] if rc else ""))
    for i, (name, _f, code) in enumerate(MCP_BAD):
        bad = out[2 * i + 1] if len(out) > 2 * i + 1 else {}
        nxt = out[2 * i + 2] if len(out) > 2 * i + 2 else {}
        ck((bad.get("error") or {}).get("code") == code and nxt.get("id") == 101 + i and "result" in nxt,
           "[%s] MCP, %s: refused %s -- a TYPED refusal, not the backstop's -- and the ping after "
           "it is answered: %s" % (tag, name, code, json.dumps(bad)[:160]))
    # -- stdio
    payload = DISC
    for _n, frame, _c in STDIO_BAD:
        payload += frame + DISC
    payload += HEAR
    rc, out, er = door("harness_stdio.py", payload, enc)
    ck(rc == 0 and len(out) == 2 * len(STDIO_BAD) + 2,
       "[%s] THE STDIO DOOR OUTLIVES EVERY FRAME: %d answers, exit %s  %s"
       % (tag, len(out), rc, er.strip().split("\n")[-1][:120] if rc else ""))
    for i, (name, _f, code) in enumerate(STDIO_BAD):
        bad = out[2 * i + 1] if len(out) > 2 * i + 1 else {}
        nxt = out[2 * i + 2] if len(out) > 2 * i + 2 else {}
        ck(bad.get("ok") is False and bad.get("code") == code and nxt.get("ok") is True,
           "[%s] stdio, %s: refused %s, and the frame after it is answered: %s"
           % (tag, name, code, json.dumps(bad)[:160]))
    heard = out[-1] if out else {}
    ck(heard.get("message") == u"reached with %r" % SAID,
       "[%s] THE DOOR HEARS WHAT WAS SENT: a host sends %r as UTF-8, which is what MCP requires "
       "of it, and that is what reaches the target. On a cp1252 stdin it used to arrive as "
       "'Bear Creek â€” cafÃ©': %r" % (tag, SAID, heard.get("message")))
    ck(all(ord(ch) < 128 for l in out for ch in json.dumps(l)),
       "[%s] and what the door SAYS is ASCII-escaped JSON, which every stdout encoding carries"
       % tag)
ck(not any(f[0] == "a wrong token with an accent" and f[2] != "unauthorized" for f in STDIO_BAD),
   "(the accented wrong token is answered `unauthorized`: before ADR-221 it ended the stdio door "
   "with a TypeError, from a caller holding NO CREDENTIALS)")

# ---- D. the token is compared as bytes ------------------------------------------------
pol = C.Policy(token=TOKEN, enabled=True)
for bad in (u"café-is-not-the-token-at-all-no", u"\udcff" * 30, u"t" * 31 + u"é"):
    try:
        pol.authenticate(bad)
        ck(False, "a wrong token was accepted: %r" % bad)
    except C.HarnessError as ex:
        ck(ex.code == "unauthorized", "a wrong non-ASCII token is `unauthorized`: %r" % bad)
    except Exception as ex:
        ck(False, "a wrong non-ASCII token RAISED %s -- hmac.compare_digest refuses to compare "
                  "non-ASCII str, and the door did not catch it: %r" % (type(ex).__name__, bad))
accent = u"é" * 24
try:
    C.Policy(token=accent, enabled=True).authenticate(accent)
    ck(True, "and a RIGHT token may be non-ASCII: it is compared as UTF-8 bytes")
except Exception as ex:
    ck(False, "a right non-ASCII token was refused: %s" % ex)


def http_door():
    env = dict(ENV, CSRBT_HARNESS_HTTP="true")
    pr = subprocess.Popen([sys.executable, os.path.join(TOOLS, "harness_http.py"), "--target", "fixture",
                           "--port", "0"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    said = []

    def rd():
        for l in pr.stderr:
            said.append(l.decode("utf-8", "replace"))

    threading.Thread(target=rd, daemon=True).start()
    t0 = time.time()
    port = None
    while time.time() - t0 < 30 and port is None:
        for l in list(said):
            m = re.search(r"127\.0\.0\.1:(\d+)", l)
            if m:
                port = int(m.group(1))
        time.sleep(0.05)
    return pr, port, said


def post(port, body, bearer, extra=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        c.putrequest("POST", "/mcp")
        c.putheader("Content-Type", "application/json")
        c.putheader("Accept", "application/json, text/event-stream")
        c.putheader("Content-Length", str(len(body)))
        c.putheader("Authorization", bearer)
        for k, v in (extra or {}).items():
            c.putheader(k, v)
        c.endheaders(body)
        r = c.getresponse()
        return r.status, r.read(), dict(r.getheaders())
    except Exception as ex:
        return "no answer: %s" % type(ex).__name__, b"", {}
    finally:
        c.close()


pr, port, said = http_door()
try:
    ck(port is not None, "the HTTP door came up on a port: %s" % "".join(said)[-200:])
    init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                  "clientInfo": {"name": "verify_frames", "version": "0"}}}).encode()
    st, body, _h = post(port, init, u"Bearer café-is-not-the-token-at-all-no".encode("utf-8"))
    ck(st == 401,
       "HTTP: a wrong bearer with an accent is ANSWERED 401. It used to raise TypeError inside the "
       "handler: the connection was dropped with no response and a traceback on the door's "
       "stderr: %s" % (st,))
    st, body, h = post(port, init, ("Bearer " + TOKEN).encode())
    sid = h.get("Mcp-Session-Id") or h.get("mcp-session-id")
    ck(st == 200 and sid, "and the door is still there for the right one: %s" % st)
    for name, raw, code in (("a key given twice", b'{"jsonrpc":"2.0","id":2,"method":"ping","method":"tools/list"}', "duplicate_key"),
                            ("a malformed UTF-8 byte", b'{"jsonrpc":"2.0","id":2,"method":"pi\xffng"}', "not_utf8"),
                            ("100,000 open brackets", b"[" * 100000, "not_json"),
                            ("NaN", b'{"jsonrpc":"2.0","id":2,"method":"ping","params":{"n":NaN}}', "not_finite")):
        st, body, _h = post(port, raw, ("Bearer " + TOKEN).encode(), {"Mcp-Session-Id": sid or ""})
        ck(st == 400 and code.encode() in body,
           "HTTP, %s: answered 400 naming `%s` -- the same reader as the pipe doors, so a body one "
           "door refuses no door accepts: %s %s" % (name, code, st, body[:120]))
    st, body, _h = post(port, json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}).encode(),
                        ("Bearer " + TOKEN).encode(), {"Mcp-Session-Id": sid or ""})
    ck(st == 200 and b'"result"' in body, "and after all of them a ping is answered: %s" % st)
    ck(not any("Traceback" in l for l in said),
       "with no traceback on the door's stderr: %s" % "".join(said)[-300:])
finally:
    pr.kill()

# ---- E. the backstop --------------------------------------------------------------------
class Raises(FixturePlugin):
    def observe(self, sensitive=False):
        raise RuntimeError("the target raised while being looked at")


allow_all = C.Policy(token=TOKEN, allow={"DRAFT": True}, enabled=True)
out = io.StringIO()
rc = val(lambda: STDIO.serve(C.Gateway(C.Registry([Raises()]), allow_all),
                             io.BytesIO(j({"op": "observe", "token": TOKEN, "plugin": "csrbt-fixture"}) + DISC), out))
res = [json.loads(l) for l in out.getvalue().splitlines()] + ([{"left": repr(rc)}] if isinstance(rc, Exception) else [])
ck(len(res) == 2 and res[0].get("ok") is False and res[0].get("code") == "failed"
   and "RuntimeError" in res[0].get("message", "") and res[1].get("ok") is True,
   "STDIO BACKSTOP: a target that RAISES while being observed is an answer -- `failed`, naming "
   "what was raised -- and the next frame is served. It used to end the loop: %s" % res[:1])
out = io.StringIO()
srv = MCP.Server(C.Gateway(C.Registry([Raises()]), allow_all), TOKEN)
rc = val(lambda: MCP.serve(srv, io.BytesIO(j({"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                                              "params": {"uri": "harness://csrbt-fixture/snapshot"}}) + PING(2)), out))
res = [json.loads(l) for l in out.getvalue().splitlines()] + ([{"left": repr(rc)}] if isinstance(rc, Exception) else [])
ck(len(res) == 2 and (res[0].get("error") or {}).get("code") == MCP.INTERNAL_ERROR
   and res[0].get("id") == 1 and "result" in res[1],
   "MCP BACKSTOP: the same, as JSON-RPC's internal error with the request's own id: %s" % res[:1])

# ---- F. the stdio envelope names its fields ---------------------------------------------
def stdio(*frames_):
    o = io.StringIO()
    plug = FixturePlugin()
    STDIO.serve(C.Gateway(C.Registry([plug]), allow_all), io.BytesIO(b"".join(frames_)), o)
    return plug, [json.loads(l) for l in o.getvalue().splitlines()]


_p, res = stdio(j({"op": "observe", "token": TOKEN, "plugin": "csrbt-fixture", "sinse": "abc"}))
ck(res[0].get("ok") is False and res[0].get("code") == "invalid_argument" and "sinse" in res[0].get("message", ""),
   "A MISSPELT FIELD IS REFUSED, NOT IGNORED: `sinse` used to be dropped and the whole snapshot "
   "served, to a client that believed it had asked for the change: %s" % res[0])
_p, res = stdio(j({"op": "observe", "token": TOKEN, "plugin": "csrbt-fixture", "since": "abc"}),
                j({"op": "manifest", "token": TOKEN}), j({"op": "quit"}))
ck([r.get("ok") for r in res] == [True, True, True],
   "and every field the door does take is still taken: %s" % [r.get("code") for r in res])
_p, res = stdio(j({"op": "manifest", "token": TOKEN, "plugin": "csrbt-fixture"}))
ck(res[0].get("ok") is False and "plugin" in res[0].get("message", ""),
   "a field that belongs to ANOTHER op is refused too -- each op names its own: %s" % res[0])

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
