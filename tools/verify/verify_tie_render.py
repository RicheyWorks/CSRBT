# -*- coding: utf-8 -*-
"""Is any recorded figure still rounded AT a tie where a reader can see it?

ADR-088 swept the fixtures for figures sitting exactly on a rounding boundary
and refused to say which were displayed, because binding a value to a call site
by key name is a fact about names (ADR-077). tools/tie_render.py answers it by
experiment instead -- move the value, look at the page -- and this locks the
answer, with the canary that says the experiment can still fail.

Three things are checked, and the third is the one that matters most:

  the STATE     no tie in the flagship fixture is rounded at the tie today.
  the REACH     some tie still reaches the rendered text, so a clean board is
                not an empty one.
  the METHOD    a seeded 0 dp rendering IS caught, and it is caught by the
                DOWNWARD nudge. Under half-away-from-zero, .5 and .5+e give the
                same digit, so an upward-only version can never fail on any
                input -- which is exactly what the first draft did, reporting a
                clean board while unable to report anything else. That is
                ADR-084's wall for the third time, and this check is the shape
                of thing that catches it.

Run:  python3 tools/verify/verify_tie_render.py      (needs playwright)
"""

# Declared for tools/mutate.py: this suite renders the real page and asserts
# about the tool that renders it. The one page name it carries is that page's.
MUTATE_ROLE = "subject"
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import tie_render as R
from playwright.sync_api import sync_playwright

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


CLEAN = io.open(R.PAGE, encoding="utf-8").read()
# The fault: put one figure back on a zero-decimal rendering. This is the exact
# edit ADR-089 undid, so the canary is the defect itself rather than a
# stand-in that might not behave like it.
SEEDED = CLEAN.replace("${tile(fmt(p.chao1, 1), \"Chao1 est. richness\")}",
                       "${tile(fmt(p.chao1, 0), \"Chao1 est. richness\")}")

with sync_playwright() as pw:
    ck("the seeded page really differs from the clean one -- otherwise every "
       "check below is about one page twice", SEEDED != CLEAN)

    rows = R.scan(pw)
    live = [r for r in rows if r[5]]
    reach = [r for r in rows if r[4]]
    ck("no figure is rounded at a tie where the page shows it",
       not live, [(r[0], r[1], r[3]) for r in live])
    ck("...and the pass is not vacuous: ties still reach what a reader can see",
       len(reach) >= 1, len(reach))
    # The observation is three sources deep now, and the third is the fragile
    # one: `structural` reaches a reader ONLY through a chart tooltip. If the
    # tooltip harvest ever stops working, every check above still passes and
    # this one does not -- which is the whole point of naming it.
    ck("the tooltip harvest is live -- a figure that appears only in a tooltip "
       "is still seen", any(r[0] == "structural" and r[4] for r in rows),
       [(r[0], r[4]) for r in rows])
    ck("the fixture still holds ties to look for at all",
       len(R.ties_in()) >= 4, len(R.ties_in()))

    seeded = R.scan(pw, SEEDED)
    hot = [(r[0], r[3]) for r in seeded if r[5]]
    ck("CANARY: with a zero-decimal rendering seeded back in, it is caught",
       ("chao1", 0) in hot, hot)

    # The method check. Same seeded fault, upward nudge only.
    up_only = [(r[0], r[3]) for r in R.scan(pw, SEEDED, directions=(1,)) if r[5]]
    ck("an upward-only nudge cannot catch it -- a tie and a tie plus a hair "
       "round the same way", ("chao1", 0) not in up_only, up_only)
    ck("...so the downward nudge is doing the work, not decoration",
       ("chao1", 0) in hot and ("chao1", 0) not in up_only, (hot, up_only))

    # ---- the drop path: the same page, fed the session a reader is TOLD to
    # drop onto it. The inline session was clean; this one was not, and nothing
    # before ADR-090 had ever rendered it.
    KEYS = ["evenness", "p", "q"]
    okd, why, rows2 = R.scan_loaded(pw, "ecology-experiment-session.json",
                                    R.PAGE, "drop", only=KEYS)
    ck("the lab page accepts the experiment session when it is dropped on it",
       okd, why)
    ck("...and there are figures there to check", len(rows2) >= 3, len(rows2))
    ck("none of the dropped session's figures is rounded at a tie",
       not [r for r in rows2 if r[5]], sorted(set((r[0], r[1]) for r in rows2 if r[5])))

    # CANARY: put one of the three precisions back and it must be caught again.
    SEED2 = CLEAN.replace('${tile(fmt(st.p, 4), "allele freq p")}',
                          '${tile(fmt(st.p, 3), "allele freq p")}')
    ck("the drop-path canary really changes the page", SEED2 != CLEAN)
    _, _, rows3 = R.scan_loaded(pw, "ecology-experiment-session.json",
                                R.PAGE, "drop", only=["p"], page_src=SEED2)
    ck("CANARY: the three-decimal allele frequency is caught on the drop path",
       any(r[5] for r in rows3), [(r[0], r[1], r[5]) for r in rows3])

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
