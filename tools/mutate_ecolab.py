# -*- coding: utf-8 -*-
"""Mutation testing for the ecology lab's theory bench and sites verdict (ADR-243).

The tenth blind trial filed two defects on the lab: choosing a theory model
rebuilt its parameter boxes from the defaults, so the numbers a model had been
given were gone after a look at another model and the .eco line built next was
a protocol nobody typed; and the two-site verdict read "nearly identical
communities" at Bray-Curtis 0.17 beside "share 3 of 7 kinds". Each fix is
broken here the way it would plausibly regress, and verify_eco must notice --
against the boxes, the .eco line and the port's word, not the sentence alone.

Mutants land on docs/ecology-lab.html in a COPY of the tree.

    python3 tools/mutate_ecolab.py           # run every mutant
    python3 tools/mutate_ecolab.py --list    # the catalogue
    python3 tools/mutate_ecolab.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PAGE = "ecology-lab.html"

MUTANTS = [
    ("a chosen model is rebuilt from its defaults, whatever it was given",
     'const vals = Object.hasOwn(GIVEN, kind) ? GIVEN[kind] : MODEL_PARAMS[kind].map(([, v]) => String(v));',
     'const vals = MODEL_PARAMS[kind].map(([, v]) => String(v));',
     "the boxes hold what was typed"),
    ("what a model was given is never kept",
     '    if (SHOWN === null) return;\n    GIVEN[SHOWN] = [...document.querySelectorAll(".wb-mp")].map(el => el.value);',
     '    return;',
     "the boxes hold what was typed"),
    ("the line always calls the numbers the model's starting ones",
     'const mine = boxes.some((v, i) => String(v).trim() !== String(MODEL_PARAMS[kind][i][1]));',
     'const mine = false;',
     "drawn from the numbers you gave it"),
    ("the line never calls them the starting ones",
     'const mine = boxes.some((v, i) => String(v).trim() !== String(MODEL_PARAMS[kind][i][1]));',
     'const mine = true;',
     "starting numbers"),
    ("the line is not repainted when a number is typed",
     'el.addEventListener("input", () => { paramsNote(); runTheory(); });',
     'el.addEventListener("input", () => { runTheory(); });',
     "once a number is typed"),
    ("an imported model's numbers are not said",
     '        paramsNote();                                      // ADR-243: the line says whose numbers these are\n',
     '',
     "a file whose numbers are not the starting ones"),
    ("the .eco line is built from the model's defaults, not its boxes",
     'const mp = MODEL_PARAMS[kind].map((_, i) => boxNum("wb-mp" + i));',
     'const mp = MODEL_PARAMS[kind].map(([, v]) => v);',
     "the .eco line built next"),
    ("identical sites are nearly identical again",
     'const word = (only === 0 && bc === 0) ? "identical communities: the same kinds in the same counts" :',
     'const word = false ? "identical communities: the same kinds in the same counts" :',
     "identical"),
    ("nearly the same counts read as nearly identical communities whatever the membership",
     'bc <= 0.2 ? (only === 0 ? "nearly identical communities" :',
     'bc <= 0.2 ? (true ? "nearly identical communities" :',
     "abundant kinds agree"),
    ("the moderate band ends at 0.5",
     'bc <= 0.6 ? "moderate turnover" : "major turnover — substantially different communities";',
     'bc <= 0.5 ? "moderate turnover" : "major turnover — substantially different communities";',
     "moderate"),
    ("one kind at one site only 'are'",
     '${only === 1 ? "is" : "are"} at one site only',
     '${"are"} at one site only',
     "one kind at one site only"),
    ("the membership figure printed is Sørensen under Jaccard's name",
     '(Jaccard ${fmt(j, 2)}): the turnover is among the scarce kinds`',
     '(Jaccard ${fmt(sor, 2)}): the turnover is among the scarce kinds`',
     "abundant kinds agree"),
]
KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutecolab_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        shutil.copytree(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        target = os.path.join(tmp, "docs", PAGE)
        body = io.open(target, encoding="utf-8").read()
        if body.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times in %s -- the mutation never applied"
                    % (body.count(find), PAGE))
        io.open(target, "w", encoding="utf-8", newline="\n").write(body.replace(find, repl, 1))
        try:
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_eco.py")],
                               capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            return ("BAD MUTANT", "the suite did not finish in 900 s")
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        return ("killed" if any(expect in f for f in fails) else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:90]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", type=int, default=None)
    a = ap.parse_args(argv)
    if a.list:
        for i, (n, _, _, e) in enumerate(MUTANTS):
            print("  %2d %-72s killed by  %s" % (i, n[:72], e))
        return 0
    todo = MUTANTS if a.only is None else [MUTANTS[a.only]]
    print("mutation testing the ecology lab's theory bench and sites verdict against verify_eco -- %d mutant(s), "
          "%d known equivalent\n" % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in todo:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-74s %s" % (verdict, name[:74], detail[:50]))
        sys.stdout.flush()
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        sys.path.insert(0, TOOLS)
        import mutant_ledger
        mutant_ledger.record("mutate_ecolab", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
