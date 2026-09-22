# -*- coding: utf-8 -*-
"""Mutation testing for what the ordination page says, against verify_ord.

ADR-237. The eighth blind trial filed three things the page SAID that were not
so: "1 of 12 starts converged to the same configuration. That is not a stable
solution." beside stress 0.000, where every start that reached zero is an exact
fit and they need not agree; "1 value could not be read as a number and were
taken as zero"; and a toast that kept saying "Simulated: ... no gradient at all"
after the reader's own data was in. Each fix is broken here the way it would
plausibly be undone, and verify_ord must notice against the page's own state
and an independent construction of a second exact arrangement.

Mutants that would depend on how many of the page's clock-seeded starts reach
zero (every start perfect or not) are left out on purpose: a kill that depends
on the time of day is not a kill.

Mutants land on docs/ordination.html in a COPY of the tree.

    python3 tools/mutate_ord.py           # run every mutant
    python3 tools/mutate_ord.py --list    # the catalogue
    python3 tools/mutate_ord.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PAGE = "ordination.html"

MUTANTS = [
    ("a perfect fit gets the instability verdict again",
     "    if(RES.stress < 1e-4){\n      var pf=RES.perfect||0, rest=n-pf;",
     "    if(false){\n      var pf=RES.perfect||0, rest=n-pf;",
     "the starts verdict says how many reached a PERFECT fit"),
    ("any stress under 1 is called a perfect fit",
     "    if(RES.stress < 1e-4){\n      var pf=RES.perfect||0, rest=n-pf;",
     "    if(RES.stress < 1){\n      var pf=RES.perfect||0, rest=n-pf;",
     "keeps the convergence verdict it always had"),
    ("the site count is typed as four",
     "+ M.sites.length+' sites more than one arrangement does that",
     "+ '4 sites more than one arrangement does that",
     "with 5 sites"),
    ("the coordinates never say how many starts reached stress 0",
     '(RES.stress < 1e-4 ? (", " + (RES.perfect||0) + " of " + RES.starts',
     '(false ? (", " + (RES.perfect||0) + " of " + RES.starts',
     "the copied coordinates say how many starts reached stress 0"),
    ("the coordinates say stress 0 whatever the stress",
     '(RES.stress < 1e-4 ? (", " + (RES.perfect||0) + " of " + RES.starts',
     '(true ? (", " + (RES.perfect||0) + " of " + RES.starts',
     "its coordinates say nothing about stress 0"),
    ("one value 'were' taken as zero again",
     "' value could not be read as a number and was taken as zero:</b> '",
     "' value could not be read as a number and were taken as zero:</b> '",
     "one unreadable value 'was taken as zero'"),
    ("two values could not be read as 'a number'",
     "' values could not be read as numbers and were taken as zero:</b> '",
     "' values could not be read as a number and were taken as zero:</b> '",
     "two unreadable values"),
    ("a toast that has gone keeps its words",
     "toastT=setTimeout(function(){ t.textContent=\"\"; },300);",
     "toastT=null;",
     "nothing once it has gone"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutord_")
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
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_ord.py")],
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
    print("mutation testing the ordination page's verdicts against verify_ord -- %d mutant(s), "
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
        mutant_ledger.record("mutate_ord", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
