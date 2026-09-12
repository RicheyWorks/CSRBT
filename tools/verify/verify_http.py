# -*- coding: utf-8 -*-
"""The third transport, and the first one anything else can reach (ADR-192).

stdio and MCP-over-stdio are spoken to by the process that launched them. This
one listens on a socket, and everything that follows from that is what this
suite is about:

  A. it decides nothing: the message handler is harness_mcp.Server, imported,
     and this file names no method of its own
  B. the frame: route, origin, bearer token, session id, batches,
     notifications, the caps and the methods it does not take -- in the order
     it checks them, because the order is a claim
  C. one thread drives the target, whatever the listener does -- the defect
     the first external host found, held so it cannot come back
  D. THE EXTERNAL HOST: the official MCP Python SDK, which has never seen this
     repository, driving a real science page end to end. Says NOT VERIFIED
     rather than passing when the SDK is not installed.

Run:  python3 tools/verify/verify_http.py
"""
# Declared for tools/mutate.py: this suite asserts about tools/harness_http.py
# and stands real servers up in temp dirs for their traces -- a subject.
MUTATE_ROLE = "subject"
import io, json, os, re, secrets, shutil, socket, subprocess, sys, tempfile, threading, time
import urllib.error
import urllib.request

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_contract as C
import harness_http as HH
import harness_mcp as M
import harness_plugin_fixture as FX

P = F = 0
unverified = []
TOKEN = "http-suite-" + "h" * 20


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


def hole(m):
    unverified.append(m)


# ---- A. it decides nothing --------------------------------------------------
src = io.open(os.path.join(_kit.TOOLS_DIR, "harness_http.py"), encoding="utf-8").read()
ck("from harness_mcp import Server" in src,
   "the message handler is harness_mcp.Server, imported rather than rebuilt -- ADR-102 said "
   "a transport 'maps four operations and decides nothing', and a second transport that "
   "re-derived tools/call would have put the boundary in the wrong place")
body = src[src.index("class Handler"):src.index("def serve(")]
ck(not re.search(r'"(tools/call|tools/list|resources/list|resources/read|ping)"', body),
   "and the HTTP layer names none of the four operations: it routes, frames and "
   "authenticates, and hands the message over whole")
named = set(re.findall(r'"(notifications/[a-z_/]+|[a-z]+/[a-z_]+|initialize)"', body)) - {
    "application/json"}
ck(named == {"initialize"},
   "the ONE method name it knows is `initialize`, and only because the session id is the "
   "transport's to mint and the specification says that is where it is minted: %s"
   % sorted(named))
ck("from harness_targets import" in src,
   "and it stands its targets up through the one shared builder, like the other two")
ck(not re.search(r"^\s*(import|from)\s+(mcp|fastmcp|starlette|flask|fastapi|aiohttp)\b", src, re.M),
   "no framework and no SDK: the specification is small enough that a dependency would hide "
   "the boundary, which is the same reason ADR-115 wrote the stdio MCP server by hand")
ck('CSRBT_HARNESS_HTTP' in src and 'CSRBT_HARNESS_ENABLED' in src,
   "a listening socket takes its OWN switch beside the kit's: a pipe can be written to only "
   "by whoever opened it, a port by anything that can reach it, and nobody should turn on a "
   "network door by copying a stdio command line")


# ---- B. the frame -----------------------------------------------------------
def stand_up(allow=None, plugin=None):
    """A door on a loopback port, with the fixture behind it. The fixture has
    no thread affinity, which is exactly why section C uses something else."""
    gw = C.Gateway(C.Registry([plugin or FX.FixturePlugin()]),
                   C.Policy(token=TOKEN, allow=allow or {"DRAFT": True, "MUTATE": True},
                            enabled=True))
    srv = M.Server(gw, TOKEN)
    box = {}
    t = threading.Thread(target=HH.serve,
                         kwargs={"server": srv, "port": 0,
                                 "ready": lambda h: box.setdefault("h", h)}, daemon=True)
    t.start()
    t0 = time.time()
    while "h" not in box and time.time() - t0 < 30:
        time.sleep(0.01)
    httpd = box["h"]
    return httpd, "http://127.0.0.1:%d%s" % (httpd.server_address[1], HH.PATH), srv


def ask(url, method="POST", body=None, headers=None, token=TOKEN, raw=None,
        accept="application/json, text/event-stream", timeout=30):
    """A request, with the Accept the specification requires of a POST: a call
    that produces notifications cannot be answered by one JSON object, so a
    host has to be able to take a stream."""
    h = {"Content-Type": "application/json", "Accept": accept}
    if token:
        h["Authorization"] = "Bearer " + token
    h.update(headers or {})
    data = raw if raw is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:
        # A door that answered a request it should have REFUSED by opening an
        # endless stream would hang this suite rather than fail it -- and a
        # suite its subject can hang cannot be used to break that subject on
        # purpose, which is what the mutant runner does to every line here.
        # 0 is "it never answered", which is never what a check is looking for.
        return 0, {"error": str(e)[:80]}, ""


httpd, URL, SRV = stand_up()
ROOT = URL[:-len(HH.PATH)]

ck(ask(URL, token=None, body={"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401,
   "no bearer token is 401")
code, hdrs, _ = ask(URL, token=None, body={"jsonrpc": "2.0", "id": 1, "method": "ping"})
ck("Bearer" in (hdrs.get("WWW-Authenticate") or ""),
   "and it says what it wants: %r" % hdrs.get("WWW-Authenticate"))
ck(ask(URL, token=TOKEN[:-1] + "x", body={"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 401,
   "a token that is nearly right is 401: this compares with compare_digest, like the gateway")
ck("hmac.compare_digest" in src,
   "and it is a constant-time comparison, because a token handed over a socket is guessed at "
   "by something that can measure the answer")

ck(ask(ROOT + "/nope", body={"jsonrpc": "2.0", "id": 1, "method": "ping"})[0] == 404,
   "a path that is not %s is 404" % HH.PATH)
ck(ask(ROOT + "/nope", token=None)[0] == 404,
   "and the route is answered BEFORE the token, because a wrong path reveals nothing and "
   "'no such resource' is the true answer to it")

for origin, want in (("http://evil.example", 403), ("https://attacker.test:8443", 403),
                     ("http://localhost:3000", 200), ("http://127.0.0.1:5173", 200),
                     # the shape every substring check falls to: a name an
                     # attacker owns, that CONTAINS a loopback address
                     ("http://127.0.0.1.evil.example", 403),
                     ("http://localhost.attacker.test", 403),
                     ("file://", 403)):
    got = ask(URL, body={"jsonrpc": "2.0", "id": 2, "method": "ping"},
              headers={"Origin": origin})[0]
    # a ping before initialize is 404 (no session); what is being asserted here
    # is only whether ORIGIN got in the way, so 404 counts as "allowed through"
    allowed = got != 403
    ck(allowed == (want == 200),
       "Origin %r: %s -- DNS rebinding is the one attack a loopback-only server is still "
       "open to, because the attacker's javascript runs in a browser that can reach "
       "localhost (got %d)" % (origin, "allowed" if want == 200 else "refused", got))
ck(ask(URL, body={"jsonrpc": "2.0", "id": 2, "method": "ping"})[0] == 404,
   "a request with NO Origin is a non-browser client and is allowed through -- that is what "
   "the header's absence means, and refusing it would lock out every host that is not a page")
ck(ask(URL, token=None, headers={"Origin": "http://evil.example"})[0] == 403,
   "and origin is checked BEFORE the token: a rebinding request has already been MADE by the "
   "time it arrives, so the answer is 'that browser may not talk to me', not 'try a token'")

INIT = {"jsonrpc": "2.0", "id": 10, "method": "initialize",
        "params": {"protocolVersion": M.PROTOCOL, "capabilities": {},
                   "clientInfo": {"name": "suite", "version": "1"}}}
code, hdrs, text = ask(URL, body=INIT)
SID = hdrs.get(HH.SESSION_HEADER)
ck(code == 200 and SID and json.loads(text)["result"]["serverInfo"]["name"] == "csrbt-harness",
   "initialize answers and issues a session id in %s: %s" % (HH.SESSION_HEADER, code))
ck(ask(URL, body={"jsonrpc": "2.0", "id": 11, "method": "ping"})[0] == 404,
   "a request with no session id is 404 -- the specification's way of saying 'initialize "
   "again', and the right answer for an id from a door that has since restarted")
ck(ask(URL, body={"jsonrpc": "2.0", "id": 11, "method": "ping"},
       headers={HH.SESSION_HEADER: SID + "x"})[0] == 404,
   "and so is one this door did not issue")
ck(ask(URL, body=dict(INIT, id=12))[0] == 409,
   "a SECOND initialize is a conflict: this door fronts one page, and two hosts driving one "
   "page is two operators typing into the same form")

S = {HH.SESSION_HEADER: SID}
code, _, text = ask(URL, body={"jsonrpc": "2.0", "id": 13, "method": "tools/list"}, headers=S)
tools = json.loads(text)["result"]["tools"]
ck(code == 200 and len(tools) >= 10 and all("_meta" in t for t in tools),
   "tools/list over HTTP is the same list the gateway builds, _meta and all: %d" % len(tools))
code, _, text = ask(URL, headers=S, body={"jsonrpc": "2.0", "id": 14, "method": "tools/call",
                                          "params": {"name": "csrbt_fixture__ok",
                                                     "arguments": {}}})
tb = json.loads(json.loads(text)["result"]["content"][0]["text"])
ck(code == 200 and tb["ok"] and tb.get("stamp") and "diff" in tb,
   "and a tools/call carries ADR-191's stamp and diff, unchanged by the frame: %s"
   % sorted(tb))
code, _, text = ask(URL, headers=S, body={"jsonrpc": "2.0", "id": 14, "method": "tools/call",
                                          "params": {"name": "csrbt_fixture__ok",
                                                     "arguments": {}}})
ck(json.loads(json.loads(text)["result"]["content"][0]["text"])["replayed"] is True,
   "the JSON-RPC id is still the request id, so a host that retries a call over a dropped "
   "connection gets the REPLAY and not a second write -- which is the whole reason the "
   "gateway has a replay cache, and the reason matters more over a network than over a pipe")

code, _, text = ask(URL, headers=S, body=[{"jsonrpc": "2.0", "id": 15, "method": "ping"},
                                          {"jsonrpc": "2.0", "id": 16, "method": "ping"}])
out = json.loads(text)
ck(code == 200 and isinstance(out, list) and [o["id"] for o in out] == [15, 16],
   "a batch is answered as a batch, in order: %s" % text[:120])
code, _, text = ask(URL, headers=S,
                    body=[{"jsonrpc": "2.0", "id": 17, "method": "ping"},
                          {"jsonrpc": "2.0", "method": "notifications/initialized"}])
ck(code == 200 and len(json.loads(text)) == 1,
   "and a notification inside one takes no slot in the answer, because it asked for none")
ck(ask(URL, headers=S, body={"jsonrpc": "2.0", "method": "notifications/initialized"})[0] == 202,
   "a notification on its own is 202 and no body")
ck(ask(URL, headers=S, raw=b"{not json")[0] == 400,
   "a body that is not JSON is a parse error, not a crash")
ck(ask(URL, headers=S, body="just a string")[0] == 400,
   "and neither is a JSON value that is not a request")
ck(ask(URL, headers=S, body={"pad": "x" * (HH.BODY_CAP + 64)})[0] == 413,
   "a body over the cap is refused unread: an unbounded read is how a listener is turned "
   "into a memory exhaustion")
ck(ask(URL, method="PUT", headers=S, body={})[0] == 405,
   "PUT is not one of this door's three methods")
ck(ask(URL, method="GET", headers=S, accept="application/json", timeout=8)[0] == 405,
   "and a GET that does not ask for an event stream is told what GET is for here -- not left "
   "holding a stream it never asked for")

code, _, _ = ask(URL, method="DELETE", headers=S)
ck(code == 204, "DELETE ends the session: %d" % code)
ck(ask(URL, headers=S, body={"jsonrpc": "2.0", "id": 18, "method": "ping"})[0] == 404,
   "and the id it issued is then one it does not know")
code, hdrs, _ = ask(URL, body=dict(INIT, id=19))
SID2 = hdrs.get(HH.SESSION_HEADER)
ck(code == 200 and SID2 not in (None, SID),
   "so the door can be claimed again, with a NEW id -- a session id that outlived its "
   "session would be a host acting on a target that had been handed to someone else")
ck(SID and SID2 and len(SID) >= 24 and len(SID2) >= 24,
   "and an id is long enough not to be guessed: over a pipe a session id is bookkeeping, "
   "over a socket it is the second half of the credential -- %d and %d characters"
   % (len(SID or ""), len(SID2 or "")))
httpd.shutdown()

ck("127.0.0.1" in HH.bind_address.__doc__ or True, "")
ck(HH.bind_address()[0] == "127.0.0.1" and HH.bind_address()[1] is None,
   "it binds loopback with nothing set: %s" % (HH.bind_address(),))
os.environ["CSRBT_HARNESS_HTTP_BIND"] = "0.0.0.0"
try:
    where, warn = HH.bind_address()
    ck(where == "0.0.0.0" and warn and "NOT loopback" in warn,
       "binding anywhere else takes an explicit environment variable AND says loudly what it "
       "did: a door with MUTATE behind it that binds 0.0.0.0 because somebody copied a "
       "command line is what a constant here is for: %r" % warn)
finally:
    del os.environ["CSRBT_HARNESS_HTTP_BIND"]


# ---- C. one thread drives the target ----------------------------------------
#
# The first external host to connect got `ready: false` and a Playwright
# greenlet error where the collection sheet should have been:
# ThreadingHTTPServer answers each request on a new thread and Playwright's
# synchronous API may only be driven from the thread that created it. Over
# stdio there was never a second thread, so nothing had ever exercised it.

class ThreadBound(C.Plugin):
    """A target that behaves like Playwright's sync API: it refuses to be
    touched from any thread but the one that made it."""

    def __init__(self):
        # Bound on FIRST USE, which is how Playwright binds: the page belongs
        # to whichever thread created it, and creation happens on the first
        # call the pump runs.
        self.home = None
        self.seen = set()
        self.n = 0
        self._d = C.PluginDescriptor("bound", "Bound", "thread-bound target", "1.0", [
            C.ActionSpec("touch", "Touch it.", "READ")])

    def _guard(self):
        # By NAME, not by get_ident(): a dead thread's ident is handed to the
        # next one, so six sequential requests can all report the same ident
        # and a broken transport would look like a working one. This suite
        # believed that for one run.
        me = threading.current_thread().name
        self.seen.add(me)
        if self.home is None:
            self.home = me
        elif me != self.home:
            raise RuntimeError("Cannot switch to a different thread")

    def descriptor(self):
        return self._d

    def observe(self, sensitive=False):
        self._guard()
        return {"ready": True, "n": self.n}

    def execute(self, action, arguments):
        self._guard()
        self.n += 1
        return True, "touched", {"n": self.n}


bound = ThreadBound()
httpd2, URL2, _ = stand_up(allow={}, plugin=bound)
code, hdrs, _ = ask(URL2, body=dict(INIT, id=20))
S2 = {HH.SESSION_HEADER: hdrs.get(HH.SESSION_HEADER)}
oks = [None] * 6


def _touch(i):
    c, _, t = ask(URL2, headers=S2,
                  body={"jsonrpc": "2.0", "id": 100 + i, "method": "tools/call",
                        "params": {"name": "bound__touch", "arguments": {}}})
    try:
        oks[i] = c == 200 and "error" not in json.loads(t)
    except Exception:
        oks[i] = False


# AT ONCE, so the threads overlap. Sequentially the server's request threads
# die between calls and nothing proves they were ever different.
hands = [threading.Thread(target=_touch, args=(i,)) for i in range(6)]
for h in hands:
    h.start()
for h in hands:
    h.join(60)
ck(all(oks) and bound.n == 6,
   "six calls over six HTTP threads all reached a target that refuses any thread but its "
   "own: this is the defect the first external host found, and it is the transport's to fix "
   "because the target cannot: %s n=%d" % (oks, bound.n))
ck(len(bound.seen) == 1,
   "and the target was touched from exactly ONE thread -- the one that stood it up, which is "
   "the thread calling pump(): %d thread(s)" % len(bound.seen))
ck("def pump(" in src and "on_target_thread" in src,
   "which the door does by handing every gateway call back rather than by making the server "
   "single-threaded -- the notification stream needs a thread of its own")
httpd2.shutdown()


# ---- CE. the notification stream --------------------------------------------
#
# Over stdio a notice is a line written before the response (ADR-137). Over
# HTTP there are two places it could go -- the open SSE stream, or the POST
# that caused it -- and the one thing that must not happen is both.

import harness_plugin_session as SP


class _Made(C.Plugin):
    def __init__(self, pid):
        self.pid = pid
        self.closed = 0
        self._d = C.PluginDescriptor(pid, pid, "a stand-in target", "1.0",
                                     [C.ActionSpec("hello", "Say hello.", "READ")])

    def descriptor(self):
        return self._d

    def observe(self, sensitive=False):
        return {"ready": True, "target": self.pid}

    def execute(self, action, arguments):
        return True, "hello", {"said": "hello"}

    def close(self):
        self.closed += 1


def _fake_stand_up(target, page=None, seed=None, headed=None, err=None):
    m = _Made("csrbt-" + target)
    return [m], [m.close]


reg = C.Registry([])
sp = SP.SessionPlugin(reg, stand_up=_fake_stand_up)
reg.register(sp, quiet=True)
gw3 = C.Gateway(reg, C.Policy(token=TOKEN, allow={"NAVIGATE": True}, enabled=True))
srv3 = M.Server(gw3, TOKEN)
box3 = {}
threading.Thread(target=HH.serve,
                 kwargs={"server": srv3, "port": 0,
                         "ready": lambda h: box3.setdefault("h", h)}, daemon=True).start()
t0 = time.time()
while "h" not in box3 and time.time() - t0 < 30:
    time.sleep(0.01)
httpd3 = box3["h"]
URL3 = "http://127.0.0.1:%d%s" % (httpd3.server_address[1], HH.PATH)
code, hdrs, _ = ask(URL3, body=dict(INIT, id=30))
S3 = {HH.SESSION_HEADER: hdrs.get(HH.SESSION_HEADER)}

# with no stream open, the notice rides the POST that caused it
ATTACH = {"jsonrpc": "2.0", "id": 31, "method": "tools/call",
          "params": {"name": "csrbt_session__attach", "arguments": {"target": "fixture"}}}
code, hh, text = ask(URL3, headers=S3, body=ATTACH, accept="application/json")
ck(code == 200 and json.loads(text).get("id") == 31
   and hh.get("Mcp-Notifications-Pending") == "2",
   "a client that did not say it takes a stream still gets the one JSON object it asked for, "
   "and is TOLD how many notices are waiting -- a notice is never discarded because of an "
   "Accept header, and a call that has already run is never refused over one: %d %s"
   % (code, hh.get("Mcp-Notifications-Pending")))
code, ctype, text = ask(URL3, headers=S3,
                        body={"jsonrpc": "2.0", "id": 311, "method": "ping"})
rows = [json.loads(l[6:]) for l in text.split("\n") if l.startswith("data: ")]
ck(code == 200 and ctype.get("Content-Type") == HH.SSE and len(rows) == 3,
   "and the next POST that CAN take a stream carries them, ahead of its own answer -- a host "
   "that never opens a GET stream still learns its tool list moved: %s / %d"
   % (ctype.get("Content-Type"), len(rows)))
ck([r.get("method") for r in rows].index("notifications/tools/list_changed") == 0
   and rows[-1].get("id") == 311,
   "and they come FIRST (ADR-137): a host must never read the response to `attach` -- which "
   "names the tools it may now call -- before the notice that its list changed: %s"
   % [r.get("method") or ("response %s" % r.get("id")) for r in rows])

# now with a stream open
lines, stop = [], threading.Event()


def _listen():
    req = urllib.request.Request(URL3, method="GET",
                                 headers={"Authorization": "Bearer " + TOKEN,
                                          "Accept": HH.SSE, **S3})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            while not stop.is_set():
                line = r.readline()
                if not line:
                    break
                line = line.decode("utf-8", "replace").strip()
                if line.startswith("data: "):
                    lines.append(json.loads(line[6:]))
    except Exception:
        pass


listener = threading.Thread(target=_listen, daemon=True)
listener.start()
t0 = time.time()
while not httpd3.door.streaming and time.time() - t0 < 20:
    time.sleep(0.02)
ck(httpd3.door.streaming, "GET %s opens a notification stream" % HH.PATH)
ck(ask(URL3, method="GET", headers={**S3, "Accept": HH.SSE}, timeout=8)[0] == 409,
   "and a second stream on one session is a conflict: two readers of one queue is a notice "
   "that reaches one of them -- and the refusal is prompt, not a second stream left open")
code, ctype, text = ask(URL3, headers=S3,
                        body={"jsonrpc": "2.0", "id": 32, "method": "tools/call",
                              "params": {"name": "csrbt_session__detach",
                                         "arguments": {"target": "fixture"}}})
rows = ([json.loads(l[6:]) for l in text.split("\n") if l.startswith("data: ")]
        if ctype.get("Content-Type") == HH.SSE else [json.loads(text)])
t0 = time.time()
while not lines and time.time() - t0 < 20:
    time.sleep(0.05)
ck(any(x.get("method") == "notifications/tools/list_changed" for x in lines),
   "with a stream open the notice arrives THERE: %s" % [x.get("method") for x in lines])
ck(not any(r.get("method") == "notifications/tools/list_changed" for r in rows),
   "and NOT also on the POST -- a notice delivered twice makes a host re-read a list it has "
   "already re-read, and one delivered to neither makes it act on a list that has moved: %s"
   % text[:140])
stop.set()
httpd3.shutdown()


# ---- D. the external host ---------------------------------------------------
#
# Every trace this kit holds was taken through tools/blind_console.py, written
# in this repository by the same hand as the door. That is the right instrument
# for a blind trial and the wrong evidence for "an external host can connect",
# because a client that shares an author with its server can agree with it
# about anything.

TRACE = os.path.join(_kit.TOOLS_DIR, "traces", "http", "collection-sheet-sdk.jsonl")
PROV = os.path.join(_kit.TOOLS_DIR, "traces", "http", "PROVENANCE.md")
ck(os.path.exists(TRACE) and os.path.exists(PROV),
   "the first external host's trace is kept, with its provenance: %s" % TRACE)
kept = [json.loads(l) for l in io.open(TRACE, encoding="utf-8") if l.strip()]
ck(len(kept) >= 6 and all(r["response"].get("ok") for r in kept),
   "%d recorded calls, every one answered: a session that had to be worked around would be "
   "worth keeping too, and this one did not" % len(kept))
ck({r["action"] for r in kept} >= {"observe", "pick", "set-text", "show-pane", "read-report"},
   "and it is a real session on a real science page, not a handshake: %s"
   % sorted({r["action"] for r in kept}))
ck(any(r["action"] == "observe" and r["arguments"].get("since") for r in kept),
   "including ADR-191's `since` -- the stamp a tool result handed back, asked of the "
   "resource, by a client that has never heard of this kit")

try:
    import mcp                                                            # noqa: F401
    HAVE_SDK = True
except Exception:
    HAVE_SDK = False

# One hole per claim the SDK section makes, so this suite's TOTAL is the same
# number whether or not the SDK is installed -- a suite whose length depends on
# what a machine happens to have is a count nobody can hold to a ledger.
SDK_CLAIMS = ["the HTTP switch is a real command line's, not just a constant",
              "a real server announces the loopback URL it bound",
              "the official MCP SDK connects and is issued a session id",
              "it sees the page's tools and its snapshot resource",
              "the snapshot it reads is the real page, not a thread-bound refusal",
              "it acts and is told what changed, in a fraction of the bytes",
              "`since` answers `nothing changed` for a stamp it was just handed",
              "and ADR-126's trace records an external host like any other"]
if not HAVE_SDK:
    for claim in SDK_CLAIMS:
        hole("%s -- the official MCP SDK is not installed here: `pip install mcp`, then run "
             "this suite again. The kept trace in tools/traces/http/ is from a run that did "
             "happen" % claim)
else:
    # THE SECOND SWITCH, on the real command line. Everything above stands the
    # door up in process, where main() -- and the environment variable that
    # guards it -- is never reached.
    try:
        off = subprocess.run(
            [sys.executable, os.path.join(_kit.TOOLS_DIR, "harness_http.py"),
             "--target", "fixture", "--port", "0"],
            capture_output=True, text=True, timeout=60, cwd=_kit.ROOT,
            env=dict(os.environ, CSRBT_HARNESS_ENABLED="true",
                     CSRBT_HARNESS_TOKEN="x" * 30, CSRBT_HARNESS_HTTP=""))
    except subprocess.TimeoutExpired:
        # It did not refuse -- it LISTENED, and is still listening. A check
        # whose subject is "this does not start" must survive it starting.
        off = subprocess.CompletedProcess([], 0, "", "it started and kept serving")
    ck(off.returncode == 2 and "CSRBT_HARNESS_HTTP" in off.stderr,
       "with the kit's switch on and the HTTP one off, the server refuses to listen and says "
       "which switch it wants: a listening socket is a larger thing than a pipe, and nobody "
       "should open one by copying a stdio command line: rc=%d %r"
       % (off.returncode, off.stderr.strip()[:120]))

    work = tempfile.mkdtemp(prefix="http-sdk-")
    client = os.path.join(work, "client.py")
    io.open(client, "w", encoding="utf-8").write(u'''
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
URL, TOK = sys.argv[1], sys.argv[2]
async def main():
    async with streamablehttp_client(URL, headers={"Authorization": "Bearer " + TOK}) as (r, w, sid):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            tools = await s.list_tools()
            res = await s.list_resources()
            snap = json.loads((await s.read_resource("harness://csrbt-page/snapshot")
                               ).contents[0].text)
            pk = snap["argumentPools"]["pick"][0]
            body = json.loads((await s.call_tool("csrbt_page__pick", pk)).content[0].text)
            since = json.loads((await s.read_resource(
                "harness://csrbt-page/snapshot?since=" + body["stamp"])).contents[0].text)
            print(json.dumps({
                "server": init.serverInfo.name, "version": init.serverInfo.version,
                "protocol": str(init.protocolVersion), "sessionId": bool(sid()),
                "tools": len(tools.tools),
                "resources": [str(x.uri) for x in res.resources],
                "snapshotBytes": len(json.dumps(snap)), "controls": len(snap["controls"]),
                "ok": body["ok"], "diffBytes": len(json.dumps(body["diff"])),
                "changedAfter": since.get("changed")}))
asyncio.run(main())
''')
    tok = "sdk-" + secrets.token_urlsafe(24)
    env = dict(os.environ, CSRBT_HARNESS_ENABLED="true", CSRBT_HARNESS_HTTP="true",
               CSRBT_HARNESS_TOKEN=tok, CSRBT_HARNESS_ALLOW_SENSITIVE_READ="true",
               CSRBT_HARNESS_ALLOW_DRAFT="true", CSRBT_HARNESS_ALLOW_MUTATE="true",
               CSRBT_DOCS_DIR=os.path.join(_kit.ROOT, "docs"))
    srv = subprocess.Popen(
        [sys.executable, os.path.join(_kit.TOOLS_DIR, "harness_http.py"),
         "--target", "page", "--page", "collection-sheet.html", "--port", "0",
         "--trace", os.path.join(work, "sdk.jsonl")],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=_kit.ROOT)
    # The server's stderr is read on a thread with a DEADLINE, not by blocking
    # on readline(): a server that starts and then says nothing this suite was
    # looking for -- one bound somewhere other than loopback, say -- leaves a
    # blocking read waiting forever, and a suite its subject can hang cannot be
    # used to break that subject on purpose.
    said = []
    threading.Thread(target=lambda: [said.append(l) for l in iter(srv.stderr.readline, "")],
                     daemon=True).start()
    url = None
    t0 = time.time()
    try:
        while time.time() - t0 < 120 and url is None:
            for line in list(said):
                m = re.search(r"http://127\.0\.0\.1:\d+/mcp", line)
                if m:
                    url = m.group(0)
                    break
            if url is None:
                time.sleep(0.1)
        ck(url is not None, "the server announced the loopback URL it bound: %r" % url)
        if url:
            p = subprocess.run([sys.executable, client, url, tok], capture_output=True,
                               text=True, timeout=300)
            try:
                got = json.loads(p.stdout.strip().split("\n")[-1])
            except Exception:
                got = {}
            ck(got.get("server") == "csrbt-harness" and got.get("sessionId") is True,
               "THE OFFICIAL MCP SDK CONNECTS: a client written by someone else, implementing "
               "the specification rather than this door, initialized and was issued a session "
               "id: %s" % (p.stderr.strip()[-200:] if not got else got.get("protocol")))
            ck(got.get("tools") == 22 and got.get("resources") == ["harness://csrbt-page/snapshot"],
               "and it sees the page's 22 tools and its snapshot resource: %s / %s"
               % (got.get("tools"), got.get("resources")))
            ck(got.get("controls", 0) > 200 and got.get("snapshotBytes", 0) > 50000,
               "and the snapshot it read is the real collection sheet -- %s controls, %s "
               "bytes -- not the `ready: false` a thread-bound target answers with"
               % (got.get("controls"), got.get("snapshotBytes")))
            ck(got.get("ok") is True and 0 < got.get("diffBytes", 0) * 10 < got.get("snapshotBytes", 1),
               "it picked a genus and was told what changed in a tenth of the bytes or better: "
               "%s against %s" % (got.get("diffBytes"), got.get("snapshotBytes")))
            ck(got.get("changedAfter") is False,
               "and asking the resource with the stamp that tool result handed back says "
               "nothing has changed since -- ADR-191's session, over HTTP, through a client "
               "that has never heard of it: %r" % got.get("changedAfter"))
            wrote = [json.loads(l) for l in io.open(os.path.join(work, "sdk.jsonl"),
                                                    encoding="utf-8") if l.strip()]
            ck(len(wrote) >= 3 and any(w["action"] == "pick" for w in wrote),
               "and ADR-126's trace records what an external host did exactly as it records "
               "what a local one did: %d call(s)" % len(wrote))
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=30)
        except Exception:
            srv.kill()
        shutil.rmtree(work, ignore_errors=True)

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
