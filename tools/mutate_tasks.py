# -*- coding: utf-8 -*-
"""Mutation testing for the task runner and grader (ADR-125).

A grader that confirms everything is the worst instrument in the kit: every
task PASSes, the ledger is green, and nothing was asked. Same rule as every
suite: break harness_tasks.py on purpose and require verify_tasks to notice.
Runs in CSRBT_TASKS_QUICK mode -- the grammar, the files, the fixture tasks
over both transports, the committed ledger; no engine, no browser.

    python3 tools/mutate_tasks.py           # run every mutant
    python3 tools/mutate_tasks.py --list    # the catalogue
"""
import argparse, glob, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

MUTANTS = [
    ("every expectation is CONFIRMED",
     '            out.append((key, "CONFIRMED" if ok else "REFUTED", "%s == %r, got %r" % (real, val, got)))',
     '            out.append((key, "CONFIRMED", "%s == %r, got %r" % (real, val, got)))',
     "canary is REFUTED"),
    ("an operator expectation is always CONFIRMED",
     '            out.append((key, "CONFIRMED" if ok else "REFUTED", detail))',
     '            out.append((key, "CONFIRMED", detail))',
     "every operator grades"),
    # ---- saying what is absent (ADR-132) ----
    ("excludes is satisfied by a missing path",
     '            elif not present:\n                ok = False',
     '            elif not present:\n                ok = (op in ("excludes", "not-in"))',
     "does not prove absence"),
    ("excludes reads the wrong way round",
     '                ok = val not in got if isinstance(got, (list, str, dict)) else False\n            elif op == "not-in":',
     '                ok = val in got if isinstance(got, (list, str, dict)) else False\n            elif op == "not-in":',
     "excludes CONFIRMS"),
    ("excludes is always true",
     '                ok = val not in got if isinstance(got, (list, str, dict)) else False\n            elif op == "not-in":',
     '                ok = True\n            elif op == "not-in":',
     "REFUTED when the value IS there"),
    ("not-in reads the wrong way round",
     '                ok = got not in val if isinstance(val, (list, str, dict)) else False',
     '                ok = got in val if isinstance(val, (list, str, dict)) else False',
     "not-in CONFIRMS"),
    ("the loader and the grader keep separate op tables",
     'OPS = ("==", "!=", ">", ">=", "<", "<=", "~=", "in", "not-in", "contains", "excludes", "exists")',
     'OPS = ("==", "!=", ">", ">=", "<", "<=", "in", "contains", "exists")',
     "ONE op table"),
    ("a trailing #n is part of the path",
     '        key, real = path, re.sub(r"(?<! )#\\d+$", "", path)',
     '        key, real = path, path',
     "labels a second claim"),
    ("a read-report duplicate label is stripped as if it were a #n label",
     '        key, real = path, re.sub(r"(?<! )#\\d+$", "", path)',
     '        key, real = path, re.sub(r"#\\d+$", "", path).rstrip()',
     "real path segment"),
    # ---- a control the page never named (ADR-135) ----
    ("kind= is not a way to name a control",
     '    if name.startswith("kind="):',
     '    if False:',
     "nameable by WHAT IT IS"),
    ("kind= matches on the label instead of the kind",
     '        hits = [c for c in controls if c.get("kind") == want and c.get("selector")]',
     '        hits = [c for c in controls if c.get("label") == want and c.get("selector")]',
     "nameable by WHAT IT IS"),
    ("kind= swallows a plain id",
     '    if name.startswith("kind="):\n',
     '    if True:\n',
     "an id wins over a control merely labelled"),
    # ---- two targets, one task (ADR-133) ----
    ("a step's target is ignored: every step goes to the task's own target",
     '        if s.get("target"):\n            if s["target"] not in wires:',
     '        if False:\n            if s["target"] not in wires:',
     "the wire its target names"),
    ("a step naming a target nobody opened quietly uses the task's own",
     '                verdict = "DEFECT"\n                break\n            w, p = wires[s["target"]]',
     '                verdict = "DEFECT"\n            w, p = wires.get(s["target"], (wire, pid))',
     "did not open"),
    ("the ledger entry names only the target the task declares",
     '            "targets": sorted(set([task["target"]] + [x["target"] for x in task["steps"] if x.get("target")])),\n            # ADR-142',
     '            "targets": [task["target"]],\n            # ADR-142',
     "every target the task used"),
    ("only the task's own target is opened",
     '        want = [tgt] + [s["target"] for s in task["steps"] if s.get("target") and s["target"] != tgt]',
     '        want = [tgt]',
     "every target a task opened is closed"),
    ("an unknown target is opened as the task's own instead of refused",
     '                if t not in PLUGIN:\n                    bad = "step names an unknown target %r (known: %s)" % (t, ", ".join(sorted(PLUGIN)))',
     '                if t not in PLUGIN:\n                    wires[t] = (wires[tgt] if tgt in wires else (None, None))\n                    continue',
     "does not exist is the task's DEFECT"),
    ("the targets are closed in the order they were opened",
     '            for w in reversed(opened):\n                w.close()',
     '            for w in opened:\n                w.close()',
     "reverse of the order"),
    ("a target is opened and never closed",
     '            for w in reversed(opened):\n                w.close()',
     '            for w in []:\n                w.close()',
     "every target a task opened is closed"),
    ("~= has a default tolerance",
     '                if "tolerance" not in want:',
     '                want = dict(want, tolerance=want.get("tolerance", 1e9))\n                if "tolerance" not in want:',
     "was tolerated"),
    ("~= ignores the tolerance and asks for equality",
     '                    ok = abs(float(got) - float(val)) <= float(tol)',
     '                    ok = float(got) == float(val)',
     "two instruments"),
    ("held is hard-coded False when a target cannot be opened",
     '                                       "held": task.get("must", "PASS") == "DEFECT",',
     '                                       "held": False,',
     "canary written to be a DEFECT is HELD"),
    ("a REFUTED expectation does not fail the task",
     '        if any(v == "REFUTED" for _, v, _ in graded):\n            verdict = "FAIL"',
     '        if False:\n            verdict = "FAIL"',
     "canary is REFUTED"),
    ("a bad reference resolves to None instead of a DEFECT",
     '        except KeyError:\n            raise TaskDefect("%s: reference %r names a path that is not in the response" % (where, value))',
     '        except KeyError:\n            return None',
     "task DEFECT, not a refutation"),
    ("an unexpected failure does not end the task",
     '            entry["detail"] = "the target failed: %s" % (r.get("message") or "")[:120]\n            verdict = "FAIL"\n            break',
     '            entry["detail"] = "the target failed: %s" % (r.get("message") or "")[:120]',
     "target's failure and ends the task"),
    ("must is ignored: every PASS is held",
     '            "held": verdict == must,',
     '            "held": verdict == "PASS",',
     "HELD because it said it must fail"),
    ("a missing path counts as present",
     '        except KeyError:\n            got, present = None, False',
     '        except KeyError:\n            got, present = None, True',
     "every operator grades"),
    ("escaped dots are not unescaped",
     '    return [x.replace("\\\\.", ".") for x in re.split(r"(?<!\\\\)\\.", path)]',
     '    return path.split(".")',
     "escaped dot stays"),
    ("a target that went away is a failed step, not a DEFECT",
     '        if r.get("code") == "unavailable":',
     '        if False:',
     "goes away mid-task"),
    ("the result buckets are mislabelled: a refusal is driven",
     '        result = ("driven" if r.get("ok") else\n                  "refused" if r.get("code") in ("invalid_argument", "not_found", "conflict") else',
     '        result = ("driven" if r.get("ok") else\n                  "driven" if r.get("code") in ("invalid_argument", "not_found", "conflict") else',
     "each step's result is its bucket"),
]

MUTANTS += [
    # ADR-126: the trace grader
    ("a trace step is satisfied by any call with its action, expectations unread",
     '            if all(v == "CONFIRMED" for _, v, _ in graded):\n                return i, result, graded',
     '            if True:\n                return i, result, graded',
     "order is order"),
    ("order is not order: a required step may match an earlier call",
     '    for s in required:\n        hit = match(s, pos)',
     '    for s in required:\n        hit = match(s, 0)',
     "order is order"),
    ("one call may satisfy two steps",
     '            if i in used:\n                continue                                    # one call satisfies one step',
     '            if False:\n                continue                                    # one call satisfies one step',
     "probe never takes a call"),
    ("a failure the step did not ask for satisfies it",
     '            if result == "failed" and not any(p == "code" for p, _, _ in graded):\n                continue                                    # a failure the step did not ask for',
     '            if False:\n                continue                                    # a failure the step did not ask for',
     "never satisfies it"),
    ("an UNMET required step does not fail the trace",
     '            verdict = "FAIL"\n            if s.get("stop_on_refute", True):\n                break\n            continue\n        i, result, graded = hit\n        done[s["id"]] = trace[i].get("response") or {}\n        used.add(i)\n        pos = i + 1',
     '            if s.get("stop_on_refute", True):\n                break\n            continue\n        i, result, graded = hit\n        done[s["id"]] = trace[i].get("response") or {}\n        used.add(i)\n        pos = i + 1',
     "UNMET and fails the task"),
    ("the MCP server records nothing",
     '        if self._trace is not None:\n            entry = dict(entry, at=time.time())',
     '        if False:\n            entry = dict(entry, at=time.time())',
     "records every call"),
]

MUTANTS += [
    # ADR-128: a page control by the page's own name
    ("@control is not a reference: the name is passed as the selector",
     '    if isinstance(value, str) and value.startswith("@control:"):\n        return find_control(value[len("@control:"):], done, where)',
     '    if False:\n        return find_control(value[len("@control:"):], done, where)',
     "an id wins over a control merely labelled"),
    ("a label beats an id",
     '        for key in ("id", "label", "host"):',
     '        for key in ("label", "id", "host"):',
     "an id wins over a control merely labelled"),
    ("host/label scoping ignores the host",
     '        hits = [c for c in controls if c.get("host") == host and c.get("label") == label and c.get("selector")]',
     '        hits = [c for c in controls if c.get("label") == label and c.get("selector")]',
     "host/label scopes"),
    ("#n is ignored: the first match is always taken",
     '    return hits[nth]["selector"]',
     '    return hits[0]["selector"]',
     "#n is the nth match"),
    ("a trailing #n is not parsed",
     '    m = re.match(r"^(.*)#(\\d+)$", name)          # a trailing #n is the nth match; "season #" is a label',
     '    m = None',
     "#n is the nth match"),
    ("a control nothing matches resolves to None",
     '    if nth >= len(hits):\n        raise TaskDefect("%s: no control named %r%s in the latest snapshot"\n                         % (where, name, " (match #%d of %d)" % (nth, len(hits)) if hits or nth else ""))',
     '    if nth >= len(hits):\n        return None',
     "a control nothing matches is a task DEFECT"),
    ("@control before any snapshot searches nothing instead of objecting",
     '    if controls is None:\n        raise TaskDefect("%s: @control:%s before any step observed the page" % (where, name))',
     '    if controls is None:\n        controls = []',
     "before any step carried a snapshot"),
    ("the FIRST snapshot is resolved against, not the latest",
     '    for r in reversed(list(done.values())):',
     '    for r in list(done.values()):',
     "LATEST snapshot"),
]

MUTANTS += [
    # ---- ADR-136: the blind trial ----
    ('an observation does not ride a response: observe needs its own read',
     '                if not (s["action"] == "observe" and (e.get("response") or {}).get("snapshot")):\n                    continue',
     '                continue',
     'met by the snapshot on ANY response'),
    ("the licence is not observe's alone: any step is met by any response with a snapshot",
     '                if not (s["action"] == "observe" and (e.get("response") or {}).get("snapshot")):\n                    continue',
     '                if not (e.get("response") or {}).get("snapshot"):\n                    continue',
     "the licence is observe's alone"),
    ('an observe step is met by a response that carries no snapshot',
     '                if not (s["action"] == "observe" and (e.get("response") or {}).get("snapshot")):\n                    continue',
     '                if not (s["action"] == "observe"):\n                    continue',
     'carrying no snapshot observes nothing'),
    ('a required step may rest on a probe',
     '                if v[1:].partition(".")[0] in probes:\n                    raise TaskDefect',
     '                if False:\n                    raise TaskDefect',
     'a required step resting on a probe loaded'),
    ('the rule reads backwards: a probe may not read a required step',
     '    probes = set(s["id"] for s in t["steps"] if s.get("optional"))\n    for s in t["steps"]:\n        if s.get("optional"):',
     '    probes = set(s["id"] for s in t["steps"] if not s.get("optional"))\n    for s in t["steps"]:\n        if not s.get("optional"):',
     'the rule is one-way'),
    ("page-enter-and-read-back reads back the author's own constant",
     '    "output.value": "$type.output.value"',
     '    "output.value": "Quercus rubra"',
     'meets every required step'),
    ("organism-crash-road requires the author's route to the crashed state",
     '    "snapshot.chaos": "once:2"\n   },\n   "optional": true',
     '    "snapshot.chaos": "once:2"\n   }',
     'meets every required step'),
    ("organism-crash-road counts the author's batch, not the goal's claim",
     '    "output.count": {\n     "op": ">=",\n     "value": 3\n    }',
     '    "output.count": 3',
     'meets every required step'),
    ('organism-replica-behind requires four writes because the author wrote four',
     '    "key": 51,\n    "attr": 1,\n    "start": 1,\n    "end": 2\n   },\n   "optional": true',
     '    "key": 51,\n    "attr": 1,\n    "start": 1,\n    "end": 2\n   }',
     'meets every required step'),
    ('the blind grades are filed as if they were the sighted ones',
     '            results[task["id"] + ("@blind" if blind else "@trace")] = res',
     '            results[task["id"] + "@trace"] = res',
     'and says so on every line it prints'),
    ('--grade-trace all does not reach the blind traces',
     '        files = (sorted(glob.glob(os.path.join(TRACES_DIR, "*.jsonl"))) +\n                 sorted(glob.glob(os.path.join(BLIND_DIR, "*.jsonl")))) if a.grade_trace == "all" else [a.grade_trace]',
     '        files = sorted(glob.glob(os.path.join(TRACES_DIR, "*.jsonl"))) if a.grade_trace == "all" else [a.grade_trace]',
     'grades every trace it has, sighted and blind'),
]


MUTANTS += [
    # ---- ADR-142: the rungs a task needs ----
    ("the runner opens every rung again, the way it did until ADR-142",
     "    if not pol:\n        return tuple(SUPERVISED_RUNGS), None",
     "    if not pol:\n        return tuple(WALK_RUNGS), None",
     "a task that says nothing runs SUPERVISED"),
    ("a task's declaration is read and then ignored",
     '                             page=task.get("page", page), allow=rungs)',
     '                             page=task.get("page", page))',
     "grants what the file declared and nothing more"),
    ("DESTRUCTIVE may be opened with no reason given",
     '            if not (pol.get("why") or "").strip():',
     "            if False:",
     "with no reason is refused"),
    ("a reason is enough: no step need be named",
     '            need = pol.get("needs")\n            if not isinstance(need, list) or not need:',
     '            need = pol.get("needs") or []\n            if False:',
     "names no step is refused"),
    ("a named step need not exist",
     "                if n not in ids:",
     "                if False:",
     "named step does not exist is refused"),
    ("a rung this runner cannot open is accepted",
     "            if r not in WALK_RUNGS:",
     "            if False:  # rung",
     "does not open is refused"),
    ("the ledger stops saying what a task was allowed to do",
     '            "rungs": list(task_rungs(task)[0]), "rungsWhy": task_rungs(task)[1],',
     '            "rungsWhy": task_rungs(task)[1],',
     # The greedy-task check sees it first: an entry that cannot say what it was
     # allowed to do is unreadable at exactly the moment it matters, which is a
     # refusal. Both checks are about the same clause; this names the one that
     # actually fires first.
     "the entry says what it was allowed"),
]


MUTANTS += [
    # ---- ADR-145: a refusal is a move too ----
    ("a refused step leaves the runner looking at the page as it was before",
     '        if not r.get("ok") and not r.get("snapshot"):',
     "        if False:",
     "the refusal carries one"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="muttasks_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        cands = [os.path.join(dst, "harness_tasks.py"),
                 os.path.join(dst, "harness_mcp.py")]              # a mutant of the recorder lives in the server
        # ADR-136: and a mutant of a TASK lives in its file. The blind traces
        # are the only check that can notice one -- an author's constant put
        # back into a required step still grades against the author's own
        # trace, and only against an operator that never saw it does it fail.
        cands += sorted(glob.glob(os.path.join(dst, "tasks", "*.json")))
        path, src = cands[0], io.open(cands[0], encoding="utf-8").read()
        for c in cands:
            t = io.open(c, encoding="utf-8").read()
            if t.count(find) == 1:
                path, src = c, t
                break
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        suite = os.path.join(dst, "verify", "verify_tasks.py")
        env = dict(os.environ, CSRBT_TASKS_QUICK="1")
        p = subprocess.run([sys.executable, suite], capture_output=True, text=True, timeout=600, env=env)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if "NOT VERIFIED" in out:
            return ("BAD MUTANT", "the suite could not run under mutation")
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        hit = any(expect in f for f in fails)
        return ("killed" if hit else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-56s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the task runner against verify_tasks (quick) -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-56s %s" % (verdict, name, detail[:60]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        if verdict == "SURVIVED":
            survived += 1
        elif verdict != "killed":
            bad += 1
    import mutant_ledger
    mutant_ledger.record("mutate_tasks", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
