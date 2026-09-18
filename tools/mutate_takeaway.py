# -*- coding: utf-8 -*-
"""Mutation testing for the take-away audit (ADR-212).

`audit_takeaway.py` says 0 of the 81 controls that hand something over in this
kit are stranded -- reachable only by a page-started download, which the frame a
published artifact runs in refuses silently. It said 3 on the day it was written,
and all three told the reader the file had gone. A wrong reading is worse than
none in both directions: too high and the rule is noise and gets switched off,
after which a page that quietly loses its only working channel is invisible; too
low and a reader is told their morning is on their disk when it is nowhere. So
the measurement is broken on purpose and `verify_takeaway` has to notice.

    python3 tools/mutate_takeaway.py           # run every mutant
    python3 tools/mutate_takeaway.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_takeaway.py", "exempt.py")   # ADR-224: the shared rule is mutated here too

KNOWN_EQUIVALENT = []

MUTANTS = [
    ("a download counts as a channel that survives publication",
     'PUBLISHABLE = frozenset(["clipboard", "copy", "print"])',
     'PUBLISHABLE = frozenset(["clipboard", "copy", "print", "download"])',
     "A CONTROL WHOSE ONLY CHANNEL IS A DOWNLOAD IS STRANDED"),
    ("the clipboard does not count, so every copy button is stranded too",
     'PUBLISHABLE = frozenset(["clipboard", "copy", "print"])',
     'PUBLISHABLE = frozenset(["copy", "print"])',
     "IS NOT STRANDED"),
    ("print does not count",
     'PUBLISHABLE = frozenset(["clipboard", "copy", "print"])',
     'PUBLISHABLE = frozenset(["clipboard", "copy"])',
     "print is a channel a published page keeps"),
    ("nothing is stranded",
     '            r["stranded"] = bool(r["kinds"]) and not r["publishable"]',
     '            r["stranded"] = False',
     "A CONTROL WHOSE ONLY CHANNEL IS A DOWNLOAD IS STRANDED"),
    ("a control that hands nothing over at all is stranded",
     '            r["stranded"] = bool(r["kinds"]) and not r["publishable"]',
     '            r["stranded"] = not r["publishable"]',
     "the worklist is the stranded controls and nothing else"),
    ("nothing is ever a claim",
     '            return t[:120]',
     '            return None',
     "A CLAIM IS AN ASSERTION THAT THE PAYLOAD LEFT"),
    ("a hedged message is a claim too",
     '        if t and CLAIMED.search(t) and not HEDGED.search(t):',
     '        if t and CLAIMED.search(t):',
     "A HEDGED MESSAGE IS NOT A CLAIM"),
    ("any message at all is a claim",
     '        if t and CLAIMED.search(t) and not HEDGED.search(t):',
     '        if t:',
     "a refusal is not a claim"),
    ("only the past tense is a claim, so 'Downloading x' is not one",
     r'CLAIMED = re.compile(r"\b(download(ed|ing)|sav(ed|ing)|export(ed)?|writ(ten)?)\b", re.I)',
     r'CLAIMED = re.compile(r"\b(downloaded|saved)\b", re.I)',
     "in any tense the pages use"),
    ("a claim on a control that is not stranded is reported too",
     '                "claims": [(r["key"], r["said"]) for r in rows if r["stranded"] and r["said"]]}',
     '                "claims": [(r["key"], r["said"]) for r in rows if r["said"]]}',
     "A CLAIM IS ONLY A CLAIM ON A CONTROL NOTHING REACHES THE READER BY"),
    ("what the act said is not read at all",
     '                    rec["said"] = claims([m.get("text") if isinstance(m, dict) else m\n'
     '                                          for m in ((act or {}).get("said") or [])])',
     '                    rec["said"] = None',
     "WHAT THE PAGE SAID IS THIS PRESS'S"),
    ("which controls hand something over is decided here, by the label alone",
     '            for c in AO.candidates(snap):',
     '            for c in [x for x in snap.get("controls", [])\n'
     '                      if "download" in (x.get("label") or "").lower()]:',
     "WHICH CONTROLS HAND SOMETHING OVER IS AUDIT_OUTPUTS' RULE"),
    ("a declaration does not exempt the control",
     '    return [k for k in r.get("stranded", []) if k not in declared]',
     '    return list(r.get("stranded", []))',
     "a declared control leaves the worklist"),
    ("declaring a stranded control needs no reason at all",
     '        except ValueError:\n'
     '            print("declaring a stranded control expected needs --reason',
     '        except ValueError:\n            pass\n        if False:\n'
     '            print("declaring a stranded control expected needs --reason',
     "WITHOUT a reason is refused"),
    ("a declaration keeps no reason, so the ledger says what but never why",
     '        X.declare(state, page, key, a.reason)',
     '        X.declare(state, page, key, "yes")',
     "THE REASON IS WHAT IS STORED, word for word"),
    ("the ratchet runs upward",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):',
     '        if a.raise_floors and (ceiling is None or len(bad) > ceiling):',
     "--raise-floors LOWERS the ceiling"),
    ("a reading above the ceiling is not a failure",
     '        if ceiling is not None and len(bad) > ceiling:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     '        if False:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     "A PAGE THAT STRANDS MORE THAN IT DID FAILS"),
    ("a claim is reported and the exit code is not",
     '    return 1 if (above or lying or broken) else 0',
     '    return 1 if (above or broken) else 0',
     "FAILS ON SIGHT"),
    ("the claim names no page, no control and no sentence",
     '                print("    %-24s %-14s %s" % (name, k, m))',
     '                print("    a page said something that cannot be true")',
     "the run NAMES the page, the control and the sentence"),
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
    tmp = tempfile.mkdtemp(prefix="muttakeaway_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_takeaway.py")],
                           capture_output=True, text=True, timeout=1200)
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
    print("mutation testing the take-away audit -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_takeaway", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
