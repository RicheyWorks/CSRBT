# -*- coding: utf-8 -*-
"""Mutation testing for the restored-page audit (ADR-210).

`audit_restored.py` says 0 of 552 things the seventeen keeping pages say before
the tab closes go missing when it comes back. It said 125 on the day it was
written. A miscount is invisible in both directions: too high and the rule gets
turned off, after which a page that loses a morning's analysis on reload is
invisible again; too low and a sheet comes back with its records and without the
answers, with every suite in this kit green. So the measurement is broken on
purpose and `verify_restored` has to notice.

    python3 tools/mutate_restored.py           # run every mutant
    python3 tools/mutate_restored.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_restored.py", "exempt.py")   # ADR-224: the shared rule is mutated here too

KNOWN_EQUIVALENT = [
    ("the autosave is never flushed before the reload",
     "KEEP flushes a pending write on `pagehide`, which a reload fires -- so a page that is "
     "about to be reloaded saves whether this audit asks it to or not, and removing the explicit "
     "flush changes nothing any check can see. The flush stays because it makes the measurement "
     "independent of that: a page whose autosave stopped listening for pagehide would still be "
     "measured against what it actually holds, rather than reported clean because nothing was "
     "saved to come back from."),
]

MUTANTS = [
    ("nothing is ever a loss",
     '        lost = sorted(k for k, v in before.items()\n'
     '                      if k not in after or after[k] != v)',
     '        lost = []',
     "a page whose snapshot leaves its records out comes back without them"),
    ("only a key that VANISHED counts, so a value that came back wrong is not a loss",
     '                      if k not in after or after[k] != v)',
     '                      if k not in after)',
     "A VALUE THAT CHANGED IS A LOSS"),
    ("every key that changed counts, so the status strips are losses too",
     '        lost = [k for k in lost\n'
     '                if k.split("/")[1] not in STATUS and k.split("/")[1] not in panes]',
     '        lost = list(lost)',
     "A PAGE THAT KEEPS WHAT IT HOLDS AND REPAINTS IT COMES BACK WHOLE"),
    ("a pane counts, so the same difference is counted twice under its container",
     '        lost = [k for k in lost\n                if k.split("/")[1] not in STATUS and k.split("/")[1] not in panes]',
     '        lost = [k for k in lost\n                if k.split("/")[1] not in STATUS]',
     "A PANE IS A CONTAINER, NOT A REPORT"),
    ("the autosave's own strip is taken off the list, so a restored page reports it as a loss",
     '    "keepBox": "the autosave\'s own strip',
     '    "keepBoxNever": "the autosave\'s own strip',
     "A PAGE THAT KEEPS WHAT IT HOLDS AND REPAINTS IT COMES BACK WHOLE"),
    ("the page is never entered, so there is nothing to lose",
     '        for _state, _r in S.each_state(pg, name, probe, entered=True):\n'
     '            pass',
     '        pass',
     "every fixture was entered, flushed and reloaded"),
    ("the tab is never reloaded, so the two readings are the same reading",
     '        pg.reload(wait_until="domcontentloaded")',
     '        pass',
     "a page whose snapshot leaves its records out comes back without them"),
    ("whether the page restored is not recorded",
     '        restored = bool(pg.evaluate(RESTORED_JS))',
     '        restored = True',
     "reported as NOT RESTORED"),
    ("the boxes are dropped from the reading, so only figures are compared",
     '    for box, txt in (rep.get("boxes") or {}).items():\n'
     '        out["box/%s" % box] = txt',
     '    pass',
     "A PAGE THAT KEEPS EVERYTHING AND REPAINTS HALF OF IT"),
    ("the figures are dropped from the reading, so only prose is compared",
     '    for box, vals in (rep.get("by") or {}).items():',
     '    for box, vals in {}.items():',
     "BOTH HALVES OF THE READING ARE COMPARED"),
    ("a declaration does not exempt the difference",
     '    return [k for k in r.get("lost", []) if k not in declared]',
     '    return list(r.get("lost", []))',
     "a declared difference leaves the worklist"),
    ("declaring a difference needs no reason at all",
     '        except ValueError:\n'
     '            print("declaring a difference expected needs --reason',
     '        except ValueError:\n            pass\n        if False:\n'
     '            print("declaring a difference expected needs --reason',
     "WITHOUT a reason is refused"),
    ("a declared difference keeps no reason, so the ledger says what but never why",
     '        X.declare(state, page, key, a.reason)',
     '        X.declare(state, page, key, "yes")',
     "THE REASON IS WHAT IS STORED, word for word"),
    ("the ratchet runs upward, so a page that lost something records it as the new normal",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):',
     '        if a.raise_floors and (ceiling is None or len(bad) > ceiling):',
     "--raise-floors LOWERS the ceiling"),
    ("a reading above the ceiling is not a failure",
     '        if ceiling is not None and len(bad) > ceiling:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     '        if False:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     "COMES BACK SAYING LESS THAN IT SAID FAILS"),
    ("the failure is reported and the exit code is not",
     '    return 1 if (above or broken) else 0',
     '    return 0',
     "COMES BACK SAYING LESS THAN IT SAID FAILS"),
    ("the failure names no page and nothing that went",
     '            print("    %-30s %d, ceiling %d: %s" % (name, now, ceiling, ", ".join(keys[:a.names])))',
     '            print("    a page came back saying less")',
     "it NAMES the page and what went"),
    ("the pages walked are a list kept here rather than the emitter's",
     'KEEPERS = list(_ke.CONSUMERS)',
     'KEEPERS = ["releve.html"]',
     "THE PAGES THIS AUDIT WALKS ARE THE EMITTER'S LIST"),
]


MUTANTS += [
    # ---- ADR-224: the shared rule, asserted through THIS audit's own reading ----
    ("the exemption is applied and nothing is recorded",
     '    entry[raw] = list(flagged)\n    entry[universe] = sorted(',
     '    entry[universe] = sorted(',
     "records what was flagged BEFORE the exemption"),
    ("the raw list is recorded, and the universe is not",
     '    entry[universe] = sorted(set(str(k) for k in seen) | set(str(k) for k in flagged))',
     '    pass',
     "everything the reading could have flagged"),
    ("the record is what SURVIVED the filter, not what was flagged",
     '    return [k for k in flagged if k not in declared]',
     '    kept = [k for k in flagged if k not in declared]\n    entry[raw] = list(kept)\n    return kept',
     "records what was flagged BEFORE the exemption"),
    ("a reason of nothing but spaces will do",
     '    if not (reason or "").strip():\n        raise ValueError("a declaration needs a reason")',
     '    if reason is None:\n        raise ValueError("a declaration needs a reason")',
     "WITHOUT a reason is refused"),
    ("the row holds the audit's own live list rather than a copy of it",
     '    flagged = list(flagged)\n    entry[raw] = list(flagged)',
     '    entry[raw] = flagged',
     "the record is a COPY"),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutrestored_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_restored.py")],
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
            print("  %-64s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the restored-page audit -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-64s %s" % (verdict, name, detail[:52]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    import mutant_ledger
    mutant_ledger.record("mutate_restored", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
