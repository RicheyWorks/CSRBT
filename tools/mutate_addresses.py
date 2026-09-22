# -*- coding: utf-8 -*-
"""Mutation testing for whether a control's name outlives pressing it.

ADR-239. `tools/audit_addresses.py` presses every addressed control of every
page through the door and asks whether the name it was given still names it:
HELD, GONE, RENAMED or SHADOWED. It found two pages whose tally cards were
named by their count (`species-a0`, `honeybee0`), and a door that read names
off stamps a rebuild had wiped, so a name published before a press answered
"no control answers to it" after one. Each piece is broken here the way it
would plausibly regress -- the rule, the walk, the door, the pages -- and
verify_addresses must notice.

Mutants land in a COPY of the tree.

    python3 tools/mutate_addresses.py           # run every mutant
    python3 tools/mutate_addresses.py --list    # the catalogue
    python3 tools/mutate_addresses.py --only N  # one mutant; the ledger is not written
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUITE = "verify_addresses.py"

AUD = "tools/audit_addresses.py"
MUTANTS = [
    ("the door reads names off the stamps of the last observe",
     "tools/harness_plugin_page.py",
     "            self.page.evaluate(H.DISCOVER, self.kinds)\n            r = self.page.evaluate(RESOLVE, [form, name, stamp])",
     "            r = self.page.evaluate(RESOLVE, [form, name, stamp])",
     "A NAME SURVIVES THE REBUILD"),
    ("the field notebook's tally card is named by its count again",
     "docs/field-notebook.html",
     """<div class="name nm">'+esc(it.name)+'</div>""",
     """<div class="name">'+esc(it.name)+'</div>""",
     "field-notebook.html, the page the audit found"),
    ("the farm scout's tally card is named by its count again",
     "docs/farm-scout.html",
     """<div class="name nm">'+esc(it.name)+'</div>""",
     """<div class="name">'+esc(it.name)+'</div>""",
     "farm-scout.html, the page the audit found"),
    ("a quadrat's + no longer says which quadrat",
     "docs/field-notebook.html",
     """ aria-label="add one to Q'+(i+1)+'">+</button>""",
     """>+</button>""",
     "answers to a name that says what it counts"),
    ("a rebuilt count is not recognised as the same control",
     AUD,
     "if h == host and l != label and digitless(l) == digitless(label) and",
     "if h == host and l != label and l == label and",
     "A TALLY WHOSE NAME CARRIES ITS COUNT IS RENAMED"),
    ("a node that kept its place under a new name is called gone",
     AUD,
     '        return "renamed", after.get("address") or after.get("label")',
     '        return "gone", None',
     "RENAMED, with its new name"),
    ("a name that lands on another control is called held",
     AUD,
     '            return "shadowed", after.get("address")',
     '            return "held", None',
     "SHADOWED, and says"),
    ("an id rebuilt with a new label is not the same control",
     AUD,
     '                and after.get("resolvedId") == before["id"]:',
     '                and False:',
     "rebuilt under its id with a new label is HELD"),
    ("a renamed control is pressed again under its new name",
     AUD,
     "            seen.add(now)",
     "            pass",
     "the counts add up"),
    ("a shadowed page is not a problem",
     AUD,
     'r.get("error") or any(r.get(k) for k in BAD)',
     'r.get("error") or r.get("renamed")',
     "a page with a renamed or shadowed control"),
    ("only names are pressed, never ids",
     AUD,
     '(c.get("address") or "")[:1] in ("@", "#")',
     '(c.get("address") or "")[:1] in ("@",)',
     "a stable button is HELD"),
    ("the digit rule ignores letters too",
     AUD,
     'return re.sub(r"\\d+", "#", s or "")',
     'return re.sub(r"[\\w]+", "#", s or "")',
     "digits are what is ignored"),
]
KNOWN_EQUIVALENT = []


def run_one(path, find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutaddr_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        shutil.copytree(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        target = os.path.join(tmp, path)
        body = io.open(target, encoding="utf-8").read()
        if body.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times in %s -- the mutation never applied"
                    % (body.count(find), path))
        io.open(target, "w", encoding="utf-8", newline="\n").write(body.replace(find, repl, 1))
        try:
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", SUITE)],
                               capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            return ("BAD MUTANT", "the suite did not finish in 900 s")
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        return ("killed" if any(expect in f for f in fails) else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:90]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", type=int, default=None)
    a = ap.parse_args(argv)
    if a.list:
        for i, (n, f, _, _, e) in enumerate(MUTANTS):
            print("  %2d %-60s %-28s killed by  %s" % (i, n[:60], f, e))
        return 0
    todo = MUTANTS if a.only is None else [MUTANTS[a.only]]
    print("mutation testing the address audit and the door's resolver against verify_addresses -- "
          "%d mutant(s), %d known equivalent\n" % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, path, find, repl, expect in todo:
        verdict, detail = run_one(path, find, repl, expect)
        print("  %-9s %-70s %s" % (verdict, name[:70], detail[:50]))
        sys.stdout.flush()
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        sys.path.insert(0, TOOLS)
        import mutant_ledger
        mutant_ledger.record("mutate_addresses", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
