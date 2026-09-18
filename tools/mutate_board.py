# -*- coding: utf-8 -*-
"""Mutation testing for the Harness Board's renderer (ADR-227).

tools/harness_board.py is the one page whose job is to say what the harness
can vouch for, and until this runner it was the one subject in the kit with no
mutant runner: verify_board held the committed page byte-for-byte to a fresh
render and the arithmetic to the committed ledgers, and the committed ledgers
are GREEN -- every suite n == of, no mutant survived, no engine failed. A
renderer that summed `of` where it should sum `n`, counted every mutant as
killed, or rendered every engine's pill good renders those ledgers to the same
page, so no check could fail on it.

Two things make the runner honest:

  * EVERY MUTANT RE-RENDERS ITS OWN BOARD before the suite runs. Otherwise the
    byte-for-byte check kills every mutant that changes a byte of output and
    proves only that the output changed, not that any rule held (ADR-140's
    lesson: a mutant killed by the wrong check is a mutant nobody aimed).
  * THE SUITE HOLDS A FIXTURE LEDGER SET with every gate broken at known
    numbers (verify_board section 9), so a miscount has somewhere to show.

    python3 tools/mutate_board.py           # run every mutant
    python3 tools/mutate_board.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = "harness_board.py"
SUITE = "verify_board.py"

MUTANTS = [
    # ---- the summary's arithmetic ----
    ("suite checks are the sum of `of`, so a suite with a hole still reads whole",
     '    n = sum(v.get("n", 0) for v in c.values())',
     '    n = sum(v.get("of", 0) for v in c.values())',
     "summary[checks]"),
    ("holes are never counted",
     '    holes = sum(v.get("unverified", 0) for v in c.values())',
     '    holes = 0',
     "summary[holes]"),
    ("every suite is green",
     '    green = sum(1 for v in c.values() if v.get("green"))',
     '    green = len(c)',
     "summary[green]"),
    ("a walk whose command FAILED still holds",
     '                 or e.get("invariants_broken") or (e.get("totals") or {}).get("failed")]',
     '                 or e.get("invariants_broken")]',
     "a walk is bad when a command FAILED"),
    ("a walk whose identity did not hold still holds",
     '    bad_walks = [k for k, e in W.items() if e.get("identity") != "holds" or e.get("undriven") or e.get("unschemable")',
     '    bad_walks = [k for k, e in W.items() if e.get("undriven") or e.get("unschemable")',
     "a walk is bad when a command FAILED or its identity did not hold"),
    ("a blind trace is counted as a task",
     '    runs = {k: e for k, e in T.items() if not k.endswith(("@trace", "@blind"))}',
     '    runs = {k: e for k, e in T.items() if not k.endswith("@trace")}',
     "summary[tasks]"),
    ("every task is held",
     '        "tasks": len(runs), "tasks_held": sum(1 for e in runs.values() if e.get("held")),',
     '        "tasks": len(runs), "tasks_held": len(runs),',
     "summary[tasks_held]"),
    ("every trace is held",
     '        "traces": len(traces), "traces_held": sum(1 for e in traces.values() if e.get("held")),',
     '        "traces": len(traces), "traces_held": len(traces),',
     "summary[traces_held]"),
    ("the values handed over are never summed",
     '        "given": sum(e.get("gives") or 0 for e in runs.values()),',
     '        "given": 0,',
     "summary[given]"),
    ("a task that declares DESTRUCTIVE counts as supervised",
     '                          if e.get("rungs") and "DESTRUCTIVE" not in e["rungs"]),',
     '                          if e.get("rungs")),',
     "summary[supervised]"),
    ("fields entered reads the field count",
     '        "fields_entered": sum(e.get("entered", 0) for e in (L["entry"].get("pages") or {}).values()),',
     '        "fields_entered": sum(e.get("fields", 0) for e in (L["entry"].get("pages") or {}).values()),',
     "summary[fields_entered]"),
    ("a page with nothing to enter is counted as an entry page",
     '        "entry_pages": sum(1 for e in (L["entry"].get("pages") or {}).values() if e.get("fields")),',
     '        "entry_pages": len(L["entry"].get("pages") or {}),',
     "summary[entry_pages]"),
    ("unreadable figures are counted per page rather than per figure",
     '        "unreadable": sum(len(e.get("unreadable") or [])',
     '        "unreadable": sum(1 if e.get("unreadable") else 0',
     "summary[unreadable]"),
    ("slices are counted per path rather than per slice",
     '        "slices": len(set(e.get("by") for e in (L["delivery"].get("paths") or {}).values()',
     '        "slices": len(list(e.get("by") for e in (L["delivery"].get("paths") or {}).values()',
     "summary[slices]"),
    ("every load reading is clean",
     '        "load_clean": sum(1 for e in (L["contention"].get("suites") or {}).values()\n'
     '                          if not e.get("failed")),',
     '        "load_clean": len(L["contention"].get("suites") or {}),',
     "summary[load_clean]"),
    ("no mutant ever survived",
     '        "survived": sum(e.get("survived", 0) for e in M.values()),',
     '        "survived": 0,',
     "summary[survived]"),
    ("no mutant was ever inconclusive",
     '        "inconclusive": sum(e.get("inconclusive", 0) for e in M.values()),',
     '        "inconclusive": 0,',
     "summary[inconclusive]"),
    ("an engine's errors are not failures",
     '        "engine_failures": sum(e.get("failures", 0) + e.get("errors", 0) for e in E.values()),',
     '        "engine_failures": sum(e.get("failures", 0) for e in E.values()),',
     "summary[engine_failures]"),
    ("the newest reading ignores the mutant runners",
     '                      [e.get("at", 0) for e in T.values()] + [e.get("at", 0) for e in M.values()] +',
     '                      [e.get("at", 0) for e in T.values()] +',
     "summary[newest]"),
    # ---- the verdict ----
    ("the banner is green whatever the gates say",
     '    all_green = all(ok for _n, ok, _t in GATES)',
     '    all_green = True',
     "THE VERDICT IS DERIVED FROM THE NAMED LIST"),
    ("a gate that is not met is not named as such",
     '''                "; ".join("%s%s" % (n, "" if ok else " \\u2014 NOT MET") for n, ok, _t in GATES)))''',
     '''                "; ".join("%s" % n for n, ok, _t in GATES)))''',
     "the gate is NOT MET and says so"),
    ("the trace gate is dropped from the list",
     '        ("every trace is held", S["traces_held"] == S["traces"], None),\n',
     '',
     "all of them, counted"),
    ("the task gate is always met",
     '        ("every task is held", S["tasks_held"] == S["tasks"], "tasks held"),',
     '        ("every task is held", True, "tasks held"),',
     "the gate is NOT MET and says so: every task is held"),
    ("the walk gate is always met",
     '        ("every walk of every target holds", not S["bad_walks"], None),',
     '        ("every walk of every target holds", True, None),',
     "the gate is NOT MET and says so: every walk"),
    ("the engine gate is always met",
     '        ("no engine suite failed", S["engine_failures"] == 0, "engine tests"),',
     '        ("no engine suite failed", True, "engine tests"),',
     "the gate is NOT MET and says so: no engine suite failed"),
    ("the suite gate is always met",
     '        ("every suite check passes", S["of"] == S["checks"], "suite checks passing"),',
     '        ("every suite check passes", True, "suite checks passing"),',
     "A GATE THAT IS NOT MET TURNS THE BANNER RED"),
    ("every tile is a reading, the gating ones included",
     '''                    "gate" if gate else "reading",''',
     '''                    "reading",''',
     "a tile that does NOT gate says in one line"),
    # ---- the tiles ----
    ("a hole is reported as no holes",
     '''            S["suites"], S["green"], (", %d NOT VERIFIED" % S["holes"]) if S["holes"] else ", no holes")),''',
     '''            S["suites"], S["green"], ", no holes")),''',
     "1 NOT VERIFIED"),
    ("targets are counted per transport",
     '''        ("%d" % S["commands"], "commands walked", "%d targets × 2 transports, %d pages" % (S["targets"] // 2, S["pages"])),''',
     '''        ("%d" % S["commands"], "commands walked", "%d targets × 2 transports, %d pages" % (S["targets"], S["pages"])),''',
     "1 targets"),
    # ---- the tables ----
    ("a suite's pill is good whenever its ratio is whole, green or not",
     '''        kind = "good" if e.get("green") and e.get("n") == e.get("of") else "bad"''',
     '''        kind = "good" if e.get("n") == e.get("of") else "bad"''',
     "whole and NOT green is still bad"),
    ("a suite's stamp is rendered in local time",
     '    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts)) if ts else "—"',
     '    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "—"',
     "instant in UTC"),
    ("a missing stamp is rendered as the epoch",
     '    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts)) if ts else "—"',
     '    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts or 0))',
     "no `at` is a dash"),
    ("every walk holds",
     '''                    esc(pr.get("median", "—")), pill("holds" if not bad else "BAD", "good" if not bad else "bad")))''',
     '''                    esc(pr.get("median", "—")), pill("holds", "good")))''',
     "the one with a failed command is BAD"),
    ("routed pages are counted with their duplicates",
     '''             '</div><div class="pages">' % (len({r["page"] for r in L["routes"]["routes"]}), len(pages)))''',
     '''             '</div><div class="pages">' % (len(L["routes"]["routes"]), len(pages)))''',
     "counted by DISTINCT page"),
    ("a page whose walk failed is not red",
     '''                 '</span></div>' % ("bad" if bad else "", esc(k[len("csrbt-page/"):]), t.get("driven", 0),''',
     '''                 '</span></div>' % ("", esc(k[len("csrbt-page/"):]), t.get("driven", 0),''',
     "a page whose walk failed is red"),
    ("a canary that must FAIL is not marked as one",
     '''                 % (esc(k), esc(e.get("target")), pill("%s%s" % (e.get("verdict"), " · must FAIL" if e.get("must") == "FAIL" else ""),''',
     '''                 % (esc(k), esc(e.get("target")), pill("%s" % e.get("verdict"),''',
     "must FAIL and did is good, and says so"),
    ("a blind trace that failed renders good",
     '''                    pill("%s" % bl.get("verdict"), "good" if bl.get("held") else "bad") if bl else pill("—", "na"),''',
     '''                    pill("%s" % bl.get("verdict"), "good") if bl else pill("—", "na"),''',
     "its blind trace that failed is bad"),
    ("the calls column reads the sighted trace over the blind one",
     '''                    esc("%d for %d" % ((bl or tr).get("calls", 0), (bl or tr).get("required", 0))) if (tr or bl) else "—"))''',
     '''                    esc("%d for %d" % ((tr or bl).get("calls", 0), (tr or bl).get("required", 0))) if (tr or bl) else "—"))''',
     "the calls column is the BLIND one's"),
    ("a runner with an inconclusive mutant and no survivor is good",
     '''        kind = "good" if e.get("survived", 0) == 0 and e.get("inconclusive", 0) == 0 else "bad"''',
     '''        kind = "good" if e.get("survived", 0) == 0 else "bad"''',
     "an inconclusive mutant and no survivor is STILL bad"),
    ("engines are listed by name rather than by size",
     '''    for name in sorted(E, key=lambda n: (-E[n].get("tests", 0), n)):''',
     '''    for name in sorted(E):''',
     "ordered by tests, most first"),
    ("an engine that failed still gets a good pill",
     '''        kind = "good" if e.get("green") else "bad"''',
     '''        kind = "good"''',
     "an engine's pill is its own green"),
    ("an engine with no reading is rendered as a reading",
     '''            o.append('<div class="engine"><span class="ename">%s</span>%s</div>' % (esc(name), pill("no reading", "na")))''',
     '''            o.append('<div class="engine"><span class="ename">%s</span>%s</div>' % (esc(name), pill("0 ✓", "good")))''',
     "no tests is 'no reading'"),
    ("the footer's newest reading is the suites' alone",
     '''             % esc(when(S["newest"])))''',
     '''             % esc(when(max(v.get("at", 0) for v in c.values()))))''',
     "the newest reading is the newest `at` across every ledger"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutboard_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        path = os.path.join(dst, SUBJECT)
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        # THE MUTANT RENDERS ITS OWN BOARD. verify_board's first check holds
        # the committed page byte-for-byte to a fresh render, and against the
        # committed page every mutant that moves a byte dies there -- which
        # proves the byte moved and nothing about the rule. Re-rendered, the
        # only checks left to kill it are the ones that hold the rule.
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return ("BAD MUTANT", "the mutant cannot render at all: %s"
                    % ((r.stdout + r.stderr).strip().split("\n")[-1][:70] or "no output"))
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", SUITE)],
                           capture_output=True, text=True, timeout=300)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        hit = any(expect in f for f in fails)
        return ("killed" if hit else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    except subprocess.TimeoutExpired:
        return ("BAD MUTANT", "the suite hung")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-70s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the harness board -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-70s %s" % (verdict, name, detail[:58]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    import mutant_ledger
    mutant_ledger.record("mutate_board", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
