# -*- coding: utf-8 -*-
"""The second transport, checked at the boundary an AI actually meets (ADR-115).

MCP is what a model speaks. tools/harness_mcp.py maps it onto the gateway's
four operations and decides nothing -- and "decides nothing" is a claim this
suite makes falsifiable:

  A. the adapter names no target: nothing in the Server knows what stands
     behind the gateway, and both transports stand their targets up through
     the same shared builder
  B. in-process, over a fixture plugin: the handshake, tools/list omitting
     what the policy does not allow, risk as annotations, tools/call as
     execute with the JSON-RPC id as the request id (so a retry is a replay,
     not a second write), the target's no as isError rather than a protocol
     error, the client's bad call as -32602, an unknown method as -32601, a
     parse error as -32700, notifications answered with silence, snapshots
     as resources
  C. the real thing: the server as a child process over the organism, spoken
     to in JSON-RPC from here, with the policy doing its job through it

Run:  python3 tools/verify/verify_mcp.py
"""
import io, json, os, re, subprocess, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_contract as C
import harness_mcp as M

P = F = 0
unverified = []
TOKEN = "mcp-suite-" + "m" * 20


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- A. names no target ----------------------------------------------------
src = io.open(os.path.join(_kit.TOOLS_DIR, "harness_mcp.py"), encoding="utf-8").read()
body = src[src.index("class Server"):src.index("def main(")]
ck("organism" not in body and "page" not in body.replace("PagePlugin", ""),
   "the Server and serve() name no target")
ck("from harness_targets import" in src and
   "from harness_targets import" in io.open(os.path.join(_kit.TOOLS_DIR, "harness_stdio.py"),
                                            encoding="utf-8").read(),
   "both transports stand their targets up through the one shared builder")
ck(not re.search(r"^\s*(import|from)\s+(mcp|fastmcp|jsonrpc)", src, re.M),
   "no SDK: the protocol is small enough that a dependency would hide the boundary")
ck(all(k in src for k in ("initialize", "tools/list", "tools/call", "resources/read", "ping")),
   "the five methods an MCP host uses are mapped")


# ---- B. in-process over a fixture ------------------------------------------
class Fake(C.Plugin):
    def __init__(self):
        self.ran = []
        self._d = C.PluginDescriptor("fake", "Fake", "fixture", "1.0", [
            C.ActionSpec("look", "read something", "READ", []),
            C.ActionSpec("peek", "read a value", "SENSITIVE_READ", []),
            C.ActionSpec("poke", "change a record", "MUTATE",
                         [C.ArgumentSpec("n", "integer", "how hard", required=True, minimum=0, maximum=9)]),
            C.ActionSpec("nope", "always says no", "NAVIGATE", []),
            C.ActionSpec("look-twice", "read something, hyphenated", "READ", []),
        ])

    def descriptor(self):
        return self._d

    def observe(self, sensitive=False):
        return {"ready": True, "sensitive": sensitive, "ran": len(self.ran)}

    def execute(self, action, arguments):
        self.ran.append((action, dict(arguments)))
        if action == "nope":
            return False, "no", {}
        return True, "did %s" % action, {"n": arguments.get("n")}


fake = Fake()
gw = C.Gateway(C.Registry([fake]), C.Policy(token=TOKEN, enabled=True, allow={"MUTATE": True}))
srv = M.Server(gw, TOKEN)


def rpc(method, params=None, mid=1):
    msg = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        msg["params"] = params
    return srv.handle(msg)


r = rpc("initialize", {"protocolVersion": M.PROTOCOL, "capabilities": {}, "clientInfo": {"name": "suite"}})
ck(r["result"]["protocolVersion"] == M.PROTOCOL and r["result"]["capabilities"]["tools"] is not None and
   "fake" in r["result"]["instructions"], "initialize answers with the protocol, capabilities and the plugins")
ck(srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None,
   "a notification is accepted with silence")
ck(rpc("ping")["result"] == {}, "ping")
tools = rpc("tools/list")["result"]["tools"]
names = [t["name"] for t in tools]
ck(names == ["fake__look", "fake__poke", "fake__nope", "fake__look_twice"],
   "tools/list lists exactly what the policy allows, in manifest order: %s" % names)
ck(all(t["annotations"]["readOnlyHint"] is (t["name"] != "fake__poke") for t in tools) and
   all(t["annotations"]["destructiveHint"] is (t["name"] == "fake__poke") for t in tools),
   "risk is published as MCP annotations: read-only unless it changes a record")
ck(all(t["description"].startswith("[") for t in tools) and tools[1]["inputSchema"]["properties"]["n"]["maximum"] == 9,
   "the description names the risk and the schema carries the bounds")
ck([t["_meta"] for t in tools] == [{"pluginId": "fake", "action": a, "risk": r_}
                                    for a, r_ in (("look", "READ"), ("poke", "MUTATE"), ("nope", "NAVIGATE"),
                                                  ("look-twice", "READ"))],
   "every tool carries _meta with the contract's own plugin id, action and risk (ADR-121), so a client "
   "never guesses an action back out of a slug -- look-twice, not look_twice: %s" % [t.get("_meta") for t in tools])
r = rpc("tools/call", {"name": "fake__poke", "arguments": {"n": 3}}, mid=7)
body = json.loads(r["result"]["content"][0]["text"])
ck(r["result"]["isError"] is False and body["ok"] and body["output"]["n"] == 3 and not body["replayed"],
   "tools/call executes and returns the output as text content")
ck(isinstance(body.get("ms"), int) and isinstance(body.get("snapshotMs"), int) and body.get("requestId") == "mcp-7",
   "the body prices the action and the snapshot separately and names the request id the gateway recorded: %s"
   % {k: body.get(k) for k in ("ms", "snapshotMs", "requestId")})
ck(fake.ran[-1] == ("poke", {"n": 3}), "and the plugin ran it")
n_ran = len(fake.ran)
r2 = rpc("tools/call", {"name": "fake__poke", "arguments": {"n": 3}}, mid=7)
ck(json.loads(r2["result"]["content"][0]["text"])["replayed"] is True and len(fake.ran) == n_ran,
   "the same JSON-RPC id is a replay: served from the cache, the plugin did not run again")
r3 = rpc("tools/call", {"name": "fake__poke", "arguments": {"n": 4}}, mid=7)
ck("error" in r3 and r3["error"]["code"] == M.INVALID_PARAMS and "conflict" in r3["error"]["message"],
   "the same id with a different body is a conflict, reported as the client's error")
r = rpc("tools/call", {"name": "fake__nope", "arguments": {}}, mid=8)
ck(r["result"]["isError"] is True and json.loads(r["result"]["content"][0]["text"])["ok"] is False,
   "a target that ran and said no is isError, not a protocol error")
r = rpc("tools/call", {"name": "fake__poke", "arguments": {"n": 99}}, mid=9)
ck("error" in r and r["error"]["code"] == M.INVALID_PARAMS and "invalid_argument" in r["error"]["message"],
   "an argument outside its bound is -32602 with the gateway's code in the message")
r = rpc("tools/call", {"name": "fake__peek", "arguments": {}}, mid=10)
ck("error" in r and r["error"]["code"] == M.INVALID_PARAMS and "not_found" in r["error"]["message"] and
   not any(a == "peek" for a, _ in fake.ran),
   "a tool the policy hid is not callable by name, and never reached the plugin")
r = rpc("tools/call", {"name": "fake__look"}, mid=None)
ck("error" in r and r["error"]["code"] == M.INVALID_PARAMS,
   "a call with no id has no request id and is refused rather than run unreplayably")
ck(rpc("prompts/list")["error"]["code"] == M.METHOD_NOT_FOUND, "an unknown method is -32601")
ck(srv.handle({"id": 1, "method": "ping"})["error"]["code"] == M.INVALID_REQUEST,
   "a message without jsonrpc 2.0 is -32600")
res = rpc("resources/list")["result"]["resources"]
ck(res == [{"uri": "harness://fake/snapshot", "name": "fake snapshot",
            "description": "The current observation of Fake (redacted unless SENSITIVE_READ).",
            "mimeType": "application/json"}], "a snapshot is a resource: %s" % res)
r = rpc("resources/read", {"uri": "harness://fake/snapshot"})
snap = json.loads(r["result"]["contents"][0]["text"])
ck(snap["ready"] and snap["sensitive"] is False, "resources/read is observe, redacted under this policy")
ck(rpc("resources/read", {"uri": "harness://nope/snapshot"})["error"]["code"] == M.INVALID_PARAMS and
   rpc("resources/read", {"uri": "file:///etc/passwd"})["error"]["code"] == M.INVALID_PARAMS,
   "an unknown plugin or a foreign URI is refused")
out = io.StringIO()
M.serve(srv, io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\nnot json\n\n{"jsonrpc":"2.0","method":"notifications/x"}\n'), out)
lines = [json.loads(l) for l in out.getvalue().strip().split("\n")]
ck(len(lines) == 2 and lines[0]["result"] == {} and lines[1]["error"]["code"] == M.PARSE_ERROR,
   "serve(): one line per request, a parse error for junk, silence for a notification")

# ---- C. the real thing -----------------------------------------------------
cp_file = os.path.join(os.environ.get("CSRBT_WHOLEHOG") or os.path.join(_kit.ROOT, "..", "WholeHog"),
                       "build", "harness", "classpath.txt")
if not os.path.isfile(cp_file):
    unverified.append("C  the MCP server as a child over the organism -- WholeHog is not built")
else:
    env = dict(os.environ)
    env.update({"CSRBT_HARNESS_ENABLED": "true", "CSRBT_HARNESS_TOKEN": TOKEN,
                "CSRBT_HARNESS_ALLOW_MUTATE": "true"})
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": M.PROTOCOL, "capabilities": {}, "clientInfo": {"name": "suite"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "csrbt_organism__put", "arguments": {"key": 5, "attr": 1, "start": 1, "end": 2, "via": "wire"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "csrbt_organism__put", "arguments": {"key": 5, "attr": 1, "start": 1, "end": 2, "via": "wire"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "csrbt_organism__get", "arguments": {"key": 5}}},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "harness://csrbt-organism/snapshot"}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "csrbt_organism__report", "arguments": {}}},
    ]
    p = subprocess.run([sys.executable, os.path.join(_kit.TOOLS_DIR, "harness_mcp.py"),
                        "--target", "organism", "--seed", "9"],
                       input="\n".join(json.dumps(m) for m in msgs) + "\n",
                       capture_output=True, text=True, env=env, timeout=180)
    outs = [json.loads(l) for l in p.stdout.strip().split("\n") if l.strip()]
    ck(p.returncode == 0 and len(outs) == 7,
       "the server answered seven requests and one notification with silence, then exited "
       "clean: rc=%d n=%d %s" % (p.returncode, len(outs), p.stderr.strip()[-160:]))
    if len(outs) == 7:
        by = dict((o["id"], o) for o in outs)
        ck("csrbt-organism" in by[1]["result"]["instructions"], "initialize names the organism")
        listed = [t["name"] for t in by[2]["result"]["tools"]]
        ck(len(listed) == 21 and "csrbt_organism__put" in listed and "csrbt_organism__get" not in listed,
           "tools/list is the 21 the policy allows (MUTATE opened, SENSITIVE_READ not): %d" % len(listed))
        meta = dict((t["name"], t.get("_meta") or {}) for t in by[2]["result"]["tools"])
        ck(meta.get("csrbt_organism__retain_newest") == {"pluginId": "csrbt-organism", "action": "retain-newest",
                                                         "risk": "MUTATE"},
           "a tool's _meta carries the hyphenated action and plugin id the slug cannot give back: %s"
           % meta.get("csrbt_organism__retain_newest"))
        first = json.loads(outs[2]["result"]["content"][0]["text"])
        again = json.loads(outs[3]["result"]["content"][0]["text"])
        ck(first["ok"] and not first["replayed"] and again["replayed"] is True,
           "a wire put over MCP lands, and the retry with the same id is a replay")
        ck("error" in by[4] and by[4]["error"]["code"] == M.INVALID_PARAMS,
           "get is not listed for this session and cannot be called by name")
        snap = json.loads(by[5]["result"]["contents"][0]["text"])
        ck(snap["size"] == 1 and "sample" not in snap and snap["wire"]["puts"] == 1,
           "the snapshot resource shows one key, one wire put, and no record")
        ck(by[6]["result"]["isError"] is False and "rub" in json.loads(by[6]["result"]["content"][0]["text"])["output"]["report"],
           "the physical reads over MCP")

# ---- D. listChanged, with a consumer (ADR-137) ------------------------------
#
# ADR-115 declared listChanged:false and ADR-121 held it there, for the honest
# reason that nothing could change a list. This section is what makes the
# capability worth declaring: the registry can move, the gateway hears it, the
# server drops what it cached and says so, and a client that caches is the one
# the notification is for.
import harness_plugin_session as SP


class _Made(C.Plugin):
    """A target a fake stand_up hands back: cheap, and it records its close."""

    def __init__(self, pid="csrbt-made"):
        self.closed = 0
        self._d = C.PluginDescriptor(pid, "Made", "attached by the session plugin", "1.0",
                                     [C.ActionSpec("hello", "say hello", "READ", [])])

    def descriptor(self):
        return self._d

    def observe(self, sensitive=False):
        return {"ready": True}

    def execute(self, action, arguments):
        return True, "hello", {"said": "hello"}

    def close(self):
        self.closed += 1


made = {}


def fake_stand_up(target, page=None, seed=None, headed=None, err=None):
    if target == "organism":
        raise SystemExit(2)                       # a target that cannot come up
    m = _Made("csrbt-" + target)
    made[target] = m
    return [m], [m.close]


def session_server(extra=(), allow=None):
    reg = C.Registry(list(extra))
    sp = SP.SessionPlugin(reg, stand_up=fake_stand_up)
    reg.register(sp, quiet=True)
    pol = C.Policy(token=TOKEN, enabled=True,
                   allow=allow or {"NAVIGATE": True, "SENSITIVE_READ": True})
    gw = C.Gateway(reg, pol)
    return reg, sp, gw, M.Server(gw, TOKEN)


def call(srv, mid, name, args=None):
    return srv.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                       "params": {"name": name, "arguments": args or {}}})


# the declaration is honest in both directions
plain = M.Server(C.Gateway(C.Registry([Fake()]), C.Policy(token=TOKEN, enabled=True)), TOKEN)
caps = plain.initialize()["capabilities"]
ck(caps["tools"]["listChanged"] is False and caps["resources"]["listChanged"] is False,
   "a session nothing can change declares listChanged FALSE, as ADR-115 did and was right to: %s" % caps)
reg, sp, gw, srv = session_server()
caps = srv.initialize()["capabilities"]
ck(caps["tools"]["listChanged"] is True and caps["resources"]["listChanged"] is True,
   "a session that serves csrbt-session declares listChanged TRUE, because now something can: %s" % caps)
ck(plain.drain() == [] and srv.drain() == [], "and neither has said anything yet")

# the round trip
before = set(t["name"] for t in srv.tools())
call(srv, 6, "csrbt_session__targets")                                 # fills the server's cache
ck(srv._tools is not None, "the server caches the name map a call needs")
r = call(srv, 7, "csrbt_session__attach", {"target": "fixture"})
ck(r["result"]["isError"] is False and "csrbt-fixture" in json.loads(r["result"]["content"][0]["text"])["output"]["plugins"],
   "attach stands a target up and puts it in the session")
ck(srv._tools is None, "and the server DROPS its own name map -- a notification sent over a stale cache "
                       "is a courtesy, clearing it is the fix")
notes = [n["method"] for n in srv.drain()]
ck(notes == ["notifications/tools/list_changed", "notifications/resources/list_changed"],
   "a plugin arriving changes both lists, and the tool list is announced first: %s" % notes)
after = set(t["name"] for t in srv.tools())
ck(after - before == {"csrbt_fixture__hello"} and len(srv.resources()) == 2,
   "the tool arrived and so did its snapshot resource: %s" % sorted(after - before))
ck(call(srv, 8, "csrbt_fixture__hello")["result"]["isError"] is False,
   "and the new tool is callable by name on the same session")

# the refusals
for i, (args, head, why) in enumerate((({"target": "nope"}, "invalid_argument", "a target that is not a target"),
                                       ({"target": "fixture"}, "conflict", "a target already attached"),
                                       ({"target": "organism"}, "failed", "a target that cannot come up"))):
    e = call(srv, 20 + i, "csrbt_session__attach", args)
    msg = e.get("error", {}).get("message", "")
    ck("error" in e and msg.startswith(head + ":") and e["error"]["code"] == M.CODE[head],
       "attach refuses %s, as %s: %s" % (why, head, msg[:70]))
e = call(srv, 40, "csrbt_session__detach", {"target": "lab"})
ck("error" in e and "not attached" in e["error"]["message"], "detach refuses a target this session did not attach")
ck(srv.drain() == [], "and a refused attach or detach announces nothing")

# detach
r = call(srv, 9, "csrbt_session__detach", {"target": "fixture"})
ck(r["result"]["isError"] is False and made["fixture"].closed == 1,
   "detach takes the target out AND closes it: closed=%d" % made["fixture"].closed)
notes = [n["method"] for n in srv.drain()]
ck(notes == ["notifications/tools/list_changed", "notifications/resources/list_changed"],
   "and says both lists changed again: %s" % notes)
ck(set(t["name"] for t in srv.tools()) == before and len(srv.resources()) == 1,
   "the list is back to what it was, and the snapshot resource is gone")
e = call(srv, 10, "csrbt_fixture__hello")
ck("error" in e and e["error"]["code"] == M.INVALID_PARAMS,
   "a detached target's tool is not listed and cannot be called")

# a re-attached target has done nothing, whatever the cache remembers
_, _, gw2, srv2 = session_server()
call(srv2, 11, "csrbt_session__attach", {"target": "fixture"})
one = json.loads(call(srv2, 77, "csrbt_fixture__hello")["result"]["content"][0]["text"])
call(srv2, 12, "csrbt_session__detach", {"target": "fixture"})
call(srv2, 13, "csrbt_session__attach", {"target": "fixture"})
two = json.loads(call(srv2, 77, "csrbt_fixture__hello")["result"]["content"][0]["text"])
ck(one["replayed"] is False and two["replayed"] is False,
   "a target detached and attached again is a NEW target: the replay cache does not answer for a machine "
   "that no longer exists (%s, %s)" % (one["replayed"], two["replayed"]))

# the registry's own contract
reg3 = C.Registry([Fake()])
heard = []
reg3.watch(lambda kind: heard.append(kind))
reg3.watch(lambda kind: (_ for _ in ()).throw(RuntimeError("a watcher that raises")))
f2 = Fake()
f2._d = C.PluginDescriptor("fake2", "Fake2", "another", "1.0", [C.ActionSpec("look", "l", "READ", [])])
try:
    reg3.register(f2)
    ck(heard == ["plugins"], "register after construction announces the change: %s" % heard)
except Exception as e:
    ck(False, "a watcher that raises took the registry down with it: %s" % e)
ck(reg3.retire("fake2") is f2 and heard == ["plugins", "plugins"] and len(reg3.descriptors()) == 1,
   "retire hands the plugin back and announces: %s" % heard)
reg4 = C.Registry([])
heard4 = []
reg4.watch(heard4.append)
reg4.register(Fake(), quiet=True)
csrc = io.open(os.path.join(_kit.TOOLS_DIR, "harness_contract.py"), encoding="utf-8").read()
ck(heard4 == [] and len(reg4.descriptors()) == 1
   and "self.register(p, quiet=True)          # construction is not a change" in csrc,
   "construction is not a change: quiet=True puts a plugin in and announces nothing, and that is how a "
   "registry is BUILT from its list -- a session that opens by announcing a change it did not make teaches "
   "every client to ignore the notice: %s" % heard4)
ck(C.Gateway(C.Registry([Fake()]), C.Policy(token=TOKEN, enabled=True)).changes == 0,
   "and a gateway over a freshly built registry has counted no change")
try:
    reg3.register(Fake())
    ck(False, "the registry accepted a duplicate plugin id")
except ValueError:
    ck(True, "")
try:
    reg3.retire("gone")
    ck(False, "the registry retired a plugin it does not have")
except C.HarnessError as e:
    ck(e.code == "not_found", "retiring an unknown id is not_found, not a crash: %s" % e.code)

# serve(): the notice goes out BEFORE the answer
_, _, _, srv4 = session_server()
out4 = io.StringIO()
M.serve(srv4, io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                      "params": {"name": "csrbt_session__attach",
                                                 "arguments": {"target": "fixture"}}}) + "\n"), out4)
wrote = [json.loads(l) for l in out4.getvalue().strip().split("\n")]
ck([w.get("method") or "response" for w in wrote] ==
   ["notifications/tools/list_changed", "notifications/resources/list_changed", "response"],
   "serve() writes the notifications first and the response last, so no client ever holds the answer to "
   "attach while the notice is still behind it in the pipe: %s"
   % [w.get("method") or "response" for w in wrote])

# the consumer: the robot's wire drops what it cached, on hearing it
sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_walk as W


class _NoProc(W.McpWire):
    def __init__(self):
        self._tools = {("a", "b"): "x"}
        self._plugins = ["a"]
        self.notified = []
        self.list_changed = 0


w = _NoProc()
w.on_notification("notifications/tools/list_changed")
ck(w._tools is None and w.list_changed == 1 and w._plugins == ["a"],
   "the robot's wire drops its cached tool-name map when the server says the list changed")
w.on_notification("notifications/resources/list_changed")
ck(w._plugins is None and w.notified == ["notifications/tools/list_changed",
                                         "notifications/resources/list_changed"],
   "and its cached plugin list on the other notice, keeping both on the record")
wsrc = io.open(os.path.join(_kit.TOOLS_DIR, "harness_walk.py"), encoding="utf-8").read()
ck('if "id" not in msg and "method" in msg:' in wsrc and "while True:" in wsrc[wsrc.index("def rpc("):wsrc.index("def on_notification(")],
   "and it reads until its id comes back rather than taking the next line for its answer")


# ---- E. attaching a real target over a real child ---------------------------
env = dict(os.environ)
env.update({"CSRBT_HARNESS_ENABLED": "true", "CSRBT_HARNESS_TOKEN": TOKEN,
            "CSRBT_HARNESS_ALLOW_NAVIGATE": "true", "CSRBT_HARNESS_ALLOW_DRAFT": "true",
            "CSRBT_HARNESS_ALLOW_MUTATE": "true", "CSRBT_HARNESS_ALLOW_SENSITIVE_READ": "true"})
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": M.PROTOCOL, "capabilities": {}, "clientInfo": {"name": "suite"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "csrbt_session__attach", "arguments": {"target": "page", "page": "collection-sheet.html"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "csrbt_page__read_page", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
     "params": {"name": "csrbt_session__detach", "arguments": {"target": "page"}}},
    {"jsonrpc": "2.0", "id": 8, "method": "tools/list"},
]
p = subprocess.run([sys.executable, os.path.join(_kit.TOOLS_DIR, "harness_mcp.py"),
                    "--target", "fixture", "--attachable"],
                   input="\n".join(json.dumps(m) for m in msgs) + "\n",
                   capture_output=True, text=True, env=env, timeout=240)
outs = [json.loads(l) for l in p.stdout.strip().split("\n") if l.strip()]
notes = [o["method"] for o in outs if "id" not in o]
res = dict((o["id"], o) for o in outs if "id" in o)
ck(p.returncode == 0 and len(res) == 8 and len(notes) == 4,
   "the child answered eight requests and volunteered four notifications: rc=%d res=%d notes=%d %s"
   % (p.returncode, len(res), len(notes), p.stderr.strip()[-160:]))
if len(res) == 8:
    ck(res[1]["result"]["capabilities"]["tools"]["listChanged"] is True,
       "--attachable declares listChanged")
    n0 = [t["name"] for t in res[2]["result"]["tools"]]
    n1 = [t["name"] for t in res[4]["result"]["tools"]]
    ck("csrbt_page__read_page" not in n0 and "csrbt_page__read_page" in n1 and len(n1) - len(n0) == 20,
       "a real browser target attached mid-session brings its tools with it -- 20 of the page's 21, the "
       "DESTRUCTIVE one omitted because this session never opened that gate: %d -> %d" % (len(n0), len(n1)))
    uris = [x["uri"] for x in res[5]["result"]["resources"]]
    ck("harness://csrbt-page/snapshot" in uris, "and its snapshot is a resource: %s" % uris)
    ck(res[6]["result"]["isError"] is False,
       "and the page it opened is really there: read-page answers over the same session")
    n2 = [t["name"] for t in res[8]["result"]["tools"]]
    ck(n2 == n0, "detached, the list is exactly what it was: %d back to %d" % (len(n1), len(n2)))
    order = [o.get("method", "r%s" % o.get("id")) for o in outs]
    ck(order.index("notifications/tools/list_changed") < order.index("r3"),
       "and every notice was written before the response that caused it: %s" % order)

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
