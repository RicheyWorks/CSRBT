# -*- coding: utf-8 -*-
"""The print channel: which pages put text on paper that no screen shows.

ADR-091 defined "on screen" as innerText + SVG <text> + every chart tooltip,
and named the one channel outside that definition: a print stylesheet. It is
not a small channel. Seventeen of thirty-nine pages build a report under
`@media print` -- the field sheets emit a whole tab-separated record -- and
until ADR-092 no suite had rendered a single line of it.

WHAT IS LOCKED HERE

  the inventory   which pages have a print-only report is DECLARED, and checked
                  both ways. A page that stops emitting one has lost something a
                  reader takes to the field; a page that starts emitting one has
                  gained a surface nothing checks. Either way the list is wrong
                  and this says so.
  the method      a page declared to have none must show none. If the media
                  switch stopped working every page would show none and the
                  first check would fail; if the observation were unstable every
                  page would show some, and this one would.

Run:  python3 tools/verify/verify_print_channel.py      (needs playwright)
"""

# Declared for tools/mutate.py: this suite renders real pages and asserts about
# the channel they print. Its page names are its subjects.
MUTATE_ROLE = "subject"
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import _kit
import audit_print_channel as A
from playwright.sync_api import sync_playwright

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


# Measured, then declared. Seventeen pages; the list is the finding of ADR-092.
PRINTS = [
    "breeding-bench.html", "cell-bench.html", "collection-sheet.html", "cp-bench.html",
    "deployment-log.html", "ethogram.html", "farm-scout.html", "field-notebook.html",
    "greenhouse.html", "micro-bench.html", "ordination.html", "pheno-tracker.html",
    "releve.html", "selection-log.html", "soil-bench.html", "stand-sheet.html",
    "survey-design.html",
]
# A sample of the twenty-two that do not, as the control. Not the whole set:
# this suite is checking that the method distinguishes, not re-running the sweep.
NO_PRINT = ["adr-031.html", "cp-characters.html", "ecology-glossary.html",
            "ecology-lab.html"]

with sync_playwright() as pw:
    res = A.sweep(pw, PRINTS + NO_PRINT)

missing = [p for p in PRINTS if res[p][0] == 0]
ck("every page declared to print a report still prints one", not missing, missing)
appeared = [p for p in NO_PRINT if res[p][0] > 0]
ck("CONTROL: a page declared to print nothing extra prints nothing extra",
   not appeared, [(p, res[p]) for p in appeared])
ck("...and the control is not vacuous -- the declared printers really do differ "
   "from it", sum(res[p][0] for p in PRINTS) > 0,
   sum(res[p][0] for p in PRINTS))
ck("the printed reports carry FIGURES, not just headings -- which is why this "
   "channel matters at all",
   sum(res[p][1] for p in PRINTS) > 0, sum(res[p][1] for p in PRINTS))

# The flagship page is in the control list on purpose: every rounding-tie
# verdict in verify_tie_render is taken from its screen view, and that verdict
# is only complete if the page adds nothing on paper. Measured, not assumed.
ck("ecology-lab adds nothing in print, so the tie verdicts taken from its "
   "screen view are not missing a channel", res["ecology-lab.html"][0] == 0,
   res["ecology-lab.html"])

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
