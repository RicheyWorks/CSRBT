# -*- coding: utf-8 -*-
"""The science engine behind the contract (ADR-116).

The kit's pages describe experiments; csrbt-experimental runs them. Until the
csrbt-lab plugin no robot could run one. This suite drives the lab through the
gateway only and holds it to oracles the kit already keeps:

  A. the descriptor: risks, bounds, examples; three plugins in one manifest
  B. the canonical oracle: the shipped protocol run through the gateway
     produces the session the repository ships, byte for byte -- the same
     artifact verify_engine_sessions binds the flagship page to
  C. grading: CONFIRMED / REFUTED / UNGRADEABLE, and a malformed line is a
     named problem, never a guess
  D. the one thing the harness refuses: a dwc: line, at the boundary and at
     the target
  E. the arena: four strategies ranked, deterministic in everything but time
  F. the controller: a morph log that is ordered, deterministic, and ends
     where it says
  G. the field day parses into its stations
  H. export writes the bundle into scratch the plugin owns, text identical to
     the run, Office files present
  I. policy: NAVIGATE runs under the default rung, MUTATE does not; the
     snapshot hides the protocol's name unless SENSITIVE_READ
  J. operable from the manifest alone: every lab tool is formable by the
     first robot's generator
  K. the stdio transport with --target lab, and --target all naming three

NOT VERIFIED where csrbt-experimental is not built
(`./gradlew :csrbt-experimental:harnessClasspath`).

Run:  python3 tools/verify/verify_lab.py
"""
import io, json, os, random, subprocess, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_contract as C
import harness_plugin_lab as L
import organism_walk as W
from harness_plugin_organism import OrganismPlugin
from harness_plugin_page import PagePlugin

P = F = 0
unverified = []
TOKEN = "lab-suite-" + "l" * 20
_rid = [0]


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


def rid():
    _rid[0] += 1
    return "l%d" % _rid[0]


def gw_for(plugin, **allow):
    return C.Gateway(C.Registry([plugin]), C.Policy(token=TOKEN, enabled=True, allow=allow or None))


def run(gw, action, **args):
    return gw.execute(TOKEN, L.LabPlugin.ID, {"request_id": rid(), "action": action, "arguments": args})


def refused(fn, code):
    try:
        fn()
    except C.HarnessError as e:
        return e.code == code, e.code
    return False, "no refusal"


# ---- A. descriptor ----------------------------------------------------------
plug = L.LabPlugin()
d = plug.descriptor()
names = [a.name for a in d.actions]
ck(d.id == "csrbt-lab" and len(names) == 8 and len(set(names)) == 8, "eight distinct actions")
ck({a.name for a in d.actions if a.risk == "READ"} == {"protocols", "lint"} and
   {a.name for a in d.actions if a.risk == "NAVIGATE"} == {"run-protocol", "run", "battle", "adapt", "field-day"} and
   {a.name for a in d.actions if a.risk == "MUTATE"} == {"export"} and
   not any(a.risk in ("SENSITIVE_READ", "DESTRUCTIVE") for a in d.actions),
   "READ parses, NAVIGATE computes, MUTATE writes -- and nothing reads a record or presses blindly")
proto = [a for a in d.action("run").arguments if a.name == "protocol"][0]
ck(proto.examples and "expect:" in proto.examples[0] and "dwc:" not in proto.examples[0],
   "the protocol argument carries a runnable example, and it is not one the harness would refuse")
ck([a for a in d.action("battle").arguments if a.name == "workload"][0].enum == L.WORKLOADS and
   [a for a in d.action("battle").arguments if a.name == "ops"][0].maximum == L.OPS_MAX,
   "workloads are an enum and ops are bounded")
ck("sample-experiment" in [a for a in d.action("run-protocol").arguments][0].enum,
   "the shipped protocols are an enum: %s" % d.action("run-protocol").arguments[0].enum)
man = C.Gateway(C.Registry([plug, OrganismPlugin(), PagePlugin(None, None)]),
                C.Policy(token=TOKEN, enabled=True)).manifest(TOKEN)
tools = [t["name"] for t in man["tools"]]
ck({p["id"] for p in man["plugins"]} == {"csrbt-lab", "csrbt-organism", "csrbt-page"} and
   len(tools) == len(set(tools)), "three targets in one manifest, %d distinct tool names" % len(tools))

# ---- J (no engine needed): formable from the manifest ----------------------
rnd = random.Random(3)
bad = []
for t in man["tools"]:
    if t["pluginId"] != "csrbt-lab":
        continue
    try:
        for i in range(5):
            W.form(t["inputSchema"], rnd, i)
    except W.Unschemable as e:
        bad.append((t["name"], str(e)))
ck(not bad, "every lab tool is formable from its schema by the first robot's generator: %s" % bad)

CP = L.classpath()
if CP is None:
    unverified.append("B-I, K  the lab driven through the gateway -- csrbt-experimental is not built: "
                      "./gradlew :csrbt-experimental:harnessClasspath")
else:
    gw = gw_for(plug)                                    # READ + NAVIGATE
    gwW = gw_for(plug, MUTATE=True, SENSITIVE_READ=True)
    s0 = plug.observe()
    ck(s0.get("ready") and s0["runs"] == 0 and s0["workloads"] == L.WORKLOADS and "lastName" not in s0,
       "the lab stands up, counts nothing yet, names its workloads, hides the protocol name")

    # ---- B. the canonical oracle ----
    r = run(gw, "run-protocol", name="sample-experiment")
    shipped = json.load(io.open(os.path.join(_kit.ROOT, "docs", "ecology-experiment-session.json"),
                                encoding="utf-8"))
    ck(r["ok"] and r["output"]["session"] == shipped,
       "the shipped protocol run through the gateway produces the session the repository ships")
    ck(r["output"]["verdicts"] == {"CONFIRMED": 6, "REFUTED": 1} and
       any(h["expr"].startswith("evenness(bloom) > 0.9") and h["verdict"] == "REFUTED"
           for h in r["output"]["hypotheses"]),
       "six confirmed, one refuted -- the one the protocol says is deliberately wrong: %s"
       % r["output"]["verdicts"])
    ck("REFUTED" in r["output"]["report"] and r["output"]["reportTruncated"] is False,
       "the narrated report says so too")
    ck(any(f["name"] == "report.html" for f in r["output"]["files"]) and
       all(f["bytes"] > 0 for f in r["output"]["files"]),
       "and names its exports: %s" % [f["name"] for f in r["output"]["files"]][:5])
    ok_, code = refused(lambda: run(gw, "run-protocol", name="no-such"), "invalid_argument")
    ck(ok_, "a protocol outside the enum is refused at the boundary: %s" % code)

    # ---- C. grading ----
    spec = L.EXAMPLE_SPEC + "expect: evenness(nowhere) > 0.5\nfrobnicate: 3\n"
    r = run(gw, "lint", protocol=spec)
    ck(r["output"]["phases"] == 2 and r["output"]["expectations"] == 3 and
       len(r["output"]["problems"]) == 1 and "frobnicate" in r["output"]["problems"][0],
       "lint counts what is declared and names the malformed line: %s" % r["output"]["problems"])
    r = run(gw, "run", protocol=spec)
    v = r["output"]["verdicts"]
    ck(v.get("UNGRADEABLE") == 1 and sum(v.values()) == 3,
       "a hypothesis naming a phase that does not exist is UNGRADEABLE, not guessed: %s" % v)
    ck(plug.observe()["runs"] == 2 and plug.observe()["lints"] == 1, "the counters moved")

    # ---- D. the refusal ----
    dwc = L.EXAMPLE_SPEC + "dwc: plot /etc/passwd\n"
    ok_, code = refused(lambda: run(gw, "run", protocol=dwc), "invalid_argument")
    ck(ok_, "a dwc: line is refused at the boundary: %s" % code)
    ok_, code = refused(lambda: plug.console.send("run", L._b64(dwc)), "invalid_argument")
    ck(ok_, "and by the console itself, so a client that reaches around the plugin is refused too: %s" % code)
    ck(plug.observe()["runs"] == 2, "and neither refusal ran anything")
    ok_, code = refused(lambda: run(gw, "run", protocol="x" * (L.SPEC_CAP + 1)), "invalid_argument")
    ck(ok_, "a protocol over 64 KiB is refused: %s" % code)

    # ---- E. the arena ----
    a = run(gw, "battle", workload="MIXED", ops=1000, seed=7)["output"]
    b = run(gw, "battle", workload="MIXED", ops=1000, seed=7)["output"]
    strategies = {x["strategy"] for x in a["results"]}
    ck(strategies == {"RedBlack", "AVL", "Splay", "Hybrid"} and
       sorted(x["rank"] for x in a["results"]) == [1, 2, 3, 4],
       "four strategies, ranked 1..4: %s" % strategies)
    det = lambda rs: sorted((x["strategy"], x["avgDepth"], x["rotations"], x["searchHits"], x["totalOps"], x["finalSize"])
                            for x in rs)
    ck(det(a["results"]) == det(b["results"]),
       "the same seed gives the same depths, rotations, hits and sizes (time is wall-clock and is not pinned)")
    ck(all(x["totalOps"] == 1000 for x in a["results"]), "every competitor did all 1000 ops")
    c = run(gw, "battle", workload="MIXED", ops=1000, seed=8)["output"]
    ck(det(a["results"]) != det(c["results"]), "and a different seed is a different workload")
    ok_, code = refused(lambda: run(gw, "battle", workload="MIXED", ops=10), "invalid_argument")
    ck(ok_, "ops below the floor are refused at the boundary: %s" % code)

    # ---- F. the controller ----
    a = run(gw, "adapt", keys=500, ops=3000, seed=42)["output"]
    b = run(gw, "adapt", keys=500, ops=3000, seed=42)["output"]
    ck(a == b, "the controller's run is deterministic per seed")
    ck(a["morphs"] >= 1 and len(a["log"]) == a["morphs"] and
       all(a["log"][i]["op"] < a["log"][i + 1]["op"] for i in range(len(a["log"]) - 1)),
       "the morph log has %d entries in op order" % a["morphs"])
    ck(a["strategy"].upper().startswith(a["log"][-1]["to"].replace("_", "")[:5]) and
       a["log"][0]["from"] == "RED_BLACK",
       "it started Red-Black and ended where the last morph says: %s -> %s" % (a["log"][-1]["to"], a["strategy"]))

    # ---- G. the field day ----
    r = run(gw, "field-day")["output"]
    ck(isinstance(r["session"], dict) and {"meadow", "demography"} <= set(r["session"]) and
       "FIELD DAY" in r["report"], "the field day parses into its stations: %s" % sorted(r["session"])[:5])

    # ---- H. export ----
    ok_, code = refused(lambda: run(gw, "export", protocol=L.EXAMPLE_SPEC), "forbidden")
    ck(ok_, "export is refused under the default policy: %s" % code)
    r = run(gwW, "export", protocol=L.EXAMPLE_SPEC)["output"]
    names_ = {f["name"] for f in r["files"]}
    ck({"workbook.xlsx", "report.pptx", "report.html", "session.json", "report.txt"} <= names_ and
       all(f["bytes"] > 0 for f in r["files"]) and r["dir"].startswith(plug.scratch),
       "the bundle is written into the plugin's scratch: %d files" % len(r["files"]))
    ran = run(gw, "run", protocol=L.EXAMPLE_SPEC)["output"]
    sp = os.path.join(r["dir"], "session.json")
    disk = io.open(sp, encoding="utf-8").read() if os.path.isfile(sp) else None
    ck(disk is not None and json.loads(disk) == ran["session"],
       "the exported session is on disk and equals the run's")
    ck(plug.observe()["exportsWritten"] == len(r["files"]), "the snapshot counts the files written")

    # ---- I. policy and redaction ----
    s = gwW.observe(TOKEN, plug.ID)
    ck(s["lastName"] == "harness example" and "lastName" not in gw.observe(TOKEN, plug.ID),
       "the protocol's name shows only under SENSITIVE_READ")

    # ---- K. the transport ----
    env = dict(os.environ)
    env.update({"CSRBT_HARNESS_ENABLED": "true", "CSRBT_HARNESS_TOKEN": TOKEN})
    lines = [{"op": "discover", "token": TOKEN},
             {"op": "execute", "token": TOKEN, "plugin": "csrbt-lab",
              "command": {"request_id": "s1", "action": "battle",
                          "arguments": {"workload": "SEQUENTIAL", "ops": 200, "seed": 1}}},
             {"op": "quit", "token": TOKEN}]
    p = subprocess.run([sys.executable, os.path.join(_kit.TOOLS_DIR, "harness_stdio.py"), "--target", "lab"],
                       input="\n".join(json.dumps(l) for l in lines) + "\n",
                       capture_output=True, text=True, env=env, timeout=180)
    outs = [json.loads(l) for l in p.stdout.strip().split("\n") if l.strip()]
    ck(p.returncode == 0 and len(outs) == 3 and outs[1]["ok"] and outs[1]["output"]["workload"] == "SEQUENTIAL",
       "--target lab serves the lab over stdio: rc=%d %s" % (p.returncode, p.stderr.strip()[-120:]))
    plug.close()

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
