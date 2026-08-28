# -*- coding: utf-8 -*-
"""What does a page put on paper that no screen can show?

ADR-091 named a print stylesheet as the channel outside its definition of "on
screen". ADR-092 measured it and got the measurement wrong; ADR-093 corrected
it. Both numbers are worth carrying, because the gap between them IS the check:

    print vs the DEFAULT tab   1682 lines across 17 pages
    print vs EVERY tab           11 lines across  1 page

These pages print with `.pane { display:block !important }`, so printing opens
every tab at once. Text in another tab is not a channel a reader cannot reach;
it is a click away, and the page suites already check it. Only the difference
that survives clicking every tab is a print-only channel.

WHAT IS LOCKED HERE

  the inventory   exactly one page prints something no screen shows, and it does
                  so deliberately: stand-sheet forces #htCard open, with a CSS
                  comment saying why -- the two-angle height method is what you
                  need standing under the tree with no signal.
  the method      the tab-visiting must be load-bearing. If it ever stops
                  working the comparison silently balloons back to measuring
                  tabs, which is the mistake ADR-092 shipped. Checked by doing
                  it both ways and requiring them to differ.

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


PRINTS_EXTRA = "stand-sheet.html"          # the only one, and on purpose
CONTROLS = ["releve.html", "greenhouse.html", "cp-bench.html", "ecology-lab.html"]

with sync_playwright() as pw:
    b = pw.chromium.launch()

    def observe(name):
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        _kit.offline(pg)
        pg.goto(_kit.url(name), wait_until="load")
        pg.wait_for_timeout(1000)
        first = A.lines(pg)                      # the tab that opens
        every = A.screen_everywhere(pg)          # every tab
        pg.emulate_media(media="print")
        pg.wait_for_timeout(350)
        printed = A.lines(pg)
        pg.close()
        return first, every, printed

    first, every, printed = observe(PRINTS_EXTRA)
    ck("the page that prints an extra card still prints it",
       len(printed - every) > 0, len(printed - every))
    ck("...and it is a small, deliberate card, not a hidden report",
       len(printed - every) < 40, len(printed - every))
    # The method check: clicking the tabs has to be doing real work, or this
    # suite is measuring tabs again without saying so.
    ck("visiting every tab is load-bearing -- it removes most of the difference",
       len(printed - first) > 5 * len(printed - every),
       (len(printed - first), len(printed - every)))
    ck("...and the tabs really are reachable on screen",
       len(every) > len(first), (len(first), len(every)))

    for name in CONTROLS:
        f, e, p = observe(name)
        ck("CONTROL: %s prints nothing a reader cannot already reach" % name,
           not (p - e), sorted(p - e)[:3])
        if name != "ecology-lab.html":
            ck("...and it WOULD have looked like a channel against one tab only",
               len(p - f) > 20, len(p - f))

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
