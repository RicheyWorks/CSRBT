# -*- coding: utf-8 -*-
"""Mutation testing for the brief (ADR-193).

verify_brief says a goal hands over every value its task enters and holds
exactly what the grader scores. Both are claims about what an OPERATOR is
given before being marked, which is the thing the third blind trial got wrong,
so a suite that asserted them and could not be broken by removing them would be
the same mistake wearing a checkmark.

Cheap on purpose: verify_brief opens nothing and runs in under a second, so
every mutant here costs a second rather than eight minutes -- which is the
difference between a runner that is run and one that is written down.

    python3 tools/mutate_brief.py           # run every mutant
    python3 tools/mutate_brief.py --list    # the catalogue

SAFETY: tools/ is copied to a temp directory and the COPY is mutated. The real
harness_tasks.py is never written to.
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("harness_tasks.py",)

MUTANTS = [
    # ---- ADR-193: the brief ----------------------------------------------
    ("a brief hands over the values but not the picks",
     '''"pick": ("value",),
          "choose-option"''',
     '''"choose-option"''',
     "EVERY value every task supplies is in its brief"),
    ("a file dropped on the page is not data the operator was given",
     '''          "attach-file": ("name", "text", "path"), "drop-files": ("files", "names"),''',
     '''          "attach-file": ("name", "text", "path"),''',
     "EVERY value every task supplies is in its brief"),
    ("bad input typed on purpose is not data either",
     '''GIVING = {"set-text": ("value",), "type-text": ("value",), "pick": ("value",),''',
     '''GIVING = {"set-text": ("value",), "pick": ("value",),''',
     "EVERY value every task supplies is in its brief"),
    ("the seed and the clock are not things a task gives",
     '''          "set-clock": ("at", "clock"), "set-seed": ("seed",),''',
     '''          ''',
     "EVERY value every task supplies is in its brief"),
    ("a step's direction is route rather than data",
     '''          "set-checkbox": ("checked",), "press-step": ("direction", "times"),''',
     '''          "set-checkbox": ("checked",),''',
     "EVERY value every task supplies is in its brief"),
    ("a brief stops at the first step that gives nothing",
     '''        keys = GIVING.get(s["action"])
        if not keys:
            continue''',
     '''        keys = GIVING.get(s["action"])
        if not keys:
            break''',
     "EVERY value every task supplies is in its brief"),
    ("a control is the selector of the moment again",
     '''    if sel.startswith("@control:"):
        return sel[len("@control:"):]''',
     '''    if False:
        return sel[len("@control:"):]''',
     "with the control it is pointed at"),
    ("what a brief holds is a sample of what it holds",
     '''    for s, claims in outcomes_of(task):
        a = dict(s.get("arguments") or {})''',
     '''    for s, claims in outcomes_of(task)[:4]:
        a = dict(s.get("arguments") or {})''',
     "exactly what the outcome grader scores"),
    ("a brief counts its claims as its readings",
     '''                       "claims": sum(len(h["claims"]) for h in holds)}}''',
     '''                       "claims": len(holds)}}''',
     "the brief's count is the grader's count"),
    ("a brief is blind unless somebody asks for the answers",
     '''def brief_of(task, claims=True):''',
     '''def brief_of(task, claims=False):''',
     "asked for with no argument is the FULL one"),
    ("a blind brief hands the answers over after all",
     '''    if claims:
        L += ["", "## What it holds (%d reading(s), %d claim(s))"''',
     '''    if True:
        L += ["", "## What it holds (%d reading(s), %d claim(s))"''',
     "really are absent from the blind one"),
    ("a brief guesses the rungs rather than reading the task's",
     '''    rungs, why = task_rungs(task)''',
     '''    rungs, why = SUPERVISED_RUNGS, None''',
     "the rungs the task declares"),
    ("a ledger row stops counting what the brief hands over",
     '''    return {"gives": len(gives_of(task)), "holds": len(h),''',
     '''    return {"gives": 0, "holds": len(h),''',
     "what a LEDGER ROW says about a brief"),
    ("a ledger row counts its claims as its readings",
     '''            "claims": sum(len(x["claims"]) for x in h)}''',
     '''            "claims": len(h)}''',
     "what a LEDGER ROW says about a brief"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutbrief_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        path = os.path.join(dst, SUBJECT[0])
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT",
                    "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_brief.py")],
                           capture_output=True, text=True, timeout=600,
                           env=dict(os.environ, CSRBT_DOCS_DIR=os.path.join(ROOT, "docs")))
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        return ("killed" if any(expect in f for f in fails) else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", type=int, metavar="N", help="run one mutant by index")
    a = ap.parse_args(argv)
    if a.list:
        for i, (n, _, _, e) in enumerate(MUTANTS):
            print("  %2d  %-56s must be killed by  %s" % (i, n, e))
        return 0
    todo = [MUTANTS[a.only]] if a.only is not None else MUTANTS
    print("mutation testing the brief -- %d mutant(s), %d known equivalent\n"
          % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in todo:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-56s %s" % (verdict, name, detail[:56]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        sys.path.insert(0, TOOLS)
        import mutant_ledger
        mutant_ledger.record("mutate_brief", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             "" if a.only is not None else " (recorded)"))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
