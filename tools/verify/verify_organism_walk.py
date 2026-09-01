# -*- coding: utf-8 -*-
"""Is the manifest enough to operate the organism? (ADR-114)

tools/organism_walk.py is a client that reads only the manifest and the
snapshots, forms every call from the schema, and drives all of it through the
stdio transport. This suite pins what makes that claim believable:

  A. the walker is an outsider -- it imports nothing from this kit and speaks
     only the four operations (plus quit)
  B. the generator forms calls the schema permits and nothing the schema
     forbids: bounds are respected and both ends reached, every enum value is
     reached, patterns are satisfied by their examples, a pool is preferred
     when the snapshot publishes one, and a string the manifest gives no way
     to form is reported UNSCHEMABLE rather than guessed (the canary)
  C. the walk itself, against the built engine: the accounting identity, every
     tool driven, nothing unschemable, no invariant broken, no failure
  D. the committed ledger is a coverage claim and is held to the same bar

Run:  python3 tools/verify/verify_organism_walk.py
"""
import io, json, os, random, re, secrets, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import organism_walk as W

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
src = io.open(os.path.join(_kit.TOOLS_DIR, "organism_walk.py"), encoding="utf-8").read()
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
ck(all(1 <= len(v) <= 3 and set(v) <= {"p 1", "p 2"} for v in vals),
   "an array of patterned strings is one to three examples")
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

# ---- C. the walk, against the engine --------------------------------------
cp_file = os.path.join(os.environ.get("CSRBT_WHOLEHOG") or os.path.join(_kit.ROOT, "..", "WholeHog"),
                       "build", "harness", "classpath.txt")
if not os.path.isfile(cp_file):
    unverified.append("C  the walk itself: identity, coverage, nothing unschemable, no invariant broken, "
                      "no failure -- WholeHog is not built")
else:
    wire = W.Wire("walk-suite-" + secrets.token_urlsafe(18), seed=3)
    try:
        res = W.walk(wire, rounds=2, seed=11, per_round=2)
    finally:
        wire.close()
    ck(res["identity"] == "holds" and res["accounted"] == res["commands"] > 100,
       "commands == driven + refused + declined + chaos + failed: %d" % res["commands"])
    ck(res["tools"] == 33 and not res["undriven"],
       "every one of the %d published tools was driven at least once from the schema alone: undriven %s"
       % (res["tools"], res["undriven"]))
    ck(not res["unschemable"], "nothing was unschemable: %s" % res["unschemable"])
    ck(not res["invariants_broken"], "no cross-check broke: %s" % res["invariants_broken"][:2])
    ck(res["totals"]["failed"] == 0, "nothing failed: %s" % res["failures"][:2])
    ck(res["totals"]["refused"] > 0,
       "and the target defended itself against some of what the schema allowed (%d refused), "
       "which is counted rather than hidden" % res["totals"]["refused"])
    ck(res["protocolVersion"] == "1.1", "the walk ran against protocol 1.1")

# ---- D. the committed ledger ----------------------------------------------
led = os.path.join(_kit.TOOLS_DIR, "organism_ledger.json")
ck(os.path.isfile(led), "the ledger exists")
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))
    ck(L["identity"] == "holds" and L["accounted"] == L["commands"],
       "the committed ledger's identity holds")
    ck(L["tools"] == 33 and not L["undriven"] and not L["unschemable"],
       "the committed ledger drove every tool: undriven %s unschemable %s"
       % (L["undriven"], L["unschemable"]))
    ck(not L["invariants_broken"] and L["totals"]["failed"] == 0,
       "with no invariant broken and nothing failed")
    ck(L["rounds"] >= 8 and L["commands"] >= 800, "and it was a full walk, not a smoke test")

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
