# -*- coding: utf-8 -*-
"""Mutation testing for the tree proofs' worst-case sentence, against verify_proofs.

ADR-234. The worst-case note said the 63 keys were "inserted in ascending
order" over a loop that counts down -- the seventh blind trial read it -- and
the task held only "Built as a path", so nothing could see it. The note is now
read off the tree spWorst built: the order its root betrays, the depth walked.

So the fix is broken on purpose in the ways a sentence goes back to being typed
-- the order fixed either way, the depth written as n-1, the first key written
as n -- and the demonstration under it is broken too (the loop turned round,
the cost off by one), and verify_proofs has to notice every one against its own
Python port of the splay core and a counterfactual built the other way round.

Mutants land on docs/tree-proofs.html in a COPY of the tree; the real one is
never touched.

    python3 tools/mutate_proofs.py           # run every mutant
    python3 tools/mutate_proofs.py --list    # the catalogue
    python3 tools/mutate_proofs.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PAGE = "tree-proofs.html"

MUTANTS = [
    ("the note says ascending whatever the tree is",
     'order=r===n?"descending":r===1?"ascending":"mixed";',
     'order="ascending";',
     "names the order the loop ran"),
    ("the note says descending whatever the tree is",
     'order=r===n?"descending":r===1?"ascending":"mixed";',
     'order="descending";',
     "the same button says ascending"),
    ("the depth is typed as n-1 again",
     '+d+" edges down. Now access key 1',
     '+(n-1)+" edges down. Now access key 1',
     "the same button says ascending"),
    ("the first key is typed as n",
     '" order ("+r+" first)',
     '" order ("+n+" first)',
     "the same button says ascending"),
    ("the depth walk goes right at every node",
     'x=(1<x.key)?x.left:x.right; }',
     'x=x.right; }',
     "names the order the loop ran"),
    ("the worst case is built ascending, key 1 at the root",
     "for(var i=SPN;i>=1;i--)bstInsert(SP,i);",
     "for(var i=1;i<=SPN;i++)bstInsert(SP,i);",
     "names the order the loop ran"),
    ("an access costs its rotations and not the +1",
     "actual=(SP.rot-r0)+1, d=after-before;",
     "actual=(SP.rot-r0), d=after-before;",
     "on the balanced 63"),
    ("a zig-zig rotates the child before the parent",
     "else if(x===p.left && p===g.left){ rotR(T,g); rotR(T,p); }",
     "else if(x===p.left && p===g.left){ rotR(T,p); rotR(T,g); }",
     "on the balanced 63"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutproofs_")
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
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_proofs.py")],
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
    print("mutation testing the tree proofs' worst-case sentence against verify_proofs -- %d mutant(s), "
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
        mutant_ledger.record("mutate_proofs", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
