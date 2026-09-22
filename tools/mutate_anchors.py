# -*- coding: utf-8 -*-
"""Mutation testing for the anchor audit (ADR-235), against verify_anchors.

audit_anchors says whether the mutant ledger is still about the code: whether
every anchor lands somewhere, and whether every ledger entry is about the
catalogue its runner has now. An audit that could not be broken by removing
what it reads would be the very thing it exists to catch, so here it is broken
on purpose. The changes are the ones that would plausibly creep in: a corpus
that loses a kind of file, a shape rule dropped, the runners counted as places
an anchor can land, drift judged by count alone, and a broken runner skipped
in silence.

Cheap: verify_anchors opens nothing and takes about a second.

    python3 tools/mutate_anchors.py           # run every mutant
    python3 tools/mutate_anchors.py --list    # the catalogue
    python3 tools/mutate_anchors.py --only N  # one mutant; the ledger is not written

SAFETY: tools/ is copied to a temp directory and the COPY is mutated.
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = "audit_anchors.py"

MUTANTS = [
    ("the runners count as a place an anchor can land",
     '''            if os.path.isdir(p) or is_runner(p) or any(s in p for s in SKIP_PARTS):''',
     '''            if os.path.isdir(p) or any(s in p for s in SKIP_PARTS):''',
     "an anchor found only in the runner that names it"),
    ("the sibling engine is never read",
     '''    eng = engine_dir(root)
    if os.path.isdir(eng):''',
     '''    eng = engine_dir(root)
    if False:''',
     "or the sibling engine's source"),
    ("the pages are not in the corpus",
     '''                "docs/**/*.html", "docs/**/*.js",''',
     '''                "docs/**/*.js",''',
     "an anchor lands in a tool, a page"),
    ("the task files are not in the corpus",
     '''CORPUS_GLOBS = ("tools/**/*.py", "tools/**/*.js", "tools/**/*.json", "tools/**/*.html",''',
     '''CORPUS_GLOBS = ("tools/**/*.py", "tools/**/*.js", "tools/**/*.html",''',
     "an anchor lands in a tool, a page"),
    ("a one-word target first is read as the name",
     '''        if " " not in m[0].strip() and " " in m[1].strip():
            return m[1], m[2]''',
     '''        if False:
            return m[1], m[2]''',
     "a one-word target first"),
    ("a file second is read as the anchor",
     '''        if m[1].endswith(FILE_EXT) and " " not in m[1]:
            return m[0], m[2]''',
     '''        if False:
            return m[0], m[2]''',
     "a file second, the anchor third"),
    ("an anchor is never looked for",
     '''            if not anchor or not any(anchor in t for t in texts):''',
     '''            if not anchor:''',
     "a reworded line is stale"),
    ("drift is judged by the count alone",
     '''            if was != sorted(names) or e.get("mutants") != len(cat):''',
     '''            if e.get("mutants") != len(cat):''',
     "a renamed mutant is drift"),
    ("a runner that does not import is skipped in silence",
     '''            row["why"] = "does not import: %s: %s" % (type(e).__name__, str(e)[:80])
            rows.append(row)
            continue''',
     '''            continue''',
     "every mutate_*.py is read and nothing else"),
    ("the sweep script is read as a runner",
     '''    for path in sorted(glob.glob(os.path.join(root, "tools", "mutate_*.py"))):''',
     '''    for path in sorted(glob.glob(os.path.join(root, "tools", "mutate*.py"))):''',
     "every mutate_*.py is read and nothing else"),
    ("drift is not a problem",
     '''    return [r for r in rows if not r["read"] or r["unshaped"] or r["stale"] or r["drifted"]]''',
     '''    return [r for r in rows if not r["read"] or r["unshaped"] or r["stale"]]''',
     "the problems are exactly"),
    ("an entry of an unknown shape is passed over",
     '''            if s is None:
                row["unshaped"] += 1
                continue''',
     '''            if s is None:
                continue''',
     "an entry of an unknown shape is counted"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutanchors_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        for name in ("docs", ".github"):
            if os.path.isdir(os.path.join(ROOT, name)):
                os.symlink(os.path.join(ROOT, name), os.path.join(tmp, name))
        path = os.path.join(dst, SUBJECT)
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        env = dict(os.environ, CSRBT_DOCS_DIR=os.path.join(ROOT, "docs"),
                   CSRBT_WHOLEHOG=os.environ.get("CSRBT_WHOLEHOG") or os.path.join(ROOT, "..", "WholeHog"))
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_anchors.py")],
                           capture_output=True, text=True, timeout=600, env=env)
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
    print("mutation testing the anchor audit -- %d mutant(s), %d known equivalent\n"
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
        mutant_ledger.record("mutate_anchors", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             "" if a.only is not None else " (recorded)"))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
