# -*- coding: utf-8 -*-
"""Mutation testing for the delivery manifest and its audit (ADR-147).

This is the file that decides whether a slice's work reaches the repository at
all, and its failure mode is the quietest one in the kit: nothing is red,
nothing is missing from any measurement, and the file exists only on one
machine. A miscount here restores exactly the blind spot the slice was built to
close. So both halves are broken on purpose and `verify_delivery` has to notice.

    python3 tools/mutate_delivery.py           # run every mutant
    python3 tools/mutate_delivery.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("deliver.py", "audit_delivery.py")

MUTANTS = [
    # ---- the generated script ----
    ("the script stages nothing, because the paths are not written into it",
     '    for i, p in enumerate(paths):\n        a("  %s%s" % (p, " `" if i < len(paths) - 1 else ""))',
     '    for i, p in enumerate([]):\n        a("  %s%s" % (p, " `" if i < len(paths) - 1 else ""))',
     "the script stages tools/one.py"),
    ("only the first path is staged",
     '    for i, p in enumerate(paths):',
     '    for i, p in enumerate(paths[:1]):',
     "the script stages tools/two.py"),
    ("the paths are sorted rather than kept in the manifest's order",
     '    mid, paths = m["id"], list(m["paths"])',
     '    mid, paths = m["id"], sorted(m["paths"], reverse=True)',
     "in the manifest's order"),
    ("the backtick is escaped last, so every other escape is escaped again",
     '    return (s.replace("`", "``").replace(\'"\', \'`"\')\n             .replace("$", "`$")',
     '    return (s.replace(\'"\', \'`"\').replace("$", "`$")\n             .replace("`", "``")',
     "escaped for PowerShell"),
    ("a quote in the subject is not escaped",
     '.replace(\'"\', \'`"\')',
     '.replace(\'"\', \'"\')',
     "escaped for PowerShell"),
    ("a newline in the body is left in",
     '.replace("\\r", " ").replace("\\n", " "))',
     ')',
     "the body is one line"),
    ("the script is written where it used to live, outside the repo",
     '    p = os.path.join(PUSH, "push-%s.ps1" % mid)',
     '    p = os.path.join(os.path.dirname(ROOT), "push-%s.ps1" % mid)',
     "written into the repo"),
    ("the chain never runs the previous script",
     '            a(\'  if ($st) { Write-Host "%s is not committed yet -- running its script first"; & $prev }\'',
     '            a(\'  if ($false) { Write-Host "%s is not committed yet"; }\'',
     "a chain that only looks is not a chain"),
    ("the tarballs it delivered are never cleaned up",
     '    for t in m.get("clean") or []:',
     '    for t in []:',
     "tarballs it names are cleaned"),
    # ---- --check ----
    ("a hand-edited script is not compared, only its existence",
     '            if on_disk != script_text(m):',
     '            if False:',
     "edited by hand"),
    ("the comparison ignores what the manifest would generate",
     '            on_disk = io.open(sp, encoding="utf-8", newline="").read().replace("\\r\\n", "\\n")',
     '            on_disk = script_text(m)',
     "edited by hand"),
    ("a manifest may name a file that is not there",
     '            if not os.path.isfile(os.path.join(ROOT, p)):',
     '            if False:',
     "not there"),
    ("a manifest's id need not be its filename",
     '        if m.get("id") != mid:',
     '        if False:',
     "not its filename"),
    ("a chain may point at nothing",
     '        if c and not (os.path.isfile(manifest_path(c))',
     '        if False and not (os.path.isfile(manifest_path(c))',
     "worse than no chain"),
    # ---- the bundle ----
    ("the tarball leaves out the script that commits it",
     '    if script not in paths:\n        paths.append(script)',
     '    if False:\n        paths.append(script)',
     "the script that commits them"),
    ("the tarball ships the whole tree rather than the manifest's paths",
     '    paths = list(m["paths"])',
     '    paths = ["tools", "docs"]',
     "exactly the manifest's paths"),
    # ---- the audit ----
    ("a file the ledger has never seen counts as delivered",
     '        same = bool(e) and e.get("sha") == D.sha(os.path.join(ROOT, rel))',
     '        same = True',
     "UNDELIVERED"),
    ("the bytes are not compared, only the path",
     '        same = bool(e) and e.get("sha") == D.sha(os.path.join(ROOT, rel))',
     '        same = bool(e)',
     "BYTES have changed"),
    ("what a manifest claims is undelivered too, so a slice cannot work",
     '        elif rel in cl:\n            rows["claimed"].append(rel)',
     '        elif False:\n            rows["claimed"].append(rel)',
     "IN FLIGHT rather than undelivered"),
    ("every path counts as claimed, so nothing is ever undelivered",
     '        elif rel in cl:',
     '        elif True:',
     "UNDELIVERED"),
    ("the undelivered files are counted but not named",
     '    for p in r["undelivered"][:a.names]:\n        print("    %s" % p)',
     '    for p in []:\n        print("    %s" % p)',
     "they are NAMED in what it prints"),
    ("an undelivered file is reported and the exit code is not",
     '    return 1 if r["undelivered"] else 0',
     '    return 0',
     "fails with NO FLAG"),
    ("a path may be ignored with no reason given",
     '        if not a.reason.strip():',
     '        if False:',
     "WITHOUT a reason is refused"),
    ("the reason is not what is stored",
     '        state.setdefault("ignored", {})[a.ignore] = a.reason.strip()',
     '        state.setdefault("ignored", {})[a.ignore] = ""',
     "the reason is what is stored"),
    ("an ignored path is still on the worklist",
     '        if rel in ignored:\n            rows["ignored"].append(rel)\n            continue',
     '        if False:\n            rows["ignored"].append(rel)\n            continue',
     "leaves the worklist"),
    ("a file that was delivered and then deleted is a failure",
     '    rows["gone"] = sorted(p for p in led if p not in have and p not in ignored)',
     '    rows["gone"] = []\n    rows["undelivered"] += sorted(p for p in led if p not in have and p not in ignored)',
     "is not a failure"),
    # ---- the adoption ----
    ("an adoption takes in the slice's own work in flight",
     '        n = record(a.adopt, adopt=[p for p in AD.tracked() if p not in cl])',
     '        n = record(a.adopt, adopt=AD.tracked())',
     "does not adopt what a manifest CLAIMS"),
    ("an adoption does not say that it is one",
     '        state["_adopted"] = {"by": a.adopt, "at": int(time.time()), "paths": n,',
     '        state["_adopted"] = {"by": None, "at": int(time.time()), "paths": n,',
     "says in the ledger that it is an adoption"),
]

MUTANTS += [
    ("the script does not stage itself, so the record of what a slice staged is never committed",
     '    own = "tools/push/push-%s.ps1" % mid\n    if own not in paths:\n        paths.append(own)',
     '    own = "tools/push/push-%s.ps1" % mid\n    if False:\n        paths.append(own)',
     "stages ITSELF"),
]

MUTANTS += [
    ("the audit's summary line is scored by run_all, so files count as checks",
     '    print("%d delivered or claimed, %d undelivered" % (accounted, len(r["undelivered"])))',
     '    print("%d/%d files delivered or claimed" % (accounted, accounted + len(r["undelivered"])))',
     "is NOT in the shape run_all"),
]

KNOWN_EQUIVALENT = []




def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutdelivery_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        path = None
        for cand in SUBJECT:
            p2 = os.path.join(dst, cand)
            if io.open(p2, encoding="utf-8").read().count(find) == 1:
                path = p2
                break
        if path is None:
            n = sum(io.open(os.path.join(dst, c), encoding="utf-8").read().count(find)
                    for c in SUBJECT)
            return ("BAD MUTANT",
                    "anchor matched %d times across the subject -- the mutation never applied" % n)
        src = io.open(path, encoding="utf-8").read()
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_delivery.py")],
                           capture_output=True, text=True, timeout=900)
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
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-58s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the delivery manifest and its audit -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_delivery", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
