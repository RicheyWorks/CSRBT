# -*- coding: utf-8 -*-
"""The findings ratchet: what the harness finds now has to fail something.

THE DEFECT THIS EXISTS FOR

tools/harness.py drives 3,699 affordances across 41 pages and has been reporting
real defects for weeks -- twelve controls wired to nothing, four actions that
raise, sixty rows spilling out of a 390px phone. Every suite was green the whole
time. The harness was a detector with no alarm: it printed findings into a run
that nothing depended on, and a finding nobody's build reads is indistinguishable
from a finding nobody made.

That is the same shape as ADR-106's audit reporting clean having examined
nothing, and ADR-108's harness reporting coverage of a page it had never opened.
Third instance, same family: a tool that produces truth into a vacuum.

WHAT THIS DOES

Compares the signatures in tools/harness_ledger.json against the accepted debt
in tools/harness_baseline.json, and fails in BOTH directions:

  NEW      a finding not in the baseline -- a regression, and the build breaks
  FIXED    a baseline entry that no longer occurs -- debt paid and not written
           off, which makes the register longer than the kit's real problem and
           is how a defect list stops being read

Neither direction is optional. A ratchet that only tightens becomes a list of
things nobody believes; one that only loosens is not a ratchet.

WHAT IT DOES NOT DO

It does not judge whether a finding is worth fixing. The baseline carries the
reasons and names the known ones -- the row2 flex-chain repair ADR-103 left, and
the two Workbench textareas that time out under the walk. Accepting a defect is a
deliberate act with a name on it, which is the point.

Run:  python3 tools/verify/verify_findings.py
"""
import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import findings                                                  # noqa: E402

LEDGER = os.path.join(ROOT, "tools", "harness_ledger.json")
BASE = os.path.join(ROOT, "tools", "harness_baseline.json")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


ck("the harness ledger exists", os.path.isfile(LEDGER), LEDGER)
ck("the accepted-findings baseline exists", os.path.isfile(BASE), BASE)
if bad:
    print("-" * 70); print("%d passed, %d failed" % (ok, bad)); sys.exit(1)

led = json.load(io.open(LEDGER, encoding="utf-8"))
base_doc = json.load(io.open(BASE, encoding="utf-8"))
baseline = base_doc["accepted"]
current = findings.signatures(led)

new, fixed = findings.diff(baseline, current)

ck("no NEW finding -- a control that stops working breaks the build", not new, new[:6])
ck("no baseline entry has been fixed without being written off", not fixed, fixed[:6])

# The accounting identity, asserted here too: this suite reads the ledger, and a
# ledger that does not add up is not evidence about anything.
t = led.get("totals", {})
buckets = ("driven", "dead", "sequenced", "hidden", "failed", "excluded")
ck("the ledger accounts for every affordance it discovered",
   sum(t.get(k, 0) for k in buckets) == t.get("discovered"), t)

# A finding that names the TOOL is not a finding about the page. Kept visible and
# kept out of the debt register (ADR-109).
ck("harness sequencing artifacts are counted apart from real dead controls",
   "sequenced" in t, sorted(t))

ck("every page with accepted debt is named with a reason",
   set(base_doc.get("by_page", {})) >= {p.split(" | ")[0] for p in baseline},
   sorted({p.split(" | ")[0] for p in baseline} - set(base_doc.get("by_page", {}))))

# ---- the ratchet is canaried, in both directions -------------------------
# An alarm nobody has watched fire is an alarm nobody knows the shape of. These
# seed faults into copies of the real data rather than trusting that a rule which
# passed today would have failed yesterday.
_led = {"pages": [{"page": "canary.html", "dead": [{"label": "a button"}],
                   "failed": [], "errors": []}]}
_base = {"canary.html | dead | a button": 1}

_new, _fixed = findings.diff(_base, findings.signatures(_led))
ck("canary: an unchanged finding is neither new nor fixed", not _new and not _fixed,
   (_new, _fixed))

_led2 = json.loads(json.dumps(_led))
_led2["pages"][0]["dead"].append({"label": "a second button"})
_new, _fixed = findings.diff(_base, findings.signatures(_led2))
ck("canary: a NEW dead control is reported", any("a second button" in x for x in _new), _new)

_new, _fixed = findings.diff(dict(_base, **{"canary.html | dead | a third": 1}),
                             findings.signatures(_led))
ck("canary: a baseline entry that no longer occurs is reported as fixed",
   any("a third" in x for x in _fixed), _fixed)

# Duplicates must not collapse: eight identical spills are eight facts, and a
# baseline of one would otherwise hide seven regressions behind it.
_led3 = json.loads(json.dumps(_led))
_led3["pages"][0]["dead"].append({"label": "a button"})
_new, _fixed = findings.diff(_base, findings.signatures(_led3))
ck("canary: a SECOND occurrence of an accepted finding is still a regression",
   any("a button" in x for x in _new), _new)

print("-" * 70)
print("accepted debt: %d distinct, %d occurrences across %d page(s)"
      % (len(baseline), sum(baseline.values()), len(base_doc.get("by_page", {}))))
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
