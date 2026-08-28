# -*- coding: utf-8 -*-
"""Locks the honest-science slice.

Four claims were changed because they asserted more than the kit could support.
This checks the corrections are actually on the page and say what they should,
and that the finder that surfaced them still finds things.
"""
import io, os, re
from playwright.sync_api import sync_playwright
import os as _os
# The kit is checked out wherever the user keeps it; these suites used to hard-code
# a container path and so could only ever run in the container that wrote them.
ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = _os.path.join(ROOT, "docs") + _os.sep
def _u(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + _os.path.join(ROOT, "docs", name).replace(_os.sep, "/")


DOCS = DOCS_DIR
P = F = 0
def ck(c, m):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", m)

def text(f):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", io.open(DOCS+f, encoding="utf-8").read()))

# ---- 1. the ten-percent rule is labelled, and carries its real range -------
g = text("ecology-glossary.html")
ck("Lindeman 1942" in g, "glossary cites Lindeman 1942 for trophic transfer efficiency")
ck("teaching convention" in g, "glossary calls the 10% figure a teaching convention")
ck("0.1% to 37.5%" in g, "glossary gives Lindeman's own reported range")
ck("roughly 90% of the energy is lost at each" not in g,
   "the bare 'roughly 90% is lost' assertion is gone")
ck("state the assumption" in g, "glossary tells the reader the argument is only as good as the assumption")

# ---- 2. the countable window names its standards ---------------------------
m = text("micro-bench.html")
for s in ("FDA BAM", "25", "250", "ASTM", "20", "200", "8", "80"):
    ck(s in m, "micro-bench names %r among the countable-window standards" % s)
ck("no single countable range" in m, "micro-bench says outright there is no single window")
ck("deliberate one rather than an oversight" in m,
   "micro-bench declares its own simplification instead of hiding it")
ck("30" in m and "300" in m, "micro-bench still states the window it actually uses")

# ---- 3. cover error is sourced and correctly shaped ------------------------
ss = text("stand-sheet.html")
ck("Morrison" in ss and "2016" in ss, "stand-sheet cites Morrison 2016 for observer error")
ck("25" in ss and "50%" in ss, "stand-sheet gives the coefficient-of-variation figure")
ck("proportional error, not a flat number of percentage points" in ss,
   "stand-sheet corrects the shape of the error, not just its size")
ck("disagree between trained observers by 10" not in ss,
   "the unsourced flat 10-20 percentage-point claim is gone")

# ---- 4. rules of thumb say that they are ----------------------------------
sb = text("soil-bench.html")
ck("Rule of thumb, not a measurement" in sb, "soil-bench labels the bucket and barrow volumes")
ck("measure your own once" in sb, "soil-bench tells the reader how to replace the guess")
fc = text("fungal-characters.html")
ck("customary ones in the keys, not measured optima" in fc,
   "fungal-characters labels the spot-test reading times")
ck("record which you used" in fc, "fungal-characters asks for the reading time to be recorded")

# ---- 5. no marker debris from the reverted attempt ------------------------
import glob
# an ATTRIBUTE inside a tag -- not the escaped mention of one in the ADR's prose,
# which is documentation of a reverted attempt rather than debris from it
bad = [os.path.basename(p) for p in glob.glob(DOCS+"*.html")
       if re.search(r'<[^>]*\sdata-claim="', io.open(p, encoding="utf-8").read())]
ck(not bad, "no stray data-claim attributes left behind: %s" % bad)

# ---- 5b. the extraction marker is unique in every tool read this way -----
# This suite, verify_claims_triage and verify_print_slice all read a probe out
# of a tool by splitting the file on one literal sequence. A second occurrence
# -- another constant whose name ends with it, or a comment quoting it -- hands
# the reader the wrong body. Both happened in one slice: a constant named for
# it, then the comment written to warn about the constant. Checked here rather
# than remembered.
MARK = "PROBE" + ' = r"""'
for tool in ("audit_claims.py", "audit_print.py"):
    src = io.open(_os.path.join(ROOT, "tools", tool), encoding="utf-8").read()
    ck(src.count(MARK) == 1,
       "%s carries the extraction marker exactly once (found %d)"
       % (tool, src.count(MARK)))

# ---- 6. the finder still finds ------------------------------------------
CAN = """<!doctype html><html><head><meta charset="utf-8"><title>c</title></head><body>
<p>Incubate the pile at 55 C for 3 days before turning it, then hold above 45 C for a further 10 days.</p>
<p>By convention the reading is taken at 30 s; this one is labelled and should not be reported.</p>
<p>Hold at 55 C for 3 days (40 CFR 503 Appendix B), which names its standard and should not be reported.</p>
</body></html>"""
os.makedirs("/tmp/_ccan", exist_ok=True)
io.open("/tmp/_ccan/c.html", "w", encoding="utf-8").write(CAN)
probe = io.open(_os.path.join(ROOT, "tools", "audit_claims.py"), encoding="utf-8").read()
probe = probe.split('PROBE = r"""')[1].split('"""')[0]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1100, "height": 900})
    pg.set_default_timeout(20000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    pg.goto("file:///tmp/_ccan/c.html", wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    hits = pg.evaluate(probe)
    ck(len(hits) == 1, "canary: exactly one of three claims is reported (got %d)" % len(hits))
    ck(hits and "Incubate the pile" in hits[0], "canary: the unlabelled, uncited one is the one reported")
    ck(not any("By convention" in h for h in hits), "canary: a labelled convention is not reported")
    ck(not any("40 CFR" in h for h in hits), "canary: a named regulation is not reported")
    b.close()

print("---"); print("%d/%d" % (P, P+F))
raise SystemExit(1 if F else 0)
