# -*- coding: utf-8 -*-
"""Is the manifest enough to operate every target? (ADR-114, ADR-117)

tools/harness_walk.py is a client that reads only the manifest and the
snapshots, forms every call from the schema, and drives all of it through the
stdio transport -- the organism, the science lab and a kit page alike. This
suite pins what makes that claim believable:

  A. the walker is an outsider -- it imports nothing from this kit and speaks
     only the four operations (plus quit)
  B. the generator forms calls the schema permits and nothing the schema
     forbids: bounds are respected and both ends reached, every enum value is
     reached, patterns are satisfied by their examples, a pool is preferred
     when the snapshot publishes one, and a string the manifest gives no way
     to form is reported UNSCHEMABLE rather than guessed (the canary)
  C. the walk itself, against the built engine: the accounting identity, every
     tool driven, nothing unschemable, no invariant broken, no failure --
     for the organism, the lab, and a page (where a tool the page offers
     nothing for is UNREACHABLE, a fact about the page, and not a hole)
  D. the committed ledger is a coverage claim, per target, held to the same bar
  E. scoped pools: "<action>.<argument>" is preferred over "<argument>", and
     a page's snapshot publishes them per action
  F. the robot, broken on purpose (ADR-119): a walk of the csrbt-fixture
     target, whose every action lands in a KNOWN bucket, so each bucket's
     count is pinned exactly -- refused is refused, declined is declined, a
     Crash under an armed plan is chaos and a raise without one is the
     finding; a pool the target rotates on every call is re-read from every
     response; an empty pool is unreachable only when nothing was driven;
     the cross-check reports the fixture's own inconsistency; a target that
     goes away is an alarm, not a bucket. tools/mutate_walk.py breaks the
     walker and requires these checks to notice.
  G. the same robot over the second transport (ADR-121): McpWire speaks
     JSON-RPC to harness_mcp.py and folds it into the shape the walk reads;
     the fixture walked over MCP lands every action in the same bucket the
     same number of times as over stdio, and so does the organism -- the
     transport decides nothing, measured; over MCP the snapshot is a second
     round trip and every execute pays it.
  H. the leak checks (ADR-123): round one is the baseline; a thread not there
     in round one is reported by name; descriptors may rise by the segments
     the store rolled and a little slack, no more.
  I. every routed page, walked (ADR-124): the committed ledger carries one
     entry per page in tools/routes.json, each at the same bar; every page
     tool was driven on at least one page; a link that leaves the page is
     refused (leaving is `open`'s job); a select's option pairs are an
     argument-set pool and choose-option is driven from them.

Run:  python3 tools/verify/verify_walk.py
      CSRBT_WALK_QUICK=1 python3 tools/verify/verify_walk.py   # no engine or page walks (the mutant runner)
"""
import io, json, os, random, re, secrets, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_walk as W

P = F = 0
unverified = []


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- A. an outsider --------------------------------------------------------
src = io.open(os.path.join(_kit.TOOLS_DIR, "harness_walk.py"), encoding="utf-8").read()
imports = re.findall(r"^\s*(?:import|from)\s+([\w.]+)", src, re.M)
kit_modules = {f[:-3] for f in os.listdir(_kit.TOOLS_DIR) if f.endswith(".py")} | {"_kit"}
ck(not (set(imports) & kit_modules) and "harness_contract" not in src.replace("harness_stdio.py", ""),
   "the walker imports nothing from the kit: %s" % sorted(set(imports) & kit_modules))
ck(set(re.findall(r'"op":\s*"(\w+)"', src)) | set(W.OPS) == set(W.OPS) and
   set(W.OPS) == {"manifest", "discover", "observe", "execute", "quit"},
   "and speaks the four operations plus quit, nothing else")
ck("harness_stdio.py" in src and "--target" in src and "CSRBT_HARNESS_TOKEN" in src,
   "it reaches the organism through the stdio transport with a token in the environment")
ck("token_urlsafe" in src and "--token" not in src,
   "the token is generated per run and never appears on a command line")

# ---- B. the generator ------------------------------------------------------
rnd = random.Random(1)
bounded = {"type": "integer", "minimum": 3, "maximum": 9}
vals = [W.value("n", bounded, rnd, i) for i in range(300)]
ck(all(3 <= v <= 9 for v in vals) and 3 in vals and 9 in vals and any(3 < v < 9 for v in vals),
   "a bounded integer stays within its bounds and reaches both ends")
num = {"type": "number", "minimum": 1.5, "maximum": 2.5}
vals = [W.value("x", num, rnd, i) for i in range(100)]
ck(all(1.5 <= v <= 2.5 for v in vals), "a bounded number too")
enum = {"type": "string", "enum": ["a", "b", "c"]}
ck({W.value("e", enum, rnd, i) for i in range(9)} == {"a", "b", "c"}, "every enum value is reached")
pat = {"type": "string", "pattern": r"^once:\d+$", "examples": ["once:2", "once:5"]}
vals = {W.value("p", pat, rnd, i) for i in range(50)}
ck(vals <= {"once:2", "once:5"} and len(vals) == 2, "a pattern is satisfied by its examples, verbatim")
arr = {"type": "array", "items": {"type": "string", "pattern": "^p \\d+$"}, "examples": ["p 1", "p 2"]}
vals = [W.value("ops", arr, rnd, i) for i in range(30)]
ck(all(1 <= len(v) <= 3 and set(v) <= {"p 1", "p 2"} for v in vals) and len(vals[0]) == 1 and len(vals[1]) == 2,
   "an array of patterned strings is one to three examples, one first")
exs = {"type": "integer", "examples": [0, 5, 7]}
vals = [W.value("k", exs, rnd, i) for i in range(200)]
ck(all(v in (0, 5, 7) or 0 <= v <= 16 for v in vals) and any(v in (5, 7) for v in vals),
   "an unbounded integer draws from its examples or a small default pool")
pooled = [W.value("generation", {"type": "integer", "minimum": 0, "examples": [0, 1]}, rnd, i,
                  pools={"generation": [40, 41]}) for i in range(200)]
ck(sum(1 for v in pooled if v in (40, 41)) > 100 and all(v in (40, 41, 0, 1) or 0 <= v <= 16 for v in pooled),
   "a pool the snapshot publishes is preferred over the schema's static examples")
try:
    W.value("s", {"type": "string"}, rnd, 0)
    ck(False, "a string with no enum and no examples was guessed")
except W.Unschemable as e:
    ck("no examples" in str(e), "a string the manifest gives no way to form is UNSCHEMABLE, not guessed")
try:
    W.value("ops", {"type": "array", "items": {"type": "string"}}, rnd, 0)
    ck(False, "an array of unexampled strings was guessed")
except W.Unschemable:
    ck(True, "and so is an array of them")
schema = {"type": "object", "properties": {"n": bounded, "s": {"type": "string", "examples": ["x"]}},
          "required": ["n"]}
formed = [W.form(schema, rnd, i) for i in range(60)]
ck(all("n" in a for a in formed) and any("s" not in a for a in formed) and any("s" in a for a in formed),
   "required arguments are always formed and optional ones sometimes left out")

sets = {"choose": [{"s": "sel:0", "v": "a"}, {"s": "sel:1", "v": "b"}], "s": ["sel:9"], "v": ["z"]}
schema2 = {"type": "object", "properties": {"s": {"type": "string", "examples": ["x"]},
                                            "v": {"type": "string", "examples": ["y"]},
                                            "n": {"type": "integer", "minimum": 0, "maximum": 3}},
           "required": ["s", "v"]}
formed = [W.form(schema2, rnd, i, sets, "choose") for i in range(40)]
ck(all((a["s"], a["v"]) in (("sel:0", "a"), ("sel:1", "b")) for a in formed) and
   len({(a["s"], a["v"]) for a in formed}) == 2 and any("n" in a for a in formed),
   "an argument-SET pool keyed by the action is taken whole -- the pair stays a pair, the per-argument "
   "pools are not mixed in, and arguments the set does not cover are formed as before (ADR-124)")
ck(W.relevant_pools({"action": "choose", "inputSchema": {"required": ["s", "v"]}}, sets) == ["choose", "s", "v"],
   "the set pool is the first relevant pool of its action")

# ---- C. the walks, against the engine ---------------------------------------
def walk_target(target, rounds=2, per_round=2, transport="stdio", **kw):
    wire = W.wire_for(transport, "walk-suite-" + secrets.token_urlsafe(18), seed=3, target=target, **kw)
    try:
        return W.walk(wire, rounds=rounds, seed=11, per_round=per_round)
    finally:
        wire.close()


def hold(res, label, tools_expected, allow_unreachable=False):
    ck(res["identity"] == "holds" and res["accounted"] == res["commands"] > 20,
       "%s: commands == driven + refused + declined + chaos + failed: %d" % (label, res["commands"]))
    ck(res["tools"] == tools_expected and not res["undriven"],
       "%s: every one of the %d published tools was driven from the schema alone (or is unreachable "
       "on this target): undriven %s" % (label, res["tools"], res["undriven"]))
    ck(not res["unschemable"], "%s: nothing was unschemable: %s" % (label, res["unschemable"]))
    ck(not res["invariants_broken"], "%s: no cross-check broke: %s" % (label, res["invariants_broken"][:2]))
    ck(res["totals"]["failed"] == 0, "%s: nothing failed: %s" % (label, res["failures"][:2]))
    ck(res["protocolVersion"] == "1.3", "%s: protocol 1.3" % label)
    if not allow_unreachable:
        ck(not res["unreachable"], "%s: nothing was unreachable: %s" % (label, res["unreachable"]))


cp_org = os.path.join(os.environ.get("CSRBT_WHOLEHOG") or os.path.join(_kit.ROOT, "..", "WholeHog"),
                      "build", "harness", "classpath.txt")
cp_lab = os.path.join(_kit.ROOT, "csrbt-experimental", "build", "harness", "classpath.txt")
QUICK = os.environ.get("CSRBT_WALK_QUICK") == "1"
if QUICK:
    print("QUICK: the engine and page walks of section C are skipped (CSRBT_WALK_QUICK=1)")
elif not os.path.isfile(cp_org):
    unverified.append("C  the organism walk -- WholeHog is not built")
else:
    res = walk_target("organism")["csrbt-organism"]
    hold(res, "organism", 35)
    ck(res["totals"]["refused"] > 0,
       "organism: the target defended itself against some of what the schema allowed (%d refused), "
       "counted rather than hidden" % res["totals"]["refused"])
    pr = res["price"]["snapshotMs"]
    ck(pr["n"] > 20 and 0 <= pr["median"] <= 250 and pr["max"] <= 2000,
       "organism: the snapshot on every response is priced from the responses (ADR-120): median %s ms, "
       "p95 %s, max %s over %d" % (pr.get("median"), pr.get("p95"), pr.get("max"), pr["n"]))
if QUICK:
    pass
elif not os.path.isfile(cp_lab):
    unverified.append("C  the lab walk -- csrbt-experimental is not built")
else:
    res = walk_target("lab")["csrbt-lab"]
    hold(res, "lab", 9)
    ck(res["per_action"]["csrbt_lab__run"]["driven"] >= 2 and res["per_action"]["csrbt_lab__export"]["driven"] >= 1,
       "lab: protocols ran and a bundle was exported, from the schema's example protocol")
# a page needs only Playwright, which every kit suite needs
if not QUICK:
    res = walk_target("page", page="collection-sheet.html", rounds=3, per_round=3)["csrbt-page"]
    hold(res, "page", 15, allow_unreachable=True)
    ck(set(res["unreachable"]) == {"csrbt_page__choose_option", "csrbt_page__drop_files",
                                  "csrbt_page__set_checkbox", "csrbt_page__set_slider"},
       "page: collection-sheet has no select, drop zone, checkbox or slider, and the walk says so "
       "rather than calling them undriven: %s" % res["unreachable"])
    ck(res["per_action"]["csrbt_page__attach_file"]["driven"] >= 1 and
       res["per_action"]["csrbt_page__show_pane"]["driven"] >= 1 and
       res["per_action"]["csrbt_page__set_text"]["driven"] >= 1,
       "page: a file input behind a tab, a pane and a text control were all reached through the pools")
    res2 = walk_target("page", page="ecology-lab.html", rounds=3, per_round=3)["csrbt-page"]
    ck(res2["per_action"]["csrbt_page__choose_option"]["driven"] >= 1 and
       "csrbt_page__choose_option" not in res2["unreachable"],
       "page: on a page WITH selects choose-option is driven, from the option-value pool")
    ck(res2["totals"]["failed"] == 0 and not res2["invariants_broken"], "page: and ecology-lab breaks nothing")

# ---- D. the committed ledger ----------------------------------------------
led = os.path.join(_kit.TOOLS_DIR, "walk_ledger.json")
ck(os.path.isfile(led), "the ledger exists")
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["targets"]
    ck({k for k in L if not k.startswith("csrbt-page/")} ==
       {"csrbt-organism", "csrbt-lab", "csrbt-page", "csrbt-organism@mcp", "csrbt-lab@mcp", "csrbt-page@mcp"},
       "one entry per target per transport, plus one per routed page: %s"
       % sorted(k for k in L if not k.startswith("csrbt-page/")))
    for pid, want in (("csrbt-organism", 35), ("csrbt-lab", 9), ("csrbt-page", 15),
                      ("csrbt-organism@mcp", 35), ("csrbt-lab@mcp", 9), ("csrbt-page@mcp", 15)):
        e = L.get(pid) or {}
        ck(e.get("identity") == "holds" and e.get("accounted") == e.get("commands") and
           e.get("tools") == want and not e.get("undriven") and not e.get("unschemable") and
           not e.get("invariants_broken") and (e.get("totals") or {}).get("failed") == 0 and
           e.get("rounds", 0) >= 8,
           "%s: the committed walk holds the identity, drove every tool, broke nothing, failed nothing, "
           "and was a full walk" % pid)
        pr = (e.get("price") or {}).get("snapshotMs") or {}
        ck(pr.get("n", 0) > 0 and isinstance(pr.get("median"), int) and pr["median"] <= 250,
           "%s: the committed walk carries the snapshot's price (median %s ms over %s responses)"
           % (pid, pr.get("median"), pr.get("n")))
        ck(e.get("transport") == ("mcp" if pid.endswith("@mcp") else "stdio"),
           "%s: the entry names its transport" % pid)

# ---- E. scoped pools ---------------------------------------------------------
rnd = random.Random(5)
scoped = [W.value("selector", {"type": "string", "examples": ["x:0"]}, rnd, i,
                  pools={"selector": ["a:1"], "set-text.selector": ["t:1", "t:2"]}, action="set-text")
          for i in range(100)]
ck(all(v in ("t:1", "t:2") for v in scoped),
   "a pool scoped to the action is used every time: the target said 'these', and nothing is mixed in")
plain = [W.value("selector", {"type": "string", "examples": ["x:0"]}, rnd, i,
                 pools={"selector": ["a:1"]}, action="activate") for i in range(100)]
ck("a:1" in plain, "and the plain pool is used when no scoped one exists")
ck(W.relevant_pools({"action": "show-pane", "inputSchema": {"required": ["pane"]}}, {"pane": []}) == ["pane"] and
   W.relevant_pools({"action": "attach-file", "inputSchema": {"required": ["selector", "files"]}},
                    {"selector": ["a:1"], "attach-file.selector": []}) == ["attach-file.selector"],
   "the pools a required argument would draw from are found scoped-first")
from harness_plugin_page import PagePlugin, POOL_KINDS
try:
    import swarm as SW
    ck(all(SW.DRIVER.get(k) == a for a, ks in POOL_KINDS.items() for k in ks if k in SW.DRIVER),
       "the page plugin's pool kinds agree with the swarm's DRIVER map")
except ImportError:
    ck(True, "(swarm not importable here)")

# ---- F. the robot, broken on purpose ------------------------------------------
# The fixture target lands every action in a known bucket, every time, so the
# walker's bookkeeping is pinned by exact counts rather than by "nothing
# failed" against a target that mostly succeeds. 2 rounds x 2 per round: each
# action is called exactly four times unless the walker stops early.
def walk_fixture(rounds=2, per_round=2, env=None, transport="stdio"):
    old = dict(os.environ)
    os.environ.update(env or {})
    try:
        wire = W.wire_for(transport, "walk-suite-" + secrets.token_urlsafe(18), seed=3, target="fixture")
        try:
            res = W.walk(wire, rounds=rounds, seed=11, per_round=per_round)["csrbt-fixture"]
            snap = wire.op("observe", plugin="csrbt-fixture").get("snapshot") or {}
            return res, snap
        finally:
            wire.close()
    finally:
        os.environ.clear()
        os.environ.update(old)


fx, fsnap = walk_fixture()
F_ = "csrbt_fixture__"
pa = fx["per_action"]
N = 4


def only(name, bucket):
    c = pa.get(F_ + name) or {}
    return c.get(bucket) == N and sum(c.values()) == N


ck(fx["tools"] == 12 and set(pa) == {F_ + n for n in ("ok", "refuse", "decline", "crash", "boom", "pooled",
                                                    "empty_pool", "reached", "paired", "unformable", "array", "broken")}
   | {"_cross_checks"},
   "fixture: twelve tools published, one row each plus the cross-checks' row: %s" % sorted(pa))
ck(only("ok", "driven"), "fixture: ok is driven, %d of %d: %s" % (N, N, pa.get(F_ + "ok")))
ck(only("refuse", "refused"), "fixture: a target defending itself is REFUSED, never driven or failed: %s"
   % pa.get(F_ + "refuse"))
ck(only("decline", "declined"), "fixture: ok:false with no code is DECLINED: %s" % pa.get(F_ + "decline"))
ck(only("crash", "chaos"), "fixture: a raise naming a Crash under an armed plan is CHAOS: %s" % pa.get(F_ + "crash"))
ck(only("boom", "failed"), "fixture: a raise with no Crash in it is FAILED -- the finding: %s" % pa.get(F_ + "boom"))
ck(fx["totals"]["failed"] == N and len(fx["failures"]) == N and all("boom" in f for f in fx["failures"]),
   "fixture: every failure is noted by action and message, and only boom's: %s" % fx["failures"][:2])
ck(only("pooled", "driven"),
   "fixture: a pool the target rotates on every call is re-read from every response -- pooled is driven "
   "%d of %d (a walker acting on a stale pool is refused): %s" % (N, N, pa.get(F_ + "pooled")))
ck(only("broken", "driven") and only("array", "driven"), "fixture: array and broken are driven")
ck(only("paired", "driven"),
   "fixture: an argument-SET pool keyed by the action is taken whole (ADR-124) -- paired is driven %d of %d "
   "where forming a and b alone would be refused: %s" % (N, N, pa.get(F_ + "paired")))
ck(only("empty_pool", "refused") and fx["unreachable"] == [F_ + "empty_pool"],
   "fixture: a tool whose scoped pool was published empty throughout AND was never driven is "
   "UNREACHABLE, and its refusals are still counted: %s %s" % (fx["unreachable"], pa.get(F_ + "empty_pool")))
ck(only("reached", "driven") and F_ + "reached" not in fx["unreachable"],
   "fixture: a tool whose scoped pool is empty but whose schema example gets through was REACHED, "
   "whatever the pool said: %s" % pa.get(F_ + "reached"))
ck(F_ + "empty_pool" not in fx["undriven"] and F_ + "unformable" not in fx["undriven"] and fx["undriven"] ==
   [F_ + n for n in ("refuse", "decline", "crash", "boom")],
   "fixture: undriven names exactly the tools that answered but never ok, not the unreachable or the "
   "unschemable: %s" % fx["undriven"])
ck(list(fx["unschemable"]) == [F_ + "unformable"] and "no examples" in fx["unschemable"][F_ + "unformable"]
   and sum((pa.get(F_ + "unformable") or {}).values()) == 0,
   "fixture: a string the manifest gives no way to form is UNSCHEMABLE, named, and never sent: %s"
   % fx["unschemable"])
ck(fx["identity"] == "holds" and fx["accounted"] == fx["commands"] == 11 * N and fx["commands"] == sum(
    fsnap.get("calls", {}).values()) and fx["accounted"] == sum(fx["totals"].values()) and
   fx["totals"] == {"driven": 6 * N, "refused": 2 * N, "declined": N, "chaos": N, "failed": N},
   "fixture: commands == driven + refused + declined + chaos + failed == %d, the totals are %s, and the "
   "fixture counted the same" % (fx["commands"], fx["totals"]))
ck(fsnap.get("arrayLengths", [None])[0] == 1 and sorted(set(fsnap.get("arrayLengths", []))) == [1, 2, 3],
   "fixture: arrays are one item first, then longer: %s" % fsnap.get("arrayLengths"))
ck(len(fx["invariants_broken"]) == 2 and all("not consistent" in b for b in fx["invariants_broken"]),
   "fixture: the cross-check ran every round and reported the fixture's own broken flag, nothing else: %s"
   % fx["invariants_broken"])
ck(W.bad(fx), "fixture: the walker's verdict on a target that fails on purpose is failing")
clean = {"identity": "holds", "undriven": [], "unschemable": {}, "invariants_broken": [],
         "totals": {"driven": 3, "refused": 0, "declined": 0, "chaos": 0, "failed": 0}}
spoilt = [dict(clean, identity="UNACCOUNTED"), dict(clean, undriven=["x"]), dict(clean, unschemable={"x": "y"}),
          dict(clean, invariants_broken=["z"]), dict(clean, totals=dict(clean["totals"], failed=1))]
ck(not W.bad(clean) and all(W.bad(r) for r in spoilt),
   "the verdict is failing on any one of: identity broken, a tool undriven, unschemable, a cross-check broken, "
   "a failure -- and passing with none (refusals, declines and chaos are counted, not failed)")
ck(fx["rounds"] == 2 and fx["per_round"] == 2 and fx["seconds"] < 30,
   "fixture: a walk of the fixture is a fast one: %ss" % fx["seconds"])
ck(fx["price"]["snapshotMs"]["n"] == 7 * N and fx["price"]["snapshotMs"]["max"] <= 5,
   "fixture: the price is read from the responses that carry one -- the %d driven and declined; a "
   "refusal carries no snapshot -- and a fixture's snapshot costs nothing: %s"
   % (7 * N, fx["price"]["snapshotMs"]))
try:
    walk_fixture(env={"CSRBT_FIXTURE_DIE": "1"})
    ck(False, "fixture: a target that went away was walked to the end as if it had answered")
except RuntimeError as e:
    ck("went away" in str(e), "fixture: a target that goes away mid-walk is an alarm (unavailable), "
                              "not a bucket: %s" % str(e)[:60])

# ---- G. the same robot over MCP --------------------------------------------
gx, gsnap = walk_fixture(transport="mcp")
ck(gx["transport"] == "mcp" and fx["transport"] == "stdio", "the result names its transport")
ck(gx["per_action"] == fx["per_action"] and gx["totals"] == fx["totals"] and gx["commands"] == fx["commands"],
   "the fixture walked over MCP lands every action in the same bucket the same number of times as over "
   "stdio -- refused, declined, chaos and failed all read back through JSON-RPC: %s vs %s"
   % (gx["totals"], fx["totals"]))
ck(gx["unreachable"] == fx["unreachable"] and gx["undriven"] == fx["undriven"] and
   list(gx["unschemable"]) == list(fx["unschemable"]) and gx["invariants_broken"] == fx["invariants_broken"],
   "and says the same about the unreachable, the undriven, the unschemable and the cross-checks")
ck(gx["price"]["snapshotMs"]["n"] == gx["commands"] and gx["price"]["snapshotMs"]["n"] > fx["price"]["snapshotMs"]["n"],
   "over MCP every execute pays for a snapshot -- a second round trip, priced by the client's own clock -- "
   "where over stdio a refusal carries none: %d vs %d priced" % (gx["price"]["snapshotMs"]["n"],
                                                                 fx["price"]["snapshotMs"]["n"]))
ck(gsnap.get("calls") == fsnap.get("calls"), "the fixture counted the same calls from either transport")
try:
    walk_fixture(env={"CSRBT_FIXTURE_DIE": "1"}, transport="mcp")
    ck(False, "over MCP a target that went away was walked to the end")
except RuntimeError as e:
    ck("went away" in str(e), "over MCP a target that goes away (-32002, unavailable) is the same alarm")
src_mcp = io.open(os.path.join(_kit.TOOLS_DIR, "harness_mcp.py"), encoding="utf-8").read()
ck('"_meta"' in src_mcp and "_meta" in src and "split(\"__\"" not in src,
   "the MCP wire reads the action from a tool's _meta and never guesses it back out of the slug")
if not QUICK and os.path.isfile(cp_org):
    res_s = walk_target("organism")["csrbt-organism"]
    res_m = walk_target("organism", transport="mcp")["csrbt-organism"]
    hold(res_m, "organism over MCP", 35)
    ck(res_m["per_action"] == res_s["per_action"],
       "the organism walked over MCP and over stdio from the same seed land every action in the same "
       "buckets: %s vs %s" % (res_m["totals"], res_s["totals"]))
    pr = res_m["price"]["snapshotMs"]
    ck(pr["n"] == res_m["commands"] and pr["median"] <= 250,
       "organism over MCP: every command paid a snapshot round trip, median %s ms" % pr["median"])
elif not QUICK:
    unverified.append("G  the organism over MCP -- WholeHog is not built")

# ---- H. the leak checks (ADR-123) ------------------------------------------
W.FIRST.clear()
ck(W.leak_checks("t", 10, ["a", "b"], 40, 3) == [] and W.leak_checks("t", 10, ["a", "b"], 40, 3) == [],
   "round one is the baseline, and a process that stays where it started breaks nothing")
ck(any("threads grew" in b for b in W.leak_checks("t", 11, ["a", "b", "c"], 40, 3)),
   "a thread that was not there in round one is reported by name")
ck(any("descriptors grew" in b for b in W.leak_checks("t", 10, ["a", "b"], 60, 3)),
   "descriptors up by more than the segments explain are reported")
ck(W.leak_checks("t", 10, ["a", "b"], 45, 8) == [] and W.leak_checks("t", 10, ["a", "b"], 47, 3) == [],
   "descriptors up by the segments the store rolled, or within the slack, are not")
ck(W.leak_checks("t", 10, ["a"], -1, 3) == [] and W.leak_checks("u", 5, None, 10, 0) == [] and
   any("threads grew" in b for b in W.leak_checks("u", 12, None, 10, 0)),
   "a platform with no descriptor count is not accused, and a target with counts but no names is held "
   "to the count")
W.FIRST.clear()

# ---- I. every routed page ----------------------------------------------------
pages = W.routed_pages()
ck(len(pages) == 41 and "douglas-explorer.html" in pages, "the route table names the kit's %d pages" % len(pages))
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["targets"]
    walked = {k[len("csrbt-page/"):] for k in L if k.startswith("csrbt-page/")}
    ck(walked == set(pages), "the ledger carries a walk of every routed page and of nothing unrouted: missing %s, "
       "extra %s" % (sorted(set(pages) - walked), sorted(walked - set(pages))))
    badp = [p for p in pages if "csrbt-page/" + p in L and W.bad(L["csrbt-page/" + p])]
    ck(not badp, "every page's walk holds the identity, drove every tool it offers, broke nothing, failed nothing: "
       "bad %s" % badp)
    ck(all(L["csrbt-page/" + p].get("page") == p and L["csrbt-page/" + p].get("rounds", 0) >= 3
           for p in pages if "csrbt-page/" + p in L),
       "each entry names its page and was at least a three-round walk")
    driven_somewhere = {}
    for p in pages:
        for name, c in L.get("csrbt-page/" + p, {}).get("per_action", {}).items():
            if not name.startswith("_"):
                driven_somewhere[name] = driven_somewhere.get(name, 0) + c["driven"]
    ck(len(driven_somewhere) == 15 and all(v > 0 for v in driven_somewhere.values()),
       "every one of the 15 page tools was driven on at least one page: never %s"
       % sorted(n for n, v in driven_somewhere.items() if v == 0))
    unreach = {p: len(L["csrbt-page/" + p]["unreachable"]) for p in pages if "csrbt-page/" + p in L}
    ck(unreach.get("stand-sheet.html", 99) <= 3 and unreach.get("ecology-teachers-guide.html", 0) >= 6,
       "unreachable is a fact about the page: a bench offers nearly every tool, a guide offers few: %s"
       % {k: unreach[k] for k in ("stand-sheet.html", "ecology-teachers-guide.html") if k in unreach})
if not QUICK:
    # the two defects the first walk of every page found, pinned live
    wire = W.Wire("walk-suite-" + secrets.token_urlsafe(18), seed=3, target="page", page="ecology.html")
    try:
        wire.op("discover")
        snap = wire.op("observe", plugin="csrbt-page")["snapshot"]
        link = next((c["selector"] for c in snap.get("controls", []) if c["kind"] == "nav_link"), None)
        r = wire.op("execute", plugin="csrbt-page",
                    command={"request_id": "leave-1", "action": "activate", "arguments": {"selector": link}})
        ck(link and not r.get("ok") and r.get("code") == "invalid_argument" and "use open" in (r.get("message") or ""),
           "on the hub, activating a link to another page is refused -- leaving is open's job: %s"
           % (r.get("message") or "")[:80])
        ck((wire.op("observe", plugin="csrbt-page")["snapshot"].get("page") or "ecology.html") == "ecology.html"
           and wire.op("execute", plugin="csrbt-page",
                       command={"request_id": "leave-2", "action": "reload", "arguments": {}}).get("ok"),
           "and the walk is still on its page: reload works")
    finally:
        wire.close()
    wire = W.Wire("walk-suite-" + secrets.token_urlsafe(18), seed=3, target="page", page="experiment-guide.html")
    try:
        wire.op("discover")
        snap = wire.op("observe", plugin="csrbt-page")["snapshot"]
        sets_ = snap["argumentPools"].get("choose-option") or []
        ck(len(sets_) >= 10 and all(set(x) == {"selector", "value"} for x in sets_) and
           len({x["selector"] for x in sets_}) >= 4,
           "experiment-guide publishes its selects' (selector, value) pairs as an argument-set pool: %d pairs "
           "over %d selects" % (len(sets_), len({x["selector"] for x in sets_})))
        okc = 0
        for i, x in enumerate(sets_[:8]):
            r = wire.op("execute", plugin="csrbt-page",
                        command={"request_id": "pair-%d" % i, "action": "choose-option", "arguments": dict(x)})
            okc += 1 if r.get("ok") else 0
        ck(okc == min(8, len(sets_)), "and every published pair is accepted: %d of %d" % (okc, min(8, len(sets_))))
    finally:
        wire.close()

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
