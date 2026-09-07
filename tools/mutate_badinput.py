# -*- coding: utf-8 -*-
"""Mutation testing for the rejected-buffer audit (ADR-151).

`audit_badinput.py` says N live number boxes across the kit cannot tell a
keystroke buffer the browser rejected from an empty one. That number is a
worklist and a ratchet, and a miscount is invisible in both directions: too
high invents work on pages doing nothing wrong, too low leaves a box that shows
the reader's characters and reports a blank. Neither looks any different from a
green number. So the measurement is broken on purpose and `verify_badinput` has
to notice.

    python3 tools/mutate_badinput.py           # run every mutant
    python3 tools/mutate_badinput.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_badinput.py",)

MUTANTS = [
    # ---- the subject ----
    ("every text input is a subject, so a box with no badInput joins the worklist",
     "document.querySelectorAll('input[type=\"number\"][data-h]')",
     "document.querySelectorAll('input[data-h]')",
     "not a subject"),
    # ---- the control ----
    ("the GOOD reading is never taken, so every box read only on submit is blind",
     '    live = _diff(g, b, unstable)',
     '        live = ["forced"]',
     "INERT, not blind"),
    ("a live box is one the page ignores",
     '    if not live:\n        rec["verdict"] = "inert"',
     '    if live:\n        rec["verdict"] = "inert"',
     "the finding this audit exists for"),
    # ---- the finding ----
    ("the bad value is ASSIGNED rather than typed, so badInput never goes true",
     '        plug.execute("type-text", {"selector": f["h"], "value": TOKEN})',
     '        plug.execute("set-text", {"selector": f["h"], "value": TOKEN})',
     "the finding this audit exists for"),
    ("badInput is not confirmed, so a box the token never reached counts as rejected",
     '    if not st.get("bad"):',
     '    if False:',
     "there is nothing there to be blind to"),
    ("blank is compared against blank, so nothing can ever differ",
     '    told = _diff(b, x, unstable)',
     '    told = _diff(b, b, unstable)',
     "checks validity.badInput"),
    # ---- what counts as telling them apart ----
    ("only text is compared, so a page that marks its bad boxes red reads as silent",
     '    out["m:" + at] = [e.className || "", e.getAttribute("aria-invalid") || "",\n                      e.hidden ? "h" : "", e.disabled ? "d" : ""].join("|");',
     '    ;',
     "marking the box aria-invalid"),
    ("aria-invalid is not part of the mark, which is the one attribute pages set",
     '    out["m:" + at] = [e.className || "", e.getAttribute("aria-invalid") || "",',
     '    out["m:" + at] = [e.className || "", "",',
     "marking the box aria-invalid"),
    ("only elements with ids are read, so a page that answers in one without an id is silent",
     '    const at = e.id ? ("#" + e.id) : ("@" + path(e));',
     '    if (!e.id) return; const at = "#" + e.id;',
     "carrying no id has still answered"),
    # ---- the walk and the ladder ----
    ("the states are not walked, so a box behind a tab is never asked",
     '    for _state, _r in S.each_state(pg, name, probe, entered=True):\n        pass',
     '    probe()',
     "the entry BRINGS INTO BEING"),
    ("the entry is not replayed, so the page is measured with nothing in it",
     '    for _state, _r in S.each_state(pg, name, probe, entered=True):\n        pass',
     '    for _state, _r in S.each_state(pg, name, probe, entered=False):\n        pass',
     "the page's own entry"),
    ("the first answer is the last one, so a box that tells them apart later is blind",
     '        if was is not None and (RANK[was["verdict"]] >= 5 or was.get("tries", 1) >= TRIES):',
     '        if was is not None:',
     "only moves up the ladder"),
    ("a later reading always wins, so a box that goes quiet in a later state is demoted",
     '        if was is None or RANK[rec["verdict"]] >= RANK[was["verdict"]]:',
     '        if True:',
     "letting a later, quieter reading overwrite"),
    # ---- what moves on its own ----
    ("nothing is dropped for moving on its own, so a clock tells every box apart",
     '    unstable = set(k for k in (set(r0) | set(r1)) if r0.get(k) != r1.get(k))',
     '    unstable = set()',
     "the finding this audit exists for"),
    ("the two readings are taken with no time between them, so nothing looks unstable",
     '    pg.wait_for_timeout(300)\n    r1 = _report(pg)',
     '    r1 = dict(r0)',
     "the clock is found by reading the page twice"),
    # ---- the good value ----
    ("the GOOD value ignores the box's own bounds",
     '    lo, hi = _num(f.get("min")), _num(f.get("max"))',
     '    lo, hi = None, None',
     "picked from the box's own bounds"),
    # ---- the worklist and the ratchet ----
    ("the blind boxes are counted but not named",
     '    return [_key(f) for f in r.get("fields", [])',
     '    return [_key(f) for f in []',
     "on the worklist, named"),
    ("a declared box is subtracted from the count instead of the worklist",
     '            if f.get("verdict") == "cannot-tell" and _key(f) not in declared]',
     '            if f.get("verdict") == "cannot-tell"]',
     "leaves the worklist"),
    ("a box may be declared exempt with no reason given",
     '        if not a.reason.strip():',
     '        if False:',
     "WITHOUT a reason is refused"),
    ("the reason is not what is stored",
     '        ledger.setdefault(page, {}).setdefault("declared", {})[eid] = a.reason.strip()',
     '        ledger.setdefault(page, {}).setdefault("declared", {})[eid] = ""',
     "the reason is what is stored"),
    ("a plain run lowers the ceilings, so nothing can ever be above one",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):',
     '        if (ceiling is None or len(bad) < ceiling):',
     "records what it found and no ceiling"),
    ("the ceiling ratchets UPWARD, so a page that grows a blind box keeps its pass",
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
    ("the box's value is restored with type-text instead of set-text",
     "`plug.execute(\"set-text\", ...)` in the restore -> `type-text`. The restore puts the "
     "box back the way the entry left it so the next box is measured against the same page; "
     "either action gets the characters in, and the restored value is read by nothing before "
     "the next set-text overwrites it. Typing it would be slower and no fixture can tell the "
     "two apart -- which is the point of ADR-150's own held claim that type-text is for the "
     "cases where the difference matters, not a replacement."),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutbadinput_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_badinput.py")],
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
            print("  %-62s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the rejected-buffer audit -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-62s %s" % (verdict, name, detail[:54]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    import mutant_ledger
    mutant_ledger.record("mutate_badinput", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
