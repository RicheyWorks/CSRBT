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
  5. the renderer is deterministic: two renders are identical.

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

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
