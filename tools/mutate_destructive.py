# -*- coding: utf-8 -*-
"""Mutation testing for the destructive audit (ADR-209).

`audit_destructive.py` says 0 of 95 destructive controls across this kit take
two or more records on one tap and ask nothing. It said 15 on the day it was
written. A miscount is invisible in both directions: too high and the rule gets
turned off, after which the sheet-clearing ones are invisible again; too low and
a page ships a button that empties a morning next to the Add button, with every
suite in this kit green. So the measurement is broken on purpose and
`verify_destructive` has to notice.

    python3 tools/mutate_destructive.py           # run every mutant
    python3 tools/mutate_destructive.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_destructive.py",)

KNOWN_EQUIVALENT = []

MUTANTS = [
    # ---- what counts as a destructive control ----
    ("every control the door presses is a remover, so an export is a delete",
     '        why = PP.destroys((c.get("label") or "").strip(), c.get("title") or "")\n'
     '        if why:',
     '        why = "everything"\n'
     '        if why:',
     "MULTIPLICATION SIGN in the middle of a name is not a remover"),
    ("the gateway's rule is restated here, with the multiplication sign in it",
     '        why = PP.destroys((c.get("label") or "").strip(), c.get("title") or "")',
     '        import re as _re\n'
     '        why = "local" if _re.search(r"clear|delete|erase|reset|\\u00d7",\n'
     '                                    (c.get("label") or ""), _re.I) else None',
     "MULTIPLICATION SIGN in the middle of a name is not a remover"),
    ("a text box is a control somebody taps",
     '        if c.get("kind") not in PRESSED:\n            continue',
     '        if False:\n            continue',
     "neither is a TEXT BOX whose label says clear"),
    ("what a control is gets written down here instead of read from the door's pool",
     'PRESSED = frozenset(PP.POOL_KINDS["activate"])',
     'PRESSED = frozenset(["action_btn", "chip"])',
     "read from that pool rather than restated here"),
    ("the reason the gateway gave is dropped, so a row cannot be read",
     '"id": c.get("id") or "", "kind": c.get("kind") or "", "why": why}',
     '"id": c.get("id") or "", "kind": c.get("kind") or "", "why": ""}',
     "each carries the reason that rule gave"),
    # ---- where the loss is read from ----
    ("the loss is counted off the screen even when the page keeps its own state",
     '        kb = kept(pg)',
     '        kb = None',
     "THREE RECORDS, NOT SIX"),
    ("the autosave is never reachable, so every page falls back to the screen",
     '  if (typeof KEEP === "undefined" || !KEEP || typeof KEEP.live !== "function") return null;',
     '  if (true) return null;',
     "a page with an autosave is read through it"),
    ("a record's own fields count as records, so an undo reads as a bulk delete",
     '    if (typeof v === "object") {\n'
     '      for (var kk in v) if (Object.prototype.hasOwnProperty.call(v, kk)) arrays(v[kk], depth + 1);\n'
     '    }',
     '    if (typeof v === "object") {\n'
     '      for (var kk in v) if (Object.prototype.hasOwnProperty.call(v, kk)) arrays(v[kk], depth + 1);\n'
     '    }\n'
     '    if (typeof v === "string" && v.trim() !== "") n += 1;',
     "THREE RECORDS, NOT SIX"),
    ("a typed field is not a record, so clearing two text boxes reads as nothing",
     '  var f = b.fields;',
     '  var f = null;',
     "A TYPED FIELD IS A RECORD"),
    ("which reading was taken is not recorded, so a fallback cannot be told from a real one",
     '               "read": "screen" if kb is None else "autosave",',
     '               "read": "autosave",',
     "A PAGE WITH NO AUTOSAVE IS READ OFF THE SCREEN, and says which reading it is"),
    # ---- asking ----
    ("the page is never heard to ask",
     '    return "confirm" in calls',
     '    return False',
     "control that ASKS before it takes anything is not on the worklist"),
    ("the row reports an `after` it did not measure, so the ledger's own arithmetic is a fiction",
     '        out = {"asked": asked(pg), "before": before, "after": after,',
     '        out = {"asked": asked(pg), "before": before, "after": before,',
     "AND THE ROW SAYS WHERE THE NUMBER CAME FROM"),
    ("asking counts for nothing, so a page that asks is still on the worklist",
     '        return "asks"\n    loss = m.get("loss", 0)',
     '        pass\n    loss = m.get("loss", 0)',
     "control that ASKS before it takes anything is not on the worklist"),
    # ---- a question whose answer changes nothing (ADR-210) ----
    ("the answer is never given, so only the YES path is ever watched",
     '        if out["asked"]:\n'
     '            out["said"] = said_no(ctx, name, key, tasks_dir, kb is None)',
     '        if False:\n'
     '            out["said"] = said_no(ctx, name, key, tasks_dir, kb is None)',
     "ANSWERING NO TO THE DEFIANT ONE CHANGES NOTHING"),
    ("saying no is the same as saying yes, so the refusal path is not a path",
     '                                return false; }; }"""',
     '                                return true; }; }"""',
     "answering no to the honest one stops it dead"),
    ("a page that asks and destroys anyway still counts as asking",
     '        said = m.get("said")\n'
     '        if isinstance(said, dict) and said.get("lost", 0) > 0:\n'
     '            return "ignores"',
     '        said = m.get("said")\n'
     '        if False:\n'
     '            return "ignores"',
     "IGNORES, not ASKS"),
    ("a page that asks and destroys anyway is kept off the worklist",
     'BAD = ("bulk", "ignores")',
     'BAD = ("bulk",)',
     "IT IS ON THE WORKLIST, beside the controls that never asked"),
    ("the second press is made on every control, asked or not",
     '        if out["asked"]:\n'
     '            out["said"] = said_no',
     '        if True:\n'
     '            out["said"] = said_no',
     "a control that never asked is not asked a second time"),
    # ---- the audit's own history ----
    ("storage is left alone between pages, so the audit measures its own history",
     '        ctx.add_init_script("try{localStorage.clear();sessionStorage.clear();}catch(e){}")',
     '        pass',
     "THREE RECORDS, NOT SIX"),
    # ---- the bar ----
    ("one record is a bulk delete, and the rule starts crying wolf",
     'BULK = 2',
     'BULK = 1',
     "the bar is two records"),
    ("nothing is ever a bulk delete",
     'BULK = 2',
     'BULK = 99',
     "ONE BARE REMOVER ON THIS FIXTURE"),
    # ---- the page is measured with its data in it ----
    ("the page is measured at rest, so every clear clears nothing",
     '    return (not has_task) or getattr(pg, "_audit_entered", None) is not None',
     '    return True',
     "ONE BARE REMOVER ON THIS FIXTURE"),
    ("a declaration does not exempt the control",
     '        dec = declared_of(state, name)',
     '        dec = {}',
     "the page passes at a ceiling of zero"),
    ("declaring a control exempt needs no reason at all",
     '        if not a.reason.strip():\n            print("declaring a bulk remover exempt needs --reason',
     '        if False:\n            print("declaring a bulk remover exempt needs --reason',
     "exempt WITHOUT a reason is refused"),
    ("a declared control keeps no reason, so the ledger says what but never why",
     '        ledger.setdefault(page, {}).setdefault("declared", {})[key] = a.reason.strip()',
     '        ledger.setdefault(page, {}).setdefault("declared", {})[key] = "yes"',
     "THE REASON IS WHAT IS STORED, word for word"),
    ("the ratchet runs upward, so a page that grew one records it as the new normal",
     '        if a.raise_floors and (ceiling is None or len(bad) < ceiling):',
     '        if a.raise_floors and (ceiling is None or len(bad) > ceiling):',
     "--raise-floors LOWERS the ceiling"),
    ("a reading above the ceiling is not a failure",
     '        if ceiling is not None and len(bad) > ceiling:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     '        if False:\n'
     '            above.append((name, len(bad), ceiling, bad))',
     "TAKING A SHEET WITHOUT ASKING FAILS"),
    ("the failure is reported and the exit code is not",
     '    return 1 if above else 0',
     '    return 0',
     "TAKING A SHEET WITHOUT ASKING FAILS"),
    ("the failure names no page and no control",
     '            print("    %-30s %d, ceiling %d: %s" % (name, now, ceiling, ", ".join(keys[:a.names])))',
     '            print("    a page is over its ceiling")',
     "it NAMES the page and the control"),
    ("the ledger records no worklist, only a count",
     '        e.update({"bare": bad, "controls": len(r["controls"]), "counts": c,',
     '        e.update({"bare": [], "controls": len(r["controls"]), "counts": c,',
     "a first reading records what it found"),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutdestructive_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_destructive.py")],
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
    print("mutation testing the destructive audit -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_destructive", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
