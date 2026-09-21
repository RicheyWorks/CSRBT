# -*- coding: utf-8 -*-
"""Mutation testing for the micro bench's reports, against verify_mb.

ADR-233. The micro bench's blind operator (ADR-230) filed three things the page
SAID rather than computed: a saturation warning that asserted "pushes µ down"
over a point that pushed it up, an intermediate band (13.5–16.5 mm) that was
neither the rule the page applies nor the whole-millimetre convention, and an
organism and medium the form took and nothing read. The task held all three,
byte for byte, because it was written by reading the page.

So the fix is broken on purpose in the ways it would plausibly be wrong -- the
direction fixed, the refit taken over the wrong points, the percentage against
the wrong slope, the band off by one, the organism read at export time instead
of kept per zone -- and verify_mb has to notice every one against an independent
recomputation, not against the page's own text.

Mutants land on docs/micro-bench.html in a COPY of the tree; the real one is
never touched.

    python3 tools/mutate_mb.py           # run every mutant (~45 s each)
    python3 tools/mutate_mb.py --list    # the catalogue
    python3 tools/mutate_mb.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PAGE = "micro-bench.html"

MUTANTS = [
    # ---- the saturation sentence is computed ------------------------------
    ("the saturation sentence says DOWN whatever the refit says",
     'var dir = Math.abs(d)<1e-9 ? "none" : (d<0 ? "down" : "up");',
     'var dir = Math.abs(d)<1e-9 ? "none" : "down";',
     "is reported as pushing"),
    ("the refit keeps the high points in",
     "var lo=use.filter(function(p){ return p.od<=0.6; });",
     "var lo=use.filter(function(p){ return p.od<=9; });",
     "is reported as pushing"),
    ("the percentage is taken against the fit WITH the high points",
     "pct=b!==0 ? Math.abs(d/b)*100 : NaN",
     "pct=a!==0 ? Math.abs(d/a)*100 : NaN",
     "is reported as pushing"),
    ("fewer than three points left is refitted anyway",
     "if(lo.length<3 || !all){",
     "if(lo.length<2 || !all){",
     "cannot be separated"),
    ("the bench sheet keeps the old asserted sentence",
     'spectrophotometer read low there. " + sat.text);',
     'spectrophotometer read low there, which flattens the line and pushes µ down");',
     "the bench sheet carries the same computed sentence"),
    # ---- the band is the rule the page applies ------------------------------
    ("the band goes back to R+0.5 to S-0.5",
     "        ' '+bandText(S,R)+'</div>';",
     "        ' The intermediate band is '+f(R+0.5,1)+'–'+f(S-0.5,1)+' mm.</div>';",
     "states the band as the rule it applies"),
    ("the whole-millimetre range is one too wide at the top",
     '(R+1)+"–"+(S-1)+" mm"',
     '(R+1)+"–"+(S)+" mm"',
     "states the band as the rule it applies"),
    ("a one-millimetre band is printed as a range",
     '(R+1===S-1 ? (R+1)+" mm" :',
     '(false ? (R+1)+" mm" :',
     "states the band as the rule it applies"),
    ("adjacent breakpoints claim a whole-millimetre reading between them",
     "if(S-R>=2)",
     "if(S-R>=1)",
     "states the band as the rule it applies"),
    # ---- organism and medium, per zone --------------------------------------
    ("the organism is not read at Add",
     'org:val("zOrg"),',
     'org:"",',
     "names the organism and medium"),
    ("the medium is read at display time, not kept per zone",
     "+(z.med?' · '+esc(z.med):'')",
     "+(val('zMed')?' · '+esc(val('zMed')):'')",
     "names the organism and medium"),
    ("the zone CSV drops the organism value",
     'src||"", z.org||"", z.med||""]',
     'src||"", "", z.med||""]',
     "every row fills them"),
    ("the bench sheet drops the medium",
     '(z.med ? "   on " + z.med : "")',
     '""',
     "the bench sheet carries organism and medium"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutmb_")
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
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_mb.py")],
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
    print("mutation testing the micro bench's reports against verify_mb -- %d mutant(s), "
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
        mutant_ledger.record("mutate_mb", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
