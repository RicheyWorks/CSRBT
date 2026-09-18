# -*- coding: utf-8 -*-
"""Mutation testing for the exemption reader (ADR-224; ADR-218 rebuilt).

verify_declared says every written exemption gets one of four verdicts and only
COVERING passes, that --forget removes one thing and says why, and that the live
ledgers obey the rule the six audits are held to. Each clause is a line somebody
could delete, and a reader that lost one would go on being green about thirty
sentences that might be about nothing.

    python3 tools/mutate_declared.py           # run every mutant
    python3 tools/mutate_declared.py --list    # the catalogue

Cheap on purpose: verify_declared opens no browser and runs in under a second.

SAFETY: tools/ is copied to a temp directory and the COPY is mutated. The real
files are never written to.
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("audit_declared.py", "exempt.py")

MUTANTS = [
    # ---- the verdicts ---------------------------------------------------------
    ("nothing is ever covering",
     '    if key in raw:\n        return "covering", "the audit still flags it", behind',
     '    if False:\n        return "covering", "the audit still flags it", behind',
     "a key the audit still flags is COVERING"),
    ("everything is covering",
     '    if key in raw:\n        return "covering", "the audit still flags it", behind',
     '    if True:\n        return "covering", "the audit still flags it", behind',
     "a key that is THERE and not flagged is IDLE"),
    ("idle and stale are the same thing, so the fix cannot be chosen",
     '    if key in seen:\n        return "idle",',
     '    if False:\n        return "idle",',
     "a key that is THERE and not flagged is IDLE"),
    ("a key that names nothing at all is called idle",
     '    return "stale", "nothing by that name was seen", behind',
     '    return "idle", "nothing by that name was seen", behind',
     "a key that is not there at all is STALE"),
    ("the raw list is checked after the universe, so every covering key reads idle",
     '    if key in raw:\n        return "covering", "the audit still flags it", behind\n    if key in seen:\n        return "idle", "the thing is there and clean, and the exemption would hide its return", behind',
     '    if key in seen:\n        return "idle", "the thing is there and clean, and the exemption would hide its return", behind\n    if key in raw:\n        return "covering", "the audit still flags it", behind',
     "a key the audit still flags is COVERING"),
    ("an entry with no universe recorded is judged against the flagged list alone",
     '    raw, seen = row.get(src["raw"]), row.get(src["seen"])\n    if not isinstance(seen, list) or not isinstance(raw, list):',
     '    raw, seen = row.get(src["raw"]), row.get(src["seen"])\n    if isinstance(raw, list) and not isinstance(seen, list):\n        seen = raw\n    if not isinstance(seen, list) or not isinstance(raw, list):',
     "the raw list alone is not enough"),
    ("a row with a declaration and no reading is judged anyway",
     '    raw, seen = row.get(src["raw"]), row.get(src["seen"])\n    if not isinstance(seen, list) or not isinstance(raw, list):',
     '    raw, seen = row.get(src["raw"]) or [], row.get(src["seen"]) or []\n    if False:',
     "a row that holds a declaration and no reading"),
    # ---- freshness --------------------------------------------------------------
    ("a reading from an earlier pass is trusted",
     '        if behind > FRESH:',
     '        if False:',
     "A READING FROM AN EARLIER PASS IS NOT EVIDENCE"),
    ("the window is exclusive, so a pass that takes the whole window reads as skipped",
     '        if behind > FRESH:',
     '        if behind >= FRESH:',
     "the window is inclusive"),
    ("BEHIND is how old the reading is rather than how far behind its own ledger",
     '        behind = int(top - row["at"])',
     '        behind = int(time.time() - row["at"])',
     "BEHIND is measured against that newest row"),
    ("BEHIND is not recorded at all",
     '                            "why": why, "reason": reason, "behind": behind,',
     '                            "why": why, "reason": reason, "behind": None,',
     "BEHIND is measured against that newest row"),
    ("the sweep's ledger is declared one-pass, which it is not",
     '     "whole": True, "verdict": lambda row: (row.get("failed") or 0) > 0, "one_pass": False,',
     '     "whole": True, "verdict": lambda row: (row.get("failed") or 0) > 0, "one_pass": True,',
     "A LEDGER NOT WRITTEN IN ONE PASS GETS NO FRESHNESS TEST"),
    ("the newest reading in a ledger is never found, so every page looks current",
     '    return max(ats) if ats else None',
     '    return None',
     "A READING FROM AN EARLIER PASS IS NOT EVIDENCE"),
    ("the newest reading is taken from `pages` whatever the ledger calls its rows",
     '        rows = (state or {}).get(src["rows"]) or {}',
     '        rows = (state or {}).get("pages") or {}',
     "A LEDGER NOT WRITTEN IN ONE PASS"),
    # ---- two ratchets, whole subjects ---------------------------------------------
    ("every source reads the `raw` key, whatever ratchet it belongs to",
     '    raw, seen = row.get(src["raw"]), row.get(src["seen"])',
     '    raw, seen = row.get("raw"), row.get("seen")',
     "EACH RATCHET READS ITS OWN RAW LIST"),
    ("a whole-subject declaration is covering whatever the audit now says",
     '        if flagged:\n            return "covering", "the audit still flags it", behind\n        return "idle",',
     '        if True:\n            return "covering", "the audit still flags it", behind\n        return "idle",',
     "a page that is no longer a trap and still hands nothing over is idle"),
    ("a page that has grown an export is merely idle, not stale",
     '        if stale_when and stale_when(row):',
     '        if False:',
     "A PAGE THAT HAS GROWN AN EXPORT IS NOT THE PAGE THE REASON WAS ABOUT"),
    ("a source with no stale test gets one anyway, so a passing pairing reads stale",
     '        stale_when = src.get("stale_when")',
     '        stale_when = src.get("stale_when") or (lambda row: not (row.get("failed") or 0))',
     "a pairing that no longer fails is idle"),
    ("the audit's own verdict field is not read, so nothing is ever covering",
     '        flagged = v(row) if callable(v) else row.get(v)',
     '        flagged = v(row) if callable(v) else False',
     "a page the audit still calls a data trap is COVERING"),
    ("the page-level declaration set is never read",
     '     "whole": True, "verdict": "trap", "one_pass": True,',
     '     "whole": True, "verdict": "trap", "one_pass": True, "declared": "no_such_key",',
     "a page the audit still calls a data trap is COVERING"),
    # ---- the report ------------------------------------------------------------------
    ("a bad exemption is reported and the exit code is not",
     '    return 1 if failing else 0\n\n\nif __name__',
     '    return 0\n\n\nif __name__',
     "A LEDGER WITH A BAD EXEMPTION IN IT FAILS"),
    ("the failing exemptions are counted and never named",
     '        print("    python3 tools/audit_declared.py --forget %s   # %s: %s"',
     '        continue\n        print("    python3 tools/audit_declared.py --forget %s   # %s: %s"',
     "one --forget line per failing declaration"),
    ("a covering declaration is listed among the problems",
     '    failing = [r for r in rows if r["verdict"] != "covering"]',
     '    failing = list(rows)',
     "one --forget line per failing declaration"),
    ("the tail counts every kind as one number",
     '    print("%d declaration(s): %d covering, %d idle, %d stale, %d unread"\n          % (len(rows), n["covering"], n["idle"], n["stale"], n["unread"]))',
     '    print("%d declaration(s): %d covering, %d idle, %d stale, %d unread"\n          % (len(rows), n["covering"], len(failing), len(failing), len(failing)))',
     "the tail counts each kind separately"),
    ("--source is ignored, so every audit's declarations are read every time",
     '        if only and src["id"] != only:\n            continue',
     '        if False:\n            continue',
     "--source restored reads no carried declarations"),
    ("--source matches on a prefix, so a page declaration answers to the button source",
     '        if only and src["id"] != only:\n            continue',
     '        if only and not src["id"].startswith(only):\n            continue',
     "--source outputs does NOT pick up"),
    ("--json drops the reason, which is the thing worth keeping",
     '                            "why": why, "reason": reason, "behind": behind,',
     '                            "why": why, "reason": None, "behind": behind,',
     "--json carries the reason"),
    ("--json does not say which --declare granted it",
     '                            "declaredBy": src["declare"], "ledger": src["ledger"]})\n        if state is None',
     '                            "declaredBy": None, "ledger": src["ledger"]})\n        if state is None',
     "--json carries the reason"),
    ("a ledger that is not there is an empty one",
     '        if state is None and not only:',
     '        if False:',
     "A LEDGER THAT IS NOT THERE IS NOT AN EMPTY ONE"),
    ("a source that does not exist is not named in the complaint",
     '        print("no source %r; the sources are %s" % (a.source, ", ".join(s["id"] for s in SOURCES)))\n        return 2',
     '        return 0',
     "a source that does not exist is refused"),
    # ---- --forget ---------------------------------------------------------------------
    ("forgetting a declaration does not print the reason it carried",
     '    return True, "forgot %s: %s -- the reason it carried was: %s" % (spec, "declared" if src.get("whole")\n                                                                    else key, reason)',
     '    return True, "forgot %s" % spec',
     "THE REMOVAL IS NOT SILENT"),
    ("a key that was never declared is reported as removed",
     '        if key not in dec:\n            return False, "%s:%s is not declared in %s; nothing to forget" % (page, key, src["id"])\n        reason = dec.pop(key)',
     '        reason = dec.pop(key, None)',
     "a key that is not declared is refused"),
    ("the removal is not written back to the ledger",
     '    save(path, state)\n    return True, "forgot',
     '    return True, "forgot',
     "that one and no other"),
    ("an emptied declaration block is left behind",
     '        if not dec:\n            del row[src["declared"]]          # the last one removed takes the empty block with it',
     '        pass',
     "the last one removed takes the empty block with it"),
    ("forgetting one declaration takes the whole page's reading with it",
     '        reason = dec.pop(key)\n',
     '        reason = dec.pop(key)\n        for k in list(row):\n            if k not in (src["declared"],):\n                del row[k]\n',
     "while the reading itself is untouched"),
    ("a key containing a colon is split into a fourth field",
     '    parts = spec.split(":", 2)',
     '    parts = spec.split(":")',
     "A KEY MAY CONTAIN A COLON"),
    ("the shape of --forget is not stated when it is got wrong",
     '        return False, ("--forget takes SOURCE:PAGE:KEY, or SOURCE:PAGE for a whole-subject source "\n                       "(a key may itself contain a colon; only the first two are split on)")',
     '        return False, "no"',
     "a spec with too few parts says the shape"),
    ("a whole-subject declaration cannot be forgotten",
     '    if src.get("whole"):\n        reason = row.get(src["declared"])',
     '    if src.get("whole"):\n        return False, "cannot"\n        reason = row.get(src["declared"])',
     "a page-level declaration is removed by name"),
    ("forgetting a whole-subject declaration takes the reading with it",
     '        del row[src["declared"]]\n    else:',
     '        row.clear()\n    else:',
     "a page-level declaration is removed by name"),
    # ---- the rule, and the live check -------------------------------------------------
    ("the exemption is applied and nothing is recorded",
     '    entry[raw] = list(flagged)\n    entry[universe] = sorted(',
     '    entry[universe] = sorted(',
     "the shared rule records raw and seen"),
    ("a reason of nothing but spaces will do",
     '    if not (reason or "").strip():\n        raise ValueError("a declaration needs a reason")',
     '    if reason is None:\n        raise ValueError("a declaration needs a reason")',
     "a declaration with no reason, or only whitespace"),
    ("the declaration does not exempt anything",
     '    return [k for k in flagged if k not in declared]',
     '    return list(flagged)',
     "the shared rule filters by the declared keys"),
    ("the live check does not compare raw minus filtered with the declared keys",
     '            if sorted(set(raw) - set(filt)) != sorted(k for k in raw if k in dec):',
     '            if False:',
     "raw minus filtered is NOT its declared keys"),
    ("the live check does not hold raw within seen",
     '            if not set(raw) <= set(seen):',
     '            if False:',
     "raw outside seen is caught"),
    ("this audit grows a --declare",
     '    ap.add_argument("--forget", metavar="SOURCE:PAGE:KEY", help="remove one declaration, printing its reason")',
     '    ap.add_argument("--forget", metavar="SOURCE:PAGE:KEY", help="remove one declaration, printing its reason")\n    ap.add_argument("--declare", help="grant one")',
     "THIS AUDIT HAS NO --declare"),
]

KNOWN_EQUIVALENT = [
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutdecl_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence",
                                                                  "traces", "push"))
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
        try:
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_declared.py")],
                               capture_output=True, text=True, timeout=300,
                               env=dict(os.environ, CSRBT_DOCS_DIR=os.path.join(ROOT, "docs")))
        except subprocess.TimeoutExpired:
            return ("BAD MUTANT", "the suite hung rather than failed")
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
    ap.add_argument("--only", type=int, metavar="N", help="run one mutant by index")
    a = ap.parse_args(argv)
    if a.list:
        for i, (n, _, _, e) in enumerate(MUTANTS):
            print("  %2d  %-62s must be killed by  %s" % (i, n, e))
        return 0
    todo = [MUTANTS[a.only]] if a.only is not None else MUTANTS
    print("mutation testing the exemption reader -- %d mutant(s), %d known equivalent\n"
          % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in todo:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-62s %s" % (verdict, name, detail[:58]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        import mutant_ledger
        mutant_ledger.record("mutate_declared", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             "" if a.only is not None else " (recorded)"))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
