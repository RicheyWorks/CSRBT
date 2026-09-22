# -*- coding: utf-8 -*-
"""Mutation testing for what the selection log says the next bird will carry.

ADR-238. The eighth blind trial pressed "adult" for the third bird while it
was still selected from the second: the press cleared the dial, A3 was logged
with no age, and nothing on the page said so. The page now says what the next
individual will be logged as, says in words when a tap has cleared a dial, and
names in the add confirmation what the record is missing. Each is broken here
the way it would plausibly regress, and verify_sel must notice -- against the
record KEEP's snapshot holds, not only the sentence.

Mutants land on docs/selection-log.html in a COPY of the tree.

    python3 tools/mutate_sel.py           # run every mutant
    python3 tools/mutate_sel.py --list    # the catalogue
    python3 tools/mutate_sel.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PAGE = "selection-log.html"

MUTANTS = [
    ("a clear is never noticed",
     "indCleared = (v==null && indLast[f]) ? { f:f, v:indLast[f] } : null;",
     "indCleared = null;",
     "THE TRAP, SAID"),
    ("switching to another value is called a clear",
     "indCleared = (v==null && indLast[f]) ? { f:f, v:indLast[f] } : null;",
     "indCleared = (indLast[f] && indLast[f]!==v) ? { f:f, v:indLast[f] } : null;",
     "choosing a different sex is a change, not a clear"),
    ("what the dial held is never remembered",
     'indLast[f] = v==null ? "" : v;',
     '',
     "THE TRAP, SAID"),
    ("the add confirmation names nothing missing",
     'toast("Added "+lab+indMissing(val("iSex"),val("iAge")));',
     'toast("Added "+lab);',
     "adding after the clear says what the record is missing"),
    ("a missing sex is not counted as missing",
     'if(!sx) miss.push("sex");',
     '',
     "with neither recorded the confirmation names both"),
    ("the clear warning outlives the add",
     "renderAll(); toast(\"Added \"+lab+indMissing(val(\"iSex\"),val(\"iAge\"))); buzz(12);\n    indCleared=null; indNext();",
     "renderAll(); toast(\"Added \"+lab+indMissing(val(\"iSex\"),val(\"iAge\"))); buzz(12);\n    indNext();",
     "the 'you cleared' warning has done its job"),
    ("the field names are swapped",
     'var IND_NAMES={ iSex:"sex", iAge:"age class" };',
     'var IND_NAMES={ iSex:"age class", iAge:"sex" };',
     "THE TRAP, SAID"),
    ("a restore leaves the line at its boot state",
     'indLast.iSex=val("iSex"); indLast.iAge=val("iAge"); indCleared=null; indNext();',
     '',
     "a restored sheet says what its restored dials will carry"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutsel_")
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
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_sel.py")],
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
    print("mutation testing the selection log's next-individual line against verify_sel -- %d mutant(s), "
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
        mutant_ledger.record("mutate_sel", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
