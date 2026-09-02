# -*- coding: utf-8 -*-
"""Tasks: what an operator is for (ADR-125).

tools/harness_tasks.py runs goal-shaped tasks -- steps with expectations,
references between steps, a verdict graded CONFIRMED / REFUTED the way the
science engine grades a protocol -- through the real transport. This suite
pins what makes a verdict believable:

  A. the grammar: dotted paths (with escaped dots), references that resolve
     or are DEFECTS, every operator, a literal against a reference
  B. the task files: each loads, is named by its file, names a target the
     builder stands up, refers only to earlier steps, and the canary
     declares it must FAIL
  C. the grader on the fixture: the canary is REFUTED and held; the buckets
     task is PASSed with every expectation confirmed; a task that references
     a missing path is a DEFECT, not a refutation; a target that goes away is
     a DEFECT; an unexpected failure ends the task FAIL; over MCP the same
     verdicts, expectation for expectation
  D. the real targets: every organism, lab and page task PASSes through the
     gateway (NOT VERIFIED without the builds)
  E. the committed ledger: one entry per task file, every one held, each
     naming its transport
  F. traces (ADR-126): the MCP server records every call and observation;
     grade_trace holds a trace to a task -- required steps in order, probes
     anywhere after, one call per step, a step no call satisfies UNMET, a
     failure the step did not ask for skipped over, "$." the response's
     own; a trace that took the fixture's canary task is graded FAIL and
     held; and the committed traces -- a model's, planning from the goal and
     tools/list alone -- are every one PASS

Run:  python3 tools/verify/verify_tasks.py
      CSRBT_TASKS_QUICK=1 python3 tools/verify/verify_tasks.py   # A-C and E only (the mutant runner)
"""
import copy, glob, io, json, os, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_tasks as T

P = F = 0
unverified = []
QUICK = os.environ.get("CSRBT_TASKS_QUICK") == "1"
MUTATE_ROLE = "subject"      # the temp dir here holds one malformed task file, not fixture pages


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- A. the grammar ----------------------------------------------------------
ck(T.parts_of("a.b.c") == ["a", "b", "c"] and T.parts_of("snapshot.argumentPools.pooled\\.slot.0") ==
   ["snapshot", "argumentPools", "pooled.slot", "0"],
   "a dotted path splits on dots, and an escaped dot stays in its key")
resp = {"ok": True, "output": {"n": 3, "items": [{"k": 1}, {"k": 2}]}, "snapshot": {"argumentPools": {"p.s": ["x"]}}}
ck(T.dig(resp, "output.items.1.k") == 2 and T.dig(resp, "snapshot.argumentPools.p\\.s.0") == "x",
   "dig follows dicts by key and lists by index")
for bad in ("output.none", "output.items.9", "output.n.deeper", "nope"):
    try:
        T.dig(resp, bad)
        ck(False, "dig accepted a path that is not there: %s" % bad)
    except KeyError:
        ck(True, "")
done = {"a": resp}
ck(T.resolve({"x": "$a.output.n", "y": ["$a.ok", 5], "z": "plain"}, done, "t") == {"x": 3, "y": [True, 5], "z": "plain"},
   "references resolve inside dicts and lists, literals pass through")
ck(T.resolve("$a", done, "t") is resp, "a bare step reference is the whole response")
for ref in ("$b.output.n", "$a.output.none"):
    try:
        T.resolve(ref, done, "t")
        ck(False, "an unresolvable reference was tolerated: %s" % ref)
    except T.TaskDefect as e:
        ck("reference" in str(e), "an unresolvable reference is a task DEFECT: %s" % str(e)[:60])
g = dict((p, v) for p, v, _ in T.grade({"ok": True, "output.n": "$a.output.n", "output.n2": {"op": ">=", "value": 3},
                                        "output.n3": {"op": "<", "value": 3}, "output.items": {"op": "contains", "value": {"k": 1}},
                                        "output.n4": {"op": "in", "value": [1, 3]}, "output.none": {"op": "exists", "value": False},
                                        "output.n5": {"op": "exists", "value": True}, "code": None, "output.n6": {"op": "!=", "value": 3}},
                                       {"ok": True, "output": {"n": 3, "n2": 3, "n3": 3, "n4": 3, "n5": 3, "n6": 3, "items": [{"k": 1}]}},
                                       done, "t"))
ck(g == {"ok": "CONFIRMED", "output.n": "CONFIRMED", "output.n2": "CONFIRMED", "output.n3": "REFUTED",
         "output.items": "CONFIRMED", "output.n4": "CONFIRMED", "output.none": "CONFIRMED", "output.n5": "CONFIRMED",
         "code": "REFUTED", "output.n6": "REFUTED"},
   "every operator grades, a reference grades as its value, a missing path is REFUTED unless exists:false: %s" % g)
ck(T.grade({"output.n": {"op": ">", "value": "x"}}, {"output": {"n": 3}}, {}, "t")[0][1] == "REFUTED",
   "an incomparable pair is REFUTED, not a crash")

# ---- B. the task files -------------------------------------------------------
files = sorted(glob.glob(os.path.join(T.TASKS_DIR, "*.json")))
tasks = [T.load_task(f) for f in files]
ck(len(tasks) >= 8, "%d task files" % len(tasks))
ck(all(t["id"] == os.path.basename(t["_path"])[:-5] for t in tasks), "each task is named by its file")
ck(all(t["target"] in T.PLUGIN for t in tasks), "each task names a target the builder stands up")
ck(all(len(t["goal"]) > 40 for t in tasks), "each task states its goal in words")
for t in tasks:
    seen = set()
    okrefs = True
    for s in t["steps"]:
        for v in json.dumps([s.get("arguments"), s.get("expect")]).split('"'):
            if v.startswith("$") and not v.startswith("$."):        # "$." is the step's own response
                okrefs = okrefs and v[1:].partition(".")[0] in seen
        seen.add(s["id"])
    ck(okrefs, "%s: every reference names an earlier step" % t["id"])
ck({t["target"] for t in tasks} == {"organism", "lab", "page", "fixture"}, "every target has a task")
canaries = [t for t in tasks if t.get("must") == "FAIL"]
ck(len(canaries) == 1 and canaries[0]["target"] == "fixture", "exactly one canary, on the fixture, declares it must FAIL")
try:
    T.load_task(os.path.join(_kit.TOOLS_DIR, "harness_walk.py"))
    ck(False, "a non-task loaded")
except (T.TaskDefect, ValueError):
    ck(True, "")
import tempfile
tmp = tempfile.mkdtemp()
badf = os.path.join(tmp, "bad.json")
io.open(badf, "w").write(json.dumps({"id": "bad", "target": "fixture", "goal": "x" * 50,
                                     "steps": [{"id": "a", "action": "ok", "expect": {"ok": {"op": "~", "value": 1}}}]}))
try:
    T.load_task(badf)
    ck(False, "an unknown operator was accepted at load")
except T.TaskDefect as e:
    ck("op" in str(e), "an unknown operator is a task DEFECT at load: %s" % str(e)[:50])

# ---- C. the grader on the fixture --------------------------------------------
by = dict((t["id"], t) for t in tasks)
fx = [by["fixture-canary"], by["fixture-buckets"]]
res = T.run_tasks(fx)
ck(res["fixture-canary"]["verdict"] == "FAIL" and res["fixture-canary"]["held"] and res["fixture-canary"]["refuted"] == 1
   and res["fixture-canary"]["confirmed"] == 2 and len(res["fixture-canary"]["steps"]) == 2,
   "the canary is REFUTED at its second step, stops there, and is HELD because it said it must fail: %s"
   % {k: res["fixture-canary"][k] for k in ("verdict", "held", "confirmed", "refuted")})
ck(res["fixture-buckets"]["verdict"] == "PASS" and res["fixture-buckets"]["held"] and res["fixture-buckets"]["refuted"] == 0
   and res["fixture-buckets"]["confirmed"] >= 9,
   "the buckets task PASSes: a refusal, a decline and a failure are results a task can expect, and a reference "
   "reads a pool into the next call: %s" % {k: res["fixture-buckets"][k] for k in ("verdict", "confirmed", "refuted")})
steps = dict((s["id"], s) for s in res["fixture-buckets"]["steps"])
ck(steps["r"]["result"] == "refused" and steps["d"]["result"] == "declined" and steps["b"]["result"] == "failed"
   and steps["slot"]["result"] == "driven" and steps["pair"]["result"] == "driven",
   "each step's result is its bucket: %s" % dict((k, v["result"]) for k, v in steps.items()))
broken = copy.deepcopy(by["fixture-buckets"])
broken["id"] = "fixture-broken-ref"
broken["steps"][4]["arguments"] = {"slot": "$look.snapshot.nothing.here"}
r2 = T.run_tasks([broken])["fixture-broken-ref"]
ck(r2["verdict"] == "DEFECT" and not r2["held"] and r2["steps"][-1]["result"] == "DEFECT" and "reference" in r2["steps"][-1]["detail"],
   "a reference to a path that is not in the response is a task DEFECT, not a refutation of the target: %s"
   % r2["steps"][-1].get("detail", "")[:70])
unexp = {"id": "fixture-unexpected-failure", "target": "fixture", "goal": "a failure nobody expected ends the task" * 2,
         "steps": [{"id": "a", "action": "ok"}, {"id": "b", "action": "boom"}, {"id": "c", "action": "ok"}]}
r3 = T.run_tasks([unexp])["fixture-unexpected-failure"]
ck(r3["verdict"] == "FAIL" and len(r3["steps"]) == 2 and r3["steps"][1]["result"] == "failed" and "failed" in r3["steps"][1]["detail"],
   "a step that FAILS with no expectation about it is the target's failure and ends the task: %s" % r3["steps"][1].get("detail", "")[:60])
old = dict(os.environ)
os.environ["CSRBT_FIXTURE_DIE"] = "1"
try:
    gone = {"id": "fixture-gone", "target": "fixture", "goal": "the target goes away half way through the task" * 2,
            "steps": [{"id": "a", "action": "ok"}, {"id": "d", "action": "die"}, {"id": "b", "action": "ok", "expect": {"ok": True}}]}
    r4 = T.run_tasks([gone])["fixture-gone"]
finally:
    os.environ.clear()
    os.environ.update(old)
ck(r4["verdict"] == "DEFECT" and "went away" in r4["steps"][-1].get("detail", ""),
   "a target that goes away mid-task is a DEFECT (unavailable), never a refutation: %s" % r4["steps"][-1].get("detail", "")[:60])
resm = T.run_tasks(fx, transport="mcp")
same = all(resm[k]["verdict"] == res[k]["verdict"] and resm[k]["held"] == res[k]["held"] and
           [(s["id"], s["result"], [e["verdict"] for e in s.get("expectations", [])]) for s in resm[k]["steps"]] ==
           [(s["id"], s["result"], [e["verdict"] for e in s.get("expectations", [])]) for s in res[k]["steps"]]
           for k in res)
ck(same and all(resm[k]["transport"] == "mcp" for k in resm),
   "over MCP the same tasks reach the same verdicts, step for step and expectation for expectation")

# ---- D. the real targets -------------------------------------------------------
cp_org = os.path.join(os.environ.get("CSRBT_WHOLEHOG") or os.path.join(_kit.ROOT, "..", "WholeHog"),
                      "build", "harness", "classpath.txt")
cp_lab = os.path.join(_kit.ROOT, "csrbt-experimental", "build", "harness", "classpath.txt")
if QUICK:
    print("QUICK: the organism, lab and page tasks are not run (CSRBT_TASKS_QUICK=1)")
else:
    for tgt, cp in (("organism", cp_org), ("lab", cp_lab), ("page", None)):
        if cp and not os.path.isfile(cp):
            unverified.append("D  the %s tasks -- not built" % tgt)
            continue
        rs = T.run_tasks([t for t in tasks if t["target"] == tgt])
        for k, r in rs.items():
            ck(r["verdict"] == "PASS" and r["held"] and r["refuted"] == 0,
               "%s: PASS through the gateway (%d confirmed): %s" % (k, r["confirmed"],
                                                                  [(s["id"], e["detail"]) for s in r["steps"]
                                                                   for e in s.get("expectations", []) if e["verdict"] != "CONFIRMED"][:2]))
        ck(sum(r["confirmed"] for r in rs.values()) >= 8, "%s: the tasks carry real expectations, %d confirmed"
           % (tgt, sum(r["confirmed"] for r in rs.values())))

# ---- E. the committed ledger ---------------------------------------------------
led = T.LEDGER
ck(os.path.isfile(led), "the task ledger exists")
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["tasks"]
    runs = {k: e for k, e in L.items() if not k.endswith("@trace")}
    ck(set(runs) == {t["id"] for t in tasks}, "one entry per task file, and none for a task that is gone: %s"
       % sorted(set(runs) ^ {t["id"] for t in tasks}))
    ck(all(e.get("held") and e.get("verdict") == e.get("must", "PASS") and e.get("transport") in ("stdio", "mcp")
           for e in runs.values()),
       "every committed task is held -- its verdict is the one it was written for -- and names its transport: %s"
       % [k for k, e in runs.items() if not e.get("held")])
    ck(sum(e.get("confirmed", 0) for e in runs.values()) >= 60,
       "the ledger carries %d confirmed expectations" % sum(e.get("confirmed", 0) for e in runs.values()))

# ---- F. traces ---------------------------------------------------------------
trace = [{"action": "put", "arguments": {"key": 1}, "response": {"ok": True, "output": {}, "snapshot": {"size": 1}}},
         {"action": "look", "arguments": {}, "response": {"ok": True, "output": {"n": 1}, "snapshot": {"size": 1}}},
         {"action": "boom", "arguments": {}, "response": {"ok": False, "code": "failed", "message": "x", "output": {}}},
         {"action": "put", "arguments": {"key": 2}, "response": {"ok": True, "output": {}, "snapshot": {"size": 2}}},
         {"action": "count", "arguments": {}, "response": {"ok": True, "output": {"count": 2}, "snapshot": {"size": 2}}},
         {"action": "put", "arguments": {"key": 3}, "response": {"ok": False, "code": "conflict", "output": {}}}]
task = {"id": "t", "target": "fixture", "goal": "g" * 50, "steps": [
    {"id": "a", "action": "put", "expect": {"ok": True}},
    {"id": "b", "action": "put", "expect": {"snapshot.size": 2}},
    {"id": "c", "action": "count", "expect": {"output.count": "$b.snapshot.size", "snapshot.size": "$.output.count"}},
    {"id": "p", "action": "look", "optional": True, "expect": {"output.n": 1}},
    {"id": "q", "action": "boom", "optional": True, "expect": {"code": "failed"}},
    {"id": "z", "action": "put", "optional": True, "expect": {"code": "conflict"}}]}
g = T.grade_trace(task, trace)
calls = dict((s["id"], s.get("call")) for s in g["steps"])
ck(g["verdict"] == "PASS" and g["held"] and calls == {"a": 0, "b": 3, "c": 4, "p": 1, "q": 2, "z": 5} and
   g["met"] == 3 and g["required"] == 3 and g["probed"] == 3 and g["calls"] == 6,
   "a trace is held to a task: required steps in order by the next unused call, probes anywhere, one call per "
   "step, a self-reference reads the response's own fields: %s" % calls)
g2 = T.grade_trace(dict(task, steps=task["steps"][:3] + [{"id": "d", "action": "count", "expect": {"output.count": 3}}]), trace)
ck(g2["verdict"] == "FAIL" and not g2["held"] and g2["steps"][-1]["result"] == "UNMET" and g2["unmet"] == 1,
   "a step no call satisfies is UNMET and fails the task: %s" % g2["steps"][-1].get("detail", "")[:60])
g3 = T.grade_trace({"id": "t3", "target": "fixture", "goal": "g" * 50, "steps": [
    {"id": "a", "action": "boom"}]}, trace)
ck(g3["verdict"] == "FAIL" and g3["steps"][0]["result"] == "UNMET",
   "a failure the step did not ask for never satisfies it, even a step with no expectations")
g4 = T.grade_trace({"id": "t4", "target": "fixture", "goal": "g" * 50, "steps": [
    {"id": "c", "action": "count"}, {"id": "a", "action": "put", "expect": {"ok": True}}]}, trace)
ck(g4["verdict"] == "FAIL" and g4["steps"][0].get("call") == 4 and g4["steps"][1]["result"] == "UNMET",
   "order is order: a required put after the count has no ok:true call left")
g5 = T.grade_trace({"id": "t5", "target": "fixture", "goal": "g" * 50, "steps": [
    {"id": "s", "action": "look", "optional": True, "expect": {"output.n": 1}}, {"id": "l", "action": "look", "expect": {"ok": True}}]}, trace)
ck(g5["verdict"] == "PASS" and g5["steps"][1].get("call") == 1 and g5["steps"][0]["result"] == "SKIPPED",
   "a probe never takes a call a required step needs (the first page trace lost its read-page that way)")
try:
    T.load_trace(os.path.join(_kit.TOOLS_DIR, "harness_walk.py"))
    ck(False, "a non-trace loaded")
except T.TaskDefect:
    ck(True, "")
# the MCP server records a trace, and the fixture's tasks graded from it hold
import harness_contract as C, harness_mcp as M, harness_plugin_fixture as FX
tr = os.path.join(tmp, "fixture.jsonl")
gw = C.Gateway(C.Registry([FX.FixturePlugin(can_die=False)]),
               C.Policy(token="trace-suite-" + "x" * 20, enabled=True,
                        allow={"DRAFT": True, "MUTATE": True, "SENSITIVE_READ": True}))
srv = M.Server(gw, "trace-suite-" + "x" * 20, trace=tr)
srv.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": M.PROTOCOL, "capabilities": {}, "clientInfo": {"name": "s"}}})
srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
srv.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "csrbt_fixture__ok", "arguments": {}}})
srv.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "csrbt_fixture__refuse", "arguments": {"n": 1}}})
srv.handle({"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "harness://csrbt-fixture/snapshot"}})
srv.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "csrbt_fixture__ok", "arguments": {}}})
srv.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "csrbt_fixture__decline", "arguments": {}}})
srv._trace.close()
rec = T.load_trace(tr)
ck([e["action"] for e in rec] == ["ok", "refuse", "observe", "ok", "decline"] and rec[1]["response"]["code"] == "invalid_argument"
   and rec[2]["response"]["snapshot"]["ready"] is True and "snapshot" in rec[0]["response"],
   "the MCP server records every call -- refusals included -- and every observation, with the gateway's whole "
   "response: %s" % [e["action"] for e in rec])
gc = T.grade_trace(by["fixture-canary"], rec)
ck(gc["verdict"] == "FAIL" and gc["held"] and gc["steps"][1]["result"] == "UNMET",
   "the canary graded from a trace: its 'ok declines' step is UNMET, the task FAILs, and it is held")
# the committed traces: a model's, planning from the goal and tools/list alone
tfiles = sorted(glob.glob(os.path.join(T.TRACES_DIR, "*.jsonl")))
ck(len(tfiles) == 6 and {os.path.basename(f)[:-6] for f in tfiles} == {t["id"] for t in tasks if t["target"] != "fixture"},
   "one committed trace per real task, none for the fixture's: %s" % [os.path.basename(f) for f in tfiles])
for f in tfiles:
    tid = os.path.basename(f)[:-6]
    gt = T.grade_trace(by[tid], T.load_trace(f))
    ck(gt["verdict"] == "PASS" and gt["held"] and gt["met"] == gt["required"],
       "%s: the model's trace meets every required step (%d of %d, %d probes, %d calls)"
       % (tid, gt["met"], gt["required"], gt["probed"], gt["calls"]))
    ck(any(e["arguments"] != (s.get("arguments") or {}) for e in T.load_trace(f) for s in by[tid]["steps"]
           if e["action"] == s["action"] and s.get("arguments")) or tid == "lab-run-shipped-protocol",
       "%s: and it is not the task's own steps replayed -- the arguments differ" % tid)
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["tasks"]
    traced = {k[:-6]: e for k, e in L.items() if k.endswith("@trace")}
    ck(set(traced) == {os.path.basename(f)[:-6] for f in tfiles} and all(e["held"] and e["graded"] == "trace" for e in traced.values()),
       "the ledger carries every trace's grade, held: %s" % sorted(traced))

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
