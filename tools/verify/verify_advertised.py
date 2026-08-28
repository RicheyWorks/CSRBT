# -*- coding: utf-8 -*-
"""Does the kit tell the truth about how much of itself it checks?

Four hub pages advertise a suite's size in prose -- "85/85 verified" on the
Breeding Bench card, "64/64 verified" on Soil Bench, and so on. Nobody was
comparing those numbers to anything. When this suite was written, FIVE OF THE
SIX distinct claims in docs/ were wrong:

    Soil Bench     said 64/64   verify_soil is at 70
    Stand Sheet    said 76/76   verify_ss   is at 84
    Releve         said 66/66   verify_rv   is at 81
    CP Bench       said 78/78   verify_cp   is at 87
    Breeding Bench said 85/85   verify_br   is at 90
    CP Characters  said 116/116 verify_cpc  is at 116   <- the only true one,
                                                           and true by standing
                                                           still, not by upkeep

Every one of them understated the kit, which is the direction that makes the
error invisible: nobody reads a rigour claim and thinks "that seems low". This
is ADR-052 exactly -- a value generated in one place and inlined in another with
nothing binding the two -- and ADR-041's rule against pinning a constant you did
not recompute, applied to prose instead of to a fixture.

WHY THIS DOES NOT RE-RUN THE SUITES

The obvious check runs verify_soil, verify_ss, verify_rv, verify_cp, verify_cpc
and verify_br and compares. That is a minute of browser time, spent inside a run
that has just derived every one of those numbers and thrown them away. So
run_all.py now writes tools/verify/counts.json, and this suite reads it.

That trades one staleness problem for another unless the recorded number knows
what it was recorded FROM. So each entry carries the sha1 of the suite source it
was measured from, and a count whose sha no longer matches the suite on disk is
reported as not applying -- the same rule publish_state applies to a published
page in ADR-078: an observation is only about the thing it was taken against.
Without that clause counts.json would simply be the frozen constant moved one
level down, which is the failure this suite exists to catch.

WHAT IT REFUSES TO GUESS

Which suite owns a page is DECLARED, in the suite, as PAGE_SUITE_FOR. Deriving
it from "which suites mention this page" was tried and returns seven suites for
one bench page, because every cross-cutting suite mentions it. That is a fact
about mentions, not about ownership -- the same mistake the mutate role markers
were introduced to stop making.

A claim that is not inside a tool card is not checked, and is REPORTED rather
than dropped (ADR-061). Two live in the ADR-031 page, in a dated build log: "five
tabs, first consumer of FEK v1. 64/64 verified" is a record of what was true
that day, not an assertion about today, and correcting it would be falsifying
a history. The distinction is structural -- a live claim sits in an <a
class="card"> pointing at the tool -- so it needs no list of exceptions, but the
count is printed either way so a claim that drifts out of a card cannot go quiet.

Run:  python3 tools/verify/verify_advertised.py
"""
import glob, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DOCS = os.path.join(ROOT, "docs")
COUNTS = os.path.join(HERE, "counts.json")

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))

CLAIM = re.compile(r"(\d+)\s*/\s*(\d+)\s+verified")
CARD = re.compile(r'<a\b[^>]*class="[^"]*\bcard\b[^"]*"[^>]*href="([^"]+)"', re.I)


def owner_map():
    """page -> suite, from each suite's own PAGE_SUITE_FOR declaration."""
    own = {}
    for s in sorted(glob.glob(os.path.join(HERE, "verify_*.py"))):
        txt = io.open(s, encoding="utf-8").read()
        m = re.search(r'^PAGE_SUITE_FOR\s*=\s*"([^"]+)"', txt, re.M)
        if m:
            own.setdefault(m.group(1), []).append(os.path.basename(s)[:-3])
    return own


def claims(html):
    """(page_it_links_to, claimed, whole_claim) for claims inside a tool card,
    and a separate list of the ones that are not in a card at all.

    The card is found by walking BACK from the claim to the nearest opening
    card tag and checking the claim falls before that card closes. Anchoring
    forward from the card instead would attach a claim in the next paragraph
    to the previous card, which is how a hub page with one card and a trailing
    footnote would silently mis-resolve."""
    live, loose = [], []
    cards = [(m.start(), m.group(1), html.find("</a>", m.end())) for m in CARD.finditer(html)]
    for c in CLAIM.finditer(html):
        here = c.start()
        owner = None
        for start, href, end in cards:
            if start < here and (end == -1 or here < end):
                owner = href
        if owner:
            live.append((owner, int(c.group(1)), int(c.group(2)), c.group(0)))
        else:
            loose.append(c.group(0))
    return live, loose


OWN = owner_map()
ck("at least one suite declares PAGE_SUITE_FOR", bool(OWN), "no declarations found")
for page, suites in sorted(OWN.items()):
    ck("exactly one suite claims to own %s" % page, len(suites) == 1, suites)
    ck("%s exists in docs/" % page, os.path.exists(os.path.join(DOCS, page)))

# ---- the recorded counts, and whether they still apply ---------------------
have_counts = os.path.exists(COUNTS)
ck("counts.json exists -- run_all writes it", have_counts,
   "run `python3 tools/verify/run_all.py` once to produce it")
REC = {}
if have_counts:
    REC = json.load(io.open(COUNTS, encoding="utf-8")).get("suites", {})


def recorded(suite, rec=None):
    """(n, why_not) -- n is None when the record cannot speak for this suite.

    `rec` is injectable so the three ways a record can fail to speak are
    canaried below without editing a suite file on disk to provoke them."""
    e = (REC if rec is None else rec).get(suite)
    if not e:
        return None, "no recorded count for %s" % suite
    import hashlib
    src = os.path.join(HERE, suite + ".py")
    if not os.path.exists(src):
        return None, "%s.py does not exist" % suite
    sha = hashlib.sha1(io.open(src, "rb").read()).hexdigest()[:12]
    if e.get("sha") != sha:
        return None, ("the recorded count was taken from a different version of %s "
                      "(%s, now %s) -- rerun run_all" % (suite, e.get("sha"), sha))
    if not e.get("green"):
        return None, "%s was not green when the count was recorded" % suite
    return e.get("n"), ""


# ---- canaries, before the real tree ---------------------------------------
# A page shaped like a hub, so the anchoring is tested on the structure rather
# than on a string that happens to contain the words.
# The fixture page name is deliberately not a real page in docs/. This file
# would otherwise MENTION half the kit, and mutate.py reads mentions as
# coverage -- a suite that checks prose about a page would then be swept
# against that page's logic mutants, which it cannot possibly kill.
_CARD = ('<div class="kit"><a class="card" href="fixture-bench.html">'
         '<h3>Fixture Bench</h3><p>Words. 70/70 verified.</p></a></div>')
_live, _loose = claims(_CARD)
ck("a claim inside a tool card resolves to the page the card links to",
   _live == [("fixture-bench.html", 70, 70, "70/70 verified")], (_live, _loose))
_NARR = '<p><code>fixture-bench.html</code>, five tabs. 64/64 verified.</p>'
_live2, _loose2 = claims(_NARR)
ck("a claim in narrative prose is NOT resolved to a card",
   _live2 == [] and _loose2 == ["64/64 verified"], (_live2, _loose2))
ck("a claim after a card has closed does not attach to that card",
   claims(_CARD + '<p>Elsewhere entirely. 1/1 verified.</p>')[1] == ["1/1 verified"],
   claims(_CARD + '<p>Elsewhere entirely. 1/1 verified.</p>'))
_STALE = _CARD.replace("70/70", "64/64")
_l3, _ = claims(_STALE)
ck("a page understating its suite is read as the number it PRINTS, so the "
   "comparison can fail", _l3[0][1] == 64 and _l3[0][2] == 64, _l3)

# ---- and the record layer: the three ways a stored count stops applying ----
# Without these the sha clause is decoration. A count that keeps answering after
# its suite has changed is precisely counts.json becoming the next frozen
# constant, which is the whole failure this suite was written to end.
import hashlib as _hl
_any = sorted(REC) [0] if REC else None
if _any:
    _sha = _hl.sha1(io.open(os.path.join(HERE, _any + ".py"), "rb").read()).hexdigest()[:12]
    ck("a record whose sha matches the suite on disk speaks (canary control)",
       recorded(_any, {_any: {"n": 7, "sha": _sha, "green": True}})[0] == 7)
    ck("a record taken from a DIFFERENT version of the suite does not speak",
       recorded(_any, {_any: {"n": 7, "sha": "0" * 12, "green": True}})[0] is None,
       "a stale count answered as though it were current")
    ck("a record from a run where the suite was not green does not speak",
       recorded(_any, {_any: {"n": 7, "sha": _sha, "green": False}})[0] is None)
    ck("a suite with no record at all does not speak",
       recorded(_any, {})[0] is None)
else:
    ck("counts.json holds at least one suite to canary the record layer against",
       False, "counts.json is empty")

# ---- the real tree ---------------------------------------------------------
loose_total, checked = [], 0
for path in sorted(glob.glob(os.path.join(DOCS, "*.html"))):
    name = os.path.basename(path)
    html = io.open(path, encoding="utf-8").read()
    live, loose = claims(html)
    for c in loose:
        loose_total.append((name, c))
    for href, got, tot, whole in live:
        page = href.split("/")[-1].split("#")[0]
        suites = OWN.get(page, [])
        if not suites:
            ck("%s advertises %r for %s, and some suite declares it owns that page"
               % (name, whole, page), False,
               "no suite declares PAGE_SUITE_FOR = %r" % page)
            continue
        suite = suites[0]
        n, why = recorded(suite)
        if n is None:
            ck("%s: the recorded count for %s applies" % (name, suite), False, why)
            continue
        checked += 1
        ck("%s advertises %s for %s, and %s counts %d"
           % (name, whole, page, suite, n), got == n and tot == n,
           "page says %d/%d, suite counts %d" % (got, tot, n))

ck("every advertised count was resolvable to a suite", checked > 0,
   "nothing was checked -- the anchor found no live claims at all")

# Not a failure: a number in a dated build log is a record, not an assertion.
# Printed so that a claim which drifts out of a card becomes visible rather than
# becoming exempt (ADR-061).
print("")
print("%d claim(s) outside a tool card -- narrative, not checked:" % len(loose_total))
for name, c in loose_total:
    print("    %-24s %s" % (name, c))
print("%d advertised count(s) checked against a recorded suite count." % checked)
print("")

print("\n".join("PASS  " + x for x in P))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
