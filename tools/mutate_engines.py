# -*- coding: utf-8 -*-
"""Mutation testing for the engine ledger and the engine attestation (ADR-139).

Two suites, one subject area, so one runner. A mutant in `ecosystem.py` is put
to `verify_ecosystem`; one in `engine_attest.py` is put to
`verify_engine_sessions`. The runner picks the suite from the file the anchor
is in rather than making the catalogue say it twice.

What is being defended: a ratchet that cannot go down (per engine AND per test
class), and an attestation that expires the moment the engine moves. Both are
the same kind of claim -- a record that is only allowed to say what it was
taken against -- and both fail quietly if nobody breaks them on purpose.

    python3 tools/mutate_engines.py           # run every mutant
    python3 tools/mutate_engines.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUITE_FOR = {"ecosystem.py": "verify_ecosystem.py",
             "engine_attest.py": "verify_engine_sessions.py"}

MUTANTS = [
    # ---- the ratchet, per engine ----
    ("the floor falls to whatever was last read",
     '''        if agg["tests"] > e.get("floor", 0):
            e["floor"] = agg["tests"]''',
     '''        e["floor"] = agg["tests"]''',
     "a read never lowers a floor"),
    ("a floor may be lowered with no reason given",
     '''        if not a.reason.strip():
            print("lowering a floor needs --reason: it goes into the ledger")
            return 2''',
     '''        if False:
            print("lowering a floor needs --reason: it goes into the ledger")
            return 2''',
     "lowering a floor with no reason is refused"),
    # ---- the ratchet, per test class ----
    ("the class ratchet is not kept at all",
     '''        cf = e.setdefault("classFloor", {})''',
     '''        cf = {}''',
     "a class seen for the first time joins the ratchet"),
    ("a class floor falls to what was last read",
     '''            if n > cf.get(nm, 0):
                cf[nm] = n''',
     '''            cf[nm] = n''',
     "never lowers a class floor either"),
    ("only one module's classes reach the ratchet",
     '''                merged = dict(agg["suites"])
                for k, v in r["suites"].items():
                    merged[k] = merged.get(k, 0) + v
                agg["suites"] = merged''',
     '''                pass''',
     "puts both modules' classes on the ratchet"),
    ("every test class is read under the same name",
     '''        nm = root.get("name") or os.path.basename(x)[len("TEST-"):-len(".xml")]''',
     '''        nm = "suite"''',
     "not in the results any more"),
    ("forgetting a class needs no reason",
     '''        if not a.reason.strip():
            print("forgetting a test class needs --reason: it goes into the ledger")
            return 2''',
     '''        if False:
            print("forgetting a test class needs --reason: it goes into the ledger")
            return 2''',
     "forgetting a test class with no reason is refused"),
    # ---- the attestation ----
    ("an attestation applies whatever the engine has done since",
     '''    if entry.get("engineDigest") != digest:''',
     '''    if False:''',
     "stops applying -- STALE, not attested"),
    ("nothing attested reads as attested",
     '''        return ("absent" if e is None else "stale"), why''',
     '''        return "attested", why''',
     "with nothing attested the answer is ABSENT"),
    ("the attested bytes are not compared to the shipped ones",
     '''    if e.get("sha") != sha_text(shipped_text):''',
     '''    if False:''',
     "edit the shipped file and the attestation says so"),
    ("the digest is of the bytes alone, so a rename is the same engine",
     '''        h.update(os.path.relpath(f, ROOT).replace(os.sep, "/").encode("utf-8"))
        h.update(b"\\0")''',
     '''        pass''',
     "a renamed source file is a different engine"),
    ("the digest covers one module, so the other may move unseen",
     '''SOURCE_ROOTS = (os.path.join("csrbt-core", "src", "main", "java"),
                os.path.join("csrbt-experimental", "src", "main", "java"))''',
     '''SOURCE_ROOTS = (os.path.join("csrbt-experimental", "src", "main", "java"),)''',
     "it is the digest the committed attestation was taken against"),
    ("an attestation records no engine digest at all",
     '''    entry = {"sha": sha_text(text), "bytes": len(text.encode("utf-8")),
             "engineDigest": digest, "sourceFiles": n,''',
     '''    entry = {"sha": sha_text(text), "bytes": len(text.encode("utf-8")),
             "engineDigest": "", "sourceFiles": n,''',
     "an attestation records the engine digest as it stood"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="muteng_")
    try:
        # THE SUBJECT READS ITS SIBLINGS. ecosystem.py resolves every engine at
        # <repo>/.., so a copied tools/ in a bare temp dir finds no engine at
        # all -- every ledger check is skipped and every mutant "survives" a
        # suite that never looked. The temp tree therefore mirrors the real
        # layout: <tmp>/eco/CSRBT/tools, with docs/ and every sibling repo
        # linked in beside it. Links, not copies: neither suite writes there,
        # and a mutant must not be able to.
        eco = os.path.join(tmp, "eco")
        here = os.path.join(eco, "CSRBT")
        os.makedirs(here)
        dst = os.path.join(here, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(here, "docs"))
        for d in sorted(os.listdir(os.path.join(ROOT, ".."))):
            if d != "CSRBT" and os.path.isdir(os.path.join(ROOT, "..", d)):
                os.symlink(os.path.normpath(os.path.join(ROOT, "..", d)), os.path.join(eco, d))
        for d in ("csrbt-core", "csrbt-experimental"):
            os.symlink(os.path.join(ROOT, d), os.path.join(here, d))
        for d in ("settings.gradle.kts", "build.gradle.kts", "gradle"):
            src_p = os.path.join(ROOT, d)
            if os.path.exists(src_p):
                os.symlink(src_p, os.path.join(here, d))
        path = suite = None
        for cand, s in SUITE_FOR.items():
            p2 = os.path.join(dst, cand)
            if io.open(p2, encoding="utf-8").read().count(find) == 1:
                path, suite = p2, s
                break
        if path is None:
            n = sum(io.open(os.path.join(dst, c), encoding="utf-8").read().count(find)
                    for c in SUITE_FOR)
            return ("BAD MUTANT", "anchor matched %d times across the subject -- the mutation never applied" % n)
        src = io.open(path, encoding="utf-8").read()
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        # A ledger mutant only shows up once a READ has been taken through the
        # mutated code, so take one -- into the temp tree's own copy of the
        # ledger, never the repo's.
        if os.path.basename(path) == "ecosystem.py":
            subprocess.run([sys.executable, path, "--read"], capture_output=True, text=True, timeout=600)
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", suite)],
                           capture_output=True, text=True, timeout=900)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        hit = any(expect in f for f in fails)
        return ("killed" if hit else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-58s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the engine ledger and attestation -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-58s %s" % (verdict, name, detail[:58]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    import mutant_ledger
    mutant_ledger.record("mutate_engines", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
