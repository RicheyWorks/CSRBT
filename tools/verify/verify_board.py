# -*- coding: utf-8 -*-
"""The Harness Board is what the ledgers say (ADR-127).

tools/harness_board.py renders tools/harness_board.html from seven ledgers
and nothing else. This suite holds the file to the ledgers and the ledgers
to each other:

  1. the committed board is byte-for-byte what the renderer produces from
     the committed ledgers -- a board edited by hand, or a ledger moved
     without a re-render, fails;
  2. the summary's arithmetic is the ledgers': suite checks are the sum of
     counts.json, commands the sum of the walks, tasks and traces held as
     the task ledger counts them, mutants as the runners recorded them,
     engine tests as the ecosystem ledger's;
  3. every mutant runner in the kit has a row in mutant_ledger.json and
     the row is the runner's own catalogue: as many mutants as the runner
     lists, as many recorded equivalents;
  4. the page renders: every ledger's headline number appears in it, every
     pill is one of the three kinds, no NaN or None leaks into the text;
  5. the renderer is deterministic: two renders are identical;
  9. the arithmetic and the rendering hold on a FIXTURE ledger set with every
     gate broken at known numbers (ADR-227), because the committed ledgers are
     green and a renderer that miscounts a failure renders them the same.

Run:  python3 tools/verify/verify_board.py
"""
import importlib, io, json, os, re, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_board as B
import mutant_ledger as ML

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


L = B.ledgers()
page = B.render(L)
S = B.summary(L)

# ---- 1. the file is the render ----------------------------------------------
ck(os.path.isfile(B.OUT), "the board exists at %s" % B.OUT)
cur = io.open(B.OUT, encoding="utf-8").read() if os.path.isfile(B.OUT) else ""
ck(cur == page, "the committed board is byte-for-byte what the ledgers render -- run tools/harness_board.py")
ck(B.render(L) == page, "the renderer is deterministic")

# ---- 2. arithmetic --------------------------------------------------------------
c = L["counts"]["suites"]
ck(S["checks"] == sum(v.get("n", 0) for v in c.values()) and S["of"] == sum(v.get("of", 0) for v in c.values()),
   "suite checks are the sum of counts.json: %d/%d" % (S["checks"], S["of"]))
W = L["walk"]["targets"]
ck(S["commands"] == sum(e.get("commands", 0) for e in W.values()) and S["pages"] == sum(1 for k in W if k.startswith("csrbt-page/")),
   "commands walked are the sum of the walk ledger: %d over %d entries" % (S["commands"], len(W)))
T = L["tasks"]["tasks"]
ck(S["tasks"] + S["traces"] == len(T) and S["tasks_held"] == sum(1 for k, e in T.items() if not k.endswith(("@trace", "@blind")) and e.get("held")),
   "tasks and traces are counted as the task ledger holds them, a blind trace among the traces (ADR-136): %d + %d"
   % (S["tasks"], S["traces"]))
ck(S["traces"] == sum(1 for k in T if k.endswith(("@trace", "@blind"))) and sum(1 for k in T if k.endswith("@blind")) == 6,
   "and the six blind traces are counted: %d trace(s), %d blind"
   % (S["traces"], sum(1 for k in T if k.endswith("@blind"))))
M = L["mutants"]["runners"]
ck(S["mutants"] == sum(e.get("mutants", 0) for e in M.values()) and S["killed"] == sum(e.get("killed", 0) for e in M.values()),
   "mutants are the runners' own totals: %d killed of %d" % (S["killed"], S["mutants"]))
E = L["ecosystem"]["engines"]
ck(S["engine_tests"] == sum(e.get("tests", 0) for e in E.values()), "engine tests are the ecosystem ledger's: %d" % S["engine_tests"])

# ---- 3. every runner has a row, and the row is its catalogue -------------------
# [a-z_]+, not [a-z]+: mutate_audit_states.py (ADR-130) is a runner and the
# old pattern did not match it, so the check compared a short list against a
# complete one and blamed the board. A discovery rule that cannot see a file is
# the same defect as an audit that cannot see a page.
runners = sorted(f[:-3] for f in os.listdir(_kit.TOOLS_DIR) if re.match(r"mutate_[a-z_]+\.py$", f))
ck(set(runners) == {r for r, _ in B.RUNNERS} and set(runners) <= set(M),
   "every mutant runner in tools/ is on the board and in the ledger: runners %s, ledger %s, board %s"
   % (runners, sorted(M), sorted(r for r, _ in B.RUNNERS)))
for r in runners:
    mod = importlib.import_module(r)
    e = M.get(r) or {}
    ck(e.get("mutants") == len(getattr(mod, "MUTANTS", [])) and
       e.get("equivalent") == len(getattr(mod, "KNOWN_EQUIVALENT", [])) and len(e.get("rows", [])) == e.get("mutants"),
       "%s: the ledger row is the runner's catalogue -- %s mutants (runner lists %d), %s equivalents (runner records %d)"
       % (r, e.get("mutants"), len(getattr(mod, "MUTANTS", [])), e.get("equivalent"), len(getattr(mod, "KNOWN_EQUIVALENT", []))))
    ck(e.get("killed", 0) + e.get("survived", 0) + e.get("inconclusive", 0) == e.get("mutants", -1),
       "%s: killed + survived + inconclusive == mutants" % r)
    ck(all(x["verdict"] == "killed" for x in e.get("rows", [])) == (e.get("survived", 1) == 0 and e.get("inconclusive", 1) == 0),
       "%s: the totals agree with the rows" % r)

# ---- 4. the page --------------------------------------------------------------
for n in (S["checks"], S["commands"], S["engine_tests"], S["killed"]):
    ck(str(n) in page, "the headline number %d appears on the page" % n)
ck(not re.search(r"\bNone\b|\bNaN\b|\bnan\b", re.sub(r"<style>.*?</style>", "", page, flags=re.S)),
   "no None or NaN leaks into the page's text")
ck(set(re.findall(r'class="pill (\w+)"', page)) <= {"good", "bad", "na"}, "every pill is good, bad or na")
ck(page.count("<table>") == page.count("</table>") and page.count("<section>") == page.count("</section>"),
   "every table and section is closed")
ck('<title>Harness Board</title>' in page and 'data-theme="dark"' in page and "prefers-color-scheme: dark" in page,
   "the page is named and designed for both themes")
ck(all(p[len("csrbt-page/"):] in page for p in W if p.startswith("csrbt-page/")),
   "every walked page is on the board")
ck(all(k in page for k in T if not k.endswith(("@trace", "@blind"))), "every task is on the board")
ck("blind trace" in page and "never seen the task" in page,
   "and the board says which column is the blind one, and what blind means")

# ---- 6. the verdict is the gates, and every tile says which it is (ADR-215) ----
# The verdict was a hand-written conjunction over seven summary fields while the
# page rendered eleven tiles, six of which do not gate it -- including a
# "6 / 7 clean under load" sitting beside "Everything the harness knows how to
# check is green." A reader with those two on one screen has to distrust one of
# them, and the page said nothing about which.
_GATES = re.search(r"The verdict is these (\d+) and nothing else: (.*?)\. Every other", page)
ck(_GATES is not None, "THE PAGE SAYS WHAT ITS VERDICT IS COMPUTED FROM, in the header, beside "
                       "the verdict")
if _GATES:
    _named = [g.strip() for g in _GATES.group(2).split(";")]
    ck(len(_named) == int(_GATES.group(1)) == 7,
       "...all of them, counted: %s" % _named)
    ck(all("NOT MET" not in g for g in _named) == ("verdict good" in page),
       "THE BANNER IS THE CONJUNCTION OF THOSE GATES AND NOTHING ELSE -- a gate that is not met "
       "and a green banner on the same page is the board lying about the thing it exists to "
       "report: %s" % [g for g in _named if "NOT MET" in g])
    ck(any("walk" in g for g in _named) and any("trace" in g for g in _named),
       "...INCLUDING THE TWO GATES THAT HAVE NO TILE. The honest shape is not 'every tile gates' "
       "-- the walks and the traces gate and are not tiles, so the list is named rather than "
       "inferred from what happens to be displayed: %s" % _named)

_tiles = re.findall(r'<div class="what">(.*?)</div>', page)
_kinds = re.findall(r'<p class="kind (gate|reading)">(.*?)</p>', page)
ck(len(_tiles) == len(_kinds) and len(_tiles) == 11,
   "EVERY TILE DECLARES WHICH IT IS: %d tile(s), %d declaration(s)" % (len(_tiles), len(_kinds)))
ck(all(k == "gate" or v.startswith("a reading, not a gate") and len(v) > 40 for k, v in _kinds),
   "...and a tile that does NOT gate says in one line what kind of number it is instead, rather "
   "than leaving the reader to guess why a ratio below 1 sits under a green banner: %s"
   % [v for k, v in _kinds if k != "gate" and not v.startswith("a reading, not a gate")])
_load = [v for (k, v), w in zip(_kinds, _tiles) if w == "clean under load"]
ck(_load and _load[0].startswith("a reading, not a gate") and "ceiling" in _load[0]
   and "contend" in _load[0],
   "...and the tile that started this says so, AND NAMES THE RULE THAT HOLDS IT. ADR-215's first "
   "version of this line called the reading 'a known flake with a ratchet' when the contention "
   "ledger had no ceiling, no declaration and nothing that ran it -- a reassuring sentence about "
   "a mechanism nobody had built, on the one page whose job is to say what the harness can vouch "
   "for (ADR-216): %s" % _load)

# AND IT FIRES. A rule with no violator cannot show that it works (ADR-207), and
# this one is asserted against a board that is green: every check above would
# pass on a page whose banner was hard-coded. So a gate is broken on a copy of
# the ledgers and the page is re-rendered.
import copy as _copy
_broke = _copy.deepcopy(L)
_first = sorted(_broke["counts"]["suites"])[0]
_broke["counts"]["suites"][_first]["n"] = max(0, _broke["counts"]["suites"][_first].get("of", 1) - 1)
_bad = B.render(_broke)
ck("verdict bad" in _bad and "every suite check passes \u2014 NOT MET" in _bad,
   "A GATE THAT IS NOT MET TURNS THE BANNER RED AND IS NAMED ON THE PAGE -- checked by breaking "
   "one on a copy of the ledgers, because every check above this one would pass on a board whose "
   "banner was hard-coded green")
ck("every task is held \u2014 NOT MET" not in _bad,
   "...and only the gate that broke is named, so the sentence is a diagnosis rather than an alarm")

_src = io.open(os.path.join(_kit.TOOLS_DIR, "harness_board.py"), encoding="utf-8").read()
ck("all_green = all(ok for _n, ok, _t in GATES)" in _src,
   "THE VERDICT IS DERIVED FROM THE NAMED LIST, not restated beside it -- a gate added to the "
   "list appears on the page the same day, where the old conjunction could be extended without "
   "the page ever mentioning it")

# ---- 8. the page is the same page in every time zone (ADR-226) ----
# Check 1 holds the committed page byte-for-byte to a fresh render, and the
# stamps were rendered in LOCAL time, so the check was really 'this machine is
# in the zone the page was rendered in': green in the container, red on the
# operator's VM seven hours east of it, with every ledger identical.
import time as _time
_tz = os.environ.get("TZ")
_seen = []
for _zone in ("UTC", "Asia/Tokyo", "America/Los_Angeles"):
    os.environ["TZ"] = _zone
    _time.tzset()
    _seen.append(B.render(L))
if _tz is None:
    os.environ.pop("TZ", None)
else:
    os.environ["TZ"] = _tz
_time.tzset()
ck(_seen[0] == _seen[1] == _seen[2],
   "THE RENDER DOES NOT DEPEND ON THE MACHINE'S TIME ZONE -- the same ledgers in UTC, Tokyo and "
   "Los Angeles are the same bytes, or the byte-for-byte check above is a check of where the "
   "renderer stood")
ck("every time on this page is UTC" in page, "...and the page says which zone its stamps are in")
ck(B.when(0) == "—" and B.when(1789689600) == "2026-09-18 00:00",
   "a stamp is the instant in UTC: %r" % B.when(1789689600))

# ---- 9. the arithmetic and the rendering, held on a ledger set that is NOT green (ADR-227) ----
# Every check above reads the committed ledgers, and the committed ledgers are
# green: every suite n == of, no mutant survived, no engine failed, every task
# held. So a renderer that summed `of` where it should sum `n`, or counted every
# mutant as killed, or rendered every engine's pill good, produces the SAME PAGE
# here and passes every check above -- the checks cannot fail on a board with
# nothing wrong in it. This is the ledger set with everything wrong in it, at
# known numbers, and the render is held clause by clause. mutate_board breaks
# the renderer and re-renders its own board before this suite runs, so the
# byte-for-byte check above cannot cover for these.
FIX = {
    "counts": {"suites": {
        "verify_contract": {"n": 7, "of": 7, "green": True, "at": 300},
        "verify_lab": {"n": 3, "of": 4, "green": False, "unverified": 1, "at": 200},
        "verify_mcp": {"n": 5, "of": 5, "green": True, "at": 100},
        "verify_http": {"n": 2, "of": 2, "green": False, "at": 50},
    }},
    "walk": {"targets": {
        "csrbt-lab@stdio": {"identity": "holds", "transport": "stdio", "tools": 2, "commands": 10,
                            "totals": {"driven": 5, "refused": 5}, "at": 40},
        "csrbt-lab@mcp": {"identity": "holds", "transport": "mcp", "tools": 2, "commands": 10,
                          "totals": {"driven": 5, "refused": 4, "failed": 1}, "at": 40},
        "csrbt-page/x.html": {"identity": "holds", "commands": 7, "totals": {"driven": 7},
                              "unreachable": ["a", "b"]},
        "csrbt-page/y.html": {"identity": "moved", "commands": 3, "totals": {"driven": 3}},
    }},
    "tasks": {"tasks": {
        "t1": {"target": "page", "verdict": "PASS", "held": True, "confirmed": 4, "gives": 2, "holds": 3,
               "claims": 5, "rungs": ["DRAFT"], "at": 10},
        "t2": {"target": "lab", "verdict": "FAIL", "must": "FAIL", "held": True, "confirmed": 1,
               "rungs": ["DRAFT", "DESTRUCTIVE"]},
        "t3": {"target": "page", "verdict": "FAIL", "held": False, "confirmed": 0},
        "t1@trace": {"verdict": "PASS", "held": True, "calls": 9, "required": 3, "confirmed": 2},
        "t1@blind": {"verdict": "PASS", "held": True, "calls": 5, "required": 3, "confirmed": 1},
        "t3@blind": {"verdict": "FAIL", "held": False, "calls": 4, "required": 2},
    }},
    "contention": {"suites": {"s1": {"runs": 3, "failed": 0}, "s2": {"runs": 2, "failed": 1}}},
    "entry": {"pages": {"p": {"fields": 10, "entered": 8}, "q": {"fields": 0, "entered": 0}}},
    "readable": {"pages": {"p": {"written": 6, "unreadable": ["z", "w"]}, "q": {"written": 2}}},
    "delivery": {"paths": {"a": {"by": "adr1"}, "b": {"by": "adr1"}, "c": {"by": "adr2"}, "d": {}}},
    "mutants": {"runners": {
        "mutate_organism": {"mutants": 4, "killed": 3, "survived": 1, "inconclusive": 0, "equivalent": 1, "at": 400},
        "mutate_lab": {"mutants": 2, "killed": 1, "survived": 0, "inconclusive": 1, "equivalent": 0},
    }},
    "ecosystem": {"engines": {
        "E1": {"tests": 10, "failures": 1, "errors": 0, "green": False, "floor": 10},
        "E2": {"tests": 20, "failures": 0, "errors": 2, "green": True, "floor": 19},
        "E3": {},
    }},
    "routes": {"routes": [{"page": "x.html"}, {"page": "y.html"}, {"page": "z.html"}, {"page": "x.html"}]},
}
FS = B.summary(FIX)
WANT = {
    "checks": 17, "of": 18, "holes": 1, "suites": 4, "green": 2,
    "targets": 2, "pages": 2, "commands": 30,
    "tasks": 3, "tasks_held": 2, "traces": 3, "traces_held": 2, "confirmed": 8,
    "given": 2, "held_readings": 3, "held_claims": 5, "supervised": 1, "rung_known": 2,
    "fields": 10, "fields_entered": 8, "entry_pages": 1,
    "written": 8, "unreadable": 2, "blind_pages": 1,
    "delivered": 4, "slices": 2,
    "load_readings": 2, "load_clean": 1, "load_runs": 5, "load_failed": 1,
    "mutants": 6, "killed": 4, "survived": 1, "inconclusive": 1, "equivalent": 1,
    "engine_tests": 30, "engine_failures": 3, "engines": 3, "newest": 400,
}
for _k, _v in sorted(WANT.items()):
    ck(FS.get(_k) == _v, "summary[%s] on the fixture ledgers is %r, not %r" % (_k, FS.get(_k), _v))
ck(sorted(FS["bad_walks"]) == ["csrbt-lab@mcp", "csrbt-page/y.html"],
   "a walk is bad when a command FAILED or its identity did not hold: %s" % sorted(FS["bad_walks"]))
fp = B.render(FIX)
ck(fp == B.render(FIX), "the fixture render is deterministic")
# the verdict: every one of the seven gates is broken here, and each is named
for _g in ("every suite check passes", "every walk of every target holds", "every task is held",
           "every trace is held", "no mutant survived", "no mutant was inconclusive",
           "no engine suite failed"):
    ck(("%s — NOT MET" % _g) in fp, "on the fixture ledgers the gate is NOT MET and says so: %s" % _g)
ck("verdict bad" in fp and "verdict good" not in fp, "...and the banner is red")
# the tiles, each with its numbers
for _big, _what, _note in (
        ("17 / 18", "suite checks passing", "4 suites, 2 green, 1 NOT VERIFIED"),
        ("30", "commands walked", "1 targets × 2 transports, 2 pages"),
        ("2 / 3", "tasks held", "2 / 3 traces held, 8 expectations confirmed"),
        ("2", "values handed over", "every value the 3 tasks enter is in the brief an operator is given -- 3 reading(s) and 5 claim(s)"),
        ("1 / 2", "entered supervised", "no destructive rung"),
        ("8 / 10", "fields entered", "across 1 page(s)"),
        ("6 / 8", "figures readable", "1 page(s) still publish one it cannot"),
        ("4", "files delivered", "across 2 slice(s)"),
        ("1 / 2", "clean under load", "5 run(s), 1 failed"),
        ("4 / 6", "mutants killed", "1 survived, 1 inconclusive, 1 recorded equivalent"),
        ("30", "engine tests", "3 suites, 3 failures")):
    _row = '<div class="big">%s</div><div class="what">%s</div><p>' % (_big, _what)
    _i = fp.find(_row)
    ck(_i >= 0 and _note in fp[_i:_i + 600], "the %s tile reads %s and says %r" % (_what, _big, _note))
# the suites table: a pill is good only when the suite is green AND whole
ck('<td class="mono">verify_contract</td>' in fp and
   'verify_contract</td><td class="role">' in fp and
   fp.find('verify_contract</td>') < fp.find('<span class="pill good">7 / 7</span>'),
   "a green, whole suite gets a good pill")
ck('<span class="pill bad">3 / 4</span></td><td class="num">1</td>' in fp,
   "a suite with a hole gets a bad pill and its holes are counted beside it")
ck('<span class="pill bad">2 / 2</span>' in fp,
   "a suite that is whole and NOT green is still bad: green is the suite's own verdict, not the ratio")
ck('verify_walk</td><td class="role">the robot, every target, both transports, every page</td><td colspan="3"><span class="pill na">no reading</span>' in fp,
   "a harness suite with no entry in counts.json is a 'no reading' row, not a zero")
ck('<td class="num dim">1970-01-01 00:05</td>' in fp and '<td class="num dim">—</td>' not in fp[:fp.find("The robot")],
   "a suite's stamp is its own `at`, in UTC")
# the walks
_lab = fp[fp.find("The robot's walks"):fp.find("Every page")]
ck(_lab.count('<span class="pill good">holds</span>') == 1 and _lab.count('<span class="pill bad">BAD</span>') == 1,
   "of the two lab walks the one with a failed command is BAD and the other holds")
ck('<td class="num">5</td><td class="num">4</td><td class="num">0</td><td class="num">0</td><td class="num">1</td>' in _lab,
   "driven, refused, declined, chaos, failed are the walk's own totals")
# the pages
ck("4 routed pages" not in fp and "3 routed pages · 2 walked" in fp,
   "routed pages are counted by DISTINCT page: a route listed twice is one page")
ck('<div class="page bad"><span class="pname">y.html</span>' in fp and '<div class="page "><span class="pname">x.html</span><span class="pnum">7 driven · 0 refused · 2 unreachable' in fp,
   "a page whose walk failed is red; a page's unreachable count is the length of its list")
# the tasks
_tasks = fp[fp.find("Tasks and traces"):fp.find("The mutant runners")]
ck('<td class="mono">t2</td><td class="mono">lab</td><td><span class="pill good">FAIL · must FAIL</span>' in _tasks,
   "a canary that must FAIL and did is good, and says so")
ck('<td class="mono">t3</td><td class="mono">page</td><td><span class="pill bad">FAIL</span></td><td class="num">0</td><td><span class="pill na">no trace</span></td><td><span class="pill bad">FAIL</span></td><td class="num">4 for 2</td>' in _tasks,
   "a task that failed is bad; its blind trace that failed is bad; the calls column reads the blind trace")
ck('<td class="mono">t1</td><td class="mono">page</td><td><span class="pill good">PASS</span></td><td class="num">4</td><td><span class="pill good">PASS</span></td><td><span class="pill good">PASS</span></td><td class="num">5 for 3</td>' in _tasks,
   "with both a trace and a blind trace, the calls column is the BLIND one's (5 for 3, not 9 for 3)")
ck('<td class="mono">t2</td>' in _tasks and _tasks[_tasks.find('<td class="mono">t2</td>'):].split("</tr>")[0].endswith(
       '<td><span class="pill na">no trace</span></td><td><span class="pill na">—</span></td><td class="num">—</td>'),
   "a task with no trace of either kind says so twice and has no calls")
# the mutant runners
_mut = fp[fp.find("The mutant runners"):fp.find("The engines")]
ck('<td class="mono">mutate_organism</td>' in _mut and '<td class="num">4</td><td class="num"><span class="pill bad">3</span></td><td class="num">1</td><td class="num">0</td><td class="num">1</td><td class="num dim">1970-01-01 00:06</td>' in _mut,
   "a runner with a survivor is bad, and its row is mutants, killed, survived, inconclusive, equivalent, when")
ck('<span class="pill bad">1</span></td><td class="num">0</td><td class="num">1</td><td class="num">0</td><td class="num dim">—</td>' in _mut,
   "a runner with an inconclusive mutant and no survivor is STILL bad, and no `at` is a dash")
ck(_mut.count('<span class="pill na">no reading</span>') == len(B.RUNNERS) - 2,
   "every other runner on the board is a 'no reading' row")
# the engines
_eng = fp[fp.find("The engines"):fp.find("<footer")]
ck(_eng.find("E2") < _eng.find("E1") < _eng.find("E3"),
   "engines are ordered by tests, most first, and an engine with no reading last")
ck('<span class="ename">E2</span><span class="pill good">20 ✓</span><span class="floor">floor 19</span>' in _eng
   and '<span class="ename">E1</span><span class="pill bad">10 ✗</span><span class="floor">floor 10</span>' in _eng
   and '<span class="ename">E3</span><span class="pill na">no reading</span>' in _eng,
   "an engine's pill is its own green; a floor is printed; no tests is 'no reading'")
ck("newest reading 1970-01-01 00:06;" in fp,
   "the newest reading is the newest `at` across every ledger, here a mutant runner's")
# the kinds: a gate tile says so, a reading tile says what it is
_fk = re.findall(r'<p class="kind (gate|reading)">(.*?)</p>', fp)
ck([k for k, _ in _fk] == ["gate", "reading", "gate", "reading", "reading", "reading", "reading", "reading", "reading", "gate", "gate"],
   "the tiles' kinds, in order: %s" % [k for k, _ in _fk])

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
