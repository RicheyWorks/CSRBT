# -*- coding: utf-8 -*-
"""Mutation testing for the outputs audit (ADR-153).

`audit_outputs.py` says 44 outputs across the kit leave a page with nothing
reading them. That number is a worklist and a ratchet, and a miscount is
invisible either way: too high invents work on exports somebody already checks,
too low leaves a page free to export a wrong file with every suite green. So
the measurement is broken on purpose and `verify_outputs` has to notice.

    python3 tools/mutate_outputs.py           # run every mutant
    python3 tools/mutate_outputs.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_outputs.py",)

MUTANTS = [
    # ---- what counts as a candidate ----
    ("every control is a candidate, so a page's whole toolbar is pressed",
     '        if not label or not HANDS_OVER.search(label):\n            continue',
     '        if not label:\n            continue',
     "not named for handing anything over is not a candidate"),
    ("the verb matches inside a word, so anything with save in it hands something over",
     r'HANDS_OVER = re.compile(r"\b(copy|download|export|print|save)\b|\.csv\b|\.eco\b", re.I)',
     r'HANDS_OVER = re.compile(r"(copy|download|export|print|save)|\.csv|\.eco", re.I)',
     "a verb INSIDE a word is not a verb"),
    ("a text box is a control that hands something over",
     '        if c.get("kind", "").endswith("_in") or c.get("kind") in ("pick_search",):\n            continue',
     '        if False:\n            continue',
     "TEXT BOX whose label happens to say save"),
    ("print is not a verb, so the print path is never measured",
     r'HANDS_OVER = re.compile(r"\b(copy|download|export|print|save)\b|\.csv\b|\.eco\b", re.I)',
     r'HANDS_OVER = re.compile(r"\b(copy|download|export)\b|\.csv\b|\.eco\b", re.I)',
     "a print is an output too"),
    # ---- the destructive rule ----
    ("the gateway's own risk rule is not consulted, and Forget is pressed",
     '        if PP.destroys(label, c.get("title") or ""):\n            continue',
     '        if False:\n            continue',
     "matches `copy` and is NOT a candidate"),
    # ---- measured with the page's own data in it ----
    ("the page is measured from rest, so an export hands over the empty-state line",
     '        if has_task and getattr(pg, "_audit_entered", None) is None:\n            return None',
     '        if False:\n            return None',
     "never be asked again"),
    ("the entry is never replayed at all",
     '    for _state, _r in S.each_state(pg, name, probe, entered=True):\n        pass',
     '    for _state, _r in S.each_state(pg, name, probe, entered=False):\n        pass',
     "measured AFTER the entry"),
    ("the states are not walked, so a button behind a tab is never pressed",
     '    for _state, _r in S.each_state(pg, name, probe, entered=True):\n        pass',
     '    probe()',
     "behind a tab is a button"),
    # ---- what collect-output said ----
    ("the payloads are never asked for, so nothing emits",
     '                _ok, _m, out = plug.execute("collect-output", {})\n                pays = out.get("payloads") or []',
     '                plug.execute("collect-output", {})\n                pays = []',
     "no more and no fewer"),
    ("the button is never pressed, so the payloads are somebody else's",
     '                plug.execute("activate", {"selector": c["selector"]})',
     '                pass',
     "not the empty-state placeholder"),
    ("a download is not an output",
     '            rec["kinds"] = sorted(set(p.get("k") for p in pays))',
     '            rec["kinds"] = sorted(set(p.get("k") for p in pays if p.get("k") != "download"))',
     "a Blob download comes back as one"),
    # ---- held means pressed AND read ----
    ("pressing an output counts as reading it",
     '        rec["held"] = (rec["verdict"] == "emits"\n                       and (k in read or rec["id"] in read or (rec["label"] or "") in read))',
     '        rec["held"] = (rec["verdict"] == "emits"\n                       and (k in pressed or rec["id"] in pressed or (rec["label"] or "") in pressed))',
     "presses and never asks about is NOT held"),
    ("the task is credited with reading everything it pressed",
     '    return pressed, read',
     '    return pressed, pressed',
     "presses and never asks about is NOT held"),
    ("a collect-output reads a button the task presses LATER in the run",
     '        elif a == "collect-output":',
     '        elif a == "collect-output" or True:',
     "presses and never asks about is NOT held"),
    ("a task that reads nothing still holds everything",
     '    if not task:\n        return set(), set()',
     '    if task:\n        return set(), set()',
     "presses and then asks about is HELD"),
    # ---- the worklist and the ratchet ----
    ("the unread outputs are counted but not named",
     '    return [b["key"] for b in r.get("buttons", [])',
     '    return [b["key"] for b in []',
     "no more and no fewer"),
    ("a silent button is on the worklist too",
     '            if b.get("verdict") == "emits" and not b.get("held") and b["key"] not in declared]',
     '            if not b.get("held") and b["key"] not in declared]',
     "no more and no fewer"),
    ("a declared output is subtracted from the count instead of the worklist",
     '            if b.get("verdict") == "emits" and not b.get("held") and b["key"] not in declared]',
     '            if b.get("verdict") == "emits" and not b.get("held")]',
     "leaves the worklist"),
    ("an output may be declared exempt with no reason given",
     '        if not a.reason.strip():',
     '        if False:',
     "WITHOUT a reason is refused"),
    ("the reason is not what is stored",
     '        ledger.setdefault(page, {}).setdefault("declared", {})[key] = a.reason.strip()',
     '        ledger.setdefault(page, {}).setdefault("declared", {})[key] = ""',
     "the reason is what is stored"),
    ("a plain run lowers the ceilings, so nothing can ever be above one",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):',
     '        if (ceiling is None or len(bad) < ceiling):',
     "records what it found and no ceiling"),
    ("the ceiling ratchets UPWARD, so a page that grows an unread export keeps its pass",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):\n            e["ceiling"] = len(bad)',
     '        if a.raise_floors and (ceiling is None or len(bad) > ceiling):\n            e["ceiling"] = len(bad)',
     "--raise-floors LOWERS the ceiling"),
    ("a reading above the ceiling is not a failure",
     '        if ceiling is not None and len(bad) > ceiling:\n            above.append((name, len(bad), ceiling))',
     '        if False:\n            above.append((name, len(bad), ceiling))',
     "fails, with no flag"),
    ("the failure is reported and the exit code is not",
     '            print("    %-30s %d, ceiling %d" % (name, now, ceiling))\n        return 1',
     '            print("    %-30s %d, ceiling %d" % (name, now, ceiling))\n        return 0',
     "fails, with no flag"),
]

KNOWN_EQUIVALENT = [
    ("a button is keyed by its label alone rather than id-then-label",
     "`key_of` -> return the label only. Every button on the fixture, and every export in the "
     "kit, has either an id or a label unique on its page, so the two keyings agree everywhere "
     "a fixture can reach. The id is preferred because it is what a task's selector usually "
     "names, and a page that grew two buttons with one label would key them together -- which "
     "is a fact about pages that do not exist yet."),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutoutputs_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_outputs.py")],
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
    print("mutation testing the outputs audit -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_outputs", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
