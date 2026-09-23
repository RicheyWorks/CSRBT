# -*- coding: utf-8 -*-
"""The counts are about this tree, and no suite shrinks below its floor (ADR-241).

Holds `tools/evidence.py` -- ported from the FlowersForever harness's
`verify_harness.py` -- on a scratch kit it builds and on the real one:

  1. the subject: pages, prose, tools, tasks, suites, CI are in the digest;
     ledgers, counts, floors, the board, published state, delivery manifests
     and push scripts are NOT, so a run's own outputs cannot move the tree;
  2. the digest moves on a changed byte, an added file and a removed file,
     and names each one;
  3. status(): counts about this tree; about another tree (off); carrying no
     tree (unstamped); a run the tree moved under (moved);
  4. floors: a green suite below its floor goes red and says so; a suite never
     seen is floored at what it counted; --raise-floors raises and never lowers;
  5. run_all carries it: the tree is taken before the jobs and written with
     every count, the floors are applied, and a moved tree fails the run;
  6. the real kit: counts.json is about this tree, every count is stamped,
     every green suite is at or above its floor, and floors.json has a floor
     for every suite counts.json knows.

Opens nothing; runs in about two seconds.

Run:  python3 tools/verify/verify_evidence.py
"""
# Declared for tools/mutate.py: this suite asserts about tools/evidence.py.
MUTATE_ROLE = "subject"
import io, json, os, shutil, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import evidence as E

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


def w(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(text)


tmp = tempfile.mkdtemp(prefix="evidence_")
try:
    w(tmp, "docs/page.html", "<p>one</p>")
    w(tmp, "docs/ADR-1-x.md", "# one")
    w(tmp, "tools/tool.py", "X = 1\n")
    w(tmp, "tools/tasks/t.json", "{}")
    w(tmp, "tools/verify/verify_a.py", "print('1/1')\n")
    w(tmp, ".github/workflows/ci.yml", "on: push\n")
    w(tmp, "tools/walk_ledger.json", "{}")
    w(tmp, "tools/verify/counts.json", "{}")
    w(tmp, "tools/verify/floors.json", "{}")
    w(tmp, "tools/published.json", "{}")
    w(tmp, "tools/harness_board.html", "<b>")
    w(tmp, "tools/delivery/adr1.json", "{}")
    w(tmp, "tools/push/push-adr1.ps1", "git push")
    w(tmp, "tools/routes.json", "{}")
    w(tmp, "build/publish/page.html", "<p>built</p>")
    # ---- 1. the subject and the evidence -------------------------------------
    files = E.subject_files(tmp)
    ck(files == [".github/workflows/ci.yml", "docs/ADR-1-x.md", "docs/page.html", "tools/tasks/t.json",
                 "tools/tool.py", "tools/verify/verify_a.py"],
       "THE SUBJECT is pages, prose, tools, tasks, suites and CI -- and NOT the ledgers, counts, floors, "
       "the board, published state, manifests, push scripts, routes.json or build/: %s" % files)
    d0 = E.digest(tmp)
    ck(len(d0["digest"]) == 64 and set(d0["files"]) == set(files) and all(len(v) == 12 for v in d0["files"].values()),
       "a digest is one sha256 over the subject and a sha12 per file: %s" % d0["digest"][:12])
    w(tmp, "tools/walk_ledger.json", '{"targets": {"x": 1}}')
    w(tmp, "tools/verify/counts.json", '{"suites": {"a": 1}}')
    w(tmp, "tools/harness_board.html", "<b>rendered</b>")
    ck(E.digest(tmp)["digest"] == d0["digest"],
       "A RUN'S OWN OUTPUTS DO NOT MOVE THE TREE: ledgers, counts and the board changed, the digest did not")
    # ---- 2. what moves it -----------------------------------------------------
    w(tmp, "docs/page.html", "<p>two</p>")
    d1 = E.digest(tmp)
    ck(d1["digest"] != d0["digest"] and E.compare(d0, d1) == {"changed": ["docs/page.html"], "added": [], "removed": []},
       "a changed byte in a page moves the tree, and the page is named: %s" % E.compare(d0, d1))
    w(tmp, "docs/new.html", "<p>new</p>")
    os.remove(os.path.join(tmp, "tools", "tool.py"))
    d2 = E.digest(tmp)
    c = E.compare(d0, d2)
    ck(c == {"changed": ["docs/page.html"], "added": ["docs/new.html"], "removed": ["tools/tool.py"]},
       "an added file and a removed file are named as such: %s" % c)
    ck(E.compare(d2, E.digest(tmp)) == {"changed": [], "added": [], "removed": []},
       "...and the same tree compares empty")
    # ---- 3. status --------------------------------------------------------------
    now = E.short(d2["digest"])
    good = {"tree": d2, "suites": {"verify_a": {"n": 1, "of": 1, "green": True, "tree": now}}}
    s = E.status(good, tmp)
    ck(s["same"] and not s["off"] and not s["unstamped"] and not s["moved"] and s["now"] == s["recorded"] == now
       and s["files"] == len(d2["files"]),
       "counts about this tree: same, none off, none unstamped: %s" % s)
    other = {"tree": d0, "suites": {"verify_a": {"n": 1, "of": 1, "green": True, "tree": E.short(d0["digest"])}}}
    s = E.status(other, tmp)
    ck(not s["same"] and s["off"] == ["verify_a"] and s["diff"]["changed"] == ["docs/page.html"]
       and s["diff"]["added"] == ["docs/new.html"] and s["diff"]["removed"] == ["tools/tool.py"],
       "counts about ANOTHER tree: not same, the suite is off, and the files that differ are named: %s" % s["diff"])
    mixed = {"tree": d2, "suites": {"verify_a": {"n": 1, "of": 1, "green": True, "tree": now},
                                    "verify_old": {"n": 2, "of": 2, "green": True},
                                    "verify_b": {"n": 3, "of": 3, "green": True, "tree": "000000000000"}}}
    s = E.status(mixed, tmp)
    ck(s["same"] and s["off"] == ["verify_b"] and s["unstamped"] == ["verify_old"],
       "the tree can match while one count is from another tree and one carries none -- both named: off %s, "
       "unstamped %s" % (s["off"], s["unstamped"]))
    moved = dict(good, tree_moved=["docs/page.html"])
    ck(E.status(moved, tmp)["moved"] == ["docs/page.html"], "a run the tree moved under says so")
    ck(E.status({"suites": {}}, tmp)["recorded"] == "" and not E.status({"suites": {}}, tmp)["same"],
       "counts with no tree recorded are about no tree")
    # ---- 4. floors ------------------------------------------------------------------
    rec = {"verify_a": {"n": 10, "of": 10, "green": True}, "verify_b": {"n": 4, "of": 4, "green": True},
           "verify_c": {"n": 7, "of": 9, "green": False}, "verify_new": {"n": 3, "of": 3, "green": True},
           "verify_red": {"n": 2, "of": 9, "green": False}}
    below, floors = E.apply_floors(rec, {"verify_a": 10, "verify_b": 6, "verify_c": 5, "verify_red": 8})
    ck(below == [("verify_b", 4, 6)] and rec["verify_b"]["green"] is False and rec["verify_b"]["below_floor"] == 6,
       "A GREEN SUITE THAT COUNTED FEWER THAN ITS FLOOR GOES RED and carries the floor it fell under: %s" % below)
    ck(rec["verify_a"]["green"] and "below_floor" not in rec["verify_a"],
       "a suite at its floor is left alone")
    ck(rec["verify_c"]["green"] is False and "below_floor" not in rec["verify_c"] and floors["verify_c"] == 5,
       "a red suite above its floor is red for its own reason, not the floor's")
    ck("below_floor" not in rec["verify_red"] and ("verify_red", 2, 8) not in below,
       "a red suite below its floor is not reported twice -- it is red for its own reason, and the floor is "
       "about a suite that PASSES with fewer checks")
    ck(floors.get("verify_new") == 3, "a suite never seen before is floored at what it counted: %s" % floors)
    raised = E.raise_floors({"verify_a": {"n": 12, "green": True}, "verify_b": {"n": 4, "green": True},
                             "verify_c": {"n": 20, "green": False}}, floors)
    ck(raised["verify_a"] == 12 and raised["verify_b"] == 6 and raised["verify_c"] == 5,
       "--raise-floors raises a green suite's floor to its count, NEVER lowers one, and takes nothing from "
       "a red suite: %s" % raised)
    E.save_floors(raised, os.path.join(tmp, "floors.json"))
    ck(E.load_floors(os.path.join(tmp, "floors.json")) == raised, "floors round-trip through the file")
    ck(E.load_floors(os.path.join(tmp, "nope.json")) == {}, "no floors file is no floors")
    w(tmp, "bad.json", '{"floors": {"x": 0, "y": true, "z": "9", "ok": 2}}')
    ck(E.load_floors(os.path.join(tmp, "bad.json")) == {"ok": 2},
       "a floor that is not a positive integer is not a floor")
    # ---- 5. run_all carries it ------------------------------------------------------
    src = io.open(os.path.join(_kit.TOOLS_DIR, "verify", "run_all.py"), encoding="utf-8").read()
    ck("tree0 = EV.digest(ROOT)" in src and src.index("tree0 = EV.digest(ROOT)") < src.index("ThreadPoolExecutor"),
       "run_all takes the tree BEFORE the jobs run")
    ck('"tree": EV.short(tree0["digest"])' in src and '"tree": tree0' in src,
       "...and writes it with every count, and file by file with the ledger")
    ck("EV.apply_floors(rec, floors)" in src and 'failed.append((name, "%s counted %d checks; its floor is %d' in src,
       "...applies the floors, and a suite below its floor FAILS THE RUN")
    ck("tree1 = EV.digest(ROOT)" in src and 'failed.append(("tree", "the tree moved during the run' in src,
       "...and takes the tree again after, and a tree that moved fails the run")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 6. the real kit --------------------------------------------------------------
# Inside run_all, counts.json is still LAST run's -- this run writes it at the
# end -- so the thing to hold is that the tree has not moved since the run
# began, which run_all hands every job. Outside a run, the counts themselves.
real = E.status()
run_tree = os.environ.get("CSRBT_RUN_TREE")
if run_tree:
    ck(E.short(run_tree) == real["now"],
       "INSIDE A RUN: the tree has not moved since run_all took it -- began %s, now %s"
       % (E.short(run_tree), real["now"]))
    ck(len(run_tree) == 64, "...and what run_all handed over is a digest")
else:
    ck(real["same"], "THE REAL COUNTS ARE ABOUT THIS TREE: recorded %s, now %s, %s"
       % (real["recorded"], real["now"], real["diff"]))
    ck(not real["off"] and not real["unstamped"] and not real["moved"],
       "every real count is stamped with this tree: off %s, unstamped %s, moved %s"
       % (real["off"][:4], real["unstamped"][:4], real["moved"][:4]))
counts = E.load_counts()["suites"]
floors = E.load_floors()
ck(set(floors) >= set(counts), "floors.json has a floor for every suite counts.json knows: missing %s"
   % sorted(set(counts) - set(floors))[:6])
low = sorted((k, v.get("n"), floors.get(k)) for k, v in counts.items() if v.get("green") and v.get("n", 0) < floors.get(k, 0))
ck(not low, "no green suite of the real kit is below its floor: %s" % low)
ck(real["files"] >= 1000, "the real subject is the whole kit, not a corner: %d files" % real["files"])

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
