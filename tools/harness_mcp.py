# -*- coding: utf-8 -*-
"""The second transport: MCP over stdio (ADR-115).

docs/AUTOMATION-HARNESS.md has said since ADR-102 that a client can connect
an MCP server "without changing the plugin, because a transport maps exactly
four operations and decides nothing." For thirteen ADRs there was one
transport. This is the second, and it is the one an AI actually speaks: the
Model Context Protocol, JSON-RPC 2.0, one message per line on stdin/stdout.
No SDK -- the protocol is small and the point of this file is to show that
the boundary is in the right place, which a dependency would obscure.

The mapping, and nothing else:

    initialize                -> discover  (serverInfo names the plugins)
    tools/list                -> manifest  (only tools the policy ALLOWS are
                                            listed: allowed:false is an
                                            instruction to omit, not a hint)
    tools/call                -> execute   (the JSON-RPC id IS the request_id,
                                            so a client that retries a call
                                            with the same id gets the replay,
                                            not a second write)
    resources/list, /read     -> observe   (a snapshot is a resource,
                                            harness://<plugin>/snapshot)
    ping                      -> {}

Each tool also carries `_meta` -- pluginId, action, risk -- the contract's own
names for it (ADR-121). A tool name is a provider-safe slug, and a client that
scopes argument pools by action ("set-text.selector") must not have to guess
"set-text" back out of "csrbt_page__set_text"; a `_meta` the spec reserves for
exactly this is where those names ride. tools/call's body carries the price of
the action (ms) and of the snapshot the gateway took after it (snapshotMs), and
the request id the gateway recorded (ADR-120).

Risk becomes MCP tool annotations, so a host can show an operator what it is
being asked for: READ, NAVIGATE and SENSITIVE_READ are readOnlyHint (the
last with the risk named in the description); MUTATE and DESTRUCTIVE are
destructiveHint. The gateway enforces policy regardless of what a host does
with the hints.

Refusals: a HarnessError that is the CLIENT's (invalid_argument, not_found,
conflict) is a JSON-RPC error with code -32602; forbidden and unauthorized
are -32001; unavailable is -32002; a target that ran and said no is a normal
result with isError:true, the way MCP tells a model "this happened and it
was a no" rather than "you asked wrongly".

OFF BY DEFAULT, like stdio: CSRBT_HARNESS_ENABLED and a token of 24+ chars in
the environment of the server process. The MCP client never sees the token;
the operator who launched the server holds it, which is where MCP puts
authentication for a stdio server anyway.

    CSRBT_HARNESS_ENABLED=true CSRBT_HARNESS_TOKEN=<24+ chars> \\
    CSRBT_HARNESS_ALLOW_MUTATE=true \\
    python3 tools/harness_mcp.py --target organism
"""
import argparse, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness_contract import Gateway, HarnessError, Registry
from harness_targets import require_policy, stand_up, tear_down

PROTOCOL = "2025-03-26"
SERVER = {"name": "csrbt-harness", "version": "1.3"}
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602
POLICY_REFUSED, TARGET_UNAVAILABLE = -32001, -32002
CODE = {"invalid_argument": INVALID_PARAMS, "not_found": INVALID_PARAMS, "conflict": INVALID_PARAMS,
        "forbidden": POLICY_REFUSED, "unauthorized": POLICY_REFUSED,
        "unavailable": TARGET_UNAVAILABLE, "failed": TARGET_UNAVAILABLE}


def annotations(risk):
    ro = risk in ("READ", "NAVIGATE", "SENSITIVE_READ")
    return {"title": risk, "readOnlyHint": ro, "destructiveHint": not ro,
            "idempotentHint": risk in ("READ", "SENSITIVE_READ"), "openWorldHint": False}


class Server(object):
    """The entire adapter. Holds the gateway and the token; knows no target."""

    def __init__(self, gateway, token):
        self.gw, self.token = gateway, token
        self._tools = None            # name -> (pluginId, action)

    # -- one request, one response (or nothing, for a notification) ---------
    def handle(self, msg):
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
            return self._error(msg.get("id") if isinstance(msg, dict) else None,
                               INVALID_REQUEST, "not a JSON-RPC 2.0 request")
        method, params, mid = msg["method"], msg.get("params") or {}, msg.get("id")
        if method.startswith("notifications/"):
            return None                                   # accepted, silently
        try:
            if method == "initialize":
                result = self.initialize()
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": self.tools()}
            elif method == "tools/call":
                result = self.call(mid, params)
            elif method == "resources/list":
                result = {"resources": self.resources()}
            elif method == "resources/read":
                result = self.read(params)
            else:
                return self._error(mid, METHOD_NOT_FOUND, "unknown method %r" % method)
        except HarnessError as e:
            return self._error(mid, CODE.get(e.code, TARGET_UNAVAILABLE),
                               "%s: %s" % (e.code, e.message))
        except KeyError as e:
            return self._error(mid, INVALID_PARAMS, "missing %s" % e)
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    # -- the four operations ------------------------------------------------
    def initialize(self):
        plugins = self.gw.discover(self.token)
        return {"protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}},
                "serverInfo": SERVER,
                "instructions": "CSRBT automation harness over %s. Tools not listed are not "
                                "allowed for this session. A snapshot of each target is a "
                                "resource; entered values appear only when SENSITIVE_READ is "
                                "enabled. Retrying a call with the same request id replays it."
                                % ", ".join(p["id"] for p in plugins)}

    def tools(self):
        man = self.gw.manifest(self.token)
        self._tools = {}
        out = []
        for t in man["tools"]:
            if not t["allowed"]:
                continue
            self._tools[t["name"]] = (t["pluginId"], t["action"])
            out.append({"name": t["name"],
                        "description": "[%s] %s" % (t["risk"], t["description"]),
                        "inputSchema": t["inputSchema"],
                        "annotations": annotations(t["risk"]),
                        "_meta": {"pluginId": t["pluginId"], "action": t["action"], "risk": t["risk"]}})
        return out

    def call(self, mid, params):
        name = params["name"]
        if self._tools is None:
            self.tools()
        if name not in self._tools:
            # Not listed for this session -- unknown or not allowed; the gateway
            # would refuse it anyway, but a host should hear it as a bad name.
            raise HarnessError("not_found", "no tool %r is listed for this session" % name)
        plugin_id, action = self._tools[name]
        rid = "mcp-%s" % mid if mid is not None else None
        r = self.gw.execute(self.token, plugin_id, {
            "request_id": rid, "action": action, "arguments": params.get("arguments") or {}})
        body = {"ok": r["ok"], "message": r["message"], "output": r["output"],
                "replayed": r["replayed"], "risk": r["risk"], "ms": r["ms"],
                "snapshotMs": r.get("snapshotMs"), "requestId": r["requestId"]}
        return {"content": [{"type": "text", "text": json.dumps(body, default=str)}],
                "isError": not r["ok"]}

    def resources(self):
        return [{"uri": "harness://%s/snapshot" % p["id"], "name": "%s snapshot" % p["id"],
                 "description": "The current observation of %s (redacted unless SENSITIVE_READ)."
                                % p["title"], "mimeType": "application/json"}
                for p in self.gw.discover(self.token)]

    def read(self, params):
        uri = params["uri"]
        if not (uri.startswith("harness://") and uri.endswith("/snapshot")):
            raise HarnessError("not_found", "no resource %r" % uri)
        plugin_id = uri[len("harness://"):-len("/snapshot")]
        snap = self.gw.observe(self.token, plugin_id)
        return {"contents": [{"uri": uri, "mimeType": "application/json",
                              "text": json.dumps(snap, default=str)}]}

    @staticmethod
    def _error(mid, code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(server, stdin, stdout):
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError as e:
            _w(stdout, server._error(None, PARSE_ERROR, "parse error: %s" % str(e)[:80]))
            continue
        resp = server.handle(msg)
        if resp is not None:
            _w(stdout, resp)
    return 0


def _w(out, obj):
    out.write(json.dumps(obj, default=str) + "\n")
    out.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="ecology.html")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--target", default="page", choices=["page", "organism", "lab", "both", "all", "fixture"])
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    policy = require_policy()
    if policy is None:
        return 2
    plugins, closers = stand_up(a.target, page=a.page, seed=a.seed, headed=a.headed)
    gw = Gateway(Registry(plugins), policy)
    sys.stderr.write("harness ready on MCP: %s, policy %s\n"
                     % (", ".join(p.descriptor().id for p in plugins),
                        ",".join(k for k, v in policy.allow.items() if v)))
    try:
        return serve(Server(gw, policy.token), sys.stdin, sys.stdout)
    finally:
        tear_down(closers)


if __name__ == "__main__":
    sys.exit(main())
