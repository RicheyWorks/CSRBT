# -*- coding: utf-8 -*-
"""Mutation testing for the audits' state walker (ADR-130, ADR-131).

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
     '    pg._audit_entered = None\n    pg.evaluate(OPEN_DETAILS_JS)\n    pg.wait_for_timeout(100)',
     '    pg._audit_entered = None\n    pg.wait_for_timeout(100)',
     "<details>"),
    ("the page-specific reveals are not pressed",
     "audit_states.py",
     '            yield "pane:%s" % t["id"], probe()\n    for sel in states_of(name):',
     '            yield "pane:%s" % t["id"], probe()\n    for sel in []:',
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
    ("a stamp is a counter, so a rebuilt region loses its measurements",
     "audit_states.py",
     '    const n = seen[key] = (seen[key] || 0) + 1;\n    e.setAttribute("data-audit", key + "|" + n);',
     '    if (window.__n === undefined) window.__n = 0;\n    const n = seen[key] = (seen[key] || 0) + 1;\n    if (!e.hasAttribute("data-audit")) e.setAttribute("data-audit", "a" + (window.__n++));',
     "rebuilt with innerHTML"),
    ("a state class re-keys a control",
     "audit_states.py",
     '                 .filter(c => c && !STATE.test(c)).sort().join(".");',
     '                 .filter(c => c).sort().join(".");',
     "state class"),
    ("the occurrence index is dropped, so identical controls share a stamp",
     "audit_states.py",
     '    e.setAttribute("data-audit", key + "|" + n);',
     '    e.setAttribute("data-audit", key);',
     "one stable stamp"),
    ("a hidden input is a control",
     "audit_states.py",
     'CONTROLS = "button, input:not([type=hidden]):not([type=file]), select, textarea, [role=button], .tab"',
     'CONTROLS = "button, input, select, textarea, [role=button], .tab"',
     "controls exist"),
    ("coverage never names anything",
     "audit_states.py",
     '    never = [i for i in all_ids if i and i not in exposed]',
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
    # ---- the entered state (ADR-131) ----
    ("the page is never entered",
     "audit_states.py",
     '    if entered:\n        ent = enter(pg, name)',
     '    if False:\n        ent = enter(pg, name)',
     "in order"),
    ("the entered state's tabs are not walked",
     "audit_states.py",
     '            for t in pg.evaluate(TABS_JS):\n                if _click(pg, t["sel"], t["i"]):\n                    pg.evaluate(OPEN_DETAILS_JS)\n                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))\n                    yield "entered/pane:%s" % t["id"], probe()',
     '            for t in []:\n                if _click(pg, t["sel"], t["i"]):\n                    pg.evaluate(OPEN_DETAILS_JS)\n                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))\n                    yield "entered/pane:%s" % t["id"], probe()',
     "walked again"),
    ("a canary counts as the page's task",
     "audit_states.py",
     '        if t.get("must", "PASS") != "PASS":\n            continue',
     '        if False:\n            continue',
     "only task is a canary"),
    ("a reference task counts as an entry",
     "audit_states.py",
     '        if any(s.get("action") not in ENTRY_SKIP for s in t.get("steps") or []):\n            hits.append(t)',
     '        hits.append(t)',
     "only task is all reads"),
    ("the science task is not preferred",
     "audit_states.py",
     '    return next((t for t in hits if str(t.get("id", "")).endswith("-science")), hits[0])',
     '    return hits[0]',
     "the other sorts first"),
    ("a task is matched whatever page it names",
     "audit_states.py",
     '        if t.get("target") != "page" or t.get("page") != name:',
     '        if t.get("target") != "page":',
     "the page it names"),
    ("the reads are replayed too",
     "audit_states.py",
     'ENTRY_SKIP = ("read-report", "read-page", "observe", "open", "reload")',
     'ENTRY_SKIP = ()',
     "skips the two reads"),
    ("the entry\'s steps are not driven",
     "audit_states.py",
     '            ok, msg, out = plug.execute(action, args)',
     '            ok, msg, out = True, "", {}',
     "only in a built row"),
    ("the page's own reveals are not pressed again after the entry",
     "audit_states.py",
     '            for sel in states_of(name):\n                if isinstance(sel, tuple):\n                    _, css, value = sel\n                    _reveal(pg, css)',
     '            for sel in []:\n                if isinstance(sel, tuple):\n                    _, css, value = sel\n                    _reveal(pg, css)',
     "in order"),
    ("an entry that drove nothing is not a fault",
     "audit_states.py",
     '    if ent.get("steps") and not ent.get("driven"):\n        return "the entry drove nothing: %d step(s), all refused" % ent["steps"]',
     '    if False:\n        return "the entry drove nothing: %d step(s), all refused" % ent["steps"]',
     "drove nothing"),
    ("an entry that could not run is not a fault",
     "audit_states.py",
     '    if ent.get("error"):\n        return "the entry could not run: %s" % ent["error"]',
     '    if False:\n        return "the entry could not run: %s" % ent["error"]',
     "could not run at all"),
    ("an expected refusal is called a fault",
     "audit_states.py",
     '    if ent.get("steps") and not ent.get("driven"):',
     '    if ent.get("refused"):',
     "written to be refused"),
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
     '                for state, r in S.each_state(pg, nm, probe):\n                    nstates += 1',
     '                for state, r in [("rest", probe())]:\n                    nstates += 1',
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
    # ---- ADR-136: the page may still be building ----
    ("the walk ends without settling, so a control mounted after the last stamp carries none",
     "audit_states.py",
     '    if None in pg.evaluate(UNSTAMPED_JS, CONTROLS):',
     '    if False:',
     "settles into one more state, and only then"),
    ("the final settle happens whether or not anything appeared",
     "audit_states.py",
     '    if None in pg.evaluate(UNSTAMPED_JS, CONTROLS):',
     '    if True:',
     "and only then"),
    ("coverage counts what the last probe saw and never looks again",
     "audit_states.py",
     '        _settle(pg)\n        seen = set(pg.evaluate(MARK_JS, CONTROLS))',
     '        seen = set()',
     "revealed BETWEEN two looks"),
    ("coverage takes one more look and forgets what the walk measured",
     "audit_states.py",
     '    if hasattr(pg, "_audit_exposed"):\n        pg._audit_exposed |= late\n    exposed = getattr(pg, "_audit_exposed", late)',
     '    if hasattr(pg, "_audit_exposed"):\n        pg._audit_exposed = late\n    exposed = getattr(pg, "_audit_exposed", late)',
     "B3's box in the third pane, seen once, is remembered"),
    ("the late control is stamped but never measured",
     "audit_states.py",
     '        exposed |= set(pg.evaluate(MARK_JS, CONTROLS))\n        yield "settled", probe()',
     '        pg.evaluate(MARK_JS, CONTROLS)',
     "settles into one more state, and only then"),
]


MUTANTS += [
    # ---- ADR-143: the look repeats, and says what it caught ----
    ("coverage looks once, the way it did after ADR-140",
     "audit_states.py",
     "    for i in range(max(1, int(looks))):",
     "    for i in range(1):",
     "the run SAYS a later look found"),
    ("the looking never stops early, so every page pays for three settles",
     "audit_states.py",
     "        if i and not new:\n            break",
     "        if False:\n            break",
     "the looking stops there"),
    ("lateLooks reports what each look saw, not what it was FIRST to see",
     "audit_states.py",
     "        gained.append(len(new))",
     "        gained.append(len(seen))",
     "the second look finds nothing"),
]


MUTANTS += [
    ("coverage enumerates without stamping first, so a control that just arrived is a null",
     "audit_states.py",
     "    late |= set(pg.evaluate(MARK_JS, CONTROLS))\n    if hasattr(pg, \"_audit_exposed\"):\n        pg._audit_exposed |= late\n        exposed = pg._audit_exposed\n    all_ids = pg.evaluate(UNSTAMPED_JS, CONTROLS)",
     "    all_ids = pg.evaluate(UNSTAMPED_JS, CONTROLS)",
     "arrived DURING the enumeration"),
]


MUTANTS += [
    # ---- ADR-145: an unnamed control is counted inside its host ----
    ("an unnamed control is counted across the document, so page growth renames it",
     "audit_states.py",
     '              + (e.type ? "[" + e.type + "]" : "") + (e.id ? "" : (host ? "@" + host : ""));',
     '              + (e.type ? "[" + e.type + "]" : "");',
     "keeps its stamp when the page GROWS"),
    ("a control the entry left FOCUSED is measured without blurring it first",
     "audit_focus.py",
     '      if (document.activeElement === e) e.blur();',
     '      if (false) e.blur();',
     "ENTRY LEFT FOCUSED"),
    ("the probe leaves focus wherever it put it",
     "audit_focus.py",
     '    try { if (wasActive && wasActive.focus) wasActive.focus({preventScroll:true}); } catch (_) {}',
     '    try { if (false) wasActive.focus({preventScroll:true}); } catch (_) {}',
     "puts focus back where the page had it"),
    ("a NAMED control is scoped to its host too, so its id is not enough",
     "audit_states.py",
     '(e.id ? "" : (host ? "@" + host : ""))',
     '(host ? "@" + host : "")',
     "keyed by the id alone"),
]

KNOWN_EQUIVALENT = [
    ("a control with no stamp is a control no state exposed",
     "dropping the `unstamped` bucket -- so a null id counts as a control no state exposed again "
     "-- cannot be observed once the fix is in: coverage now stamps immediately before it "
     "enumerates, and to produce a null a control would have to mount in the microseconds "
     "between those two evaluate calls. The trap that produces one for the other half of this "
     "clause fires during the last look's stamping pass, which the extra stamp then catches. "
     "Kept because the bucket is what makes the report readable if it ever happens, and recorded "
     "here rather than asserted by a check that could not fail (measured 2026-09-05)."),
    ("the walk measures as soon as the click returns, without waiting for a frame",
     "the frame wait (_frames, ADR-140) is defence against CPU CONTENTION, and no fixture can "
     "reproduce contention: _click already waits 150 ms, under which a page's own "
     "requestAnimationFrame always lands, so a deterministic suite cannot tell the two apart. "
     "Kept for the same reason ADR-134 widened _settle from one second to two -- an instrument "
     "whose answer depends on what else is running is not an instrument -- and recorded here "
     "rather than asserted by a check that could not fail (measured 2026-09-04: both mutants "
     "survive every check in the suite)"),
    ("waiting for a frame waits for none",
     "same clause, same reason: the two frames are unobservable on an idle machine"),
]


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
