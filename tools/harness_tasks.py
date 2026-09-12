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
    python3 tools/harness_tasks.py --grade-trace all      # every trace under tools/traces, into the ledger as
                                                         # <id>@trace, and tools/traces/blind as <id>@blind

    python3 tools/harness_tasks.py                  # every task under tools/tasks
    python3 tools/harness_tasks.py --target organism
    python3 tools/harness_tasks.py --task tools/tasks/organism-crash-road.json
"""
import argparse, glob, io, json, os, re, secrets, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness_contract as C
from harness_walk import wire_for, SUPERVISED_RUNGS, WALK_RUNGS

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
    # A CLAIM MAY NOT REST ON A PROBE (ADR-136).
    #
    # "optional": true marks a step the author added beyond the goal; a trace
    # that skips it is SKIPPED, not failed. So a REQUIRED step that reads a
    # probe's response -- "$look.output.n" -- is a step that cannot be graded
    # whenever the probe was skipped: the reference raises, the step is DEFECT,
    # and the task blames the operator for not taking a detour the goal never
    # asked for. The blind trial (ADR-136) is where this stops being
    # hypothetical: three of six operators skipped a probe.
    probes = set(s["id"] for s in t["steps"] if s.get("optional"))
    for s in t["steps"]:
        if s.get("optional"):
            continue
        for v in json.dumps([s.get("arguments"), s.get("expect")]).split('"'):
            if v.startswith("$") and not v.startswith("$."):
                if v[1:].partition(".")[0] in probes:
                    raise TaskDefect("%s/%s: a required step reads %s, and that step is a probe -- a claim may "
                                     "not rest on a step an operator may skip" % (t["id"], s["id"], v))
    # ADR-142: THE RUNGS THE TASK NEEDS, declared by the task.
    #
    # Until now every task ran with all four rungs open, because the runner
    # opened them -- so "the harness can enter this data" was measured with the
    # wipe-the-store rung held throughout, and nobody could say which tasks
    # actually needed it. The default is now the supervised set (ADR-141), and a
    # task that needs DESTRUCTIVE says so IN ITS OWN FILE, with a reason a
    # reader can weigh. That turns a question nobody had asked into a number:
    # how many of these data-entry tasks need the destructive rung at all.
    pol = t.get("policy")
    if pol is not None:
        if not isinstance(pol, dict) or not isinstance(pol.get("allow"), list) or not pol["allow"]:
            raise TaskDefect("%s: policy must be an object with a non-empty allow list" % t["id"])
        for r in pol["allow"]:
            if r not in WALK_RUNGS:
                raise TaskDefect("%s: policy allows %r, which is not a rung this runner opens (%s)"
                                 % (t["id"], r, ", ".join(WALK_RUNGS)))
        if "DESTRUCTIVE" in pol["allow"]:
            if not (pol.get("why") or "").strip():
                raise TaskDefect("%s: a task that opens DESTRUCTIVE must say why -- the rung that "
                                 "wipes a store is not opened by default and not opened silently"
                                 % t["id"])
            # ...and WHICH steps need it. A reason with no step named is a
            # sentence; a step id is a thing a reader can go and look at, and it
            # rots visibly when the step is renamed or removed.
            need = pol.get("needs")
            if not isinstance(need, list) or not need:
                raise TaskDefect("%s: policy.needs must name the step(s) that need DESTRUCTIVE"
                                 % t["id"])
            ids = set(x["id"] for x in t["steps"])
            for n in need:
                if n not in ids:
                    raise TaskDefect("%s: policy.needs names %r, which is not a step of this task"
                                     % (t["id"], n))
    t["_path"] = path
    return t


def task_rungs(task):
    """(rungs, why) -- what this task's sessions are allowed to do."""
    pol = task.get("policy")
    if not pol:
        return tuple(SUPERVISED_RUNGS), None
    order = dict((r, i) for i, r in enumerate(WALK_RUNGS))
    return tuple(sorted(set(pol["allow"]), key=lambda r: order[r])), (pol.get("why") or None)


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
    ancestor (a picker mounted under #genEntry). "kind=<kind>" names a control
    the page never named, by what it is -- "kind=drop_zone" is the one drop
    zone on the page (ADR-135). A dial's option or a list
    row's button has no id and a label shared with every other dial's, so a
    name may be scoped: "@control:rCov/4" is the control labelled "4" whose
    nearest identified ancestor is #rCov; "@control:iList/died#2" the third
    such -- a name that matches whole is taken whole, so a label that itself
    carries a slash ("Print / save PDF") is reachable unscoped. Selectors are
    the moment's (the widgets rebuild), so a task never
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
    if name.startswith("kind="):
        # A CONTROL WITH NO NAME (ADR-135). The interactive lab takes its
        # dropped session on the window, so the drop zone is the page's own
        # <body>: no id, no host, and a "label" that is the whole navigation
        # bar. It is perfectly identifiable by what it IS -- the one drop zone
        # on the page -- and a task that cannot say that has to invent an id
        # for the page's sake, which is the page changing to suit the harness.
        want = name[len("kind="):]
        hits = [c for c in controls if c.get("kind") == want and c.get("selector")]
    else:
        hits = []
        for key in ("id", "label", "host"):
            hits = [c for c in controls if c.get(key) == name and c.get("selector")]
            if hits:
                break
        # A SLASH IN A LABEL IS A LABEL (ADR-174). "Print / save PDF" is what
        # three pages of this kit call their print button, and a name that
        # matches whole is that control; only a name nothing answers to whole
        # is read as host/label. The scoped form was tried FIRST, so a task
        # could not name the food web's print button at all -- the builder's
        # button has no host, and "Print " is not one either.
        if not hits and "/" in name:
            host, _, label = name.partition("/")
            hits = [c for c in controls if c.get("host") == host and c.get("label") == label and c.get("selector")]
    if nth >= len(hits):
        raise TaskDefect("%s: no control named %r%s in the latest snapshot"
                         % (where, name, " (match #%d of %d)" % (nth, len(hits)) if hits or nth else ""))
    return hits[nth]["selector"]


def resolve(value, done, where):
    """Replace "$step.path" references, recursively, from the responses so far."""
    if isinstance(value, str) and value.startswith("@control:"):
        return find_control(value[len("@control:"):], done, where)
    # A DOLLAR FIGURE IS NOT A REFERENCE (ADR-155). "$14.92" is what the
    # greenhouse monitor prints for the electricity a run cost, and a task that
    # wanted to hold it was told it referred to a step called "14.92". A leading
    # "$$" is one literal dollar sign; a single "$" keeps meaning "the step named
    # after it", which is what every task written before this one relies on.
    if isinstance(value, str) and value.startswith("$$"):
        return value[1:]
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


def _is_hashable(v):
    try:
        hash(v)
        return True
    except TypeError:
        return False


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
                # `val in got` on a mapping hashes val, and a claim whose value
                # is a LIST of cells -- which is how a table row is written --
                # raised TypeError instead of failing. A claim that cannot be
                # true is false; it is not a reason for the grader to stop.
                if isinstance(got, dict) and not _is_hashable(val):
                    ok = False
                else:
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
        # A REFUSAL IS A MOVE TOO (ADR-145, ADR-126's phrase one layer down).
        # The gateway raises before it observes, so a refused response carries
        # no snapshot -- and the next "@control:<name>" then resolves against
        # the last SUCCESSFUL step's snapshot, which the refusal may have made
        # stale. It does here: typing a filter that matches nothing rebuilds
        # the collection sheet's host picker, so the selector the older
        # snapshot gave for it pointed at an element that was no longer inside
        # a picker, and the next pick was refused as "not a picker" -- the
        # runner blaming the page for a stale name of its own.
        if not r.get("ok") and not r.get("snapshot"):
            try:
                o = w.op("observe", plugin=p)
                if isinstance(o, dict) and o.get("snapshot"):
                    r = dict(r, snapshot=o["snapshot"])
            except Exception:
                pass
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
            # ADR-142: the rungs this run was allowed, per task, so the ledger
            # answers "how much power does entering this data need" with a
            # number instead of the runner's old habit of opening everything.
            "rungs": list(task_rungs(task)[0]), "rungsWhy": task_rungs(task)[1],
            "steps": steps, "verdict": verdict, "must": must,
            "held": verdict == must,       # the task did what it was written to do (a canary must FAIL)
            # ADR-193: what the brief for this task hands over and holds, so the
            # board can total them and a task that grew a step nobody added to
            # its brief is a number that moved rather than a thing nobody saw.
            **brief_counts(task),
            "confirmed": sum(1 for s in steps for e in s.get("expectations", []) if e["verdict"] == "CONFIRMED"),
            "refuted": sum(1 for s in steps for e in s.get("expectations", []) if e["verdict"] == "REFUTED"),
            "seconds": round(time.time() - t0, 1)}


PLUGIN = {"organism": "csrbt-organism", "lab": "csrbt-lab", "page": "csrbt-page", "fixture": "csrbt-fixture"}
TRACES_DIR = os.path.join(HERE, "traces")
BLIND_DIR = os.path.join(TRACES_DIR, "blind")     # the blind trial (ADR-136)


def load_trace(path):
    """A trace, one JSON object per line; a .gz is read as written (the science
    traces carry a page snapshot on every response and are kept gzipped)."""
    out = []
    import gzip
    fh = gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz") else io.open(path, encoding="utf-8")
    for i, line in enumerate(fh):
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
            if i in used:
                continue                                    # one call satisfies one step
            if e.get("action") != s["action"]:
                # AN OBSERVATION RIDES EVERY RESPONSE (ADR-136).
                #
                # ADR-126 made `observe` a step action because an observation
                # is an operator's move too. The blind trial found the other
                # half: a step that only wants to SEE the state is satisfied by
                # the snapshot on any response, and demanding a separate
                # resources/read is the instrument asking for a ceremony. An
                # operator who read the state off the answer it already had has
                # observed. Any other action still has to be the action named.
                if not (s["action"] == "observe" and (e.get("response") or {}).get("snapshot")):
                    continue
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



def outcomes_of(task):
    """The task's OUTCOMES: every step that only reads (read-report,
    read-control, read-page, collect-output, read-dialogs, observe) and claims
    something beyond `ok` about what it read. A science task is a script --
    every step required, in the author's order, with the author's arguments --
    and that is the right shape for holding a page to itself. It is the wrong
    shape for a blind operator, who reaches the same figures by another route
    and is UNMET at step three. The outcomes are the part of the script that
    is the GOAL rather than the route: what the page must be read to say."""
    out = []
    for s in task["steps"]:
        if not (s["action"].startswith("read-") or s["action"] in ("collect-output", "observe")):
            continue
        claims = {k: v for k, v in (s.get("expect") or {}).items() if k != "ok"}
        if claims:
            out.append((s, claims))
    return out


# ---------------------------------------------------------------------------
# ADR-193: the brief
# ---------------------------------------------------------------------------
#
# The third blind trial (ADR-187) graded four operators against what their
# TASKS hold and handed them what their GOALS say, and the two are not the same
# set. The stand-sheet operator was held to a 32 mm rain event, the collection
# sheet's to "Bear Cr. old-growth" and "R. Wright", the pheno tracker's to a
# scoring rule -- none of which the goal sentence mentions, and none of which
# anyone could reach by thinking harder. Measured across the 21 science tasks:
# 547 values entered, 281 of them appearing nowhere in the goal that was handed
# over. Fifty-one per cent of the data was withheld from the people being
# marked on it.
#
# So a goal stops being a sentence and becomes a BRIEF, with three parts:
#
#     says    the prose, unchanged -- what this is for and what to do
#     gives   every value the task supplies, with the control that takes it
#     holds   every reading the task holds, with its claims (ADR-187)
#
# `gives` and `holds` are DERIVED FROM THE STEPS, never typed. A brief that
# was written beside a task could go stale the first time the task was edited,
# and a stale brief is worse than no brief: it is a promise about data the
# operator will not find.

# The actions that SUPPLY something -- a value, a file, a seed, a clock. An
# operator who is not handed these cannot reach what they produce, however well
# it reasons.
GIVING = {"set-text": ("value",), "type-text": ("value",), "pick": ("value",),
          "choose-option": ("value",), "set-slider": ("value",),
          "set-checkbox": ("checked",), "press-step": ("direction", "times"),
          "attach-file": ("name", "text", "path"), "drop-files": ("files", "names"),
          # The ENVIRONMENT is given too (ADR-134). A figure that came out of a
          # seeded draw or a frozen clock is not reachable by an operator who
          # was not told the seed, and "your answer differs from mine" is the
          # least useful thing a grader can say about it.
          "set-clock": ("at", "clock"), "set-seed": ("seed",),
          "set-dialog": ("confirm", "prompt"), "answer-dialog": ("confirm", "prompt")}
# Long enough that a reader would copy rather than retype it: a CSV block, an
# imported JSON document, a paragraph of field notes. Reported, so a brief says
# which of its values are bulk rather than pretending a sentence could carry
# them.
BULK = 60


def control_of(step):
    """The readable name of the control a step is pointed at.

    `@control:runName` is the name a task author wrote and a reader reads;
    `#cName` is the page's own id; a positional selector is the moment's and is
    the least useful of the three, so it is given last and as itself."""
    a = step.get("arguments")
    if not isinstance(a, dict):
        return None
    sel = a.get("selector") or a.get("pane") or a.get("key")
    if not isinstance(sel, str):
        return None
    if sel.startswith("@control:"):
        return sel[len("@control:"):]
    if sel.startswith("@") or sel.startswith("#"):
        return sel[1:] if sel.startswith("#") else sel[1:]
    return sel


def gives_of(task):
    """Every value the task SUPPLIES, in the order it supplies them.

    This is the half of a brief ADR-187 proved was missing. Derived from the
    steps, so a task edited without its brief cannot leave the brief lying."""
    out = []
    for i, s in enumerate(task["steps"]):
        keys = GIVING.get(s["action"])
        if not keys:
            continue
        a = s.get("arguments") or {}
        for k in keys:
            if k not in a or a[k] is None or a[k] == "":
                continue
            v = a[k]
            text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
            out.append({"step": s.get("id") or "s%d" % i, "action": s["action"],
                        "control": control_of(s), "argument": k, "value": text,
                        "chars": len(text), "bulk": len(text) > BULK})
    return out


def holds_of(task):
    """Every reading the task holds, with its claims -- the outcomes (ADR-187)
    in the shape a brief hands over and a host can grade itself against."""
    out = []
    for s, claims in outcomes_of(task):
        # A step's arguments are a mapping or they are nothing: a brief that
        # crashed on a malformed one would take the whole ledger with it, and
        # a task that cannot be described is a task, not an exception.
        _a = s.get("arguments")
        a = dict(_a) if isinstance(_a, dict) else {}
        out.append({"step": s["id"], "action": s["action"], "arguments": a,
                    "control": control_of(s), "claims": claims})
    return out


def brief_counts(task):
    """What a LEDGER ROW says about a task's brief.

    One function, two call sites -- the run and the could-not-stand-up -- so a
    row's counts cannot depend on which path wrote it. A task has a brief
    whether or not its target came up, and a ledger whose totals moved with the
    weather would be a measurement of the weather."""
    h = holds_of(task)
    return {"gives": len(gives_of(task)), "holds": len(h),
            "claims": sum(len(x["claims"]) for x in h)}


def goal_of(task):
    """The brief: what this task is for, what it hands over, what it holds.

    NOT A GATEWAY ACTION, and that is deliberate. A door that served a client
    its own task would end the blind trial that made this necessary: ADR-136's
    whole discipline is that the tasks are removed from the filesystem the
    operator works in. This is what the trial's ORGANISER uses to write the
    brief, and what a host driving a task it has been GIVEN uses to grade
    itself as it goes."""
    gives, holds = gives_of(task), holds_of(task)
    rungs, why = task_rungs(task)
    return {"id": task["id"], "target": task["target"], "page": task.get("page"),
            "must": task.get("must", "PASS"),
            "says": task["goal"],
            "gives": gives, "holds": holds,
            "needs": {"rungs": list(rungs), "why": why},
            "counts": {"steps": len(task["steps"]), "gives": len(gives),
                       "bulk": sum(1 for g in gives if g["bulk"]),
                       "holds": len(holds),
                       "claims": sum(len(h["claims"]) for h in holds)}}


def brief_of(task, claims=True):
    """The brief as an operator reads it. `claims=False` withholds what the
    task holds -- which is what a BLIND trial hands over, because an operator
    told the answers is being asked to transcribe rather than to operate."""
    g = goal_of(task)
    L = ["# %s" % g["id"], "",
         "TARGET: %s%s" % (g["target"], ("  (%s)" % g["page"]) if g["page"] else ""),
         "RUNGS:  %s%s" % (", ".join(g["needs"]["rungs"]),
                           ("  -- %s" % g["needs"]["why"]) if g["needs"]["why"] else ""),
         "", "## What this is for", "", g["says"], "",
         "## The data to enter (%d value(s), %d of them bulk)"
         % (g["counts"]["gives"], g["counts"]["bulk"]), ""]
    if not g["gives"]:
        L.append("    (this task enters nothing)")
    for x in g["gives"]:
        where = x["control"] or "(unnamed control)"
        v = x["value"]
        if x["bulk"]:
            L.append("    %-24s %s  [%d characters]" % (where, x["action"], x["chars"]))
            L += ["        | " + ln for ln in v.split("\n")]
        else:
            L.append("    %-24s %s  %s" % (where, x["action"], json.dumps(v, ensure_ascii=False)))
    if claims:
        L += ["", "## What it holds (%d reading(s), %d claim(s))"
              % (g["counts"]["holds"], g["counts"]["claims"]), ""]
        for h in g["holds"]:
            L.append("    %-10s %-14s %s" % (h["step"], h["action"],
                                             json.dumps(h["claims"], ensure_ascii=False)[:150]))
    else:
        L += ["", "## What it holds", "",
              "    %d reading(s) and %d claim(s), withheld: this is a blind brief."
              % (g["counts"]["holds"], g["counts"]["claims"])]
    return "\n".join(L) + "\n"


def fold_diffs(trace):
    """REBUILD THE DOCUMENT EACH CALL ACTUALLY ANSWERED WITH.

    ADR-195 gave `read-report` a `since`, and the fifth blind trial's four
    operators used it for all but two of their sixty-one report reads -- which
    is exactly what it was built for, and which made every one of those reads
    invisible to this grader. `grade_outcomes` holds a claim against what a
    call answered with; a `since` answer is a diff, and a diff has no
    `figures` in it. The stand sheet fell 42 outcomes to 32 and the breeding
    bench 19 to 11 WITHOUT ANY OPERATOR DOING ANYTHING WORSE -- the drop was
    proportional, page by page, to how much each had used the new feature.

    A diff is not a smaller answer, it is the same answer stated differently,
    and everything that reads the document has to be able to read it. So
    before grading, each read-report and each observe is given back the
    document it stood for: the last full one this session was served, with
    every diff since applied, by the contract's own `apply_diff`.

    WHAT THE DIFF CARRIED NO VALUE FOR IS DELETED, not guessed at: a list it
    only counted, a bucket it capped, a path it declared noise, a table it
    left as {"list": 2}. Those paths come out of the rebuilt document, so a
    claim that lands on one is scored unreachable rather than confirmed.

    A TRIMMED BOX IS NOT IN THAT CLASS and is kept. What a window holds is the
    target's own words, so a claim that finds its text there has found it --
    the truncation can cost a claim and cannot manufacture one, which is the
    direction an instrument is allowed to be wrong in.

    The trace is not edited: this returns a new list, and the entries it did
    not have to rebuild are the same objects."""
    out, base = [], {}
    for e in trace:
        r = e.get("response")
        if not isinstance(r, dict):
            out.append(e)
            continue
        act, hit = e.get("action"), None
        if act == "read-report":
            hit = ("output", r.get("output"))
        elif isinstance(r.get("snapshot"), dict):
            hit = ("snapshot", r.get("snapshot"))
        if not hit or not isinstance(hit[1], dict):
            out.append(e)
            continue
        where, doc = hit
        kind = (e.get("pluginId") or "?", where)
        if doc.get("diff") is None and doc.get("changed") is None:
            base[kind] = doc                       # a document, served whole
            out.append(e)
            continue
        prev = base.get(kind)
        if prev is None:                           # nothing to rebuild from
            out.append(e)
            continue
        if doc.get("changed") is False:
            rebuilt, gone = prev, []
        else:
            got = C.apply_diff(prev, doc.get("diff") or {})
            rebuilt, gone = got["after"], got["unrestored"]
        for p in gone:
            _forget(rebuilt, p)
        base[kind] = rebuilt
        e2 = dict(e)
        r2 = dict(r)
        r2[where] = rebuilt
        e2["response"] = r2
        out.append(e2)
    return out


def _forget(doc, path):
    """Take a path out of a rebuilt document entirely. Not blanked, not
    flagged: absent, so a claim against it is unreachable by the same code
    path that handles a figure the page never published."""
    node, segs = doc, C._segments(doc, path)
    for seg in segs[:-1]:
        if not isinstance(node, dict):
            return
        node = node.get(seg)
    if isinstance(node, dict):
        node.pop(segs[-1], None)


def grade_outcomes(task, trace, fold=True):
    """Hold a trace to a task's OUTCOMES, not its route (ADR-187). Every
    outcome step is matched against every trace call of its action, in any
    order, each call on its own; an outcome is REACHED when one call confirms
    all of its claims, and the count of claims the best call confirmed is kept
    either way, so a trace that reached nine of ten figures on a readout is
    not scored as if it had reached none. A claim that refers to another
    step's answer ("$step.path") has no step to refer to here and is counted
    unreachable rather than confirmed. Nothing here writes the ledger: the
    figure this returns is a measurement of an operator, not of the page."""
    outs = outcomes_of(task)
    calls = len(trace)
    # ADR-196: a diff answer is an answer. `fold=False` is what this grader did
    # before the fifth blind trial, kept so the cost of not folding stays a
    # number the suite can print rather than a story about a bad afternoon.
    if fold:
        trace = fold_diffs(trace)
    rows = []
    for s, claims in outs:
        best, best_i = -1, None
        for i, e in enumerate(trace):
            if e.get("action") != s["action"] and not (s["action"] == "observe" and (e.get("response") or {}).get("snapshot")):
                continue
            try:
                graded = grade(claims, e.get("response") or {}, {}, "%s/%s" % (task["id"], s["id"]))
            except TaskDefect:
                continue
            n = sum(1 for _, v, _ in graded if v == "CONFIRMED")
            if n > best:
                best, best_i = n, i
        best = max(best, 0)
        rows.append({"id": s["id"], "action": s["action"], "claims": len(claims), "confirmed": best,
                     "reached": best == len(claims), "call": best_i})
    return {"id": task["id"], "target": task["target"], "goal": task["goal"], "at": int(time.time()),
            "graded": "outcomes", "calls": calls, "asked": len(task["steps"]),
            "outcomes": len(rows), "reached": sum(1 for r in rows if r["reached"]),
            "claims": sum(r["claims"] for r in rows), "confirmed": sum(r["confirmed"] for r in rows),
            "steps": rows,
            "verdict": "PASS" if rows and all(r["reached"] for r in rows) else "PARTIAL" if any(r["confirmed"] for r in rows) else "FAIL"}


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
        rungs, why_rungs = task_rungs(task)
        wires, opened = {}, []
        try:
            bad = None
            for t in order:
                if t not in PLUGIN:
                    bad = "step names an unknown target %r (known: %s)" % (t, ", ".join(sorted(PLUGIN)))
                    break
                w = wire_for(transport, "task-" + secrets.token_urlsafe(24), seed=seed, target=t,
                             page=task.get("page", page), allow=rungs)
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
                                       # ADR-193: a task has a brief whether or not it ran. A row
                                       # that left these out would make the ledger's totals depend
                                       # on which targets happened to come up.
                                       **brief_counts(task),
                                       "confirmed": 0, "refuted": 0, "seconds": 0,
                                       # every entry names its transport, this one included: the ledger
                                       # holds "held and by which door", and an entry without it is a
                                       # row nobody can read
                                       "transport": transport,
                                       # ...and the rungs it ran under, this one included, for the
                                       # same reason: an entry that does not say what it was allowed
                                       # to do cannot be compared with one that does (ADR-142)
                                       "rungs": list(rungs), "rungsWhy": why_rungs,
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


def protocol_of(trace_dir, tasks_dir=TASKS_DIR):
    """THE TASKS AS THEY STOOD WHEN THIS TRIAL WAS RUN.

    A trial's score is a count of claims confirmed, and a claim names a figure
    and the value the page gave for it. So the moment the kit FIXES a page --
    the breeding bench's ten-generation inbreeding was linear under a caption
    that said compounding, and three separate trials found it -- the task's
    claim moves with the page, and every trace recorded before the fix stops
    confirming it. The floors fall, the suite goes red, and the honest reading
    of that red is not "the door got worse" but "you edited the ruler".

    A lab keeps the protocol with the data. So does this: each trial directory
    carries `tasks/`, a copy of the task files as of the run, and its traces
    are graded against THOSE. The live tasks are free to follow the pages.

    A trial with no frozen copy falls back to the live task, which is right for
    every trial run before this existed and whose pages have not moved since.
    """
    out = {}
    frozen = os.path.join(trace_dir, "tasks")
    for t in all_tasks(tasks_dir=tasks_dir):
        out[t["id"]] = t
    if os.path.isdir(frozen):
        for f in sorted(glob.glob(os.path.join(frozen, "*.json"))):
            t = load_task(f)
            out[t["id"]] = t
    return out


def protocol_drift(trace_dir, tasks_dir=TASKS_DIR):
    """Which claims the live task holds differently from the frozen one, by
    step. Empty means the pages this trial touched have not moved since, and
    the frozen copy is ceremony rather than evidence -- which is worth being
    able to SAY rather than assume."""
    frozen = os.path.join(trace_dir, "tasks")
    if not os.path.isdir(frozen):
        return {}
    live = dict((t["id"], t) for t in all_tasks(tasks_dir=tasks_dir))
    out = {}
    for f in sorted(glob.glob(os.path.join(frozen, "*.json"))):
        was = load_task(f)
        now = live.get(was["id"])
        if now is None:
            out[was["id"]] = ["the task no longer exists"]
            continue
        moved = []
        nowby = dict((s["id"], s) for s in now["steps"])
        for s in was["steps"]:
            n = nowby.get(s["id"])
            if n is None:
                moved.append("%s: gone" % s["id"])
                continue
            for p, v in (s.get("expect") or {}).items():
                if (n.get("expect") or {}).get(p) != v:
                    moved.append("%s/%s" % (s["id"], p))
        if moved:
            out[was["id"]] = moved
    return out


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
    ap.add_argument("--goal", metavar="TASK",
                    help="print one task's BRIEF as JSON (ADR-193): what it says, every value it "
                         "gives, every reading it holds. TASK is a task id or a path; `all` is "
                         "every task. This is not a gateway action -- a door that served a client "
                         "its own task would end the blind trial (ADR-136) that made it necessary")
    ap.add_argument("--brief", metavar="TASK",
                    help="the same brief, as an operator reads it")
    ap.add_argument("--blind", action="store_true",
                    help="with --brief: withhold what the task HOLDS. An operator told the "
                         "answers is being asked to transcribe rather than to operate")
    ap.add_argument("--outcomes", action="store_true",
                    help="with --grade-trace FILE-OR-DIR: hold the trace to the task's OUTCOMES (what the page was "
                         "read to say), in any order and by any route, and print what was reached; never written to "
                         "the ledger (ADR-187)")
    a = ap.parse_args(argv)

    if a.goal or a.brief:
        want = a.goal or a.brief
        paths = (sorted(glob.glob(os.path.join(TASKS_DIR, "*.json"))) if want == "all"
                 else [want if os.path.exists(want)
                       else os.path.join(TASKS_DIR, want.rstrip(".json") + ".json")])
        out = []
        for p in paths:
            if not os.path.exists(p):
                sys.stderr.write("no task %r\n" % want)
                return 2
            t = load_task(p)
            out.append(goal_of(t) if a.goal else brief_of(t, claims=not a.blind))
        if a.goal:
            print(json.dumps(out if want == "all" else out[0], indent=1, ensure_ascii=False))
        else:
            print(("\n" + "-" * 76 + "\n\n").join(out))
        return 0

    if a.grade_trace and a.outcomes:
        files = [a.grade_trace] if os.path.isfile(a.grade_trace) else sorted(
            glob.glob(os.path.join(a.grade_trace, "*.jsonl")) + glob.glob(os.path.join(a.grade_trace, "*.jsonl.gz")))
        rc = 0
        for f in files:
            tid = os.path.basename(f).split(".")[0]
            try:
                task = load_task(a.task) if (a.task and len(files) == 1) else load_task(os.path.join(TASKS_DIR, tid + ".json"))
                res = grade_outcomes(task, load_trace(f))
            except TaskDefect as e:
                print("defect: %s" % e)
                return 2
            print("%-36s %-8s outcomes reached %d of %d, claims %d of %d, by %d call(s)"
                  % (task["id"], res["verdict"], res["reached"], res["outcomes"], res["confirmed"], res["claims"], res["calls"]))
            for r in res["steps"]:
                print("   %-14s %-16s %s %d/%d%s" % (r["id"], r["action"], "reached " if r["reached"] else "missed  ",
                                                   r["confirmed"], r["claims"], "" if r["call"] is None else "  call #%d" % r["call"]))
            rc = rc or (0 if res["verdict"] == "PASS" else 1)
        return rc
    if a.grade_trace:
        # "all" is every trace under tools/traces, the blind trial's included
        # (ADR-136): a blind trace is graded by exactly the same rules, and
        # lands in the ledger as <id>@blind beside the sighted <id>@trace.
        files = (sorted(glob.glob(os.path.join(TRACES_DIR, "*.jsonl"))) +
                 sorted(glob.glob(os.path.join(BLIND_DIR, "*.jsonl")))) if a.grade_trace == "all" else [a.grade_trace]
        results, held = {}, 0
        for f in files:
            try:
                tid = os.path.basename(f).split(".")[0]
                task = load_task(a.task) if (a.task and a.grade_trace != "all") else load_task(os.path.join(TASKS_DIR, tid + ".json"))
                res = grade_trace(task, load_trace(f))
            except TaskDefect as e:
                print("defect: %s" % e)
                return 2
            blind = os.path.basename(os.path.dirname(os.path.abspath(f))) == "blind"
            res["trace"] = ("blind/" if blind else "") + os.path.basename(f)
            res["blind"] = blind
            results[task["id"] + ("@blind" if blind else "@trace")] = res
            held += 1 if res["held"] else 0
            print("%-36s%-7s %-6s %-4s %d of %d required steps met, %d of %d probes, by %d call(s); %d confirmed"
                  % (task["id"], " blind" if blind else "", res["verdict"], "held" if res["held"] else "NOT",
                     res["met"], res["required"],
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
