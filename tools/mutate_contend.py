# -*- coding: utf-8 -*-
"""Mutation testing for the contention instrument (ADR-143).

`contend.py` produces a NUMBER -- "2 of 8 runs failed, beside verify_tie_render"
-- and a number gets believed. An instrument for measuring flakiness that is
itself wrong is worse than no instrument, so it is broken on purpose here and
`verify_contend` has to notice.

    python3 tools/mutate_contend.py           # run every mutant
    python3 tools/mutate_contend.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

MUTANTS = [
    # ---- what a run said ----
    ("a suite that crashed with no FAIL line is not a failure",
     '''    failed = bool(fails) or rc != 0''',
     '''    failed = bool(fails)''',
     "crashed is FAILED even with no FAIL line"),
    ("a run reports THAT a check failed, not which one",
     '''            "checks": [f[:120] for f in fails[:8]], "tail": lines[-1][:120] if lines else "",''',
     '''            "checks": [], "tail": lines[-1][:120] if lines else "",''',
     "the text of the check that failed"),
    ("a failing run keeps none of its output",
     '''            "lines": lines[-40:] if failed else []}''',
     '''            "lines": []}''',
     "the run's own words around it are kept"),
    ("every run keeps its output, failing or not",
     '''            "lines": lines[-40:] if failed else []}''',
     '''            "lines": lines[-40:]}''',
     "a passing run keeps none"),
    ("the ledger keeps no record of the last failure",
     '''    worst = [r for r in rows if r["failed"]]''',
     '''    worst = []''',
     "the most recent failing run's output beside it"),
    ("the run is not timed",
     '''"seconds": round(time.time() - t0, 1),''',
     '''"seconds": 0.0,''',
     "a run is timed"),
    # ---- the load ----
    ("a co-tenant that finished stays finished",
     '''            if name is not None and p.poll() is not None:''',
     '''            if False:''',
     "is RESTARTED"),
    ("a co-tenant nobody has is started anyway",
     '''        self.beside = [b for b in beside if script_for(b)]''',
     '''        self.beside = list(beside)''',
     "is dropped rather than silently"),
    ("the load is left running when the measurement ends",
     '''        for _name, p in self.procs:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)''',
     '''        for _name, p in []:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)''',
     "leaves nothing behind"),
    # ---- the ledger ----
    ("a second reading replaces the first instead of adding to it",
     '''    e["runs"] += len(rows)
    e["failed"] += sum(1 for r in rows if r["failed"])''',
     '''    e["runs"] = len(rows)
    e["failed"] = sum(1 for r in rows if r["failed"])''',
     "the counts ADD"),
    ("a reading beside a different co-tenant lands on top of the old one",
     '''    cond = " beside " + (", ".join(sorted(beside)) if beside else "nothing")
    return target + cond + (" +%dcpu" % int(cpu) if int(cpu) else "")''',
     '''    return target''',
     # The first check to notice is the one that says a second load must not
     # cost the first reading -- which is the whole point of keying by
     # conditions, so it is the right one to name.
     "a different QUESTION and lands under"),
    ("the burners are not part of the conditions",
     '''    return target + cond + (" +%dcpu" % int(cpu) if int(cpu) else "")''',
     '''    return target + cond''',
     "so is the number of burners"),
    ("the key does not read as anything",
     '''    cond = " beside " + (", ".join(sorted(beside)) if beside else "nothing")''',
     '''    cond = "|" + "".join(sorted(beside))''',
     "the key READS as what it is"),
    ("the checks that failed are not counted by name",
     '''        for c in r["checks"]:
            e["checks"][c] = e["checks"].get(c, 0) + 1''',
     '''        for c in []:
            e["checks"][c] = e["checks"].get(c, 0) + 1''',
     "counted by name"),
    ("--no-ledger writes to the ledger anyway",
     '''        if not a.no_ledger:''',
     '''        if True:''',
     "--no-ledger writes nothing"),
    ("a failure under load is not an exit code",
     '''        rc = rc or (1 if n_bad else 0)''',
     '''        rc = 0''',
     "exits non-zero"),
    # ---- finding the thing ----
    ("only suites in verify/ can be measured, so no audit can be",
     '''    for cand in (os.path.join(VERIFY, name + ".py"), os.path.join(HERE, name + ".py")):''',
     '''    for cand in (os.path.join(VERIFY, name + ".py"),):''',
     "a TOOL is found beside it"),
    ("a name nobody has resolves to something",
     '''        if os.path.isfile(cand):
            return cand
    return None''',
     '''        if os.path.isfile(cand):
            return cand
    return os.path.join(VERIFY, name + ".py")''',
     "neither is None"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutcon2_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        path = os.path.join(dst, "contend.py")
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_contend.py")],
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
    print("mutation testing the contention instrument -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_contend", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
