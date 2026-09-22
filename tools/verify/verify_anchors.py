# -*- coding: utf-8 -*-
"""The mutant ledger is about the code as it is (ADR-235).

`tools/audit_anchors.py` reads every runner's catalogue, without running any of
them, and finds two things the ledger cannot see by itself:
  - a mutant whose anchor lands nowhere, which still counts as killed until
    its runner runs again, and
  - a runner whose catalogue is not the one its ledger entry recorded.

This suite holds the audit on fixtures it builds, a scratch kit with one
runner of every shape and one of every failure, and on the real kit. The
real kit's result is held as a gate: no stale mutant, no drifted runner and
no runner it cannot read. The board's "mutants killed" is only as true as that.

Opens nothing; runs in about a second.

Run:  python3 tools/verify/verify_anchors.py
"""
# Declared for tools/mutate.py: this suite asserts about tools/audit_anchors.py.
MUTATE_ROLE = "subject"
import io, json, os, shutil, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import audit_anchors as A

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- 1. the shapes, stated here and not asked of the subject ----------------
ck(A.shape(("a name", "find", "repl", "expect")) == ("a name", "find"),
   "(name, find, repl, expect): the anchor is second")
ck(A.shape(("plugin", "a name", "find", "repl", "expect")) == ("a name", "find"),
   "(target, name, find, repl, expect): a one-word target first, the anchor third")
ck(A.shape(("a name", "audit_states.py", "find", "repl", "expect")) == ("a name", "find"),
   "(name, file, find, repl, expect): a file second, the anchor third")
ck(A.shape(("a name", "      - \"**/src/**\"\n", "", "expect", "both")) == ("a name", "      - \"**/src/**\"\n"),
   "(name, find, repl, expect, where): the anchor second, whatever it looks like")
ck(A.shape(("a name", "find", "repl")) is None and A.shape(("a", 1, "b", "c")) is None
   and A.shape({"name": "x"}) is None,
   "an entry of any other shape is not guessed at")

# ---- 2. a scratch kit, one runner per case ----------------------------------
tmp = tempfile.mkdtemp(prefix="anchors_")
eng = tempfile.mkdtemp(prefix="anchors_engine_")   # a sibling, as WholeHog is -- not inside the kit
try:
    T = os.path.join(tmp, "tools")
    os.makedirs(os.path.join(T, "verify"))
    os.makedirs(os.path.join(tmp, "docs"))
    os.makedirs(os.path.join(eng, "src"))
    io.open(os.path.join(T, "subject.py"), "w", encoding="utf-8").write(
        "def f(x):\n    return x + 1  # LANDS-IN-TOOLS\n")
    io.open(os.path.join(tmp, "docs", "page.html"), "w", encoding="utf-8").write(
        "<script>var LANDS_IN_PAGE = 1;</script>")
    io.open(os.path.join(T, "task.json"), "w", encoding="utf-8").write('{"LANDS_IN_JSON": true}')
    io.open(os.path.join(eng, "src", "Console.java"), "w", encoding="utf-8").write(
        "class Console { int LANDS_IN_ENGINE; }")

    def runner(name, body):
        io.open(os.path.join(T, name + ".py"), "w", encoding="utf-8").write(body)

    runner("mutate_good", '''MUTANTS = [
    ("lands in a tool", "return x + 1  # LANDS-IN-TOOLS", "return x", "e"),
    ("lands in a page", "var LANDS_IN_PAGE = 1;", "", "e"),
    ("lands in a task", '"LANDS_IN_JSON": true', "", "e"),
    ("console", "lands in the engine", "int LANDS_IN_ENGINE;", "", "e"),
]
''')
    runner("mutate_stale", '''MUTANTS = [
    ("still lands", "return x + 1", "return x", "e"),
    ("the line was reworded", "return x + 2", "return x", "e"),
    ("only in this runner", "ONLY-IN-THE-RUNNER-ITSELF", "", "e"),
]
''')
    runner("mutate_renamed", '''MUTANTS = [
    ("the new name", "return x + 1", "return x", "e"),
]
''')
    runner("mutate_grown", '''MUTANTS = [
    ("one", "return x + 1", "return x", "e"),
    ("two", "var LANDS_IN_PAGE", "var X", "e"),
]
''')
    runner("mutate_broken", "import no_such_module_anywhere\nMUTANTS = []\n")
    runner("mutate_empty", "X = 1\n")
    runner("mutate_odd", '''MUTANTS = [("a", "return x + 1", "b")]\n''')
    runner("mutate_unrecorded", '''MUTANTS = [("fresh", "return x + 1", "return x", "e")]\n''')
    # a sweep script is not a runner
    io.open(os.path.join(T, "mutate.py"), "w", encoding="utf-8").write("MUTANTS = [('x', 'NOWHERE', '', 'e')]\n")

    ledger = {"runners": {
        "mutate_good": {"mutants": 4, "rows": [{"name": n} for n in
                                               ("lands in a tool", "lands in a page", "lands in a task",
                                                "lands in the engine")]},
        "mutate_stale": {"mutants": 3, "rows": [{"name": n} for n in
                                                ("still lands", "the line was reworded", "only in this runner")]},
        "mutate_renamed": {"mutants": 1, "rows": [{"name": "the old name"}]},
        "mutate_grown": {"mutants": 1, "rows": [{"name": "one"}]},
    }}
    old = os.environ.get("CSRBT_WHOLEHOG")
    os.environ["CSRBT_WHOLEHOG"] = eng
    try:
        rows = dict((r["runner"], r) for r in A.audit(tmp, ledger))
    finally:
        if old is None:
            os.environ.pop("CSRBT_WHOLEHOG", None)
        else:
            os.environ["CSRBT_WHOLEHOG"] = old

    ck(sorted(rows) == ["mutate_broken", "mutate_empty", "mutate_good", "mutate_grown", "mutate_odd",
                        "mutate_renamed", "mutate_stale", "mutate_unrecorded"],
       "every mutate_*.py is read and nothing else -- tools/mutate.py is the sweep, not a runner: %s"
       % sorted(rows))
    g = rows["mutate_good"]
    ck(g["read"] and g["mutants"] == 4 and g["anchors"] == 4 and not g["stale"] and not g["drifted"],
       "an anchor lands in a tool, a page, a task file, or the sibling engine's source: %s" % g)
    s = rows["mutate_stale"]
    ck(s["stale"] == ["the line was reworded", "only in this runner"],
       "a reworded line is stale, and so is an anchor found only in the runner that names it: %s"
       % s["stale"])
    ck(not s["drifted"], "...and a stale runner whose catalogue is unchanged has not drifted")
    ck(rows["mutate_renamed"]["drifted"] == ["the new name", "the old name"] and not rows["mutate_renamed"]["stale"],
       "a renamed mutant is drift, named both ways: %s" % rows["mutate_renamed"]["drifted"])
    ck(rows["mutate_grown"]["drifted"] == ["two"],
       "a mutant added since the last run is drift: %s" % rows["mutate_grown"]["drifted"])
    ck(not rows["mutate_broken"]["read"] and "does not import" in rows["mutate_broken"]["why"],
       "a runner that does not import is reported, not skipped: %s" % rows["mutate_broken"]["why"])
    ck(not rows["mutate_empty"]["read"] and "no MUTANTS" in rows["mutate_empty"]["why"],
       "a runner with no catalogue is reported: %s" % rows["mutate_empty"]["why"])
    ck(rows["mutate_odd"]["unshaped"] == 1 and "shape" in rows["mutate_odd"]["why"],
       "an entry of an unknown shape is counted and said, not guessed past")
    u = rows["mutate_unrecorded"]
    ck(u["read"] and not u["recorded"] and not u["drifted"],
       "a runner never run has no ledger entry to drift from")
    bad = sorted(r["runner"] for r in A.problems(list(rows.values())))
    ck(bad == ["mutate_broken", "mutate_empty", "mutate_grown", "mutate_odd", "mutate_renamed", "mutate_stale"],
       "the problems are exactly the stale, the drifted, the unread and the unshaped: %s" % bad)

    # the engine is found where the plugin finds it, and only there
    os.environ["CSRBT_WHOLEHOG"] = os.path.join(tmp, "nowhere")
    try:
        g2 = dict((r["runner"], r) for r in A.audit(tmp, ledger))["mutate_good"]
    finally:
        if old is None:
            os.environ.pop("CSRBT_WHOLEHOG", None)
        else:
            os.environ["CSRBT_WHOLEHOG"] = old
    ck(g2["stale"] == ["lands in the engine"],
       "without the engine checked out, its anchor has nowhere to land and says so: %s" % g2["stale"])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(eng, ignore_errors=True)

# ---- 3. the real kit: the gate ----------------------------------------------
real = A.audit()
led = json.load(io.open(os.path.join(_kit.TOOLS_DIR, "mutant_ledger.json"), encoding="utf-8"))["runners"]
ck(len(real) >= 33 and all(r["read"] for r in real),
   "every runner in the kit is read: %d, unread %s" % (len(real), [r["runner"] for r in real if not r["read"]]))
ck(sum(r["mutants"] for r in real) == sum(r["anchors"] for r in real) >= 1180,
   "every catalogue entry has a shape and an anchor: %d mutants, %d anchors"
   % (sum(r["mutants"] for r in real), sum(r["anchors"] for r in real)))
unverified = []
if A.engine_present():
    ck(not [r for r in real if r["stale"]],
       "NO STALE MUTANT: every anchor lands somewhere in the code it breaks -- %s"
       % [(r["runner"], r["stale"][:2]) for r in real if r["stale"]])
else:
    # The console mutants' anchors are in the sibling engine. Without it
    # checked out they have nowhere to land, and calling them stale would be a
    # statement about this machine rather than about the kit.
    ck(not [r for r in real if r["stale"] and r["runner"] not in ("mutate_organism", "mutate_lab")],
       "NO STALE MUTANT outside the console runners: %s"
       % [(r["runner"], r["stale"][:2]) for r in real if r["stale"]])
    unverified.append("the console runners' anchors -- the sibling engine (WholeHog) is not checked out "
                      "at %s" % A.engine_dir(A.ROOT))
ck(not [r for r in real if r["drifted"]],
   "NO DRIFTED RUNNER: every ledger entry is about the catalogue its runner has now -- %s"
   % [(r["runner"], r["drifted"][:2]) for r in real if r["drifted"]])
ck(all(r["recorded"] for r in real) and set(led) == set(r["runner"] for r in real),
   "every runner has a ledger entry and every ledger entry has a runner: %s"
   % sorted(set(led) ^ set(r["runner"] for r in real)))
ck(sum(e.get("mutants", 0) for e in led.values()) == sum(r["mutants"] for r in real),
   "so the board's mutant count is the catalogue's: %d recorded, %d in the runners"
   % (sum(e.get("mutants", 0) for e in led.values()), sum(r["mutants"] for r in real)))

print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, P + F + len(unverified)))
raise SystemExit(1 if F else 0)
