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
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

MUTANTS = [
    ("every expectation is CONFIRMED",
     '            out.append((path, "CONFIRMED" if ok else "REFUTED", "%s == %r, got %r" % (path, val, got)))',
     '            out.append((path, "CONFIRMED", "%s == %r, got %r" % (path, val, got)))',
     "canary is REFUTED"),
    ("an operator expectation is always CONFIRMED",
     '            out.append((path, "CONFIRMED" if ok else "REFUTED", "%s %s %r, got %r" % (path, op, val, got)))',
     '            out.append((path, "CONFIRMED", "%s %s %r, got %r" % (path, op, val, got)))',
     "every operator grades"),
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
     '            if e.get("action") != s["action"] or i in used:',
     '            if e.get("action") != s["action"]:',
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

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="muttasks_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        path = os.path.join(dst, "harness_tasks.py")
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) == 0:                                   # a mutant of the recorder lives in the server
            path = os.path.join(dst, "harness_mcp.py")
            src = io.open(path, encoding="utf-8").read()
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
