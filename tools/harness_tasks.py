# -*- coding: utf-8 -*-
"""Tasks: what an operator is FOR (ADR-125).

The robot (harness_walk.py) shows a target can be operated from its manifest
-- every tool driven, nothing broken -- but a walk has no goal. An operator,
human or model, is given one: "preserve the store and read the generation
back cold", "arm a crash, let a batch fail, restart, and find the batch
whole". Whether that was DONE is a different question from whether every
button works, and until this file nothing in the harness could ask it.

A task is a JSON file under tools/tasks/: a target, a goal in words, and
the steps that accomplish it, each an action with arguments and, where it
matters, EXPECTATIONS about the response -- graded the way the science
engine grades an .eco protocol's hypotheses: CONFIRMED or REFUTED, never
"passed" by a step that merely ran.

    {"id": "organism-preserve-cold-scan", "target": "organism",
     "goal": "...",
     "steps": [
       {"id": "put",  "action": "put", "arguments": {"key": 5, "attr": 1, "start": 1, "end": 2}},
       {"id": "gen",  "action": "preserve", "expect": {"ok": true}},
       {"id": "scan", "action": "cold-scan",
        "arguments": {"generation": "$gen.output.generation"},
        "expect": {"ok": true, "output.records": "$gen.snapshot.size"}}]}

REFERENCES  "$<step>.<dotted.path>" anywhere in arguments or expectations
            reads an earlier step's response (its output, its snapshot, its
            code); "$.<path>" in an expectation is this step's own response;
            a key that holds a dot is written with it escaped
            (argumentPools.pooled\\.slot.0). A step whose action is "observe"
            reads the snapshot on its own and is graded like any response. A reference to a step that has not run, or a path that is
            not there, is a task DEFECT, not a refutation: the task is wrong,
            not the target.
CONTROLS    "@control:<name>" in an argument (ADR-128) is a page control by
            the page's own name -- its id (cName), its label ("area
            searched"), or the id of the box it is mounted in (genEntry) --
            resolved to the moment's selector from the latest snapshot a
            step carried; "@control:<host>/<label>" scopes a label to the
            box it sits in (a dial's "4" under #rCov), "#n" takes the nth
            match. A task about a data-entry page names its fields the way
            the page does and never writes a selector down.
EXPECT      "<dotted.path>": <value>  -- equal to a literal or a reference
            "<dotted.path>": {"op": ">=", "value": 3}   -- ==, !=, >, >=, <, <=,
                              "in", "contains", "exists"
            A step with no expectations is graded on one thing only: it was
            not FAILED (a refusal or a decline is a result the next step
            can read; a failure is the target's).
VERDICT     PASS  every expectation CONFIRMED and no step FAILED
            FAIL  an expectation REFUTED or a step FAILED
            DEFECT the task itself could not be run (a bad reference, an
                   unknown action, a target that went away)
            A task may declare "must": "FAIL" -- the canary: a task written
            to be refuted, so the grader is known to be able to say no.

Tasks run through the real transport (the stdio child, ADR-112's door)
and are kept in tools/task_ledger.json, merged per task id.

A TRACE (ADR-126) is what an operator that was given the GOAL and not the
steps actually did: the MCP server's --trace file, one JSON line per
tools/call with the gateway's whole response. grade_trace() holds a trace
to a task the way run_task holds the target: each step, in order, must be
satisfied by a later call in the trace with the same action whose
expectations all CONFIRM (references resolve against the calls that
satisfied earlier steps); a step no call satisfies is UNMET. Calls the
task did not ask for are allowed -- an operator may look around -- and
counted, so a trace's economy is on the record beside its verdict. A step
marked "optional": true is a probe the author added beyond the goal (a
not_found, a refused link); a trace that skips it is SKIPPED there, not
failed -- run_task still runs it.

    python3 tools/harness_tasks.py --grade-trace tools/traces/organism-crash-road.jsonl
    python3 tools/harness_tasks.py --grade-trace all      # every trace under tools/traces, into the ledger as <id>@trace

    python3 tools/harness_tasks.py                  # every task under tools/tasks
    python3 tools/harness_tasks.py --target organism
    python3 tools/harness_tasks.py --task tools/tasks/organism-crash-road.json
"""
import argparse, glob, io, json, os, re, secrets, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness_walk import wire_for

TASKS_DIR = os.path.join(HERE, "tasks")
LEDGER = os.path.join(HERE, "task_ledger.json")
# ONE op table. There were briefly two -- load_task's and the grader's -- which
# is how a grammar drifts: a task file accepted at load and rejected at grade,
# or the reverse. Everything that needs to know what an op is reads this.
OPS = ("==", "!=", ">", ">=", "<", "<=", "~=", "in", "not-in", "contains", "excludes", "exists")


class TaskDefect(Exception):
    pass


def load_task(path):
    t = json.load(io.open(path, encoding="utf-8"))
    for k in ("id", "target", "goal", "steps"):
        if k not in t:
            raise TaskDefect("%s: no %r" % (os.path.basename(path), k))
    seen = set()
    for i, s in enumerate(t["steps"]):
        if "action" not in s:
            raise TaskDefect("%s: step %d has no action" % (t["id"], i))
        sid = s.get("id") or "s%d" % i
        if s.get("target") is not None and not isinstance(s["target"], str):
            raise TaskDefect("%s/%s: a step's target must be a target name" % (t["id"], sid))
        if sid in seen:
            raise TaskDefect("%s: step id %r used twice" % (t["id"], sid))
        seen.add(sid)
        s["id"] = sid
        for k, v in (s.get("expect") or {}).items():
            if isinstance(v, dict) and ("op" not in v or v["op"] not in OPS):
                raise TaskDefect("%s/%s: expectation %r has no valid op" % (t["id"], sid, k))
    t["_path"] = path
    return t


def parts_of(path):
    """A dotted path, where a key that itself holds a dot is written with the
    dot escaped: argumentPools.pooled\\.slot.0 -- the pool "pooled.slot"."""
    return [x.replace("\\.", ".") for x in re.split(r"(?<!\\)\.", path)]


def dig(obj, path):
    """Follow a dotted path through dicts and lists. Raises KeyError."""
    cur = obj
    for part in parts_of(path):
        if isinstance(cur, dict):
            if part not in cur:
                raise KeyError(path)
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                raise KeyError(path)
        else:
            raise KeyError(path)
    return cur


def find_control(name, done, where):
    """ADR-128: "@control:<name>" -- a page control by the page's own name,
    looked up in the latest snapshot any step so far has carried. Matched in
    this order, first hit in document order: the element's id (cName), its
    label (a stepper's "area searched"), then the id of the nearest identified
    ancestor (a picker mounted under #genEntry). A dial's option or a list
    row's button has no id and a label shared with every other dial's, so a
    name may be scoped: "@control:rCov/4" is the control labelled "4" whose
    nearest identified ancestor is #rCov; "@control:iList/died#2" the third
    such. Selectors are the moment's (the widgets rebuild), so a task never
    writes one down; nothing found is the task's DEFECT, not the page's
    refusal."""
    controls = None
    for r in reversed(list(done.values())):
        snap = r.get("snapshot") if isinstance(r, dict) else None
        if isinstance(snap, dict) and isinstance(snap.get("controls"), list):
            controls = snap["controls"]
            break
    if controls is None:
        raise TaskDefect("%s: @control:%s before any step observed the page" % (where, name))
    nth = 0
    m = re.match(r"^(.*)#(\d+)$", name)          # a trailing #n is the nth match; "season #" is a label
    if m:
        name, nth = m.group(1), int(m.group(2))
    if "/" in name:
        host, _, label = name.partition("/")
        hits = [c for c in controls if c.get("host") == host and c.get("label") == label and c.get("selector")]
    else:
        hits = []
        for key in ("id", "label", "host"):
            hits = [c for c in controls if c.get(key) == name and c.get("selector")]
            if hits:
                break
    if nth >= len(hits):
        raise TaskDefect("%s: no control named %r%s in the latest snapshot"
                         % (where, name, " (match #%d of %d)" % (nth, len(hits)) if hits or nth else ""))
    return hits[nth]["selector"]


def resolve(value, done, where):
    """Replace "$step.path" references, recursively, from the responses so far."""
    if isinstance(value, str) and value.startswith("@control:"):
        return find_control(value[len("@control:"):], done, where)
    if isinstance(value, str) and value.startswith("$"):
        ref = value[1:]
        step, _, path = ref.partition(".")
        if step == "" and "" not in done:
            raise TaskDefect("%s: reference %r to this step's own response is only valid in an expectation" % (where, value))
        if step not in done:
            raise TaskDefect("%s: reference %r to a step that has not run" % (where, value))
        try:
            return dig(done[step], path) if path else done[step]
        except KeyError:
            raise TaskDefect("%s: reference %r names a path that is not in the response" % (where, value))
    if isinstance(value, dict):
        return dict((k, resolve(v, done, where)) for k, v in value.items())
    if isinstance(value, list):
        return [resolve(v, done, where) for v in value]
    return value


def grade(expect, response, done, where):
    """[(path, verdict, detail)] for one step's expectations. Inside an
    expectation, "$.path" is this step's own response -- so a step can say
    "output.recovery.entries equals snapshot.size" without knowing either."""
    done = dict(done)
    done[""] = response
    out = []
    for path, want in expect.items():
        # TWO CLAIMS ABOUT ONE PATH (ADR-132).
        #
        # Expectations are keyed by path, so a box could carry exactly one
        # claim -- and the interesting pair is "it says the refusal" AND "it no
        # longer says the answer", which are two claims about the same box. A
        # trailing "#n" (no space before it) is a label, stripped before the
        # path is followed: output.boxes.selOut and output.boxes.selOut#2 are
        # the same box, graded and reported separately.
        #
        # The space matters: read-report's own duplicate labels are written
        # "doubling time #2", with a space, and are real path segments. Only a
        # "#n" glued to the end is a label.
        key, real = path, re.sub(r"(?<! )#\d+$", "", path)
        try:
            got = dig(response, real)
            present = True
        except KeyError:
            got, present = None, False
        if isinstance(want, dict) and "op" in want:
            op, val = want["op"], resolve(want.get("value"), done, where)
            if op == "exists":
                ok = present is bool(val) if isinstance(val, bool) else present
            elif not present:
                ok = False
            elif op == "==":
                ok = got == val
            elif op == "!=":
                ok = got != val
            elif op in (">", ">=", "<", "<="):
                try:
                    ok = {">": got > val, ">=": got >= val, "<": got < val, "<=": got <= val}[op]
                except TypeError:
                    ok = False
            elif op == "in":
                ok = got in val if isinstance(val, (list, str, dict)) else False
            elif op == "contains":
                ok = val in got if isinstance(got, (list, str, dict)) else False
            elif op == "~=":
                # TWO INSTRUMENTS, ONE NUMBER (ADR-133).
                #
                # A cross-target task holds a page's figure to an ENGINE's, and
                # the two do not print the same string: the engine reports
                # 1.227621 and the page shows "1.23" because that is what a
                # reader needs. The claim is that they agree, and the grammar
                # could not say it -- "==" is false and "contains" is a
                # coincidence waiting to happen.
                #
                # The tolerance is REQUIRED and has no default. A default would
                # be this file deciding how close two instruments have to be,
                # which is the task's business and nobody else's: a page that
                # rounds to two decimals agrees to 0.005, and a page that
                # rounds to a whole number does not.
                if "tolerance" not in want:
                    raise TaskDefect("%s: ~= on %r needs a tolerance -- how close two instruments must be is the "
                                     "task's claim, not a default" % (where, real))
                tol = resolve(want["tolerance"], done, where)
                try:
                    ok = abs(float(got) - float(val)) <= float(tol)
                except (TypeError, ValueError):
                    ok = False
            elif op == "excludes":
                # SAYING WHAT IS ABSENT (ADR-132).
                #
                # Until now the grammar could only say what a box DOES hold, so
                # a task that wanted to assert a page had stopped printing a
                # warning had to guess what replaced it -- and a guess that
                # happens to be right is not the same claim. "excludes" is the
                # claim itself. It is deliberately NOT satisfied by a missing
                # path (see the `not present` rung above): a task must name a
                # box that exists and say the string is not in it, or a typo in
                # the path would read as proof of absence, which is the exact
                # failure this op was added to stop.
                ok = val not in got if isinstance(got, (list, str, dict)) else False
            elif op == "not-in":
                ok = got not in val if isinstance(val, (list, str, dict)) else False
            else:
                # An op the grader does not know is the TASK's defect, not the
                # page's. It used to fall through to ok = False and print as a
                # REFUTED expectation -- a typo in a task file reported as a
                # finding about the kit, which is ADR-125's rule broken by the
                # grader itself.
                raise TaskDefect("%s: unknown op %r in an expectation on %r (known: %s)"
                                 % (where, op, real, ", ".join(sorted(OPS))))
            detail = "%s %s %r%s, got %r" % (real, op, val,
                                             " +/- %r" % want["tolerance"] if op == "~=" else "", got)
            out.append((key, "CONFIRMED" if ok else "REFUTED", detail))
        else:
            val = resolve(want, done, where)
            ok = present and got == val
            out.append((key, "CONFIRMED" if ok else "REFUTED", "%s == %r, got %r" % (real, val, got)))
    return out


def run_task(task, wire, pid, wires=None):
    """Run one task's steps through the wire. Returns the ledger entry.

    TWO TARGETS, ONE TASK (ADR-133). A step may name its own `target`, and
    `wires` is then {target: (wire, pluginId)} -- opened once by the caller and
    kept for the task's life, so a task can write through the organism and look
    at the page's rendering of it in the same run. A step with no target uses
    the task's own, which is every task written before this one."""
    done, steps, t0 = {}, [], time.time()
    verdict = "PASS"
    wires = wires or {}
    for s in task["steps"]:
        where = "%s/%s" % (task["id"], s["id"])
        w, p = wire, pid
        if s.get("target"):
            if s["target"] not in wires:
                # naming a target the task did not open is the TASK's defect:
                # it asked for an instrument nobody plugged in
                steps.append({"id": s["id"], "action": s["action"], "result": "DEFECT",
                              "detail": "step names target %r, which this task did not open (opened: %s)"
                                        % (s["target"], ", ".join(sorted(wires)) or "none")})
                verdict = "DEFECT"
                break
            w, p = wires[s["target"]]
        try:
            args = resolve(s.get("arguments") or {}, done, where)
            if s["action"] == "observe":
                # an observation is an operator's move too (ADR-126): the
                # snapshot, read on its own, graded like any response
                o = w.op("observe", plugin=p)
                r = {"ok": bool(o.get("ok", "snapshot" in o)), "snapshot": o.get("snapshot") or {},
                     "output": {}, "requestId": None, "code": o.get("code")}
            else:
                r = w.op("execute", plugin=p,
                            command={"request_id": "task-%s-%s-%s" % (task["id"], s["id"], secrets.token_hex(4)),
                                     "action": s["action"], "arguments": args})
        except TaskDefect as e:
            steps.append({"id": s["id"], "action": s["action"], "result": "DEFECT", "detail": str(e)})
            verdict = "DEFECT"
            break
        done[s["id"]] = r
        if r.get("code") == "unavailable":
            steps.append({"id": s["id"], "action": s["action"], "result": "DEFECT",
                          "detail": "the target went away: %s" % r.get("message")})
            verdict = "DEFECT"
            break
        result = ("driven" if r.get("ok") else
                  "refused" if r.get("code") in ("invalid_argument", "not_found", "conflict") else
                  "declined" if r.get("code") is None else "failed")
        try:
            graded = grade(s.get("expect") or {}, r, done, where)
        except TaskDefect as e:
            steps.append({"id": s["id"], "action": s["action"], "result": "DEFECT", "detail": str(e)})
            verdict = "DEFECT"
            break
        entry = {"id": s["id"], "action": s["action"], "result": result,
                 "expectations": [{"path": p, "verdict": v, "detail": d} for p, v, d in graded],
                 "ms": r.get("ms"), "message": (r.get("message") or "")[:120]}
        steps.append(entry)
        if result == "failed" and not any(p == "code" for p, _, _ in graded):
            # a failure nobody expected is the target's, and ends the task
            entry["detail"] = "the target failed: %s" % (r.get("message") or "")[:120]
            verdict = "FAIL"
            break
        if any(v == "REFUTED" for _, v, _ in graded):
            verdict = "FAIL"
            if s.get("stop_on_refute", True):
                break
    must = task.get("must", "PASS")
    return {"id": task["id"], "target": task["target"], "goal": task["goal"], "at": int(time.time()),
            "targets": sorted(set([task["target"]] + [x["target"] for x in task["steps"] if x.get("target")])),
            "steps": steps, "verdict": verdict, "must": must,
            "held": verdict == must,       # the task did what it was written to do (a canary must FAIL)
            "confirmed": sum(1 for s in steps for e in s.get("expectations", []) if e["verdict"] == "CONFIRMED"),
            "refuted": sum(1 for s in steps for e in s.get("expectations", []) if e["verdict"] == "REFUTED"),
            "seconds": round(time.time() - t0, 1)}


PLUGIN = {"organism": "csrbt-organism", "lab": "csrbt-lab", "page": "csrbt-page", "fixture": "csrbt-fixture"}
TRACES_DIR = os.path.join(HERE, "traces")


def load_trace(path):
    out = []
    for i, line in enumerate(io.open(path, encoding="utf-8")):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            raise TaskDefect("%s line %d: not JSON" % (os.path.basename(path), i + 1))
        if not isinstance(e, dict) or "action" not in e or "response" not in e:
            raise TaskDefect("%s line %d: a trace entry names an action and carries a response" % (os.path.basename(path), i + 1))
        out.append(e)
    return out


def grade_trace(task, trace):
    """Hold a trace to a task. Returns a ledger-shaped entry with, per step,
    the trace call that satisfied it (its index) or UNMET. The required steps
    are matched first, in order, each by the next unused call; the optional
    probes afterwards, anywhere in what is left -- a probe must never take a
    call a required step needs (the first page trace lost its read-page to
    its own optional look-around)."""
    done, pos, used = {}, 0, set()
    by_id = {}
    verdict = "PASS"

    def match(s, start):
        where = "%s/%s" % (task["id"], s["id"])
        for i in range(start, len(trace)):
            e = trace[i]
            if e.get("action") != s["action"] or i in used:
                continue                                    # one call satisfies one step
            r = e.get("response") or {}
            try:
                graded = grade(s.get("expect") or {}, r, done, where)
            except TaskDefect:
                continue                                    # this call cannot satisfy it; a later one may
            result = ("driven" if r.get("ok") else
                      "refused" if r.get("code") in ("invalid_argument", "not_found", "conflict") else
                      "declined" if r.get("code") is None else "failed")
            if result == "failed" and not any(p == "code" for p, _, _ in graded):
                continue                                    # a failure the step did not ask for
            if all(v == "CONFIRMED" for _, v, _ in graded):
                return i, result, graded
        return None

    required = [s for s in task["steps"] if not s.get("optional")]
    optional = [s for s in task["steps"] if s.get("optional")]
    for s in required:
        hit = match(s, pos)
        if hit is None:
            by_id[s["id"]] = {"id": s["id"], "action": s["action"], "result": "UNMET",
                              "detail": "no call after #%d with action %r satisfies %s"
                                        % (pos, s["action"], json.dumps(s.get("expect") or {})[:100])}
            verdict = "FAIL"
            if s.get("stop_on_refute", True):
                break
            continue
        i, result, graded = hit
        done[s["id"]] = trace[i].get("response") or {}
        used.add(i)
        pos = i + 1
        by_id[s["id"]] = {"id": s["id"], "action": s["action"], "result": result, "call": i,
                          "expectations": [{"path": p, "verdict": v, "detail": d} for p, v, d in graded]}
    for s in optional:
        hit = match(s, 0)
        if hit is None:
            by_id[s["id"]] = {"id": s["id"], "action": s["action"], "result": "SKIPPED",
                              "detail": "optional, and no call satisfies it"}
            continue
        i, result, graded = hit
        done[s["id"]] = trace[i].get("response") or {}
        used.add(i)
        by_id[s["id"]] = {"id": s["id"], "action": s["action"], "result": result, "call": i,
                          "expectations": [{"path": p, "verdict": v, "detail": d} for p, v, d in graded]}
    steps = [by_id[s["id"]] for s in task["steps"] if s["id"] in by_id]
    must = task.get("must", "PASS")
    return {"id": task["id"], "target": task["target"], "goal": task["goal"], "at": int(time.time()),
            "targets": sorted(set([task["target"]] + [x["target"] for x in task["steps"] if x.get("target")])),
            "steps": steps, "verdict": verdict, "must": must, "held": verdict == must, "graded": "trace",
            "calls": len(trace), "asked": len(task["steps"]),
            "required": len(required), "met": sum(1 for x in required if "call" in by_id.get(x["id"], {})),
            "probes": len(optional), "probed": sum(1 for x in optional if "call" in by_id.get(x["id"], {})),
            "confirmed": sum(1 for s in steps for e in s.get("expectations", []) if e["verdict"] == "CONFIRMED"),
            "refuted": 0, "unmet": sum(1 for s in steps if s["result"] == "UNMET"), "seconds": 0}



def run_tasks(tasks, transport="stdio", log=None, page="collection-sheet.html", seed=42):
    """Each task on a fresh target (its own child): tasks must not depend on
    each other's leftovers."""
    say = log or (lambda *a: None)
    results = {}
    for task in tasks:
        tgt = task["target"]
        # ADR-133: the task's own target, plus every target its steps name --
        # each opened once, kept for the task's life, and closed in the reverse
        # of the order they were opened.
        want = [tgt] + [s["target"] for s in task["steps"] if s.get("target") and s["target"] != tgt]
        order, seen_t = [], set()
        for t in want:
            if t not in seen_t:
                seen_t.add(t); order.append(t)
        wires, opened = {}, []
        try:
            bad = None
            for t in order:
                if t not in PLUGIN:
                    bad = "step names an unknown target %r (known: %s)" % (t, ", ".join(sorted(PLUGIN)))
                    break
                w = wire_for(transport, "task-" + secrets.token_urlsafe(24), seed=seed, target=t,
                             page=task.get("page", page))
                opened.append(w)
                wires[t] = (w, PLUGIN[t])
                hello = w.op("discover")
                if not hello.get("ok"):
                    bad = "discovery refused on target %r: %s" % (t, hello)
                    break
            if bad:
                results[task["id"]] = {"id": task["id"], "target": tgt, "goal": task["goal"], "at": int(time.time()),
                                       "targets": order, "steps": [], "verdict": "DEFECT",
                                       "must": task.get("must", "PASS"),
                                       # held is verdict == must EVERYWHERE, including here: a canary
                                       # written to be a DEFECT is held when it defects, and hard-coding
                                       # False made the one canary that can reach this path unholdable
                                       "held": task.get("must", "PASS") == "DEFECT",
                                       "confirmed": 0, "refuted": 0, "seconds": 0,
                                       # every entry names its transport, this one included: the ledger
                                       # holds "held and by which door", and an entry without it is a
                                       # row nobody can read
                                       "transport": transport,
                                       "detail": bad}
                continue
            wire = wires[tgt][0]
            res = run_task(task, wire, PLUGIN[tgt], wires)
        finally:
            for w in reversed(opened):
                w.close()
        res["transport"] = transport
        results[task["id"]] = res
        say("%-36s %-6s %-4s %2d confirmed %2d refuted  %5.1fs  %s"
            % (task["id"], res["verdict"], "held" if res["held"] else "NOT", res["confirmed"], res["refuted"],
               res["seconds"], "" if res["held"] else "-- must " + res["must"]))
        for s in res["steps"]:
            for e in s.get("expectations", []):
                if e["verdict"] == "REFUTED":
                    say("      REFUTED %s: %s" % (s["id"], e["detail"]))
            if s.get("detail"):
                say("      %s %s: %s" % (s["result"], s["id"], s["detail"]))
    return results


def merge_ledger(results, path=LEDGER):
    led = {"_comment": "Written by harness_tasks.py. One entry per task id; a run updates only the "
                       "tasks it ran and keeps the rest, each with its own at.", "tasks": {}}
    if os.path.isfile(path):
        try:
            led = json.load(io.open(path, encoding="utf-8"))
        except ValueError:
            pass
    led.setdefault("tasks", {}).update(results)
    json.dump(led, io.open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)
    return led


def all_tasks(target=None, tasks_dir=TASKS_DIR):
    out = []
    for f in sorted(glob.glob(os.path.join(tasks_dir, "*.json"))):
        t = load_task(f)
        if target in (None, "all") or t["target"] == target:
            out.append(t)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="all", choices=["all", "organism", "lab", "page", "fixture"])
    ap.add_argument("--task", help="one task file")
    ap.add_argument("--transport", default="stdio", choices=["stdio", "mcp"])
    ap.add_argument("--no-ledger", action="store_true")
    ap.add_argument("--grade-trace", metavar="FILE",
                    help="grade a trace (the MCP server's --trace output) against a task named by --task, or by "
                         "the trace's file name")
    a = ap.parse_args(argv)
    if a.grade_trace:
        files = sorted(glob.glob(os.path.join(TRACES_DIR, "*.jsonl"))) if a.grade_trace == "all" else [a.grade_trace]
        results, held = {}, 0
        for f in files:
            try:
                tid = os.path.basename(f).split(".")[0]
                task = load_task(a.task) if (a.task and a.grade_trace != "all") else load_task(os.path.join(TASKS_DIR, tid + ".json"))
                res = grade_trace(task, load_trace(f))
            except TaskDefect as e:
                print("defect: %s" % e)
                return 2
            res["trace"] = os.path.basename(f)
            results[task["id"] + "@trace"] = res
            held += 1 if res["held"] else 0
            print("%-36s %-6s %-4s %d of %d required steps met, %d of %d probes, by %d call(s); %d confirmed"
                  % (task["id"], res["verdict"], "held" if res["held"] else "NOT", res["met"], res["required"],
                     res["probed"], res["probes"], res["calls"], res["confirmed"]))
            for s in res["steps"]:
                print("   %-10s %-16s %s" % (s["id"], s["action"], ("call #%d %s" % (s["call"], s["result"])) if "call" in s
                                              else "%s: %s" % (s["result"], s.get("detail", ""))))
        if not a.no_ledger and results:
            merge_ledger(results)
            print("wrote %s" % LEDGER)
        return 0 if held == len(results) else 1
    try:
        tasks = [load_task(a.task)] if a.task else all_tasks(a.target)
    except TaskDefect as e:
        print("task defect: %s" % e)
        return 2
    if not tasks:
        print("no tasks")
        return 2
    results = run_tasks(tasks, a.transport, log=print)
    held = sum(1 for r in results.values() if r["held"])
    print("\n%d task(s): %d held, %d not" % (len(results), held, len(results) - held))
    if not a.no_ledger:
        merge_ledger(results)
        print("wrote %s" % LEDGER)
    return 0 if held == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
