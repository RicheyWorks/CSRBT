# -*- coding: utf-8 -*-
"""Mutation testing for the readable-figures audit (ADR-146).

`audit_readable.py` says 26 elements across the kit hold a figure `read-report`
cannot see. That number is a worklist and a ratchet, and a miscount here is
invisible in both directions: too high invents work nobody needs to do, too low
hides a figure no task will ever hold. Neither looks any different from a green
number. So the measurement is broken on purpose and `verify_readable` has to
notice.

    python3 tools/mutate_readable.py           # run every mutant
    python3 tools/mutate_readable.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_readable.py",)

MUTANTS = [
    # ---- what counts as written ----
    ("the baseline page runs its own scripts, so a boot figure reads as unchanged",
     'dead = b.new_context(viewport=H.VIEWPORT, java_script_enabled=False)',
     'dead = b.new_context(viewport=H.VIEWPORT, java_script_enabled=True)',
     "written AT BOOT counts"),
    ("there is no baseline, so every paragraph on the page is a figure the page wrote",
     '                before = dpg.evaluate(TEXT_JS, False)',
     '                before = {}',
     "never writes is not a written element"),
    ("the page is measured at rest, so a figure the entry brings into being is missed",
     '    ent = S.enter(pg, name, tasks_dir=tasks_dir)',
     '    ent = None',
     "once the entry has run"),
    ("the states are not walked, so a figure behind a tab is not one",
     '    for _state, _r in S.each_state(pg, name, lambda: None, entered=False):\n        pass',
     '    for _state, _r in []:\n        pass',
     "behind a tab is a figure"),
    ("every changed id is reported, not just the deepest",
     '    written = pg.evaluate(DEEPEST_JS, changed) if changed else []',
     '    written = changed',
     "DEEPEST id in a chain"),
    ("an element that never changed is written too",
     '    changed = sorted(k for k, v in after.items() if before.get(k) != v)',
     '    changed = sorted(after.keys())',
     "never writes is not a written element"),
    ("a control's own text is a report",
     '    if (e.hasAttribute("data-h")) return;',
     '    if (false) return;',
     "a control is not a report"),
    ("an input's value is a report",
     '    if (t === "input" || t === "textarea" || t === "select" || t === "option") return;',
     '    if (false) return;',
     "neither is an <option>"),
    # ---- what counts as readable ----
    ("boxes are the only channel, so every table and chart is a figure nobody can read",
     '    readable = sorted(set(boxes) | set(channels))',
     '    readable = sorted(boxes)',
     "read through the second one"),
    ("a table is a figure nobody can read",
     '  document.querySelectorAll("svg, table").forEach(e => {',
     '  document.querySelectorAll("svg").forEach(e => {',
     "read through the second one"),
    ("an svg is a figure nobody can read",
     '  document.querySelectorAll("svg, table").forEach(e => {\n    const host',
     '  document.querySelectorAll("table").forEach(e => {\n    const host',
     "through the third"),
    ("a channel is keyed by the element, not by the id that holds it",
     '    const host = e.id || ((e.closest("[id]") || {}).id) || "";',
     '    const host = e.id || "";',
     "read through the second one"),
    ("read-report is never asked, so nothing is readable",
     '        boxes = sorted((rep.get("boxes") or {}).keys())',
     '        boxes = []',
     "named the kit's way"),
    # ---- an entry host is not a report ----
    ("an entry host is a figure, so every entry kit mount in the kit is on the worklist",
     '    if (skipHosts && e.querySelector("[data-h]")) return;',
     '    if (false) return;',
     "mounts CONTROLS into is not a figure"),
    ("the controls are not stamped first, so on a page with no task every mount is a figure",
     '        pg.evaluate(H.DISCOVER, H.KINDS)',
     '        pass',
     "the AUDIT stamped the controls"),
    # ---- the worklist ----
    ("the unreadable elements are counted but not named",
     '    return [i for i in r.get("written", [])',
     '    return [i for i in []',
     "on the worklist, NAMED"),
    ("furniture is subtracted from the readable side instead of the worklist",
     '            if i not in set(r.get("readable", [])) and i not in furniture]',
     '            if i not in set(r.get("readable", []))]',
     "leaves the worklist"),
    # ---- the ratchet ----
    ("furniture may be declared with no reason given",
     '        if not a.reason.strip():',
     '        if False:',
     "WITHOUT a reason is refused"),
    ("the reason is not what is stored",
     '        ledger.setdefault(page, {}).setdefault("furniture", {})[eid] = a.reason.strip()',
     '        ledger.setdefault(page, {}).setdefault("furniture", {})[eid] = ""',
     "the reason is what is stored"),
    ("a plain run lowers the ceilings, so nothing can ever be above one",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):',
     '        if (ceiling is None or len(bad) < ceiling):',
     "records what it found and no ceiling"),
    ("the ceiling ratchets UPWARD, so a page that grows a blind figure keeps its pass",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):\n            e["ceiling"] = len(bad)',
     '        if a.raise_floors and (ceiling is None or len(bad) > ceiling):\n            e["ceiling"] = len(bad)',
     "--raise-floors LOWERS it"),
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
    ("the baseline snapshot is taken with the entry-host rule ON",
     "`dpg.evaluate(TEXT_JS, False)` -> `(TEXT_JS, True)`. The rule is structural -- skip an "
     "element that HOLDS A CONTROL -- and a control is one because H.DISCOVER stamped it "
     "data-h. The baseline context runs no scripts at all, so nothing in it is stamped and the "
     "flag has nothing to act on. The argument is there to say which side of the measurement "
     "the rule belongs to, and no fixture can make it matter."),
]




def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutreadable_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_readable.py")],
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
    print("mutation testing the readable-figures audit -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_readable", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
