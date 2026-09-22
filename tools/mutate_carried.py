# -*- coding: utf-8 -*-
"""Mutation testing for the carried-figures audit (ADR-211).

`audit_carried.py` says 132 of the 317 figures nineteen exporting pages of this
kit work out appear in nothing those pages hand over. A wrong number is worse
than none: too high and the audit reads as noise and gets switched off, after
which a page that quietly stops exporting its analysis is invisible again; too
low and an ethogram session is scored, exported and argued about for a year
without the kappa that says whether it is worth anything, with every suite in
this kit green. So the measurement is broken on purpose and `verify_carried`
has to notice.

    python3 tools/mutate_carried.py           # run every mutant
    python3 tools/mutate_carried.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_carried.py", "exempt.py")   # ADR-224: the shared rule is mutated here too

KNOWN_EQUIVALENT = [
    ("each page is measured in its own browser context",
     "These pages keep their work in localStorage, and a shared context would carry one page's "
     "sheet into the next one's export -- the defect ADR-209 found next door, and the reason "
     "audit_restored does the same thing. No fixture here can show it, because the fixtures "
     "deliberately keep nothing: a fixture that autosaved would be testing KEEP rather than this "
     "rule. The separation stays because the kit's real pages do autosave, and a reading taken "
     "from a page holding the previous page's data is about neither page."),
]

MUTANTS = [
    ("nothing is ever lost",
     '            if not c:\n                lost.append(lab)',
     '            if False:\n                lost.append(lab)',
     "A FIGURE IN NO PAYLOAD IS LOST"),
    ("everything is lost, because nothing is ever found",
     '    for w, tol in want:\n'
     '        if not any(abs(p - w) < tol for p in pool):\n'
     '            return False\n'
     '    return True',
     '    return False',
     "A PAGE THAT EXPORTS WHAT IT WORKS OUT LOSES NOTHING"),
    ("only the FIRST number of a figure has to be found",
     '    for w, tol in want:',
     '    for w, tol in want[:1]:',
     "EVERY NUMBER IN THE FIGURE MUST BE FOUND"),
    ("a superscript exponent is left as it was written",
     '    s = "".join(SUP.get(ch, ch) for ch in s)',
     '    s = "".join(ch for ch in s)',
     "a superscript exponent is a number"),
    ("`x10^n` is not rewritten as an exponent",
     '    s = re.sub(r"x\\s*10\\s*\\^?\\s*([-+]?\\d+)", r"e\\1", s)',
     '    s = s',
     "a superscript exponent is a number"),
    ("a typographic minus is left as it was written",
     '    s = s.replace(u"\u2212", "-")',
     '    s = s.replace(u"\u2212", "\u2212")',
     "a typographic minus is a minus"),
    ("every comma after a digit is a thousands separator",
     '    s = re.sub(r"(?<=\\d),(?=\\d\\d\\d(?!\\d))", "", s)',
     '    s = re.sub(r"(?<=\\d),", "", s)',
     "a comma before four digits is not a separator either"),
    ("the precision read is nobody's, so every figure is matched to the unit",
     '        out.append((float(m.group(0)), 10.0 ** (exp - dec)))',
     '        out.append((float(m.group(0)), 1.0))',
     "and one carrying LESS has not"),
    ("a token no float can hold is taken as a figure, and the page is reported broken",
     '        if not (-300 < exp - dec < 300):\n'
     '            continue',
     '        if False:\n'
     '            continue',
     "A TOKEN IN A PAGE IS NOT ALWAYS A QUANTITY"),
    ("the exponent is not read, so a figure in scientific notation is matched to its mantissa",
     '        exp = int(m.group(2) or 0)',
     '        exp = 0',
     "AND THE EXPONENT COUNTS"),
    ("the decimals are not read, so every figure is matched to the unit it is scaled by",
     '        dec = len(m.group(1) or "")',
     '        dec = 0',
     "and one carrying LESS has not"),
    ("the match is exact, so an export carrying more detail loses the figure",
     '        if not any(abs(p - w) < tol for p in pool):',
     '        if not any(p == w for p in pool):',
     "AN EXPORT CARRYING MORE PRECISION"),
    ("a figure with no number in it is counted as lost",
     '            if c is None:\n                continue',
     '            if False:\n                continue',
     "A FIGURE WITH NO NUMBER IN IT IS NOT MEASURED"),
    ("the payload is never parsed, so no figure is ever in it",
     '        pool = nums(blob)',
     '        pool = []',
     "A PAGE THAT EXPORTS WHAT IT WORKS OUT LOSES NOTHING"),
    ("the page is never entered, so the export is pressed on an empty sheet",
     '    for _state, _r in S.each_state(pg, name, probe, entered=True):',
     '    for _state, _r in S.each_state(pg, name, probe, entered=False):',
     "THE FIGURES ARE THE ONES THE PAGE PUBLISHES"),
    ("which controls hand something over is decided here, by the label alone",
     '        for c in AO.candidates(snap):',
     '        for c in [x for x in snap.get("controls", [])\n'
     '                  if "copy" in (x.get("label") or "").lower()]:',
     "WHICH CONTROLS HAND SOMETHING OVER IS AUDIT_OUTPUTS' RULE"),
    ("a page that hands nothing over is reported as losing everything",
     '        if r.get("noexport"):\n            continue',
     '        if False:\n            continue',
     "A PAGE THAT HANDS NOTHING OVER GETS NO ROW AND NO CEILING"),
    ("a declaration does not exempt the figure",
     '    return [k for k in r.get("lost", []) if k not in declared]',
     '    return list(r.get("lost", []))',
     "a declared figure leaves the worklist"),
    ("declaring a figure right to stay needs no reason at all",
     '        except ValueError:\n'
     '            print("declaring a figure right to stay needs --reason',
     '        except ValueError:\n            pass\n        if False:\n'
     '            print("declaring a figure right to stay needs --reason',
     "WITHOUT a reason is refused"),
    ("a declaration keeps no reason, so the ledger says what but never why",
     '        X.declare(state, page, key, a.reason)',
     '        X.declare(state, page, key, "yes")',
     "THE REASON IS WHAT IS STORED, word for word"),
    ("the ratchet runs upward, so a page that stopped exporting records it as normal",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):',
     '        if a.raise_floors and (ceiling is None or len(bad) > ceiling):',
     "--raise-floors LOWERS the ceiling"),
    ("a reading above the ceiling is not a failure",
     '        if ceiling is not None and len(bad) > ceiling:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     '        if False:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     "EXPORTS LESS THAN IT DID FAILS"),
    ("the failure is reported and the exit code is not",
     '    return 1 if (above or broken) else 0',
     '    return 0',
     "EXPORTS LESS THAN IT DID FAILS"),
    ("the failure names no page and no figure",
     '            print("    %-30s %d, ceiling %d: %s" % (name, now, ceiling, ", ".join(keys[:a.names])))',
     '            print("    a page stopped exporting something")',
     "it NAMES the page and the figure"),
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

MUTANTS += [
    # ---- ADR-236: two clocks ----------------------------------------------
    ("the page is read under the real clock only",
     '''            for off in shifts:''',
     '''            for off in shifts[:1]:''',
     "A FIGURE ONLY THE CLOCK CARRIES IS LOST"),
    ("the second clock is never installed",
     '''                if off:
                    ctx.add_init_script(SHIFT_JS % off)''',
     '''                if False:
                    ctx.add_init_script(SHIFT_JS % off)''',
     "A FIGURE ONLY THE CLOCK CARRIES IS LOST"),
    ("the shift script shifts nothing",
     '''  if (!off) return;''',
     '''  return;''',
     "A FIGURE ONLY THE CLOCK CARRIES IS LOST"),
    ("the shift moves the date but not the hour or minute",
     '''SHIFTS_MS = (0, ((405 * 24 + 7) * 60 + 23) * 60 * 1000 + 31 * 1000 + 457)''',
     '''SHIFTS_MS = (0, ((405 * 24 + 0) * 60 + 0) * 60 * 1000 + 31 * 1000 + 457)''',
     "A FIGURE ONLY THE CLOCK CARRIES IS LOST"),
    ("a figure is lost only if EVERY clock lost it",
     '''    lost = sorted(set(l for r in ok for l in (r.get("lost") or [])))''',
     '''    lost = sorted(set.intersection(*[set(r.get("lost") or []) for r in ok]))''',
     "A FIGURE ONLY THE CLOCK CARRIES IS LOST"),
    ("the figures are the first clock's labels only",
     '''    labels = sorted(set(l for r in ok for l in (r.get("labels") or [])))''',
     '''    labels = sorted(ok[0].get("labels") or [])''',
     "combine: a figure is lost if any clock lost it"),
    ("a reading that failed under one clock is dropped",
     '''    if len(ok) < len(readings):
        return [r for r in readings if r.get("error")][0]''',
     '''    if False:
        return [r for r in readings if r.get("error")][0]''',
     "a reading that failed under either clock is the reading"),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutcarried_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_carried.py")],
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
    print("mutation testing the carried-figures audit -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_carried", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
