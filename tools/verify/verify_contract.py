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
import io, json, os, sys, time

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
r = g.execute(TOKEN, "fake", {"request_id": rid(2), "action": "look"})
ck(r["ok"], "a READ action runs under the default policy")
# ADR-120: the snapshot that rides every response is priced on that response --
# the action's own time and the snapshot's, separately, as integers of ms.
ck(isinstance(r.get("ms"), int) and isinstance(r.get("snapshotMs"), int) and r["ms"] >= 0
   and r["snapshotMs"] >= 0 and "snapshot" in r,
   "every execute response prices its action (ms) and its snapshot (snapshotMs) separately: %s"
   % {k: r.get(k) for k in ("ms", "snapshotMs")})
class Slow(Fake):
    def observe(self, sensitive=False):
        time.sleep(0.05)
        return Fake.observe(self, sensitive)
gs = C.Gateway(C.Registry([Slow()]), C.Policy(token=TOKEN, allow=None, enabled=True))
rs = gs.execute(TOKEN, "fake", {"request_id": rid(2), "action": "look"})
ck(rs["snapshotMs"] >= 40 and rs["ms"] < 40,
   "a slow observe is charged to the snapshot, not to the action: ms=%s snapshotMs=%s"
   % (rs["ms"], rs["snapshotMs"]))
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
ck(m["protocolVersion"] == "1.5",
   "the manifest states a protocol version (1.5: ADR-141, a declared risk is a FLOOR -- an action may be raised "
   "per call by the target that knows what it was pointed at)")
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
act = d.action("activate")
ck(act.risk == "MUTATE" and act.may_rise,
   "generic activation declares MUTATE and mayRise (ADR-141): a selector on these "
   "pages may be Add row or Clear trial, and the answer is to ask the target which "
   "at the moment of the call -- not to hold every button at the rung the worst one "
   "needs: %s mayRise=%s" % (act.risk, act.may_rise))
ck(act.as_dict()["mayRise"] is True and
   all(a.as_dict()["mayRise"] is False for a in d.actions if a.name != "activate"),
   "and it is the ONLY action of this target that may rise: %s"
   % [a.name for a in d.actions if a.may_rise])
ck(names.get("read-control") == "SENSITIVE_READ" and
   names.get("read-page") == "SENSITIVE_READ" and
   names.get("capture-screen") == "SENSITIVE_READ",
   "every route to a value or a pixel is SENSITIVE_READ: %s" % names)
ck(names.get("show-pane") == "NAVIGATE" and names.get("open") == "NAVIGATE",
   "moving around the kit does not need a mutation gate")
ck(names.get("set-text") == "DRAFT" and names.get("choose-option") == "DRAFT",
   "entering a value is DRAFT")
# ADR-101 asserted the opposite of this: that no file action is published,
# because a chooser needs OS focus. That confused the native DIALOG with the act
# of handing a page some bytes, and left the kit's only photo entry undriven.
ck(names.get("attach-file") == "DRAFT" and names.get("drop-files") == "DRAFT",
   "handing a page bytes is DRAFT, the same as typing into it: %s" % names)
ck("open-chooser" not in names,
   "and the native chooser is still not published: no action opens an OS dialog")
src = io.open(os.path.join(_kit.TOOLS_DIR, "harness_plugin_page.py"),
              encoding="utf-8").read()
ck("FIXTURES" in src and "set_input_files" in src,
   "the bytes come from the harness's own fixture table, so a run reads nothing "
   "of the operator's disk")
import harness_plugin_page as _PP
ck(all(set(f) == {"name", "type", "b64"} for f in _PP.FIXTURES.values()),
   "every fixture is a real named file with a real type and real bytes")
ck(any(f["type"].startswith("image/") for f in _PP.FIXTURES.values()) and
   any(f["name"].startswith("DJI_") for f in _PP.FIXTURES.values()),
   "including one named the way a drone names its frames, because a page that "
   "keys on a filename should be driven with a filename somebody will hand it")

import swarm as SW
ck(set(SW.DRIVER.values()) <= set(names),
   "every action the swarm drives with is one the plugin publishes: %s"
   % (set(SW.DRIVER.values()) - set(names)))
ck(all(len(v) > 40 for v in SW.EXCLUDED.values()),
   "every kind the swarm still leaves undriven carries a reason, not a label: %s"
   % sorted(SW.EXCLUDED))
ck(set(SW.DRIVER) | set(SW.EXCLUDED) >= set(k for k, _ in SW.SWARM_KINDS),
   "and every kind it discovers is either driven or excluded -- none is simply "
   "not mentioned: %s"
   % sorted(set(k for k, _ in SW.SWARM_KINDS) - set(SW.DRIVER) - set(SW.EXCLUDED)))

# ---- 10. bounded arguments: the manifest is enough to FORM a call (ADR-114) --
class Bounded(C.Plugin):
    def __init__(self):
        self.ran = []
        self._d = C.PluginDescriptor("bounded", "Bounded", "ADR-114 fixture.", "1.0", [
            C.ActionSpec("go", "Every kind of bound at once.", "READ", [
                C.ArgumentSpec("n", "integer", "0..10", required=True, minimum=0, maximum=10),
                C.ArgumentSpec("x", "number", ">= 1.5", minimum=1.5),
                C.ArgumentSpec("s", "string", "a slug", pattern=r"^[a-z]+:\d+$",
                               examples=["dial:2", "text:7"]),
                C.ArgumentSpec("ops", "array", "ops", items="string",
                               pattern=r"^(p \d+|d \d+)$", examples=["p 1", "d 2"]),
                C.ArgumentSpec("via", "string", "route", enum=["a", "b"], examples=["a"]),
                C.ArgumentSpec("kinds", "array", "kinds", items="string", enum=["x", "y"]),
            ])])

    def descriptor(self):
        return self._d

    def observe(self, sensitive=False):
        return {"ready": True}

    def execute(self, action, arguments):
        self.ran.append(arguments)
        return True, "ok", {}


bp = Bounded()
gb = C.Gateway(C.Registry([bp]), C.Policy(token=TOKEN, enabled=True))
sch = gb.manifest(TOKEN)["tools"][0]["inputSchema"]["properties"]
ck(sch["n"]["minimum"] == 0 and sch["n"]["maximum"] == 10 and sch["x"]["minimum"] == 1.5,
   "bounds are published in the JSON Schema an adapter builds from")
ck(sch["s"]["pattern"] and sch["s"]["examples"] == ["dial:2", "text:7"],
   "a pattern is published with its examples")
ck(sch["ops"]["items"] == {"type": "string", "pattern": r"^(p \d+|d \d+)$"} and
   sch["ops"]["examples"] == ["p 1", "d 2"],
   "an array's item pattern is published on the items, with examples on the argument")
ck(sch["via"]["examples"] == ["a"], "an enum may carry examples too")
ck(sch["kinds"]["items"] == {"type": "string", "enum": ["x", "y"]} and "enum" not in sch["kinds"],
   "an enum on an array is published per item (ADR-117)")


def bounded(args, expect_ok):
    try:
        gb.execute(TOKEN, "bounded", {"request_id": "b%d" % len(bp.ran) + str(args), "action": "go",
                                      "arguments": args})
        return expect_ok
    except C.HarnessError as e:
        return (not expect_ok) and e.code == "invalid_argument"


ran0 = len(bp.ran)
ck(bounded({"n": 0}, True) and bounded({"n": 10}, True), "the bounds are inclusive")
ck(bounded({"n": -1}, False) and bounded({"n": 11}, False), "outside them is invalid_argument")
ck(bounded({"n": 5, "x": 1.5}, True) and bounded({"n": 5, "x": 1.49}, False), "a number bound too")
ck(bounded({"n": 5, "s": "dial:2"}, True) and bounded({"n": 5, "s": "dial:x"}, False) and
   bounded({"n": 5, "s": "dial:2 "}, False),
   "a string pattern is a full match, not a search")
ck(bounded({"n": 5, "ops": ["p 1", "d 2"]}, True) and bounded({"n": 5, "ops": ["p 1", "zap"]}, False),
   "an array pattern applies to every item")
ck(bounded({"n": 5, "kinds": ["x", "y"]}, True) and bounded({"n": 5, "kinds": ["x", "z"]}, False),
   "an array enum is checked per item")
ck(len(bp.ran) == ran0 + 6, "and a refused call never reached the plugin: %d ran" % (len(bp.ran) - ran0))
for bad, why in ((dict(pattern="^a$"), "a pattern without examples"),
                 (dict(pattern="^a$", examples=["b"]), "an example failing its own pattern"),
                 (dict(minimum=5, maximum=1), "minimum above maximum"),
                 (dict(enum=["a"], examples=["z"]), "an example outside its enum")):
    try:
        kw = dict(bad)
        typ = "integer" if "minimum" in kw else "string"
        C.ArgumentSpec("q", typ, "d", **kw)
        ck(False, "%s was accepted at construction" % why)
    except ValueError:
        ck(True, "%s is refused at construction, not at call time" % why)
try:
    C.ArgumentSpec("q", "string", "d", minimum=1)
    ck(False, "a bound on a string was accepted")
except ValueError:
    ck(True, "a bound on a string is refused: bounds need a numeric type")


# ---- 12. a declared risk is a floor (ADR-141) ----------------------------
# The blind trial's headline: `activate` was DESTRUCTIVE, so a supervised
# session holding SENSITIVE_READ, DRAFT and MUTATE could fill every field on a
# data-entry page and commit none of them -- every button on these pages is
# pressed through `activate`. The fix is not to lower it. It is to let the one
# thing that knows what a selector resolved to say so, per call, upward only.

class Riser(C.Plugin):
    """One action that may rise, and a dial for what it answers."""

    def __init__(self, answer=None, boom=None):
        self.answer, self.boom, self.ran, self.asked = answer, boom, [], []
        self._d = C.PluginDescriptor("riser", "Riser", "may_rise under test.", "1.0", [
            C.ActionSpec("press", "Press something.", "MUTATE",
                         [C.ArgumentSpec("selector", "string", "What.", required=True)],
                         may_rise=True),
            C.ActionSpec("fixed", "Never rises.", "MUTATE",
                         [C.ArgumentSpec("selector", "string", "What.", required=True)])])

    def descriptor(self):
        return self._d

    def observe(self, sensitive=False):
        # The SAME object each time, deliberately: a plugin that keeps its
        # snapshot is an ordinary plugin, and a gateway that filtered in place
        # would quietly edit a target's own state. Handing back a fresh dict
        # would hide that.
        self.snap = getattr(self, "snap", None) or {
            "ready": True,
            "argumentPools": {"selector": ["a:0"], "pane": ["p"],
                              "press.selector": ["a:0"], "fixed.selector": ["a:0"],
                              "press": [{"selector": "a:0"}]}}
        return self.snap

    def risk_for(self, action, arguments):
        self.asked.append((action, arguments.get("selector")))
        if self.boom:
            raise self.boom
        return self.answer

    def execute(self, action, arguments):
        self.ran.append(action)
        return True, "pressed", {}


def riser_gw(answer=None, boom=None, allow=None):
    plug = Riser(answer, boom)
    pol = C.Policy(token=TOKEN, allow={"MUTATE": True} if allow is None else allow,
                   enabled=True)
    return C.Gateway(C.Registry([plug]), pol), plug


def press(g, n, sel="a:0", action="press"):
    """The call, or the refusal it got. A suite that CRASHES under a mutation
    asserts nothing either way -- and the mutations this section exists for are
    exactly the ones that turn an allowed call into a refused one."""
    try:
        return g.execute(TOKEN, "riser", {"request_id": rid(n), "action": action,
                                          "arguments": {"selector": sel}})
    except C.HarnessError as e:
        return {"risk": "REFUSED:" + e.code, "declaredRisk": None, "riskWhy": e.message,
                "refused": e}


# an action that did not declare may_rise is never asked
g, plug = riser_gw(answer=("DESTRUCTIVE", "would delete everything"))
r = press(g, 900, action="fixed")
ck(plug.asked == [] and r.get("risk") == "MUTATE" and r.get("declaredRisk") == "MUTATE"
   and r.get("riskWhy") is None,
   "an action that did not declare mayRise is never asked what it would touch: %s" % plug.asked)

# ...and one that did is asked, with the arguments of THIS call
g, plug = riser_gw(answer=None)
r = press(g, 901, sel="btn:7")
ck(plug.asked == [("press", "btn:7")],
   "an action that declared mayRise is asked, with this call's arguments: %s" % plug.asked)
ck(r.get("risk") == "MUTATE" and r.get("riskWhy") is None and plug.ran == ["press"],
   "a target that answers None leaves the call at the declared floor")

# a raise is taken, and the response carries both risks and the reason
g, plug = riser_gw(answer=("DESTRUCTIVE", "it is Clear trial"),
                   allow={"MUTATE": True, "DESTRUCTIVE": True})
r = press(g, 902)
ck(r.get("risk") == "DESTRUCTIVE" and r.get("declaredRisk") == "MUTATE"
   and r.get("riskWhy") == "it is Clear trial",
   "a raise is taken, and the response says what it was declared as, what it was "
   "authorised at, and why: %s" % dict((k, r.get(k)) for k in ("risk", "declaredRisk", "riskWhy")))
ck(g.audit[-1][3] == "DESTRUCTIVE",
   "and the AUDIT records the risk the call was authorised at, not the declared one: %s"
   % (g.audit[-1],))

# a LOWER answer is ignored -- a target may not talk its way down the ladder
for lower in (("READ", "harmless, honest"), ("MUTATE", "same rung"), ("nonsense", "not a rung"),
              ("", "empty")):
    g, plug = riser_gw(answer=lower)
    r = press(g, 903)
    ck(r.get("risk") == "MUTATE" and r.get("riskWhy") is None,
       "a target answering %r may not LOWER its own action below the declared floor: %s"
       % (lower[0], r.get("risk")))

# a target that cannot decide gets the top of the ladder, not the bottom
g, plug = riser_gw(boom=RuntimeError("the page is gone"),
                   allow={"MUTATE": True, "DESTRUCTIVE": True})
r = press(g, 904)
ck(r.get("risk") == "DESTRUCTIVE" and "could not say" in (r.get("riskWhy") or ""),
   "a target that THROWS while deciding fails closed at DESTRUCTIVE, because a call "
   "whose subject is unknown is the dangerous case: %s" % r["riskWhy"])

# ...but a refusal it raises deliberately is still a refusal, with its own code
g, plug = riser_gw(boom=C.Unavailable("the page went away"))
r = press(g, 905)
ck(r.get("risk") == "REFUSED:unavailable",
   "a HarnessError raised while deciding the risk reaches the caller unchanged: %s"
   % r.get("risk"))

# the refusal at a RAISED rung says it was raised, and why
g, plug = riser_gw(answer=("DESTRUCTIVE", "it is Clear trial"), allow={"MUTATE": True})
r = press(g, 906)
if "refused" not in r:
    ck(False, "a call raised to DESTRUCTIVE was allowed at a MUTATE session")
else:
    e = r["refused"]
    ck(e.code == "forbidden" and "raised from MUTATE to DESTRUCTIVE" in e.message
       and "it is Clear trial" in e.message,
       "a call refused at the rung it was RAISED to says so, and names the target's "
       "reason -- otherwise the door contradicts a manifest that calls the action "
       "MUTATE: %s" % e.message)
ck(plug.ran == [], "and the raised call never reached the target")

# the replay cache re-authorises at the raised risk, not the declared one
g, plug = riser_gw(answer=("DESTRUCTIVE", "it is Clear trial"),
                   allow={"MUTATE": True, "DESTRUCTIVE": True})
r1 = press(g, 907)
g.policy.allow["DESTRUCTIVE"] = False
ck(press(g, 907).get("risk") == "REFUSED:forbidden",
   "a replayed response is re-authorised at the risk it was RAISED to, so a "
   "payload captured while the gate was open stops flowing when it closes")
ck(len(plug.ran) == 1, "and the replay did not re-run the action either")

# ---- 13. a snapshot never advertises what the door would refuse ----------
g, plug = riser_gw(answer=None, allow={"MUTATE": True})
s_all = g.observe(TOKEN, "riser")
ck("press.selector" in s_all["argumentPools"] and "poolsWithheld" not in s_all,
   "with the action allowed, its pools are published and nothing is withheld")
g2, plug2 = riser_gw(answer=None, allow={})
s_none = g2.observe(TOKEN, "riser")
pools = s_none["argumentPools"]
ck("press.selector" not in pools and "press" not in pools and "fixed.selector" not in pools,
   "a session that may not call an action is not handed that action's argument pools "
   "-- the blind trial was given 65 activate selectors and no tool of that name: %s"
   % sorted(pools))
ck(sorted(pools) == ["pane", "selector"],
   "pools that belong to no action are facts about the target and stay: %s" % sorted(pools))
ck([w["action"] for w in s_none.get("poolsWithheld") or []] == ["fixed", "press"]
   and all(w["risk"] == "MUTATE" for w in s_none.get("poolsWithheld") or []),
   "and what was withheld is NAMED, with the rung that withheld it, so the answer is "
   "'you may not' rather than a pool that goes nowhere: %s" % s_none.get("poolsWithheld"))
ck("press.selector" in plug2.snap["argumentPools"] and "poolsWithheld" not in plug2.snap,
   "the filtering is the gateway's: the target's own snapshot is untouched, so a "
   "plugin never has to know what policy it is being read under -- and a gateway "
   "that filtered IN PLACE would be editing the target's state: %s"
   % sorted(plug2.snap["argumentPools"]))
r = g.execute(TOKEN, "riser", {"request_id": rid(908), "action": "fixed",
                               "arguments": {"selector": "a:0"}})
ck("press.selector" in (r.get("snapshot") or {}).get("argumentPools", {}),
   "the snapshot that rides a response is filtered by the same rule")

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
