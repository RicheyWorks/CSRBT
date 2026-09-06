# -*- coding: utf-8 -*-
"""Mutation testing for the entry-reach measurement (ADR-144).

`entry_reach.py` says the kit's tasks fill 183 of 516 fields, and that number
becomes a worklist and a ratchet. A miscount here would either invent work that
does not exist or hide work that does -- and both look exactly like a green
number. So the counting is broken on purpose and `verify_entry_reach` has to
notice.

The subject is two files, because the measurement spans two: `entry_reach.py`
counts, and `audit_states.py` records which control each entry step touched.

    python3 tools/mutate_entry.py           # run every mutant
    python3 tools/mutate_entry.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("entry_reach.py", "audit_states.py")

MUTANTS = [
    # ---- what counts as a field ----
    ("a button that does something WITH data is a field too",
     '''NOT_ENTERABLE = ("action_btn", "nav_link", "tab", "link", "readonly_out")''',
     '''NOT_ENTERABLE = ("nav_link", "tab", "link", "readonly_out")
ENTERABLE = ENTERABLE + ("action_btn",)''',
     "controls carry a value here"),
    ("a readonly display is a field nobody filled",
     '''NOT_ENTERABLE = ("action_btn", "nav_link", "tab", "link", "readonly_out")''',
     '''NOT_ENTERABLE = ("action_btn", "nav_link", "tab", "link")
ENTERABLE = ENTERABLE + ("readonly_out",)''',
     "neither is a READONLY box"),
    ("a stepper is three fields, so a page of steppers looks two thirds unfilled",
     '''        if meta.get("group"):
            return "widget:" + meta["group"]''',
     '''        if False:
            return "widget:" + meta["group"]''',
     "they are TEN fields"),
    ("a chip group is one field per chip",
     '''        if meta.get("kind") in CHOICE_KINDS and meta.get("host"):
            return "%s@%s" % (meta["kind"], meta["host"])''',
     '''        if False:
            return "%s@%s" % (meta["kind"], meta["host"])''',
     "they are TEN fields"),
    ("every choice on the page is the same field, whatever it belongs to",
     '''            return "%s@%s" % (meta["kind"], meta["host"])''',
     '''            return meta["kind"]''',
     "they are TEN fields"),
    ("a control the page removed is folded back in under a key it shares with every other",
     '''        if meta.get("kind") in CHOICE_KINDS and meta.get("host"):''',
     '''        if meta.get("kind") in CHOICE_KINDS:
            return "%s@%s" % (meta["kind"], meta.get("host") or "?")
        if False:''',
     "they are TEN fields"),
    # ---- what counts as entered ----
    ("a field counts as entered when EVERY member of it was touched",
     '''    done = set(f for f, members in fields.items() if any(m in touched for m in members))''',
     '''    done = set(f for f, members in fields.items() if all(m in touched for m in members))''',
     "six were entered"),
    ("a control the page removed after answering it was never entered",
     '''    for stamp, kind in touched.items():
        if kind in ENTERABLE and stamp not in universe:
            universe[stamp] = {"kind": kind, "group": None, "host": None}''',
     '''    for stamp, kind in []:
        if kind in ENTERABLE and stamp not in universe:
            universe[stamp] = {"kind": kind, "group": None, "host": None}''',
     "controls carry a value here"),
    ("which control a step touched is asked AFTER the step, not before",
     '''            before = None
            if isinstance(args.get("selector"), str):
                try:
                    pg.evaluate(MARK_JS, CONTROLS)
                    before = pg.evaluate(TOUCHED_JS, args["selector"])
                except Exception:
                    before = None
            ok, msg, out = plug.execute(action, args)''',
     '''            before = None
            ok, msg, out = plug.execute(action, args)
            if isinstance(args.get("selector"), str):
                try:
                    pg.evaluate(MARK_JS, CONTROLS)
                    before = pg.evaluate(TOUCHED_JS, args["selector"])
                except Exception:
                    before = None''',
     "controls carry a value here"),
    ("the entry records nothing it touched",
     '''            touched[before["stamp"]] = before.get("kind")''',
     '''            pass''',
     "six were entered"),
    # ---- the naming, which is the worklist ----
    ("the un-entered fields are counted but not named",
     '''        pick_ = [naming(fields[f]) for f in missed[:400]]''',
     '''        pick_ = []''',
     "are NAMED"),
    ("a field is named by whichever member sorts first",
     '''        ranked = sorted(members, key=lambda m: (universe[m].get("kind") == "step_btn", m))''',
     '''        ranked = sorted(members)''',
     "named by the member that says most"),
    # ---- the ratchet ----
    ("a floor may be lowered with no reason given",
     '''        if not a.reason.strip():
            print("lowering a floor needs --reason: it goes into the ledger")
            return 2''',
     '''        if False:
            print("lowering a floor needs --reason: it goes into the ledger")
            return 2''',
     "with no reason is refused"),
    ("lowering a floor forgets what it was lowered from",
     '''        e.setdefault("lowered", []).append({"at": int(time.time()), "from": e.get("floor", 0),
                                            "reason": a.reason.strip()})''',
     '''        e.setdefault("lowered", []).append({"at": int(time.time()), "from": 0,
                                            "reason": a.reason.strip()})''',
     "what it was lowered FROM"),
    ("a plain run raises the floors, so nothing can ever be below one",
     '''        if a.raise_floors and r["entered"] > floor:''',
     '''        if r["entered"] > floor:''',
     "records the reading and sets no floor"),
    ("a reading below the floor is not one",
     '''        if r["entered"] < floor:
            below.append((name, r["entered"], floor))''',
     '''        if False:
            below.append((name, r["entered"], floor))''',
     "makes --check refuse"),
    ("the run refuses whatever the reading",
     '''    return 1 if below else 0''',
     '''    return 1''',
     "it passes when no page is below its floor"),
]

KNOWN_EQUIVALENT = [
    ("a step that was REFUSED still counts as having entered its field",
     "`if ok and before` -> `if before`. The page plugin refuses by RAISING -- every wrong-kind "
     "selector, every missing control, every bad value comes back as a HarnessError -- so the "
     "line after execute() is only ever reached with ok true, and no fixture can make a refusal "
     "arrive any other way. The guard is defence against a future plugin that answers no without "
     "raising, which is a shape this kit does not currently have; recorded rather than asserted "
     "by a check that could not fail (measured 2026-09-05)."),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutentry_")
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
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_entry_reach.py")],
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
    print("mutation testing the entry-reach measurement -- %d mutant(s), %d known equivalent\n"
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
    mutant_ledger.record("mutate_entry", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
