# -*- coding: utf-8 -*-
"""Mutation testing for the relevé's voucher dials (ADR-242).

The seventh blind trial recorded a voucher without touching material or
phenophase and its label carried "[in flower, flowering]" -- a statement the
collector never made. The dials now start unset, the sheet says what the next
voucher will be recorded as, a voucher is refused until its material is said,
and a voucher with no phenophase records none. Each is broken here the way it
would plausibly regress, and verify_rv must notice -- against the record KEEP
holds, not only the sentence.

Mutants land on docs/releve.html in a COPY of the tree.

    python3 tools/mutate_rv.py           # run every mutant
    python3 tools/mutate_rv.py --list    # the catalogue
    python3 tools/mutate_rv.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PAGE = "releve.html"

MUTANTS = [
    ("material defaults to in flower again",
     'var VMAT=FEK.dial({ field:"vMat", label:"material", clearable:false, value:null,',
     'var VMAT=FEK.dial({ field:"vMat", label:"material", clearable:false, value:"fl",',
     "start UNSET"),
    ("phenophase defaults to flowering again",
     'var VPHEN=FEK.dial({ field:"vPhen", label:"phenophase", clearable:false, value:null,',
     'var VPHEN=FEK.dial({ field:"vPhen", label:"phenophase", clearable:false, value:"fl",',
     "start UNSET"),
    ("the hidden field carries the old default",
     '<input type="hidden" id="vMat"><input type="hidden" id="vPhen">',
     '<input type="hidden" id="vMat" value="fl"><input type="hidden" id="vPhen">',
     "start UNSET"),
    ("a voucher is recorded without a material",
     'if(!val("vMat")){ toast("Say what the specimen is — in flower, in fruit, flower & fruit, or sterile. Nothing recorded."); return; }',
     '',
     "RECORD WITHOUT A MATERIAL IS REFUSED"),
    ("the refusal toasts but records anyway",
     'toast("Say what the specimen is — in flower, in fruit, flower & fruit, or sterile. Nothing recorded."); return; }',
     'toast("Say what the specimen is — in flower, in fruit, flower & fruit, or sterile. Nothing recorded."); }',
     "RECORD WITHOUT A MATERIAL IS REFUSED"),
    ("an unset phenophase is written as flowering",
     'mat:val("vMat"), phen:val("vPhen"), ab:val("vAb"), note:val("vNote")});',
     'mat:val("vMat"), phen:val("vPhen")||"fl", ab:val("vAb"), note:val("vNote")});',
     "HOLDS NONE"),
    ("the label calls an unset phenophase by its empty id",
     """+' ['+esc(MAT[v.mat]||v.mat)+', '+esc(v.phen?(PH[v.phen]||v.phen):"phenophase not recorded")+(v.ab?", "+esc(v.ab):"")+']</div>'""",
     """+' ['+esc(MAT[v.mat]||v.mat)+', '+esc(PH[v.phen]||v.phen)+(v.ab?", "+esc(v.ab):"")+']</div>'""",
     "the herbarium LABEL"),
    ("the export line drops the unset phenophase",
     '"  ["+v.mat+", "+(v.phen||"phenophase not recorded")+", "+v.dup+" sheet"',
     '"  ["+v.mat+", "+v.phen+", "+v.dup+" sheet"',
     "the export line says it too"),
    ("the next-voucher line never says a material is missing",
     '+(m?"":" A voucher is not recorded until its material is said — in flower, in fruit, flower &amp; fruit, or sterile.");',
     '+"";',
     "all three are not recorded"),
    ("the next-voucher line is not repainted when a dial moves",
     'onchange:function(v){ push("vMat",v); vouNext(); },',
     'onchange:function(v){ push("vMat",v); },',
     "choosing a material moves the line"),
    ("the toast does not say when no phenophase was recorded",
     '+(val("vPhen")?"":" — no phenophase recorded"));',
     ');',
     "the toast said no phenophase was recorded"),
    ("the occurrence dial loses its vegetative default",
     'var RPHEN=FEK.dial({ field:"rPhen", label:"phenophase", clearable:false, value:"veg",',
     'var RPHEN=FEK.dial({ field:"rPhen", label:"phenophase", clearable:false, value:null,',
     "vegetative default is untouched"),
]
KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutrv_")
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
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_rv.py")],
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
    print("mutation testing the relevé's voucher dials against verify_rv -- %d mutant(s), "
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
        mutant_ledger.record("mutate_rv", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
