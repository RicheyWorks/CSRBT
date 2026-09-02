# -*- coding: utf-8 -*-
"""Mutation testing for the audits' state walker (ADR-130).

verify_audit_states.py says the audits measure every state of a page and
count what they could not reach. Same rule as every suite: break
tools/audit_states.py (and the three audits' use of it) on purpose and
require the suite to notice. Each mutant is a few browser sessions on a
fixture page and two real pages -- under a minute.

    python3 tools/mutate_audit_states.py           # run every mutant
    python3 tools/mutate_audit_states.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

# (name, file, find, replace, a word the killing FAIL line must carry)
MUTANTS = [
    ("the tabs are not pressed",
     "audit_states.py",
     '    for t in pg.evaluate(TABS_JS):\n        if _click(pg, t["sel"], t["i"]):\n            pg.evaluate(OPEN_DETAILS_JS)',
     '    for t in []:\n        if _click(pg, t["sel"], t["i"]):\n            pg.evaluate(OPEN_DETAILS_JS)',
     "in order"),
    ("an aria-controls button is not a tab",
     "audit_states.py",
     '  document.querySelectorAll("[aria-controls]").forEach((t, i) => {\n    if (t.matches(".tab[data-pane]")) return;',
     '  document.querySelectorAll("[aria-controls]").forEach((t, i) => {\n    if (true) return;',
     "in order"),
    ("<details> stay closed",
     "audit_states.py",
     '    pg.evaluate(OPEN_DETAILS_JS)\n    pg.wait_for_timeout(100)\n    exposed = set(pg.evaluate(MARK_JS, CONTROLS))',
     '    pg.wait_for_timeout(100)\n    exposed = set(pg.evaluate(MARK_JS, CONTROLS))',
     "<details>"),
    ("the page-specific reveals are not pressed",
     "audit_states.py",
     '    for sel in states_of(name):',
     '    for sel in []:',
     "in order"),
    ("a <select> reveal is skipped",
     "audit_states.py",
     '        if isinstance(sel, tuple):\n            _, css, value = sel',
     '        if isinstance(sel, tuple):\n            continue\n            _, css, value = sel',
     "in order"),
    ("the owning tab is not pressed before a <select> reveal",
     "audit_states.py",
     '            _, css, value = sel\n            _reveal(pg, css)',
     '            _, css, value = sel',
     "dependent field"),
    ("a revealed surface's tabs are not pressed",
     "audit_states.py",
     '            for t in pg.evaluate(TABS_JS):\n                if _click(pg, t["sel"], t["i"]):\n                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))',
     '            for t in []:\n                if _click(pg, t["sel"], t["i"]):\n                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))',
     "in order"),
    ("exposure is not accumulated across states",
     "audit_states.py",
     '            exposed |= set(pg.evaluate(MARK_JS, CONTROLS))\n            yield "pane:%s" % t["id"], probe()',
     '            pg.evaluate(MARK_JS, CONTROLS)\n            yield "pane:%s" % t["id"], probe()',
     "had a box"),
    ("the stamps are reassigned every state",
     "audit_states.py",
     '    if (!e.hasAttribute("data-audit")) e.setAttribute("data-audit", "a" + (n));',
     '    e.setAttribute("data-audit", "a" + (n) + "_" + Date.now());',
     "stamp"),
    ("a hidden input is a control",
     "audit_states.py",
     'CONTROLS = "button, input:not([type=hidden]):not([type=file]), select, textarea, [role=button], .tab"',
     'CONTROLS = "button, input, select, textarea, [role=button], .tab"',
     "controls exist"),
    ("coverage never names anything",
     "audit_states.py",
     '    never = [i for i in all_ids if i not in exposed]',
     '    never = []',
     "no state exposed"),
    ("the click is a pointer click",
     "audit_states.py",
     '        pg.evaluate("(el) => el.click()", els[i])',
     '        els[i].click()',
     "pointer"),
    ("the state-button table is empty",
     "audit_states.py",
     'STATE_BUTTONS = {\n    "field-season.html": ["#startBtn", "#aMark", "#aRecap", "#fileBtn", "#gradeBtn"],',
     'STATE_BUTTONS = {\n    "field-season.html": [],',
     "reaches"),
    ("the guide's hot phase is not a state",
     "audit_states.py",
     '    "experiment-guide.html": [("select", "#p-kind", "hot"), ("select", "#p-kind", "churn"),',
     '    "experiment-guide.html": [("select", "#p-kind", "churn"),',
     "reaches"),
    ("targets measures the page as loaded",
     "audit_targets.py",
     '        for state, r in S.each_state(pg, name, lambda: pg.evaluate(PROBE)):\n            nstates+=1',
     '        for state, r in [("rest", pg.evaluate(PROBE))]:\n            nstates+=1',
     "targets"),
    ("targets does not count what it never measured",
     "audit_targets.py",
     '        n=sum(r.values())+len(cov["never"])',
     '        n=sum(r.values())',
     "targets"),
    ("focus measures the page as loaded",
     "audit_focus.py",
     '                for state, r in S.each_state(pg, nm, lambda: pg.evaluate(PROBE)):\n                    nstates += 1',
     '                for state, r in [("rest", pg.evaluate(PROBE))]:\n                    nstates += 1',
     "focus"),
    ("focus does not count what it never measured",
     "audit_focus.py",
     '                res["never"] = [(nm_, 1) for nm_ in cov["never"]]',
     '                res["never"] = []',
     "focus"),
    ("contrast measures the page as loaded",
     "audit_contrast.py",
     '                for state, r in S.each_state(pg, nm, lambda: pg.evaluate(PROBE)):\n                    res["states"] += 1',
     '                for state, r in [("rest", pg.evaluate(PROBE))]:\n                    res["states"] += 1',
     "contrast"),
    ("contrast does not count what it never measured",
     "audit_contrast.py",
     '            never = len(res["coverage"]["never"])',
     '            never = 0',
     "contrast"),
]

KNOWN_EQUIVALENT = []


def run_one(fname, find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutstates_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # the suite's real-page checks read docs/ beside tools/
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        path = os.path.join(dst, fname)
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        suite = os.path.join(dst, "verify", "verify_audit_states.py")
        p = subprocess.run([sys.executable, suite], capture_output=True, text=True, timeout=900)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if "NOT VERIFIED" in out:
            return ("BAD MUTANT", "the suite could not run under mutation")
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
        for n, f, _, _, e in MUTANTS:
            print("  %-58s %-18s must be killed by  %s" % (n, f, e))
        return 0
    print("mutation testing the audits' state walker against verify_audit_states -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, fname, find, repl, expect in MUTANTS:
        verdict, detail = run_one(fname, find, repl, expect)
        print("  %-9s %-58s %s" % (verdict, name, detail[:60]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        if verdict == "SURVIVED":
            survived += 1
        elif verdict != "killed":
            bad += 1
    import mutant_ledger
    mutant_ledger.record("mutate_audit_states", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
