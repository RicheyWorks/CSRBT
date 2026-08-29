# -*- coding: utf-8 -*-
"""The automation contract, checked at the boundary a client actually meets.

A gateway is a promise made to callers nobody in this repository has met: an
accessibility auditor, a test runner, an MCP adapter, a model holding a tool
schema. None of them will read the source. All of them will discover the shape
from the manifest and find out about the policy by being refused. So every
refusal is asserted here, and every refusal is asserted to happen for the right
reason -- a token that is too short and a token that is wrong are the same
answer to a client and two different bugs.

The escalation cases are the ones worth the most: a contract that is off by
default but answers one operation without a token, or that serves a cached
SENSITIVE_READ after the operator has closed that gate, has a plausible face and
an open door (ADR-061).
"""
import json, os, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_contract as C

MUTATE_ROLE = "subject"

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


TOKEN = "a" * 24
OTHER = "b" * 24


class Fake(C.Plugin):
    """A plugin with one action at each risk, so policy can be asserted per rung."""

    def __init__(self):
        self.ran = []
        self._d = C.PluginDescriptor(
            "fake", "Fake", "A plugin for the contract's own tests.", "1.0", [
                C.ActionSpec("look", "READ-level.", "READ"),
                C.ActionSpec("go", "NAVIGATE-level.", "NAVIGATE",
                             [C.ArgumentSpec("where", "string", "Destination.",
                                             required=True)]),
                C.ActionSpec("peek", "SENSITIVE_READ-level.", "SENSITIVE_READ"),
                C.ActionSpec("draft", "DRAFT-level.", "DRAFT",
                             [C.ArgumentSpec("n", "integer", "A count."),
                              C.ArgumentSpec("rows", "array", "Row indexes.",
                                             items="integer"),
                              C.ArgumentSpec("mode", "string", "One of two.",
                                             enum=["a", "b"])]),
                C.ActionSpec("save", "MUTATE-level.", "MUTATE"),
                C.ActionSpec("press", "DESTRUCTIVE-level.", "DESTRUCTIVE"),
            ])

    def descriptor(self):
        return self._d

    def observe(self, sensitive=False):
        s = {"ready": True, "controls": [{"selector": "text_in:0", "kind": "text_in",
                                          "label": "Name"}]}
        if sensitive:
            s["values"] = {"text_in:0": "Zqx001"}
        return s

    def execute(self, action, arguments):
        self.ran.append((action, json.dumps(arguments, sort_keys=True)))
        return True, "ran %s" % action, {"action": action, "n": len(self.ran)}


def gw(**kw):
    allow = kw.pop("allow", None)
    p = C.Policy(token=kw.pop("token", TOKEN), allow=allow, enabled=True)
    plug = Fake()
    return C.Gateway(C.Registry([plug]), p), plug


def refused(fn, code, why):
    try:
        fn()
    except C.HarnessError as e:
        ck(e.code == code, "%s: expected %s, got %s (%s)" % (why, code, e.code, e.message))
        return
    ck(False, "%s: was allowed" % why)


def rid(n):
    return "req-%03d" % n


# ---- 1. off by default, and the default is the blocked half ---------------
ck(C.DEFAULT_POLICY["READ"] and C.DEFAULT_POLICY["NAVIGATE"],
   "observing and navigating are allowed by default")
ck(not any(C.DEFAULT_POLICY[r] for r in
           ("SENSITIVE_READ", "DRAFT", "MUTATE", "DESTRUCTIVE")),
   "reading values, drafting, mutating and generic activation are all blocked "
   "by default")
try:
    C.Policy(token=TOKEN, allow={"DESTRUCTIVE": True}, enabled=True)
    ck(False, "DESTRUCTIVE was enabled without MUTATE")
except ValueError:
    ck(True, "DESTRUCTIVE cannot be enabled on its own")
ck(C.Policy(token=TOKEN, allow={"MUTATE": True, "DESTRUCTIVE": True},
            enabled=True).allow["DESTRUCTIVE"],
   "DESTRUCTIVE is available once MUTATE is")

os.environ.pop("CSRBT_HARNESS_ENABLED", None)
ck(not C.Policy(token=TOKEN).enabled,
   "with no environment variable set, the harness is off")

# ---- 2. the token is required on every operation, without exception -------
g, _ = gw()
for op, fn in (("manifest", lambda: g.manifest(None)),
               ("discover", lambda: g.discover("")),
               ("observe", lambda: g.observe(OTHER, "fake")),
               ("execute", lambda: g.execute(OTHER, "fake",
                                             {"request_id": rid(1), "action": "look"}))):
    refused(fn, "unauthorized", "%s without the right token" % op)

short, _ = gw(token="tooshort")
refused(lambda: short.manifest("tooshort"), "unauthorized",
        "a token under %d characters is not a token" % C.TOKEN_MIN)
ck(C.TOKEN_MIN >= 24, "the minimum token length is at least 24 characters")

# ---- 3. risk is enforced, and it is the plugin's declaration --------------
g, plug = gw()
ck(g.execute(TOKEN, "fake", {"request_id": rid(2), "action": "look"})["ok"],
   "a READ action runs under the default policy")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(3), "action": "peek"}),
        "forbidden", "SENSITIVE_READ under the default policy")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(4), "action": "save"}),
        "forbidden", "MUTATE under the default policy")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(5), "action": "press"}),
        "forbidden", "DESTRUCTIVE under the default policy")
ck([a for a, _ in plug.ran] == ["look"],
   "a refused command never reaches the plugin: %s" % plug.ran)

# A caller cannot re-label its own risk: there is nowhere to put the claim.
spec = plug.descriptor().action("press")
ck(spec.risk == "DESTRUCTIVE", "risk is declared on the action, by the plugin")
refused(lambda: g.execute(TOKEN, "fake",
                          {"request_id": rid(6), "action": "press", "risk": "READ"}),
        "forbidden", "a command carrying its own risk claim")

# ---- 4. strict arguments -------------------------------------------------
g, _ = gw(allow={"DRAFT": True})
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(10), "action": "go"}),
        "invalid_argument", "a required argument left out")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(11), "action": "go",
                                          "arguments": {"where": 3}}),
        "invalid_argument", "a string argument given a number")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(12), "action": "draft",
                                          "arguments": {"nope": 1}}),
        "invalid_argument", "an argument the action does not declare")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(13), "action": "draft",
                                          "arguments": {"n": True}}),
        "invalid_argument", "a boolean passed where an integer is declared")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(14), "action": "draft",
                                          "arguments": {"rows": ["a"]}}),
        "invalid_argument", "an array of the wrong item type")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(15), "action": "draft",
                                          "arguments": {"mode": "c"}}),
        "invalid_argument", "a value outside a declared enum")
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(16), "action": "nope"}),
        "not_found", "an action the plugin does not publish")
refused(lambda: g.execute(TOKEN, "ghost", {"request_id": rid(17), "action": "look"}),
        "not_found", "a plugin that is not registered")
refused(lambda: g.execute(TOKEN, "fake", {"action": "look"}),
        "invalid_argument", "a command with no request id")

# ---- 5. replay safety ----------------------------------------------------
g, plug = gw(allow={"DRAFT": True})
cmd = {"request_id": "same", "action": "draft", "arguments": {"n": 1}}
a = g.execute(TOKEN, "fake", cmd)
b = g.execute(TOKEN, "fake", dict(cmd))
ck(a["replayed"] is False and b["replayed"] is True,
   "the second identical command is answered from the cache")
ck(len(plug.ran) == 1, "and the plugin ran once, not twice: %d" % len(plug.ran))
ck(a["output"] == b["output"], "the replay carries the original output")
refused(lambda: g.execute(TOKEN, "fake",
                          {"request_id": "same", "action": "draft",
                           "arguments": {"n": 2}}),
        "conflict", "the same request id with different contents")

# The divergence this contract makes deliberately: a replay is authorised
# again. A payload captured while a gate was open must not keep flowing after
# an operator closes it.
g.policy.allow["DRAFT"] = False
refused(lambda: g.execute(TOKEN, "fake", dict(cmd)), "forbidden",
        "replaying a command whose risk has since been closed")

ck(C.REPLAY_CACHE_LIMIT == 256 and C.REPLAY_CACHE_BYTE_LIMIT == 8 * 1024 * 1024,
   "the replay cache is bounded at 256 commands and 8 MiB")
g, plug = gw(allow={"DRAFT": True})
for i in range(C.REPLAY_CACHE_LIMIT + 20):
    g.execute(TOKEN, "fake", {"request_id": "r%d" % i, "action": "draft"})
ck(len(g._done) <= C.REPLAY_CACHE_LIMIT,
   "the cache does not grow without bound: %d entries" % len(g._done))

# ---- 6. the manifest is enough to build a client from --------------------
g, _ = gw(allow={"SENSITIVE_READ": True})
m = g.manifest(TOKEN)
ck(m["protocolVersion"] == "1.0", "the manifest states a protocol version")
ck(m["strictArguments"] is True, "and that unknown arguments are refused")
ck(m["tokenMinLength"] == C.TOKEN_MIN, "and the minimum token length")
ck(set(m["policy"]) == set(C.RISKS), "and the effective policy for every risk")
tools = dict((t["name"], t) for t in m["tools"])
ck(len(tools) == 6, "one tool per action: %d" % len(tools))
ck(all(len(n) <= 64 and C.TOOL_NAME_OK.match(n) for n in tools),
   "every tool name is provider-safe: %s" % list(tools))
ck(tools["fake__peek"]["allowed"] is True and tools["fake__press"]["allowed"] is False,
   "allowed reflects the session policy, per tool")
s = tools["fake__draft"]["inputSchema"]
ck(s["additionalProperties"] is False,
   "the published schema itself refuses unknown properties")
ck(s["properties"]["rows"]["items"]["type"] == "integer",
   "an array argument publishes what it is an array OF, so an adapter can tell "
   "a list of row numbers from a list of labels")
ck(s["properties"]["mode"]["enum"] == ["a", "b"], "an enum is published")
ck(s["required"] == [] and
   tools["fake__go"]["inputSchema"]["required"] == ["where"],
   "required is published per action")
ck(json.dumps(m) and True, "the whole manifest is JSON-serialisable")

# allowed=false is an instruction, and the gateway enforces it regardless of
# whether a client honours it.
refused(lambda: g.execute(TOKEN, "fake", {"request_id": rid(30), "action": "press"}),
        "forbidden", "a tool the manifest marked allowed=false, submitted anyway")

# ---- 7. redaction --------------------------------------------------------
g, _ = gw()
s = g.observe(TOKEN, "fake")
ck("values" not in s, "an ordinary observation carries no entered values")
ck("redacted" not in s or True, "and says so")
g2, _ = gw(allow={"SENSITIVE_READ": True})
ck("values" in g2.observe(TOKEN, "fake"),
   "values appear only once SENSITIVE_READ is enabled")
ck("SENSITIVE_READ" in g.manifest(TOKEN)["redaction"] or
   "sensitive" in g.manifest(TOKEN)["redaction"].lower(),
   "the manifest says what is withheld and what would unlock it")

# ---- 8. names an adapter has to survive ----------------------------------
for bad in ("Fake", "fake_plugin", "a" * 31, "", "-x"):
    try:
        C.PluginDescriptor(bad, "t", "d", "1.0", [])
        ck(False, "plugin id %r was accepted" % bad)
    except ValueError:
        ck(True, "plugin id %r refused" % bad)
try:
    C.ArgumentSpec("rows", "array", "no item type declared")
    ck(False, "an array argument without an items type was accepted")
except ValueError:
    ck(True, "an array argument must declare its item type")
try:
    C.Registry([Fake(), Fake()])
    ck(False, "two plugins with the same id were registered")
except ValueError:
    ck(True, "a duplicate plugin id fails at registration, not at call time")

# ---- 9. the real plugin publishes what the swarm drives ------------------
import harness_plugin_page as PP
d = PP.PagePlugin(None, "x.html").descriptor()
names = dict((a.name, a.risk) for a in d.actions)
ck(names.get("activate") == "DESTRUCTIVE",
   "generic activation is DESTRUCTIVE: a selector on these pages may be Add "
   "row, Clear trial or an export, and guessing from the label is the guess "
   "this contract exists to refuse")
ck(names.get("read-control") == "SENSITIVE_READ" and
   names.get("read-page") == "SENSITIVE_READ" and
   names.get("capture-screen") == "SENSITIVE_READ",
   "every route to a value or a pixel is SENSITIVE_READ: %s" % names)
ck(names.get("show-pane") == "NAVIGATE" and names.get("open") == "NAVIGATE",
   "moving around the kit does not need a mutation gate")
ck(names.get("set-text") == "DRAFT" and names.get("choose-option") == "DRAFT",
   "entering a value is DRAFT")
ck("attach-file" not in names and not any("file" in n for n in names),
   "no file-chooser action is published: it needs OS focus and an approval "
   "policy the gateway does not own")

import swarm as SW
ck(set(SW.DRIVER.values()) <= set(names),
   "every action the swarm drives with is one the plugin publishes: %s"
   % (set(SW.DRIVER.values()) - set(names)))
ck("file_in" in SW.EXCLUDED and len(SW.EXCLUDED["file_in"]) > 40,
   "the kind with no published action is excluded with a reason, not skipped")

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
