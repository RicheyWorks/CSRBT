# -*- coding: utf-8 -*-
"""Tasks: what an operator is for (ADR-125).

tools/harness_tasks.py runs goal-shaped tasks -- steps with expectations,
references between steps, a verdict graded CONFIRMED / REFUTED the way the
science engine grades a protocol -- through the real transport. This suite
pins what makes a verdict believable:

  A. the grammar: dotted paths (with escaped dots), references that resolve
     or are DEFECTS, every operator, a literal against a reference; and
     "@control:<name>" (ADR-128): a page control by id, then label, then
     host, scoped "host/label", the nth match, resolved from the latest
     snapshot, a DEFECT when nothing matches
  B. the task files: each loads, is named by its file, names a target the
     builder stands up, refers only to earlier steps, and the canaries --
     the fixture's and the page's -- declare they must FAIL
  C. the grader on the fixture: the canary is REFUTED and held; the buckets
     task is PASSed with every expectation confirmed; a task that references
     a missing path is a DEFECT, not a refutation; a target that goes away is
     a DEFECT; an unexpected failure ends the task FAIL; over MCP the same
     verdicts, expectation for expectation
  D. the real targets: every organism, lab and page task holds through the
     gateway -- PASS, or FAIL for a canary (NOT VERIFIED without the builds)
  E. the committed ledger: one entry per task file, every one held, each
     naming its transport (a trace's grade is "<id>@trace", a blind trace's
     "<id>@blind"; neither is a run)
  F. traces (ADR-126): the MCP server records every call and observation;
     grade_trace holds a trace to a task -- required steps in order, probes
     anywhere after, one call per step, a step no call satisfies UNMET, a
     failure the step did not ask for skipped over, "$." the response's
     own; a trace that took the fixture's canary task is graded FAIL and
     held; and the committed traces -- a model's, planning from the goal and
     tools/list alone -- are every one PASS
  F4. the fourth blind trial (ADR-194): the same four pages through the door
     the five slices built, graded by the same grader against the third
     trial's floors -- more outcomes reached, more claims confirmed, in fewer
     calls and one attempt each; and the rung the trial harness could not
     grant
  G. the science (ADR-128) and the whole kit (ADR-129): every data-entry,
     key, simulator and proof page has a task that enters data through the
     gateway and holds the page's report to a hand-checked oracle; every
     other routed page has a reference task that pins its outline; every
     routed page has exactly one; a task names its controls the page's way
     and never writes a selector down; the page canary claims a wrong
     figure and is refuted

Run:  python3 tools/verify/verify_tasks.py
      CSRBT_TASKS_QUICK=1 python3 tools/verify/verify_tasks.py   # A-C and E only (the mutant runner)
"""
import copy, glob, io, json, os, re, sys, tempfile

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
def _try_resolve(v):
    try:
        return T.resolve(v, done, "t")
    except Exception as e:                 # a mutant that treats $$ as a reference raises here
        return ("RAISED", str(e))
ck(_try_resolve("$$14.92") == "$14.92",
   "a leading $$ is one literal dollar sign: a task can hold '$14.92', which is what the "
   "greenhouse monitor prints for the electricity a run cost, and was being read as a reference "
   "to a step called 14.92 (ADR-155): %r" % (_try_resolve("$$14.92"),))
ck(_try_resolve({"cost": {"op": "==", "value": "$$0.04"}}) == {"cost": {"op": "==", "value": "$0.04"}},
   "...inside an expectation as well, where every value is resolved: %r"
   % (_try_resolve({"cost": {"op": "==", "value": "$$0.04"}}),))
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

# ---- ADR-133: two instruments, one number ------------------------------------
ck(T.grade({"a": {"op": "~=", "value": 1.227621, "tolerance": 0.005}}, {"a": "1.23"}, {}, "t")[0][1] == "CONFIRMED",
   "~= holds a page's rounded figure to an engine's full one: two instruments agreeing is a claim '==' cannot make")
ck(T.grade({"a": {"op": "~=", "value": 1.227621, "tolerance": 0.0001}}, {"a": "1.23"}, {}, "t")[0][1] == "REFUTED",
   "...and the tolerance is the claim: too tight, and it is REFUTED")
try:
    T.grade({"a": {"op": "~=", "value": 1}}, {"a": "1"}, {}, "t")
    ck(False, "~= without a tolerance was tolerated")
except T.TaskDefect as e:
    ck("needs a tolerance" in str(e),
       "~= without a tolerance is a task DEFECT: how close two instruments must be has no default: %s" % str(e)[:70])
ck(T.grade({"a": {"op": "~=", "value": 1, "tolerance": 1}}, {"a": "not a number"}, {}, "t")[0][1] == "REFUTED",
   "a value that is not a number is REFUTED, not a crash")

# ---- ADR-132: saying what is ABSENT ------------------------------------------
#
# The grammar could only say what a box holds, so a task asserting that a page
# had stopped printing something had to guess what replaced it. These four
# checks are the whole of the new claim: it holds when the string is not there,
# it fails when it is, a missing path does NOT prove absence (a typo in the path
# would otherwise read as evidence), and the mirror op reads the other way.
R = {"output": {"box": "the run is clean", "list": ["a", "b"]}}
gx = dict((p, v) for p, v, _ in T.grade(
    {"output.box": {"op": "excludes", "value": "INVARIANT FAILED"},
     "output.list": {"op": "excludes", "value": "c"},
     "output.box#2": {"op": "excludes", "value": "clean"}}, R, {}, "t"))
ck(gx.get("output.box") == "CONFIRMED" and gx.get("output.list") == "CONFIRMED",
   "excludes CONFIRMS when the value is not in the string or the list: %s" % gx)
ck(T.grade({"output.box": {"op": "excludes", "value": "clean"}}, R, {}, "t")[0][1] == "REFUTED",
   "excludes is REFUTED when the value IS there -- it is a claim, not a formality")
ck(T.grade({"output.gone": {"op": "excludes", "value": "anything"}}, R, {}, "t")[0][1] == "REFUTED",
   "a path that is not in the response does not prove absence: a task must name a box that exists")
gn = dict((p, v) for p, v, _ in T.grade(
    {"output.box": {"op": "not-in", "value": ["a", "b"]},
     "output.box#2": {"op": "not-in", "value": ["the run is clean"]}}, R, {}, "t"))
ck(gn.get("output.box") == "CONFIRMED", "not-in CONFIRMS when the value is not one of a set: %s" % gn)
ck(T.grade({"output.box": {"op": "not-in", "value": ["the run is clean"]}}, R, {}, "t")[0][1] == "REFUTED",
   "not-in is REFUTED when it is one of them")
try:
    T.grade({"output.box": {"op": "excldes", "value": "x"}}, R, {}, "t")
    ck(False, "a typo'd op was tolerated")
except T.TaskDefect as e:
    ck("unknown op" in str(e) and "excludes" in str(e),
       "an op the grader does not know is the TASK's DEFECT, not a finding about the kit, and the message names "
       "the ops it does know: %s" % str(e)[:90])
ck(sorted(T.OPS) == sorted(["==", "!=", ">", ">=", "<", "<=", "~=", "in", "not-in", "contains", "excludes", "exists"]),
   "ONE op table, read by the loader and the grader alike -- two would drift into a file accepted at load and "
   "rejected at grade: %s" % sorted(T.OPS))
# a path may carry a trailing "#n" label so a box can hold two claims: it says
# the refusal AND it no longer says the answer
g2 = T.grade({"output.box": {"op": "contains", "value": "clean"},
              "output.box#2": {"op": "excludes", "value": "FAILED"}}, R, {}, "t")
ck(sorted((p, v) for p, v, _ in g2) == [("output.box", "CONFIRMED"), ("output.box#2", "CONFIRMED")],
   "a trailing #n labels a second claim about the same path, graded and reported separately: %s" % g2)
ck(T.grade({"output.by.selOut.doubling time #2": {"op": "exists", "value": True}},
           {"output": {"by": {"selOut": {"doubling time #2": "4"}}}}, {}, "t")[0][1] == "CONFIRMED",
   "...and a read-report duplicate label, which has a SPACE before its #2, is a real path segment, not a label")
# ADR-128: a page control by the page's own name
snap = {"controls": [
    {"selector": "step_val:0", "kind": "step_val", "id": None, "host": "geoEntry", "label": "cName"},
    {"selector": "text_in:3", "kind": "text_in", "id": "cName", "host": "p-rec", "label": "working name"},
    {"selector": "dial_btn:0", "kind": "dial_btn", "id": None, "host": "rCov", "label": "4"},
    {"selector": "dial_btn:1", "kind": "dial_btn", "id": None, "host": "strEntry", "label": "4"},
    {"selector": "dial_btn:2", "kind": "dial_btn", "id": None, "host": "rCov", "label": "5"},
    {"selector": "action_btn:7", "kind": "action_btn", "id": None, "host": "iList", "label": "died"},
    {"selector": "action_btn:9", "kind": "action_btn", "id": None, "host": "iList", "label": "died"},
    {"selector": "pick_search:0", "kind": "pick_search", "id": None, "host": "genEntry", "label": "genus filter"},
    {"selector": "field_in:0", "kind": "field_in", "id": None, "host": "seedEntry", "label": "season #"},
    {"selector": "action_btn:11", "kind": "action_btn", "id": None, "host": None, "label": "Print / save PDF"},
    {"selector": "action_btn:12", "kind": "action_btn", "id": None, "host": "p-more", "label": "Print / save PDF"}]}
cd = {"look": {"ok": True, "snapshot": snap}}


def res(x, d=cd):
    try:
        return T.resolve(x, d, "t")
    except T.TaskDefect as e:
        return "DEFECT: " + str(e)


ck(res("@control:cName") == "text_in:3",
   "an id wins over a control merely labelled with that name, wherever it sits in the document")
ck(res("@control:working name") == "text_in:3" and res("@control:genEntry") == "pick_search:0",
   "then the label, then the host: a picker is named by the box it is mounted in")
ck(res({"selector": "@control:rCov/4"}) == {"selector": "dial_btn:0"} and
   res("@control:4") == "dial_btn:0" and res("@control:strEntry/4") == "dial_btn:1",
   "host/label scopes a label every dial shares to one dial")
ck(res("@control:iList/died#1") == "action_btn:9" and res("@control:died#0") == "action_btn:7",
   "#n is the nth match in document order: %s" % res("@control:iList/died#1"))
ck(res("@control:season #") == "field_in:0", "a label that ends in # is a label, not an index")
ck(res("@control:Print / save PDF") == "action_btn:11" and res("@control:p-more/Print / save PDF") == "action_btn:12",
   "a slash in a label is a label (ADR-174): a name that matches whole is taken whole, and only a name nothing "
   "answers to whole is read as host/label -- the food web's hostless print button is reachable, and the "
   "notebook's scoped one still is: %s / %s" % (res("@control:Print / save PDF"), res("@control:p-more/Print / save PDF")))
for bad in ("@control:nothing", "@control:rCov/4#3", "@control:iList/died#2"):
    r_ = res(bad)
    ck(isinstance(r_, str) and r_.startswith("DEFECT") and "no control" in r_,
       "a control nothing matches is a task DEFECT, not a refusal: %s -> %s" % (bad, str(r_)[:60]))
r_ = res("@control:cName", {"a": {"ok": True, "output": {}}})
ck(isinstance(r_, str) and r_.startswith("DEFECT") and "observed" in r_,
   "@control before any step carried a snapshot is a DEFECT: %s" % str(r_)[:60])
later = {"first": {"snapshot": snap}, "then": {"snapshot": {"controls": [
    {"selector": "text_in:9", "kind": "text_in", "id": "cName", "host": "p-rec", "label": "working name"}]}}}
ck(res("@control:cName", later) == "text_in:9",
   "the LATEST snapshot is the one resolved against -- the widgets rebuild and selectors are the moment's")

# ---- B. the task files -------------------------------------------------------
files = sorted(glob.glob(os.path.join(T.TASKS_DIR, "*.json")))
# a committed task that will not load is a FAILING CHECK, not a traceback: a
# suite that falls over has not noticed anything (ADR-136)
tasks, wont_load = [], []
for _f in files:
    try:
        tasks.append(T.load_task(_f))
    except T.TaskDefect as _e:
        wont_load.append("%s: %s" % (os.path.basename(_f), str(_e)[:90]))
ck(not wont_load, "every committed task file loads: %s" % wont_load[:3])
ck(len(tasks) >= 8, "%d task files" % len(tasks))
ck(all(t["id"] == os.path.basename(t["_path"])[:-5] for t in tasks), "each task is named by its file")
ck(all(t["target"] in T.PLUGIN for t in tasks), "each task names a target the builder stands up")
ck(all(len(t["goal"]) > 40 for t in tasks), "each task states its goal in words")
for t in tasks:
    seen = set()
    okrefs = True
    for s in t["steps"]:
        for v in json.dumps([s.get("arguments"), s.get("expect")]).split('"'):
            # "$." is the step's own response; "$$" is one literal dollar sign (ADR-155)
            if v.startswith("$") and not v.startswith("$.") and not v.startswith("$$"):
                okrefs = okrefs and v[1:].partition(".")[0] in seen
        seen.add(s["id"])
    ck(okrefs, "%s: every reference names an earlier step" % t["id"])
ck({t["target"] for t in tasks} == {"organism", "lab", "page", "fixture"}, "every target has a task")
canaries = [t for t in tasks if t.get("must") == "FAIL"]
ck({t["target"] for t in canaries} == {"fixture", "page"} and len(canaries) == 2,
   "two canaries declare they must FAIL: the fixture's and the page's: %s" % [t["id"] for t in canaries])
# ADR-133: a third kind of canary -- one written to be the TASK's own DEFECT
defects = [t for t in tasks if t.get("must") == "DEFECT"]
ck(len(defects) == 1 and defects[0]["id"] == "two-targets-canary",
   "one canary declares it must DEFECT: a step naming a target that does not exist is the task's fault, not any "
   "target's: %s" % [t["id"] for t in defects])
# ADR-136: a claim may not rest on a probe
probe_refs = [(t["id"], s["id"], v) for t in tasks for s in t["steps"] if not s.get("optional")
              for v in json.dumps([s.get("arguments"), s.get("expect")]).split('"')
              if v.startswith("$") and not v.startswith("$.")
              and v[1:].partition(".")[0] in set(x["id"] for x in t["steps"] if x.get("optional"))]
ck(not probe_refs, "no required step reads a probe's response -- a claim may not rest on a step an operator "
                   "may skip: %s" % probe_refs[:3])
_pr = os.path.join(tempfile.mkdtemp(), "probe.json")
io.open(_pr, "w").write(json.dumps({"id": "probe", "target": "fixture", "goal": "x" * 50, "steps": [
    {"id": "look", "action": "look", "optional": True},
    {"id": "need", "action": "count", "expect": {"output.count": "$look.output.n"}}]}))
try:
    T.load_task(_pr)
    ck(False, "a required step resting on a probe loaded")
except T.TaskDefect as e:
    ck("probe" in str(e), "a required step that reads a probe is a task DEFECT at load: %s" % str(e)[-60:])
_pr2 = os.path.join(os.path.dirname(_pr), "probe2.json")
io.open(_pr2, "w").write(json.dumps({"id": "probe2", "target": "fixture", "goal": "x" * 50, "steps": [
    {"id": "one", "action": "ok"},
    {"id": "look", "action": "look", "optional": True, "expect": {"output.n": "$one.output.n"}}]}))
try:
    ck(T.load_task(_pr2)["id"] == "probe2", "a PROBE may read a required step -- the rule is one-way")
except T.TaskDefect as e:
    ck(False, "a PROBE may read a required step -- the rule is one-way: %s" % str(e)[:80])

try:
    T.load_task(os.path.join(_kit.TOOLS_DIR, "harness_walk.py"))
    ck(False, "a non-task loaded")
except (T.TaskDefect, ValueError):
    ck(True, "")
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
    # ADR-142: `die` is the fixture's DESTRUCTIVE action, and since the runner
    # stopped opening every rung by default this task has to ask -- which is the
    # rule working, and is asserted directly in section H.
    gone = {"id": "fixture-gone", "target": "fixture", "goal": "the target goes away half way through the task" * 2,
            "policy": {"allow": ["SENSITIVE_READ", "DRAFT", "MUTATE", "DESTRUCTIVE"], "needs": ["d"],
                       "why": "the goal is what a task does when its target dies, and `die` is the "
                              "fixture's destructive action"},
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

# ---- C2. a refusal is a move too (ADR-145) -----------------------------------
# The gateway raises before it observes, so a refused response carries no
# snapshot -- and the next "@control:<name>" then resolved against the last
# SUCCESSFUL step's snapshot. On the collection sheet that is not a detail: a
# filter that matches nothing rebuilds the host picker, so the selector the
# older snapshot gave pointed at an element that was no longer inside one, and
# the next pick was refused as "not a picker" -- the runner blaming the page for
# a stale name of its own.
refused_task = {"id": "fixture-refusal-snapshot", "target": "fixture",
                "goal": "a step that is refused still leaves the runner looking at the page as it "
                        "is now, not as it was before the refusal",
                "steps": [{"id": "a", "action": "ok"},
                          {"id": "no", "action": "refuse", "arguments": {"n": 3},
                           "expect": {"ok": False, "code": "invalid_argument",
                                      "snapshot.ready": True}},
                          {"id": "after", "action": "ok", "expect": {"ok": True}}]}
rr = T.run_tasks([refused_task])["fixture-refusal-snapshot"]
ck(rr["verdict"] == "PASS" and rr["held"],
   "a task whose step reads the REFUSED step's snapshot holds: the refusal carries one: %s"
   % [(x["id"], x["result"], x.get("detail", "")[:40]) for x in rr["steps"]])
ck(rr["steps"][1]["result"] == "refused",
   "...and the refusal is still a refusal, not turned into something else: %s" % rr["steps"][1]["result"])

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
            ck(r["held"] and r["verdict"] == r["must"] and (r["refuted"] == 0 or r["must"] == "FAIL"),
               "%s: held through the gateway (%d confirmed): %s" % (k, r["confirmed"],
                                                                  [(s["id"], e["detail"]) for s in r["steps"]
                                                                   for e in s.get("expectations", []) if e["verdict"] != "CONFIRMED"][:2]))
        ck(sum(r["confirmed"] for r in rs.values()) >= 8, "%s: the tasks carry real expectations, %d confirmed"
           % (tgt, sum(r["confirmed"] for r in rs.values())))

# ---- ADR-135: a control the page never named --------------------------------
kindsnap = {"controls": [
    {"selector": "drop_zone:0", "kind": "drop_zone", "id": None, "host": None,
     "label": "Overview Interactive Lab Lab Manual Teacher's Guide"},
    {"selector": "text_in:0", "kind": "text_in", "id": "wb-field", "host": "main", "label": "field"},
    {"selector": "drop_zone:1", "kind": "drop_zone", "id": None, "host": None, "label": ""},
]}
kd = {"s": {"snapshot": kindsnap}}
def _fc(name):
    """find_control, reporting a refusal rather than dying of it: a suite that
    crashes on a mutation has not noticed it, it has fallen over."""
    try:
        return T.find_control(name, kd, "t")
    except T.TaskDefect as e:
        return "DEFECT: %s" % str(e)[:60]


ck(_fc("kind=drop_zone") == "drop_zone:0",
   "a control the page never named is nameable by WHAT IT IS: the lab's drop zone is the page's own <body>, "
   "with no id and the whole nav bar for a label -- got %s" % _fc("kind=drop_zone"))
ck(_fc("kind=drop_zone#1") == "drop_zone:1", "and #n picks among them: %s" % _fc("kind=drop_zone#1"))
ck(T.find_control("wb-field", kd, "t") == "text_in:0", "naming by id still wins, unchanged")
try:
    T.find_control("kind=telescope", kd, "t")
    ck(False, "a kind nothing matches resolved")
except T.TaskDefect as e:
    ck("no control named" in str(e), "a kind nothing matches is the task's DEFECT: %s" % str(e)[:60])

# ---- ADR-133: two targets, one task ------------------------------------------
#
# The runner's contract for a multi-target task, held without a browser or a
# JVM: a fake wire per target, so the checks are about the RUNNER -- which wire
# each step went to, that a reference crosses targets, that a step naming a
# target nobody opened is the task's defect, and that every wire is closed in
# the reverse of the order it was opened.


class FakeWire(object):
    """Records what it was asked, answers from a script, and remembers when it
    was closed."""
    LOG = []

    def __init__(self, name, answers):
        self.name, self.answers, self.calls, self.closed = name, answers, [], False

    def op(self, kind, plugin=None, command=None):
        self.calls.append((kind, plugin, (command or {}).get("action")))
        if kind == "discover":
            return {"ok": True}
        act = (command or {}).get("action") if command else "observe"
        return dict(self.answers.get(act, {"ok": True, "output": {}, "snapshot": {}}))

    def close(self):
        self.closed = True
        FakeWire.LOG.append(self.name)


ORG = FakeWire("organism", {"report": {"ok": True, "output": {"size": 3}, "snapshot": {"size": 3}}})
PAGE = FakeWire("page", {"read-report": {"ok": True, "output": {"n": 3}, "snapshot": {}}})
two = {"id": "t2", "target": "organism", "goal": "g",
       "steps": [{"id": "a", "action": "report", "expect": {"ok": True}},
                 {"id": "b", "target": "page", "action": "read-report",
                  "expect": {"output.n": "$a.output.size"}}]}
res = T.run_task(two, ORG, "csrbt-organism",
                 {"organism": (ORG, "csrbt-organism"), "page": (PAGE, "csrbt-page")})
ck(res["verdict"] == "PASS" and res["confirmed"] == 2,
   "a task can drive two targets in one run: %s %s" % (res["verdict"], res["confirmed"]))
ck([c[1] for c in ORG.calls] == ["csrbt-organism"] and [c[1] for c in PAGE.calls] == ["csrbt-page"],
   "each step went to the wire its target names, under that target's plugin id: %s / %s"
   % (ORG.calls, PAGE.calls))
ck(res["targets"] == ["organism", "page"],
   "the ledger entry names every target the task used, not just the one it declares: %s" % res["targets"])
ck(any(e["verdict"] == "CONFIRMED" for st in res["steps"] for e in st["expectations"]),
   "a reference resolves ACROSS targets: the page's figure held to the organism's size")

missing = T.run_task(two, ORG, "csrbt-organism", {"organism": (ORG, "csrbt-organism")})
ck(missing["verdict"] == "DEFECT" and "did not open" in (missing["steps"][-1].get("detail") or ""),
   "a step naming a target the runner did not open is the TASK's defect, not a refusal: %s"
   % missing["steps"][-1].get("detail"))

# closing order: a task that opened two targets closes them in the reverse of
# the order it opened them, so a target that another one depends on outlives it
FakeWire.LOG = []
A, B = FakeWire("first", {}), FakeWire("second", {})
saved = dict(T.PLUGIN)
try:
    T.PLUGIN.update({"first": "csrbt-fixture", "second": "csrbt-fixture"})
    orig = T.wire_for
    made = iter([A, B])
    T.wire_for = lambda transport, token, **kw: next(made)
    T.run_tasks([{"id": "closing", "target": "first", "goal": "g", "must": "PASS",
                  "steps": [{"id": "x", "action": "ok"},
                            {"id": "y", "target": "second", "action": "ok"}]}], log=None)
finally:
    T.wire_for = orig
    T.PLUGIN.clear(); T.PLUGIN.update(saved)
ck(FakeWire.LOG == ["second", "first"] and A.closed and B.closed,
   "every target a task opened is closed, in the reverse of the order it was opened: %s" % FakeWire.LOG)

# a target that does not exist is the TASK's defect, and a canary written to be
# one is HELD when it defects -- run_tasks decides both, and neither is reached
# by the FakeWire path above
out = T.run_tasks([{"id": "telescope", "target": "fixture", "goal": "g", "must": "DEFECT",
                    "steps": [{"id": "x", "target": "telescope", "action": "ok"}]}], log=None)
e = out["telescope"]
ck(e["verdict"] == "DEFECT" and "unknown target" in (e.get("detail") or ""),
   "a step naming a target that does not exist is the task's DEFECT, and the message says so: %s" % e.get("detail"))
ck(e["held"] is True and e.get("transport") == "stdio",
   "...and a canary written to be a DEFECT is HELD when it defects, and still names its transport: held=%s "
   "transport=%s" % (e["held"], e.get("transport")))

# ---- E. the committed ledger ---------------------------------------------------
led = T.LEDGER
ck(os.path.isfile(led), "the task ledger exists")
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["tasks"]
    runs = {k: e for k, e in L.items() if not k.endswith(("@trace", "@blind"))}
    ck(set(runs) == {t["id"] for t in tasks}, "one entry per task file, and none for a task that is gone: %s"
       % sorted(set(runs) ^ {t["id"] for t in tasks}))
    ck(all(e.get("held") and e.get("verdict") == e.get("must", "PASS") and e.get("transport") in ("stdio", "mcp")
           for e in runs.values()),
       "every committed task is held -- its verdict is the one it was written for -- and names its transport: %s"
       % [k for k, e in runs.items() if not e.get("held")])
    ck(sum(e.get("confirmed", 0) for e in runs.values()) >= 1200,
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
# ADR-136: an observation rides every response
obs_trace = [{"action": "put", "arguments": {"key": 1},
              "response": {"ok": True, "output": {}, "snapshot": {"size": 1, "gapped": False}}},
             {"action": "boom", "arguments": {}, "response": {"ok": False, "code": "failed", "output": {}}}]
og = T.grade_trace({"id": "og", "target": "fixture", "goal": "g" * 50, "steps": [
    {"id": "see", "action": "observe", "expect": {"snapshot.size": 1, "snapshot.gapped": False}}]}, obs_trace)
ck(og["verdict"] == "PASS" and og["steps"][0].get("call") == 0,
   "an observe step is met by the snapshot on ANY response -- an operator who read the state off the answer it "
   "already had has observed, and a separate resources/read is a ceremony the goal never asked for")
og2 = T.grade_trace({"id": "og2", "target": "fixture", "goal": "g" * 50, "steps": [
    {"id": "see", "action": "observe", "expect": {"ok": True}}]},
    [{"action": "count", "arguments": {}, "response": {"ok": True, "output": {"count": 1}}}])
ck(og2["verdict"] == "FAIL" and og2["steps"][0]["result"] == "UNMET",
   "and a response carrying no snapshot observes nothing: the step is still UNMET")
og3 = T.grade_trace({"id": "og3", "target": "fixture", "goal": "g" * 50, "steps": [
    {"id": "c", "action": "count", "expect": {"snapshot.size": 1}}]}, obs_trace)
ck(og3["verdict"] == "FAIL" and og3["steps"][0]["result"] == "UNMET",
   "the licence is observe's alone: every other step is still met only by the action it names, snapshot or no")

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
ck(len(tfiles) == 6 and {os.path.basename(f)[:-6] for f in tfiles} <= {t["id"] for t in tasks if t["target"] != "fixture"}
   and {by[os.path.basename(f)[:-6]]["target"] for f in tfiles} == {"organism", "lab", "page"},
   "the six committed traces each name a real task, on every real target, none the fixture's: %s"
   % [os.path.basename(f) for f in tfiles])
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

# ---- F2. the blind trial (ADR-136) -------------------------------------------
#
# The six traces above were produced by the session that had written the tasks
# earlier the same day. It knew the answers. These six were produced by
# operators that could not: a fresh context each, given the task's goal
# sentence VERBATIM and a JSON-RPC console, working in a copy of the repo with
# tools/tasks, tools/traces, the ledger and every ADR deleted.
#
# This is the strongest check in the file, and the only one that is empirical
# rather than structural: a task whose required steps pin the author's route
# rather than the goal's claim STOPS GRADING against a blind trace, and this
# block fails. It is the regression guard for every task-shape finding the
# trial produced -- there is no rule here that says "do not pin a constant",
# only six operators who did not know what the constant was.
bfiles = sorted(glob.glob(os.path.join(T.BLIND_DIR, "*.jsonl")))
ck(len(bfiles) == 6 and {os.path.basename(f)[:-6] for f in bfiles} <= {t["id"] for t in tasks if t["target"] != "fixture"}
   and {by[os.path.basename(f)[:-6]]["target"] for f in bfiles} == {"organism", "lab", "page"},
   "six blind traces, each naming a real task, on every real target: %s" % [os.path.basename(f) for f in bfiles])
prov = os.path.join(T.BLIND_DIR, "PROVENANCE.md")
ptext = io.open(prov, encoding="utf-8").read() if os.path.isfile(prov) else ""
ck("verbatim" in ptext and "mis-conducted" in ptext and len(ptext) > 1500,
   "the blind traces carry a provenance that states the conditions verbatim, and owns the one run that was "
   "mis-conducted -- a trial whose conduct is not on the record proves nothing")
rode = skipped = 0
for f in bfiles:
    tid = os.path.basename(f)[:-6]
    tr = T.load_trace(f)
    gb = T.grade_trace(by[tid], tr)
    ck(gb["verdict"] == "PASS" and gb["held"] and gb["met"] == gb["required"],
       "%s: an operator who never saw the task meets every required step (%d of %d, %d of %d probes, %d calls): %s"
       % (tid, gb["met"], gb["required"], gb["probed"], gb["probes"], gb["calls"],
          [(x["id"], x.get("detail", "")[:60]) for x in gb["steps"] if x["result"] == "UNMET"][:2]))
    ck(any(e["arguments"] != (s.get("arguments") or {}) for e in tr for s in by[tid]["steps"]
           if e["action"] == s["action"] and s.get("arguments")) or tid == "lab-run-shipped-protocol",
       "%s: and it is not the task's own steps replayed -- the arguments differ" % tid)
    for x in gb["steps"]:
        if x["result"] == "SKIPPED":
            skipped += 1
        elif x["action"] == "observe" and "call" in x and tr[x["call"]]["action"] != "observe":
            rode += 1
ck(rode >= 1, "at least one blind operator met an observe step by reading the snapshot off a response it already "
              "had -- the rule the trial found is exercised by the evidence, not only by the fixture (%d)" % rode)
ck(skipped >= 3, "and blind operators skipped probes they were never told to take (%d) -- which is why no required "
                 "step may rest on one" % skipped)
_out = io.StringIO()
_save, sys.stdout = sys.stdout, _out
try:
    _rc = T.main(["--grade-trace", "all", "--no-ledger"])
finally:
    sys.stdout = _save
_lines = [l for l in _out.getvalue().split("\n") if "required steps met" in l]
ck(_rc == 0 and len(_lines) == 12 and sum(1 for l in _lines if " blind " in l) == 6
   and all("PASS" in l and "held" in l for l in _lines),
   "--grade-trace all grades every trace it has, sighted and blind, and says so on every line it prints: "
   "%d line(s), %d blind" % (len(_lines), sum(1 for l in _lines if " blind " in l)))
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["tasks"]
    blind = {k[:-6]: e for k, e in L.items() if k.endswith("@blind")}
    ck(set(blind) == {os.path.basename(f)[:-6] for f in bfiles}
       and all(e["held"] and e["verdict"] == "PASS" and e["blind"] and e["trace"].startswith("blind/")
               for e in blind.values()),
       "the ledger carries every blind grade beside the sighted one, each marked blind: %s" % sorted(blind))

# ---- F3. the third blind trial: outcomes, not routes (ADR-187) --------------
#
# ADR-141's trial could not press a button. This one, under the door as it
# stands, put four fresh operators on four science pages -- stand sheet,
# collection sheet, pheno tracker, breeding bench -- with the goal sentence
# verbatim and nothing else, and every one of them reported reaching every
# figure the goal names. Graded as a TRACE they are UNMET at the first step:
# a science task is a script, every step required in the author's order with
# the author's arguments. So the grader gained a second question: of the
# things the task reads the page to say, how many did this operator's trace
# reach, by any route? That is grade_outcomes, and the numbers below are what
# it measured on 2026-09-10. They are floors: a widened goal or a better door
# may raise them, and a change to the grader that lowers one is a regression.
BLIND3 = os.path.join(T.TRACES_DIR, "blind3")
b3 = sorted(glob.glob(os.path.join(BLIND3, "*.jsonl.gz")))
ck(len(b3) == 4 and {os.path.basename(f).split(".")[0] for f in b3} ==
   {"page-stand-sheet-science", "page-collection-sheet-science", "page-pheno-tracker-science", "page-breeding-bench-science"},
   "the third trial's four traces, gzipped, one per science page it was pointed at: %s" % [os.path.basename(f) for f in b3])
p3 = os.path.join(BLIND3, "PROVENANCE.md")
t3 = io.open(p3, encoding="utf-8").read() if os.path.isfile(p3) else ""
ck("verbatim" in t3 and "DESTRUCTIVE" in t3 and "attempt" in t3 and "outcomes" in t3 and len(t3) > 2500,
   "the third trial carries a provenance: the conditions verbatim, the rungs, how many attempts each operator took, "
   "and what the outcome grade means")
# the grader itself, on a fixture: order-free, partial credit, a reference claim unreachable, entry steps ignored
_ft = {"id": "fx", "target": "page", "goal": "g", "steps": [
    {"id": "e1", "action": "set-text", "arguments": {"selector": "text_in:1", "value": "3"}, "expect": {"ok": True, "output.value": "3"}},
    {"id": "r1", "action": "read-report", "expect": {"ok": True, "output.figures.a": "1", "output.figures.b": "2"}},
    {"id": "r2", "action": "read-report", "expect": {"output.figures.c": "3"}},
    {"id": "r3", "action": "read-control", "expect": {"output.value": "9"}},
    {"id": "r4", "action": "read-report", "expect": {"output.figures.a": {"op": "==", "value": "$r1.output.figures.a"}}},
    {"id": "r5", "action": "read-page", "expect": {"ok": True}}]}
_rr = lambda fig: {"action": "read-report", "arguments": {}, "response": {"ok": True, "output": {"figures": fig}}}
_tr = [_rr({"c": "3"}), {"action": "read-control", "arguments": {}, "response": {"ok": True, "output": {"value": "9"}}},
       _rr({"a": "1", "b": "5"}), {"action": "set-text", "arguments": {}, "response": {"ok": True, "output": {}}}]
_g = T.grade_outcomes(_ft, _tr)
ck([x[0]["id"] for x in T.outcomes_of(_ft)] == ["r1", "r2", "r3", "r4"],
   "a task's outcomes are its reading steps that claim something beyond ok -- entry steps and a bare read-page are not: %s"
   % [x[0]["id"] for x in T.outcomes_of(_ft)])
ck(_g["outcomes"] == 4 and _g["reached"] == 2 and _g["claims"] == 5 and _g["confirmed"] == 3 and _g["verdict"] == "PARTIAL",
   "outcomes are matched in any order (c before a), each by the call that confirms most of its claims, with partial "
   "credit for a readout that got one of two figures, and a claim that refers to another step is unreachable: %s"
   % {k: _g[k] for k in ("outcomes", "reached", "claims", "confirmed", "verdict")})
_by = {r["id"]: r for r in _g["steps"]}
ck(_by["r2"]["call"] == 0 and _by["r3"]["call"] == 1 and _by["r1"]["call"] == 2 and _by["r1"]["confirmed"] == 1
   and not _by["r1"]["reached"] and _by["r4"]["call"] is None and _by["r4"]["confirmed"] == 0,
   "...and says which call reached each: %s" % {k: (v["call"], v["confirmed"]) for k, v in _by.items()})
ck(T.grade_outcomes(_ft, _tr + [_rr({"a": "1", "b": "2"})])["reached"] == 3
   and T.grade_outcomes(_ft, [])["verdict"] == "FAIL" and T.grade_outcomes({"id": "z", "target": "page", "goal": "", "steps": []}, _tr)["verdict"] == "FAIL",
   "a later call that confirms both figures reaches the outcome; an empty trace, or a task with no outcomes, is FAIL not PASS")
# the four traces, held at the floors they measured
FLOORS = {"page-stand-sheet-science": (30, 57, 88, 125), "page-collection-sheet-science": (5, 21, 26, 45),
          "page-pheno-tracker-science": (8, 12, 21, 32), "page-breeding-bench-science": (10, 22, 34, 58)}
for f in b3:
    tid = os.path.basename(f).split(".")[0]
    g3 = T.grade_outcomes(by[tid], T.load_trace(f))
    lo = FLOORS[tid]
    ck(g3["reached"] >= lo[0] and g3["outcomes"] == lo[1] and g3["confirmed"] >= lo[2] and g3["claims"] == lo[3]
       and g3["verdict"] in ("PARTIAL", "PASS") and g3["calls"] > 50,
       "%s: a blind operator who never saw the task reached %d of its %d outcomes (%d of %d claims) by %d calls -- "
       "at or above the floor the trial measured %s" % (tid, g3["reached"], g3["outcomes"], g3["confirmed"], g3["claims"], g3["calls"], lo[:1] + lo[2:3]))
    gr = T.grade_trace(by[tid], T.load_trace(f))
    ck(gr["verdict"] == "FAIL" and gr["met"] < gr["required"] // 4,
       "%s: and graded as a ROUTE the same trace is unmet by step %d of %d, short of a quarter of the script -- which "
       "is the finding, not the operator's failure" % (tid, gr["met"] + 1, gr["required"]))
_out = io.StringIO(); _save, sys.stdout = sys.stdout, _out
_led_before = io.open(led, "rb").read() if os.path.isfile(led) else b""
try:
    _rc = T.main(["--grade-trace", BLIND3, "--outcomes"])
finally:
    sys.stdout = _save
_l3 = [l for l in _out.getvalue().split("\n") if "outcomes reached" in l]
ck(_rc == 1 and len(_l3) == 4 and all("PARTIAL" in l for l in _l3)
   and (io.open(led, "rb").read() if os.path.isfile(led) else b"") == _led_before,
   "--grade-trace DIR --outcomes grades every trace in the directory, exits non-zero while any is short of PASS, and "
   "writes nothing to the ledger -- an operator's score is not the page's: %d line(s)" % len(_l3))

# ---- F4. the fourth blind trial: what the five slices were for (ADR-194) ----
#
# Same four pages, same grader, same floors. Between the two trials the door
# gained names (ADR-188), settling (ADR-189), the manual (ADR-190), the session
# and the diff (ADR-191), and the operator gained a brief instead of a sentence
# (ADR-193). This section is the measurement, and it is the only kind of
# evidence that matters for an API: not that the door is better designed, but
# that a stranger got further with it.
BLIND4 = os.path.join(T.TRACES_DIR, "blind4")
b4 = sorted(glob.glob(os.path.join(BLIND4, "*.jsonl.gz")))
ck(len(b4) == 4 and {os.path.basename(f).split(".")[0] for f in b4} == set(FLOORS),
   "the fourth trial's four traces, one per science page the third was pointed at -- the same "
   "four, or the comparison is not one: %s" % [os.path.basename(f) for f in b4])
p4 = os.path.join(BLIND4, "PROVENANCE.md")
t4 = io.open(p4, encoding="utf-8").read() if os.path.isfile(p4) else ""
ck(all(w in t4 for w in ("blind brief", "DESTRUCTIVE", "attempt", "removed from the",
                         "lower bound")) and len(t4) > 3500,
   "the fourth trial carries a provenance: the conditions, what each operator was handed, what "
   "it measured, and what it found -- including which of its own numbers are floors")

# THE FOURTH TRIAL'S OWN FLOORS. Written down here, from the run, so the next
# door has something to beat and a regression in this one has something to
# fail. The third trial's floors are the SAME dictionary above: a trial that
# did not clear them would be a door that had got worse.
FOURTH = {"page-stand-sheet-science": (42, 107), "page-collection-sheet-science": (12, 34),
          "page-pheno-tracker-science": (9, 25), "page-breeding-bench-science": (19, 47)}
CALLS = {"page-stand-sheet-science": 123, "page-collection-sheet-science": 100,
         "page-pheno-tracker-science": 87, "page-breeding-bench-science": 88}
rose = gained = 0
for f in b4:
    tid = os.path.basename(f).split(".")[0]
    g4 = T.grade_outcomes(by[tid], T.load_trace(f))
    was, now = FLOORS[tid], FOURTH[tid]
    ck(g4["reached"] >= now[0] and g4["confirmed"] >= now[1] and g4["outcomes"] == was[1]
       and g4["claims"] == was[3] and g4["verdict"] in ("PARTIAL", "PASS"),
       "%s: the fourth trial's operator reached %d of %d outcomes (%d of %d claims) -- at or "
       "above what it measured %s" % (tid, g4["reached"], g4["outcomes"], g4["confirmed"],
                                      g4["claims"], now))
    ck(g4["reached"] > was[0] and g4["confirmed"] > was[2],
       "%s: and MORE than the third trial reached on the same page with the same grader -- "
       "%d against %d outcomes, %d against %d claims. This is the only evidence that the five "
       "slices between the trials were worth building"
       % (tid, g4["reached"], was[0], g4["confirmed"], was[2]))
    ck(g4["calls"] <= CALLS[tid],
       "%s: in %d call(s), one attempt, where the third trial took four to six attempts and "
       "%d-odd calls in all" % (tid, g4["calls"], {"page-stand-sheet-science": 290,
                                                   "page-collection-sheet-science": 270,
                                                   "page-pheno-tracker-science": 207,
                                                   "page-breeding-bench-science": 229}[tid]))
    rose += g4["reached"] - was[0]
    gained += g4["confirmed"] - was[2]
    gr4 = T.grade_trace(by[tid], T.load_trace(f))
    ck(gr4["verdict"] == "FAIL",
       "%s: and graded as a ROUTE it is still FAIL -- a better door does not make a stranger "
       "take the author's steps in the author's order, which is ADR-187's finding standing"
       % tid)
ck(rose >= 29 and gained >= 44,
   "across the four pages the fourth trial reached %d more outcomes and confirmed %d more "
   "claims than the third -- 53 -> 82 of 112 and 169 -> 213 of 260" % (rose, gained))
ck(sum(T.grade_outcomes(by[os.path.basename(f).split(".")[0]], T.load_trace(f))["calls"]
       for f in b4) <= 398,
   "in 398 calls against the third trial's 996: the door got cheaper to use, not just further")

# The rung the trial could not grant. The console's own end of this is held in
# verify_mcp, where a mutant runner can afford to break it; what belongs here
# is the thing that made the mismatch VISIBLE -- a task that declares the
# fourth rung, and a brief that prints the declaration.
need4 = [t["id"] for t in tasks if "DESTRUCTIVE" in T.task_rungs(t)[0]]
ck(len(need4) >= 2 and all(T.task_rungs(by[i])[1] for i in need4),
   "%d task(s) declare the fourth rung and every one says why -- which is what made the "
   "mismatch visible: %s" % (len(need4), need4[:3]))


# ---- G. the science (ADR-128) and the whole kit (ADR-129) ---------------------
DATA_ENTRY = {"collection-sheet.html", "releve.html", "stand-sheet.html", "ethogram.html", "selection-log.html",
              "farm-scout.html", "pheno-tracker.html", "deployment-log.html", "cell-bench.html", "micro-bench.html",
              "cp-bench.html", "soil-bench.html", "breeding-bench.html", "survey-design.html", "ordination.html",
              "food-web.html", "soil-recipes.html", "field-notebook.html", "field-season.html", "experiment-guide.html",
              "greenhouse.html"}
# ADR-129: the keys, the simulators and the proofs are operated and held too
INTERACTIVE = {"plant-characters.html", "fungal-characters.html", "cp-characters.html", "tree-visualizer.html",
               "tree-proofs.html", "ecology-lab.html"}
science = [t for t in tasks if t["target"] == "page" and t["id"] != "page-enter-and-read-back"
           and t.get("must", "PASS") == "PASS" and not t["id"].endswith("-reference")
           and not t["id"].startswith("two-targets-")]
reference = [t for t in tasks if t["target"] == "page" and t["id"].endswith("-reference")]
ck({t["page"] for t in science} == DATA_ENTRY | INTERACTIVE,
   "every data-entry, key, simulator and proof page of the kit has a science task, and every science task is on one: "
   "missing %s, extra %s" % (sorted((DATA_ENTRY | INTERACTIVE) - {t["page"] for t in science}),
                             sorted({t["page"] for t in science} - (DATA_ENTRY | INTERACTIVE))))
import harness_walk as W_
routed = set(W_.routed_pages())
ck({t["page"] for t in science} | {t["page"] for t in reference} == routed and
   not ({t["page"] for t in science} & {t["page"] for t in reference}),
   "every routed page of the kit has exactly one kind of task -- a science task or a reference task (ADR-129): "
   "untasked %s" % sorted(routed - {t["page"] for t in science} - {t["page"] for t in reference}))
ENTRY = ("set-text", "pick", "activate", "choose-option", "set-slider", "press-step", "set-checkbox", "attach-file", "drop-files")


def reads_after_entry(t):
    acts = [s["action"] for s in t["steps"]]
    last_entry = max(i for i, a in enumerate(acts) if a in ENTRY)
    return any(a == "read-report" and t["steps"][i].get("expect") for i, a in enumerate(acts) if i > last_entry)


ck(all(reads_after_entry(t) for t in science) and
   all(t["steps"][-1]["action"] == "read-page" and t["steps"][-1]["expect"].get("output.junk", 1) is None
       and t["steps"][-1]["expect"].get("output.overflow") == 0 for t in science + reference),
   "each ends by reading the report against its oracle and by finding the page intact -- no junk, no errors, "
   "nothing pushed sideways")
ck(all(any(s["action"] == "read-report" and any(k.startswith(("output.figures.", "output.by.", "output.tables.", "output.rows."))
                                                or (k.startswith("output.boxes.") and not isinstance(v, dict))
                                                for k, v in s.get("expect", {}).items()) for s in t["steps"]) for t in science),
   "each holds a FIGURE, a table cell, a row count or a box's whole text -- never a substring alone -- to its oracle")
ck(all(sum(1 for s in t["steps"] if s["action"] in ENTRY) >= 3 for t in science),
   "each enters data: at least three entries through the gateway")
raw = [(t["id"], s["id"]) for t in science + reference for s in t["steps"]
       if isinstance((s.get("arguments") or {}).get("selector"), str) and not s["arguments"]["selector"].startswith("@control:")]
ck(not raw, "a science task names its controls the page's way and never writes a selector down: %s" % raw[:3])
ck(all(len(t["goal"]) > 200 and any(ch.isdigit() for ch in t["goal"]) for t in science),
   "each goal states the numbers it expects, in words a reader can check by hand")
ck(all(any(s["action"] == "read-report" and isinstance(s.get("expect", {}).get("output.headings"), list)
           and len(s["expect"]["output.headings"]) >= 6 for s in t["steps"]) for t in reference),
   "a reference page's report is its outline: every reference task pins the page's headings, in order")
canary = by.get("page-collection-sheet-canary")
ck(canary and canary["page"] == "collection-sheet.html" and canary["steps"][-1]["action"] == "read-report"
   and canary["steps"][-1]["expect"].get("output.figures.collections") == "2",
   "the page canary enters one collection and claims the sheet counts two")
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["tasks"]
    sci = {t["id"]: L.get(t["id"]) for t in science}
    ck(all(e and e["held"] and e["confirmed"] >= 18 for e in sci.values()),
       "the ledger holds every science task with at least eighteen confirmed expectations: %s"
       % [k for k, e in sci.items() if not (e and e["held"] and e["confirmed"] >= 18)])
    ck(all(L.get(t["id"], {}).get("held") for t in reference), "and every reference task")
    ck(L.get("page-collection-sheet-canary", {}).get("verdict") == "FAIL" and L.get("page-collection-sheet-canary", {}).get("held"),
       "and the page canary was refuted and held")


# ---- H. the rungs a task needs (ADR-142) -------------------------------------
# Until this ADR the runner opened all four rungs for every task, so "the
# harness can enter this data" had been measured with the wipe-the-store rung
# held throughout, and nobody could say which tasks needed it. The default is
# the supervised set; a task that needs DESTRUCTIVE declares it, with a reason
# and the step ids that need it.
ck(tuple(W_.SUPERVISED_RUNGS) == ("SENSITIVE_READ", "DRAFT", "MUTATE"),
   "the supervised set is read what is entered, draft and write -- and not the fourth rung: %s"
   % (W_.SUPERVISED_RUNGS,))
plain = [t for t in tasks if not t.get("policy")]
ck(plain and all(T.task_rungs(t)[0] == tuple(W_.SUPERVISED_RUNGS) for t in plain),
   "a task that says nothing runs SUPERVISED: %d task(s) declare no policy and every one of "
   "them gets exactly the supervised set" % len(plain))
declared = [t for t in tasks if t.get("policy")]
ck(declared, "and some tasks do declare one: %d" % len(declared))
for t in declared:
    got, why = T.task_rungs(t)
    ck(got == tuple(r for r in W_.WALK_RUNGS if r in t["policy"]["allow"]),
       "%s: the runner grants exactly what the task declared, in ladder order: %s" % (t["id"], list(got)))
    if "DESTRUCTIVE" in got:
        ck(why and len(why) > 30 and all(n in set(x["id"] for x in t["steps"])
                                         for n in t["policy"]["needs"]),
           "%s: it says why it needs the fourth rung and names the step(s) that do: %s / %s"
           % (t["id"], (why or "")[:40], t["policy"].get("needs")))
# ...and the refusals a bad declaration gets, on fixtures, because a rule that
# is only ever obeyed is a rule nobody has tested.
def defect(mutate, why):
    base = json.load(io.open(os.path.join(T.TASKS_DIR, "page-food-web-science.json"), encoding="utf-8"))
    mutate(base)
    d = tempfile.mkdtemp(prefix="taskpol_")
    f = os.path.join(d, "page-food-web-science.json")
    io.open(f, "w", encoding="utf-8").write(json.dumps(base))
    try:
        T.load_task(f)
        ck(False, why + ": was accepted")
    except T.TaskDefect as e:
        ck(True, why + ": %s" % str(e)[:60])

defect(lambda t: t.__setitem__("policy", {"allow": ["SENSITIVE_READ", "DRAFT", "MUTATE", "DESTRUCTIVE"],
                                          "needs": ["undo"]}),
       "a task opening DESTRUCTIVE with no reason is refused")
defect(lambda t: t.__setitem__("policy", {"allow": ["SENSITIVE_READ", "DRAFT", "MUTATE", "DESTRUCTIVE"],
                                          "why": "because I said so, at length and with feeling"}),
       "...and one that gives a reason but names no step is refused too")
defect(lambda t: t.__setitem__("policy", {"allow": ["SENSITIVE_READ", "DRAFT", "MUTATE", "DESTRUCTIVE"],
                                          "why": "because I said so, at length and with feeling",
                                          "needs": ["no-such-step"]}),
       "...and one whose named step does not exist is refused")
defect(lambda t: t.__setitem__("policy", {"allow": ["ROOT"]}),
       "a rung this runner does not open is refused")
defect(lambda t: t.__setitem__("policy", {"allow": []}),
       "an empty allow list is refused: a task that may do nothing is a task nobody wrote")

# THE RUNNER GRANTS NO MORE THAN THE TASK DECLARED, and the only way to assert
# that is to run one and be refused. A task with no policy, whose step needs the
# fourth rung, must be refused by the door -- not quietly allowed because the
# runner opened everything the way it used to.
_had = os.environ.get("CSRBT_FIXTURE_DIE")
os.environ["CSRBT_FIXTURE_DIE"] = "1"
try:
    greedy = {"id": "fixture-undeclared-destructive", "target": "fixture",
              "goal": "a task that never declared the fourth rung reaches for it anyway" * 2,
              "steps": [{"id": "a", "action": "ok"},
                        {"id": "d", "action": "die", "expect": {"ok": True}}]}
    rg = T.run_tasks([greedy])["fixture-undeclared-destructive"]
    last = rg["steps"][-1]
    ck(rg["verdict"] != "PASS" and "not enabled" in (last.get("message", "") + last.get("detail", "")),
       "a task that did not declare DESTRUCTIVE is refused when it reaches for it -- the runner "
       "grants what the file declared and nothing more: %s"
       % (last.get("detail") or last.get("message") or "")[:70])
    ck(rg.get("rungs") == list(W_.SUPERVISED_RUNGS),
       "...and the entry says what it was allowed, so the refusal is readable: %s" % rg.get("rungs"))
finally:
    if _had is None:
        os.environ.pop("CSRBT_FIXTURE_DIE", None)
    else:
        os.environ["CSRBT_FIXTURE_DIE"] = _had

# the ledger says, per task, what it was allowed to do
if os.path.isfile(led):
    L = json.load(io.open(led, encoding="utf-8"))["tasks"]
    # Every entry for a committed task, by its own id. The ledger also holds
    # entries keyed "<id>@mcp", "@trace" and "@blind" -- other doors and other
    # days, merged and not rewritten (ADR-108), so they carry what they carried
    # when they were written and requiring rungs of them would be requiring a
    # past run to have known about this ADR.
    rows = [(t["id"], L[t["id"]]) for t in tasks if isinstance(L.get(t["id"]), dict)]
    miss = [k for k, e in rows if not e.get("rungs")]
    ck(rows and not miss,
       "every ledger entry for a committed task records the rungs it ran under: %d entry/entries, "
       "%d without: %s" % (len(rows), len(miss), miss[:4]))
    sup = [k for k, e in rows if "DESTRUCTIVE" not in (e.get("rungs") or [])]
    # AGAINST THE TASKS THAT DECLARED *IT*, NOT THE TASKS THAT DECLARED ANYTHING
    # (ADR-148). This compared `sup` with the tasks carrying a policy of any
    # kind, which was the same set only for as long as every policy in the kit
    # went all the way to DESTRUCTIVE. The lab's task is the first to declare one
    # that stops short -- it opens SENSITIVE_READ, DRAFT and MUTATE and says why
    # it needs no more -- and the arithmetic then counted it on both sides. The
    # sentence this check prints always said "did NOT declare IT"; the set it
    # used did not.
    destructive = [t for t in tasks
                   if "DESTRUCTIVE" in ((t.get("policy") or {}).get("allow") or [])]
    ck(len(sup) == len(rows) - len(destructive),
       "and exactly the tasks that did NOT declare it entered their data with no destructive "
       "rung at all: %d of %d supervised, %d declared DESTRUCTIVE (of %d that declare a policy "
       "at all)" % (len(sup), len(rows), len(destructive), len(declared)))
    for k, e in rows:
        if "DESTRUCTIVE" in (e.get("rungs") or []):
            ck(bool(e.get("rungsWhy")),
               "%s ran with the fourth rung open and the ledger carries the reason" % k)

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
