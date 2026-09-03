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

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
