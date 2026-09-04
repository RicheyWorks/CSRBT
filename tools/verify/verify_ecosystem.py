# -*- coding: utf-8 -*-
"""The engines' own suites, held to the ledger (ADR-118).

tools/ecosystem.py reads every engine's JUnit results into
tools/ecosystem_ledger.json with a floor per engine. This is the consumer
that keeps that ledger honest:

  1. the ledger names every repo the organism's composite build reaches
     (derived from the settings files, not from what sits beside this repo)
     -- a NEW engine fails until it is listed, the way a new page fails
     verify_routes until it is routed -- and nothing the composite does not
     reach;
  2. every listed engine's repo exists (a ledger about repos that are gone
     is a coverage claim about nothing);
  3. for every engine whose results are on THIS machine: no failures, no
     errors, and tests >= floor -- a suite that shrank without --lower and a
     reason is a regression;
  4. an engine without results here, or whose results are older than its
     sources, is NOT VERIFIED, by name, never green -- stale evidence is not
     a shrunken suite;
  5. a floor only rises on a read; every lowering carries a reason;
  6. the ledger's arithmetic: the total it prints is the sum of its rows;
  7. the Atlas's engine table (WholeHog/docs/atlas.html) is what tools/atlas.py
     renders from this ledger and the repos' build files -- a version or a
     suite count typed by hand is drift, and drift fails (ADR-120).

The ledger is the claim; the XML on disk is the evidence. Where the XML is
newer than the ledger's reading, the reading is stale and this says so
rather than passing on last week's number.

Run:  python3 tools/verify/verify_ecosystem.py
"""
# Declared for tools/mutate.py: the temp dir here holds a fixture LEDGER, not fixture pages: the ratchet's rule is driven against data that would break it (ADR-139)
MUTATE_ROLE = "subject"

import io, json, os, sys, time

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import ecosystem as E

P = F = 0
unverified = []


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


led = E.load_ledger()
eng = led.get("engines", {})
listed = {name for name, _, _, _ in E.ENGINES}

# ---- 1. every engine the composite reaches is listed -------------------------
# Derived from the build files (WholeHog's settings includes every engine; each
# includes what it depends on), not from what happens to sit beside this repo:
# the first run on the author's machine listed BlackJackPro as an unlisted
# engine because it, too, has a Gradle build. A neighbour is not an organ.
closure = E.composite_closure("WholeHog") if os.path.isdir(E.repo_dir("WholeHog")) else []
repos = {repo for _, repo, _, _ in E.ENGINES}
ck(set(closure) <= repos if closure else True,
   "every repo the organism's composite build reaches is an engine the ledger lists: unlisted %s"
   % sorted(set(closure) - repos))
ck(repos <= set(closure) if closure else True,
   "and the ledger lists nothing the composite does not reach: extra %s" % sorted(repos - set(closure)))
siblings = closure
ck(len(E.ENGINES) == 15 and len(listed) == 15,
   "fifteen suites: fourteen engines, with CSRBT's two modules read separately")

# ---- 2. every listed repo exists ---------------------------------------------
present = {repo for _, repo, _, _ in E.ENGINES if os.path.isdir(E.repo_dir(repo))}
ck(present == repos or not siblings,
   "every listed engine's repo exists beside this one: missing %s" % sorted(repos - present))

# ---- 3/4. each engine against its results -----------------------------------
for name, repo, modules, note in E.ENGINES:
    e = eng.get(name)
    if not e or "tests" not in e:
        unverified.append("%s: no reading in the ledger" % name)
        continue
    live = None
    for m in modules:
        r = E.read_results(repo, m)
        if r is not None:
            live = r if live is None else {k: (live[k] + r[k] if k != "results_at" else max(live[k], r[k]))
                                          for k in live}
    if live is None:
        unverified.append("%s: %d tests on the record, no results on this machine" % (name, e["tests"]))
        continue
    # Results older than the sources they claim to test are stale evidence --
    # an old build's XML on a machine that has edited since -- and say nothing
    # about the suite as it stands. The first run on the author's machine read
    # nine such and called them shrunken suites. Right about what it matched;
    # wrong about what the match meant.
    newest = max(E.newest_source(repo, m) for m in modules)
    if live["results_at"] < newest:
        unverified.append("%s: results on this machine (%d tests) are older than the sources -- "
                          "rerun the suite (%s)" % (name, live["tests"],
                                                   time.strftime("%Y-%m-%d", time.localtime(live["results_at"]))))
        continue
    ck(live["failures"] == 0 and live["errors"] == 0,
       "%s: %d tests, %d failures, %d errors" % (name, live["tests"], live["failures"], live["errors"]))
    ck(live["tests"] >= e["floor"],
       "%s: %d tests on disk is below the floor of %d -- a suite that shrank without --lower"
       % (name, live["tests"], e["floor"]))
    ck(live["results_at"] <= e.get("at", 0) + 1 or live["tests"] == e["tests"],
       "%s: the results on disk (%d tests) are newer than the ledger's reading (%d) -- rerun "
       "ecosystem.py --read" % (name, live["tests"], e["tests"]))
    # ADR-139: THE RATCHET GOES DOWN TO THE CLASS. A total that has not fallen
    # is not a suite that has not shrunk: delete one test class, grow another
    # by the same count, and the engine-level floor is satisfied by a suite
    # that lost a subject. So every class ever read is on the record, and a
    # class that is gone -- or smaller -- is named, with the size it had.
    floors = e.get("classFloor") or {}
    forgotten = set(f["class"] for f in e.get("forgotten", []))
    gone = sorted(c for c in floors if c not in live["suites"] and c not in forgotten)
    shrunk = sorted((c, floors[c], live["suites"][c]) for c in floors
                    if c in live["suites"] and live["suites"][c] < floors[c])
    ck(not gone, "%s: %d test class(es) on the ratchet are not in the results any more -- "
                 "a suite that lost a subject, without --forget: %s" % (name, len(gone), gone[:3]))
    ck(not shrunk, "%s: %d test class(es) shrank -- %s" % (name, len(shrunk),
                   ["%s %d -> %d" % x for x in shrunk[:3]]))

# ---- 5. floors only rise, lowering carries a reason -------------------------
ck(all(e.get("floor", 0) >= e.get("tests", 0) for e in eng.values()),
   "every floor is at least the count it was read from")
ck(all(all(l.get("reason", "").strip() for l in e.get("lowered", [])) for e in eng.values()),
   "every lowering of a floor carries a reason")
ck(all(all(f.get("reason", "").strip() and f.get("class") for f in e.get("forgotten", []))
       for e in eng.values()),
   "every test class taken off the ratchet carries a reason and names itself")
ck(sum(len(e.get("classFloor") or {}) for e in eng.values()) >= 200
   and all(all(v > 0 for v in (e.get("classFloor") or {}).values()) for e in eng.values()),
   "the class ratchet holds every test class of every engine, each at a count above zero: %d"
   % sum(len(e.get("classFloor") or {}) for e in eng.values()))
ck(all(sum((e.get("classFloor") or {}).values()) >= e.get("tests", 0)
       for n, e in eng.items() if e.get("classFloor")),
   "and the class floors add up to at least the engine's own floor -- no class is missing from it: %s"
   % [n for n, e in eng.items() if e.get("classFloor")
      and sum(e["classFloor"].values()) < e.get("tests", 0)][:3])

# ---- 5b. the ratchet's RULE, on a fixture (ADR-139) --------------------------
#
# Checks 4 and 5 read the ledger as it stands, and as it stands nothing has
# shrunk -- so a read that LOWERED a floor would satisfy every one of them.
# "The floor only rises" is a rule about the code, and the only way to hold code
# to a rule is to run it against data that would break it.
import tempfile as _tf, json as _json
_led = {"engines": {"csrbt-core": {"floor": 99999, "repo": "CSRBT", "note": "",
                                   "classFloor": {"a.B": 500, "gone.C": 7}}}}
_saved_read = E.read_results
try:
    E.read_results = lambda repo, module: ({"tests": 3, "failures": 0, "errors": 0, "skipped": 0,
                                            "classes": 1, "suites": {"a.B": 2, "new.D": 1},
                                            "results_at": 1788000000}
                                           if module == "csrbt-core" else None)
    E.read_all(_led, only=["csrbt-core"])
finally:
    E.read_results = _saved_read
_e = _led["engines"]["csrbt-core"]
ck(_e["floor"] == 99999, "a read never lowers a floor: 99999 stayed %s after reading 3 tests" % _e["floor"])
ck(_e["classFloor"].get("a.B") == 500,
   "...and never lowers a class floor either: a.B was 500, read 2, is %s" % _e["classFloor"].get("a.B"))
ck(_e["classFloor"].get("gone.C") == 7,
   "a class that did not appear in this read keeps its floor -- that is what makes its absence "
   "visible: gone.C is %s" % _e["classFloor"].get("gone.C"))
ck(_e["classFloor"].get("new.D") == 1,
   "a class seen for the first time joins the ratchet at what it read: new.D is %s"
   % _e["classFloor"].get("new.D"))
_led2 = {"engines": {"csrbt-core": {"floor": 0, "repo": "CSRBT", "note": "",
                                    "classFloor": {}, "forgotten": [{"class": "a.B", "reason": "r"}]}}}
_saved_read = E.read_results
try:
    E.read_results = lambda repo, module: ({"tests": 3, "failures": 0, "errors": 0, "skipped": 0,
                                            "classes": 1, "suites": {"a.B": 2, "new.D": 1},
                                            "results_at": 1788000000}
                                           if module == "csrbt-core" else None)
    E.read_all(_led2, only=["csrbt-core"])
finally:
    E.read_results = _saved_read
ck("a.B" not in _led2["engines"]["csrbt-core"]["classFloor"],
   "a class taken off the ratchet with --forget does not rejoin it on the next read")

# the two escape hatches are the only way down, and both are on the record
_tmpd = _tf.mkdtemp()
_lp = os.path.join(_tmpd, "led.json")
io.open(_lp, "w", encoding="utf-8").write(_json.dumps(
    {"engines": {"X": {"floor": 10, "classFloor": {"a.B": 4}}}}))
ck(E.main(["--lower", "X", "2", "--ledger", _lp, "--reason", " "]) == 2
   and _json.load(io.open(_lp, encoding="utf-8"))["engines"]["X"]["floor"] == 10,
   "lowering a floor with no reason is refused, and changes nothing")
ck(E.main(["--forget", "X", "a.B", "--ledger", _lp, "--reason", "  "]) == 2
   and "a.B" in _json.load(io.open(_lp, encoding="utf-8"))["engines"]["X"]["classFloor"],
   "forgetting a test class with no reason is refused, and changes nothing")
ck(E.main(["--lower", "X", "2", "--ledger", _lp, "--reason", "the arena module moved out"]) == 0
   and _json.load(io.open(_lp, encoding="utf-8"))["engines"]["X"]["lowered"][0]["from"] == 10,
   "...and with one, the lowering is written down with where it came from")
ck(E.main(["--forget", "X", "a.B", "--ledger", _lp, "--reason", "class deleted with the feature"]) == 0
   and _json.load(io.open(_lp, encoding="utf-8"))["engines"]["X"]["forgotten"][0]["had"] == 4,
   "...and a forgotten class records the size it had when it went")

# an engine spread over two modules keeps BOTH modules' classes
_led3 = {"engines": {}}
_saved_read, _saved_engines = E.read_results, E.ENGINES
try:
    E.ENGINES = [("Two", "CSRBT", ["m1", "m2"], "")]
    E.read_results = lambda repo, module: {"tests": 2, "failures": 0, "errors": 0, "skipped": 0,
                                           "classes": 1, "suites": {module + ".T": 2},
                                           "results_at": 1788000000}
    E.read_all(_led3)
finally:
    E.read_results, E.ENGINES = _saved_read, _saved_engines
ck(sorted(_led3["engines"]["Two"]["classFloor"]) == ["m1.T", "m2.T"]
   and _led3["engines"]["Two"]["tests"] == 4,
   "an engine spread over two modules puts both modules' classes on the ratchet: %s"
   % sorted(_led3["engines"]["Two"].get("classFloor", {})))

# ---- 6. arithmetic -----------------------------------------------------------
ck(sum(e.get("tests", 0) for e in eng.values()) ==
   sum(eng[n].get("tests", 0) for n in listed if n in eng),
   "the total is the sum of the rows, and only listed engines count")

# ---- 7. the Atlas is regenerated from this ledger, not typed ------------------
import atlas as A
if os.path.isfile(A.ATLAS):
    html = io.open(A.ATLAS, encoding="utf-8").read()
    ck("<!-- engines:begin -->" in html and "<!-- stamp:begin -->" in html,
       "the Atlas carries the generation markers tools/atlas.py writes between")
    ck(A.render(html, led) == html,
       "the Atlas's engine table and stamp are exactly what the ledger and the build files say -- "
       "run tools/atlas.py")
    ck(len(A.ROWS) == 14 and {r[1] for r in A.ROWS} == {repo for _, repo, _, _ in E.ENGINES},
       "the Atlas rows are the fourteen repos the ledger lists, no more, no fewer")
    ck(sorted(n for _, _, engines, _ in A.ROWS for n in engines) == sorted(e for e, _, _, _ in E.ENGINES),
       "every ledger engine feeds exactly one Atlas row")
else:
    unverified.append("Atlas: WholeHog/docs/atlas.html is not beside this repo")

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
