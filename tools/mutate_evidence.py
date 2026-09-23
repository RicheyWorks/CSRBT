# -*- coding: utf-8 -*-
"""Mutation testing for what the kit's evidence is about (ADR-241).

`tools/evidence.py` binds every suite count to the tree it measured and holds
every suite to a committed floor -- ported from the FlowersForever harness.
`tools/verify/run_all.py` takes the tree before the jobs, applies the floors,
and fails a run the tree moved under; `tools/harness_board.py` gates its
verdict on both. Each is broken here the way it would plausibly regress, and
verify_evidence (or verify_board, for the two board mutants) must notice.

Mutants land in a COPY of the tree.

    python3 tools/mutate_evidence.py           # run every mutant
    python3 tools/mutate_evidence.py --list    # the catalogue
    python3 tools/mutate_evidence.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUITE = "verify_evidence.py"

AUD = "tools/audit_addresses.py"
EVI = "tools/evidence.py"
RUN = "tools/verify/run_all.py"
BRD = "tools/harness_board.py"
MUTANTS = [
    ("a ledger is part of the subject",
     EVI, 'EVIDENCE_PARTS = ("_ledger.json", ', 'EVIDENCE_PARTS = ("_ledger.jsonx", ',
     "A RUN'S OWN OUTPUTS DO NOT MOVE THE TREE"),
    ("the pages are not part of the subject",
     EVI, 'SUBJECT_GLOBS = ("docs/**/*.html", ', 'SUBJECT_GLOBS = (',
     "THE SUBJECT is pages"),
    ("the digest ignores a file's bytes",
     EVI, 'h.update(rel.encode("utf-8") + b"\\0" + s.encode("ascii") + b"\\0")', 'h.update(rel.encode("utf-8") + b"\\0")',
     "a changed byte in a page moves the tree"),
    ("a removed file is not named",
     EVI, '"removed": sorted(k for k in rf if k not in cf)}', '"removed": []}',
     "an added file and a removed file are named"),
    ("a count from another tree is not off",
     EVI, 'off = sorted(k for k, t in stamped.items() if t != short(now["digest"]))', 'off = []',
     "the suite is off"),
    ("a count with no tree is not unstamped",
     EVI, 'unstamped = sorted(k for k in entries if not entries[k].get("tree"))', 'unstamped = []',
     "one carries none"),
    ("a suite below its floor stays green",
     EVI, '            e["green"] = False\n            e["below_floor"] = f', '            e["below_floor"] = f',
     "A GREEN SUITE THAT COUNTED FEWER THAN ITS FLOOR GOES RED"),
    ("a suite never seen gets no floor",
     EVI, '        if f is None:\n            new[name] = n\n            continue', '        if f is None:\n            continue',
     "a suite never seen before is floored"),
    ("--raise-floors lowers a floor",
     EVI, 'if n is not None and e.get("green") and n >= new.get(name, 0):', 'if n is not None and e.get("green"):',
     "NEVER lowers one"),
    ("run_all takes the tree after the jobs",
     RUN, '    tree0 = EV.digest(ROOT)', '    tree0 = None',
     "run_all takes the tree BEFORE the jobs"),
    ("a suite below its floor does not fail the run",
     RUN, '        failed.append((name, "%s counted %d checks; its floor is %d.', '        print((name, "%s counted %d checks; its floor is %d.',
     "FAILS THE RUN"),
    ("the board's tree gate is always met",
     BRD, '"tree_ok": bool(tree.get("same")) and not tree.get("off") and not tree.get("moved")', '"tree_ok": True or bool(tree.get("same")) and not tree.get("off") and not tree.get("moved")',
     "WHEN THE TREE HAS CHANGED SINCE THE RUN"),
    ("the board's floor gate is always met",
     BRD, '("no suite counts fewer than its floor", not S["below_floor"], "suite checks passing"),', '("no suite counts fewer than its floor", True, "suite checks passing"),',
     "A SUITE BELOW ITS FLOOR is a gate not met"),
]
KNOWN_EQUIVALENT = []


def run_one(path, find, repl, expect):
    # the two board mutants are held by verify_board, which renders its own
    # board from the copy first (mutate_board's rule), so the copy is rendered
    suite = "verify_board.py" if path == BRD else SUITE
    tmp = tempfile.mkdtemp(prefix="mutevid_")
    try:
        # THE WHOLE SUBJECT, not tools/ and docs/: the suite's real-kit gate
        # digests the tree, and a copy missing .github or the engines' sources
        # is another tree, which would fail every mutant at the wrong check.
        shutil.copytree(ROOT, tmp, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "build", "__pycache__", "*_evidence",
                                                      "node_modules", ".gradle"))
        dst = os.path.join(tmp, "tools")
        target = os.path.join(tmp, path)
        body = io.open(target, encoding="utf-8").read()
        if body.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times in %s -- the mutation never applied"
                    % (body.count(find), path))
        io.open(target, "w", encoding="utf-8", newline="\n").write(body.replace(find, repl, 1))
        # THE MUTANT'S TREE IS A NEW TREE. The mutation itself moves the digest,
        # and the suite's real-kit gate would fail every mutant at "the counts
        # are about this tree" -- the right check for a kit, the wrong one for
        # a mutant. So the copy's counts are restamped as if a run had taken
        # them on the mutated tree, through the COPY's own evidence module
        # (mutate_board's rule: the mutant renders its own evidence). A mutant
        # that breaks the digest still fails on the fixtures, which do not read
        # the real counts. This lives here and not as a CLI on purpose: a
        # restamp anyone could run would be a forgery switch.
        subprocess.run([sys.executable, "-c",
                        "import sys, io, json; sys.path.insert(0, %r); import evidence as E\n"
                        "c = E.load_counts(); t = E.digest(%r); c['tree'] = t; c['tree_moved'] = []\n"
                        "for e in c['suites'].values(): e['tree'] = E.short(t['digest'])\n"
                        "io.open(E.COUNTS, 'w', encoding='utf-8').write(json.dumps(c, indent=1, sort_keys=True) + '\\n')"
                        % (dst, tmp)], capture_output=True, text=True, timeout=120)
        if path == BRD:
            subprocess.run([sys.executable, os.path.join(dst, "harness_board.py")], capture_output=True, text=True, timeout=300)
        try:
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", suite)],
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
        for i, (n, f, _, _, e) in enumerate(MUTANTS):
            print("  %2d %-60s %-28s killed by  %s" % (i, n[:60], f, e))
        return 0
    todo = MUTANTS if a.only is None else [MUTANTS[a.only]]
    print("mutation testing the evidence binding -- tree and floors -- against verify_evidence and verify_board -- "
          "%d mutant(s), %d known equivalent\n" % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, path, find, repl, expect in todo:
        verdict, detail = run_one(path, find, repl, expect)
        print("  %-9s %-70s %s" % (verdict, name[:70], detail[:50]))
        sys.stdout.flush()
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        sys.path.insert(0, TOOLS)
        import mutant_ledger
        mutant_ledger.record("mutate_evidence", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
