# -*- coding: utf-8 -*-
"""Mutation testing for the ethogram's budget note, session sheet and budget CSV.

ADR-240. The seventh blind trial filed three things on the ethogram: the
budget note called the time in a state "elapsed" beside a tile that said
elapsed was something else; the budget CSV carried the state rows and nothing
else -- no out-of-sight row, no event rates; and the sheet said "1 bouts".
Each is broken here the way it would plausibly regress, and verify_etho must
notice from the durations it states itself, not from the page's own words.

Mutants land on docs/ethogram.html in a COPY of the tree.

    python3 tools/mutate_etho.py           # run every mutant
    python3 tools/mutate_etho.py --list    # the catalogue
    python3 tools/mutate_etho.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PAGE = "ethogram.html"

MUTANTS = [
    ("the note calls the time in a state 'elapsed' again",
     "mmss(obs)+' observed, not the '+mmss(obs+oos)+' in a state (observed plus out of sight)'+",
     "mmss(obs)+' observed, not '+mmss(obs+oos)+' elapsed'+",
     "does not call the time in a state 'elapsed'"),
    ("the note's third number is the time in a state, not the time the session ran",
     "(gap>=1000 ? ', and not the '+mmss(ran)+' the session ran' : '')",
     "(gap>=1000 ? ', and not the '+mmss(obs+oos)+' the session ran' : '')",
     "names the time the session ran"),
    ("the sheet says '1 bouts' again",
     '(per[k].n===1?" bout":" bouts"));',
     '" bouts");',
     "says 'bout' of one"),
    ("the sheet counts every state's bouts as one",
     '"%   "+per[k].n+\n          (per[k].n===1?" bout":" bouts"));',
     '"%   "+1+\n          (per[k].n===1?" bout":" bouts"));',
     "bout count on the sheet is the count of its segments"),
    ("the sheet drops the out-of-sight line",
     'if(oosMs>0) L.push("  out of sight        "+mmss(oosMs)+"   excluded from the denominator");',
     '',
     "names the out-of-sight time it excluded"),
    ("the sheet's in-no-state line is elapsed minus observed, forgetting out of sight",
     "var gapMs=now()-(obs+oosMs);",
     "var gapMs=now()-obs;",
     "the time in no state"),
    ("the budget CSV has no out-of-sight row",
     'if(oosS>0) rows.push(["out of sight","state","seconds_excluded",(oosS/1000).toFixed(1),',
     'if(false) rows.push(["out of sight","state","seconds_excluded",(oosS/1000).toFixed(1),',
     "out-of-sight row carrying the seconds excluded"),
    ("the budget CSV's rates are per elapsed minute",
     "var mins=obs/60000, ec={};",
     "var mins=now()/60000, ec={};",
     "rate per observed minute"),
    ("the budget CSV carries no event rows",
     '      if(evts.length){\n        var mins=obs/60000, ec={};',
     '      if(false){\n        var mins=obs/60000, ec={};',
     "rate per observed minute"),
    ("in point mode the dropped points are not a row",
     'if(pts.length>n) rows.push(["out of sight","state","points_excluded",String(pts.length-n),',
     'if(false) rows.push(["out of sight","state","points_excluded",String(pts.length-n),',
     "out-of-sight points dropped from n are a row"),
    ("the CSV's rate is not the page's rate",
     '"per_observed_min",(mins?(ec[k]/mins).toFixed(3):"0"),',
     '"per_observed_min",(mins?(ec[k]/mins).toFixed(2):"0"),',
     "carries alarm's rate per observed minute"),
]
KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutetho_")
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
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_etho.py")],
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
    print("mutation testing the ethogram's budget note, sheet and budget CSV against verify_etho -- %d mutant(s), "
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
        mutant_ledger.record("mutate_etho", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
