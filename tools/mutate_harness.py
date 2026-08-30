# -*- coding: utf-8 -*-
"""Mutation testing for the harness's own tester.

WHY

tools/verify/verify_harness_matrix.py passed 52 of 52 on the run it was written.
In this kit that is a reason for suspicion, not for confidence: a suite nobody
has watched fail is a suite nobody knows the shape of, and the same afternoon it
was written the harness became a build gate, so a check that cannot fail is a
gate that cannot hold.

So the tester is tested the only way a tester can be: break the harness on
purpose and require the tester to notice. Each mutant below names the check it
must kill. A mutant that SURVIVES is the finding -- it means the contract clause
it breaks is asserted by nobody.

It found two on its first run. One was my mutation, not the tester: a mis-typed
anchor that never applied, which is why every mutant is verified to have actually
changed the file before its result is believed. The other was real -- "sequenced
folded back into dead" survived, because the check only asserted that the bucket
EXISTED, not that anything landed in it. That check now asserts placement in both
directions, and the mutant dies.

SAFETY

The real tools/harness.py is never written to. The tree is copied to a temp
directory, the copy is mutated, and the copy's matrix is run against it.

    python3 tools/mutate_harness.py            # run every mutant
    python3 tools/mutate_harness.py --list     # show the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

# (name, find, replace, the check whose failure proves the mutant was caught)
MUTANTS = [
    ("discovery drops a widget kind",
     '    ("chip",        \'.fek-chip\'),\n', "",
     "A2 chip"),
    ("discovery drops the tab kind",
     '    ("tab",         \'.tab[data-pane]\'),\n', "",
     "A2 tab"),
    ("junk detector never fires",
     "const junk = t.match(", "const junk = false && t.match(",
     "D1"),
    ("spill check disabled",
     'if after["overflow"] > 1:', "if False:",
     "D4"),
    ("pane-count invariant disabled",
     'if after["panes"] and after["onp"] != 1:', "if False and after[\"panes\"]:",
     "D3"),
    ("sequencing artifacts folded back into dead",
     'res["sequenced"].append(rec)', 'res["dead"].append(rec)',
     "B5"),
    ("localStorage is no longer an observable trace",
     "let ls = -1; try { ls = JSON.stringify(localStorage).length; } catch (e) { }",
     "let ls = -1;",
     "C storage"),
    ("the .on fingerprint stops distinguishing which things are on",
     'on: h([...document.querySelectorAll(".on")].map(', "on: h([].map(",
     "C class"),
    # Anchored on the REASON, not the append: res["hidden"].append(rec) occurs
    # twice and an ambiguous anchor is a mutant whose result cannot be believed.
    # The runner caught that itself and reported BAD MUTANT rather than a pass.
    ("a control invisible with its own pane open is counted as driven",
     'rec["why"] = "not visible with its own pane open"\n            res["hidden"].append(rec)',
     'rec["why"] = "not visible with its own pane open"\n            res["driven"].append(rec)',
     "B3"),
    ("the accounting loses a bucket",
     'BUCKETS = ("driven", "dead", "sequenced", "hidden", "failed", "excluded")',
     'BUCKETS = ("driven", "dead", "sequenced", "hidden", "failed")',
     "identity"),
]


def run_one(name, find, repl, expect, keep=False):
    tmp = tempfile.mkdtemp(prefix="mutharness_")
    dst = os.path.join(tmp, "tools")
    shutil.copytree(TOOLS, dst)
    target = os.path.join(dst, "harness.py")
    src = io.open(target, encoding="utf-8").read()
    if src.count(find) != 1:
        return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied, so its "
                              "result would have been a lie" % src.count(find))
    io.open(target, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))

    matrix = os.path.join(dst, "verify", "verify_harness_matrix.py")
    p = subprocess.run([sys.executable, matrix], capture_output=True, text=True, timeout=1800)
    out = p.stdout + p.stderr
    fails = [l for l in out.split("\n") if l.startswith("FAIL")]
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    if not fails:
        return ("SURVIVED", "no check failed -- this contract clause is asserted by nobody")
    hit = any(expect in f for f in fails)
    return ("killed" if hit else "killed by the wrong check",
            "%d failure(s); first: %s" % (len(fails), fails[0][:88]))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-52s must be killed by  %s" % (n, e))
        return 0

    print("mutation testing tools/harness.py against its matrix -- %d mutant(s)\n" % len(MUTANTS))
    survived = bad = 0
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(name, find, repl, expect)
        print("  %-9s %-52s %s" % (verdict, name, detail[:60]))
        if verdict == "SURVIVED":
            survived += 1
        elif verdict != "killed":
            bad += 1
    print("\n%d killed, %d survived, %d inconclusive" % (len(MUTANTS) - survived - bad, survived, bad))
    if survived:
        print("A SURVIVING MUTANT IS THE FINDING: the harness can be broken that way and "
              "nothing notices.")
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
