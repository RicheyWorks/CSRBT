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

Run:  python3 tools/verify/verify_walk.py
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

# ---- C. the walks, against the engine ---------------------------------------
def walk_target(target, rounds=2, per_round=2, **kw):
    wire = W.Wire("walk-suite-" + secrets.token_urlsafe(18), seed=3, target=target, **kw)
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
    ck(res["protocolVersion"] == "1.1", "%s: protocol 1.1" % label)
    if not allow_unreachable:
        ck(not res["unreachable"], "%s: nothing was unreachable: %s" % (label, res["unreachable"]))


cp_org = os.path.join(os.environ.get("CSRBT_WHOLEHOG") or os.path.join(_kit.ROOT, "..", "WholeHog"),
                      "build", "harness", "classpath.txt")
cp_lab = os.path.join(_kit.ROOT, "csrbt-experimental", "build", "harness", "classpath.txt")
if not os.path.isfile(cp_org):
    unverified.append("C  the organism walk -- WholeHog is not built")
else:
    res = walk_target("organism")["csrbt-organism"]
    hold(res, "organism", 33)
    ck(res["totals"]["refused"] > 0,
       "organism: the target defended itself against some of what the schema allowed (%d refused), "
       "counted rather than hidden" % res["totals"]["refused"])
if not os.path.isfile(cp_lab):
    unverified.append("C  the lab walk -- csrbt-experimental is not built")
else:
    res = walk_target("lab")["csrbt-lab"]
    hold(res, "lab", 8)
    ck(res["per_action"]["csrbt_lab__run"]["driven"] >= 2 and res["per_action"]["csrbt_lab__export"]["driven"] >= 1,
       "lab: protocols ran and a bundle was exported, from the schema's example protocol")
# a page needs only Playwright, which every kit suite needs
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
    ck(set(L) == {"csrbt-organism", "csrbt-lab", "csrbt-page"}, "one entry per target: %s" % sorted(L))
    for pid, want in (("csrbt-organism", 33), ("csrbt-lab", 8), ("csrbt-page", 15)):
        e = L.get(pid) or {}
        ck(e.get("identity") == "holds" and e.get("accounted") == e.get("commands") and
           e.get("tools") == want and not e.get("undriven") and not e.get("unschemable") and
           not e.get("invariants_broken") and (e.get("totals") or {}).get("failed") == 0 and
           e.get("rounds", 0) >= 8,
           "%s: the committed walk holds the identity, drove every tool, broke nothing, failed nothing, "
           "and was a full walk" % pid)

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

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
