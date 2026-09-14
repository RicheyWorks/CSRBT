# -*- coding: utf-8 -*-
"""Mutation testing for the CI path filter, against verify_ci.

ADR-202. A path filter is the kind of change that looks obviously right and can
be subtly, silently wrong: drop one pattern and the build stops running on
changes that break it, while the history stays green because green now means
"did not run". So the filter is broken here on purpose, one pattern at a time,
and verify_ci has to notice each one.

The subject is the workflow itself and the suite's own matcher -- both, because
a filter that is right and a matcher that says yes to everything look identical
from outside.

    python3 tools/mutate_ci.py           # run every mutant
    python3 tools/mutate_ci.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
WF_REL = os.path.join(".github", "workflows", "ci.yml")

# WHERE a mutant lands. The workflow exists twice on purpose -- the delivery
# bridge refuses to write .github/workflows, so the slice ships tools/ci/ci.yml
# and the push command copies it into place -- and the two failure modes are
# different. "both" is the filter being wrong, which is wrong in both copies
# because they are written together. "mirror" is the two copies DRIFTING, which
# is the failure the deliverable copy introduces and is the only one that shows
# up in one file and not the other.
MUTANTS = [
    # These three drop a pattern from BOTH lists, which is the realistic
    # mistake: the filter is written once and copied, so it is wrong in both
    # places or neither. Dropping it from one would be caught by the
    # same-list check instead, and would prove nothing about coverage.
    ("the filter loses the pattern that covers every module's sources",
     '      - "**/src/**"\n', "",
     "EVERY FILE THE BUILD READS IS INSIDE THE FILTER", "both"),
    ("the filter loses the build scripts",
     '      - "**/*.kts"\n', "",
     "EVERY FILE THE BUILD READS IS INSIDE THE FILTER", "both"),
    ("the wrapper is left out, so a Gradle bump does not run the build",
     '      - "gradle/**"\n', "",
     "EVERY FILE THE BUILD READS IS INSIDE THE FILTER", "both"),
    ("the workflow is left out of its own filter",
     '      - ".github/workflows/ci.yml"\n', "",
     "THE WORKFLOW IS INSIDE ITS OWN FILTER", "both"),
    ("the push filter and the pull_request filter drift apart",
     '  pull_request:\n    paths:\n      - "**/*.java"',
     '  pull_request:\n    paths:\n      - "**/*.kts"',
     "they are THE SAME LIST", "both"),
    ("the pull_request event loses its filter entirely",
     '  pull_request:\n    paths:\n      - "**/*.java"\n      - "**/*.kt"\n      - "**/*.kts"\n'
     '      - "**/src/**"\n      - "gradle/**"\n      - "gradlew"\n      - "gradlew.bat"\n'
     '      - "gradle.properties"\n      - ".github/workflows/ci.yml"\n',
     '  pull_request:\n',
     "and so does pull_request", "both"),
    # ---- the matcher, because a filter held by a matcher that says yes to
    # everything is a filter held by nothing ----
    ("the matcher reads `**` as two single-segment stars, so nothing crosses a directory",
     '            if pat[i:i + 3] == "**/":\n                out.append("(?:.*/)?")\n                i += 3\n                continue',
     '            pass',
     "`**/` crosses directories", "suite"),
    ("a single star crosses separators after all",
     '            out.append("[^/]*")',
     '            out.append(".*")',
     "a single star does NOT cross a separator", "suite"),
    ("a pattern the matcher cannot read is treated as covering everything",
     '    if not SIMPLE.match(pat or ""):\n        return None',
     '    if not SIMPLE.match(pat or ""):\n        return re.compile(".*")',
     "A PATTERN OUT OF SCOPE IS REFUSED", "suite"),
    ("the deliverable copy drifts from the workflow it installs",
     '      - "gradlew.bat"\n      - "gradle.properties"\n', '      - "gradlew.bat"\n',
     "BYTE-IDENTICAL TO THE WORKFLOW", "mirror"),
    ("the filter is checked against nothing, because the walk files nothing as build",
     '        (build_files if is_build else others).append(rel)',
     '        others.append(rel)',
     "the tree has a Java build to be about at all", "suite"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect, where):
    tmp = tempfile.mkdtemp(prefix="mutci_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # The suite walks the tree from its own root, so the mutant needs a
        # tree: everything it reads is linked, and only the file being broken
        # is a real copy.
        for name in os.listdir(ROOT):
            if name in ("tools",):
                continue
            os.symlink(os.path.join(ROOT, name), os.path.join(tmp, name))
        target, src = None, None
        wf = os.path.join(ROOT, WF_REL)
        # ONE ANCHOR, EVERY OCCURRENCE IN EVERY COPY IT BELONGS IN. The filter
        # is written once and copied into both events AND into the deliverable
        # mirror, so a pattern that is wrong is wrong everywhere it appears --
        # mutating one place would be caught by the same-list or the drift
        # check and would prove nothing about coverage, which is what the
        # mutant is for. "mirror" is the exception: drifting is a one-sided
        # fault by definition.
        mirror = os.path.join(dst, "ci", "ci.yml")
        if where == "suite":
            targets = [os.path.join(dst, "verify", "verify_ci.py")]
        elif where == "mirror":
            targets = [mirror]
        else:
            # the workflow is linked, not copied: replace the link with files
            os.unlink(os.path.join(tmp, ".github"))
            shutil.copytree(os.path.join(ROOT, ".github"), os.path.join(tmp, ".github"))
            targets = [os.path.join(tmp, WF_REL), mirror]
        hits = 0
        for t in targets:
            body = io.open(t, encoding="utf-8").read()
            hits += body.count(find)
            io.open(t, "w", encoding="utf-8", newline="\n").write(body.replace(find, repl))
        if not hits:
            return ("BAD MUTANT",
                    "anchor matched 0 times in %s -- the mutation never applied" % where)
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_ci.py")],
                           capture_output=True, text=True, timeout=300)
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
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e, _w in MUTANTS:
            print("  %-64s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the CI path filter against verify_ci -- %d mutant(s), "
          "%d known equivalent\n" % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect, where in MUTANTS:
        verdict, detail = run_one(find, repl, expect, where)
        print("  %-9s %-64s %s" % (verdict, name, detail[:54]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    sys.path.insert(0, TOOLS)
    import mutant_ledger
    mutant_ledger.record("mutate_ci", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
