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
  6. the ledger's arithmetic: the total it prints is the sum of its rows.

The ledger is the claim; the XML on disk is the evidence. Where the XML is
newer than the ledger's reading, the reading is stale and this says so
rather than passing on last week's number.

Run:  python3 tools/verify/verify_ecosystem.py
"""
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

# ---- 5. floors only rise, lowering carries a reason -------------------------
ck(all(e.get("floor", 0) >= e.get("tests", 0) for e in eng.values()),
   "every floor is at least the count it was read from")
ck(all(all(l.get("reason", "").strip() for l in e.get("lowered", [])) for e in eng.values()),
   "every lowering of a floor carries a reason")

# ---- 6. arithmetic -----------------------------------------------------------
ck(sum(e.get("tests", 0) for e in eng.values()) ==
   sum(eng[n].get("tests", 0) for n in listed if n in eng),
   "the total is the sum of the rows, and only listed engines count")

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
