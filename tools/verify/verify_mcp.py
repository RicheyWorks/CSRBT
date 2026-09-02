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
        ck(len(listed) == 20 and "csrbt_organism__put" in listed and "csrbt_organism__get" not in listed,
           "tools/list is the 20 the policy allows (MUTATE opened, SENSITIVE_READ not): %d" % len(listed))
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

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
