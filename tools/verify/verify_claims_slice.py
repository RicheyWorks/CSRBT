# -*- coding: utf-8 -*-
"""Locks the honest-science slice.

Four claims were changed because they asserted more than the kit could support.
This checks the corrections are actually on the page and say what they should,
and that the finder that surfaced them still finds things.
"""
import io, os, re
import _kit
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

# Two readers, each saying which view it means (ADR-099). text() is what the
# page SHOWS -- script and style dropped by a real parser, not by a bracket
# regex that a page's own JavaScript defeats. src() is what the file SAYS, for
# the claims this kit renders out of a widget's `help:` option, which text()
# cannot see and must not pretend to.
text = _kit.prose
src_of = _kit.raw

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
# These two are a widget's `help:` text, which the page renders out of script.
# They are read from the source, because that is where they live (ADR-099).
sb = src_of("soil-bench.html")
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
# ADR-096 retires the split. The uniqueness check above it was the right thing
# to do while the coupling stood -- it made the failure loud instead of
# memorable -- but it protected a mechanism that should not exist, and ADR-094
# said so in the same paragraph that added it. `_kit.tool()` imports the module
# and reads the probe by name. What is checked now is that nobody goes back.
import glob as _glob, re as _re
_here = _os.path.dirname(_os.path.abspath(__file__))
_splitters = []
for _f in sorted(_glob.glob(_os.path.join(_here, "verify_*.py"))):
    _body = io.open(_f, encoding="utf-8").read()
    if _re.search(r"""\.split\(\s*['"][A-Z_]*PROBE""", _body):
        _splitters.append(_os.path.basename(_f))
ck(not _splitters,
   "no suite reads a tool's probe by splitting its source: %s" % _splitters)
_ac = _os.path.join(ROOT, "tools", "audit_claims.py")
_acs = io.open(_ac, encoding="utf-8").read()
ck(_acs.count("_VOCAB = r") == 1 and _acs.count("__VOCAB__") == 4,
   "audit_claims keeps ONE provenance vocabulary, substituted into both probes")
import _kit as _k0
_p0 = _k0.tool("audit_claims").PROBE
ck("FDA" in _p0 and "APHA" in _p0,
   "the block-level probe now knows the standards the section-level one knew")

# ---- 5b. a page is read through a named reader, never a bracket regex ----
#
# ADR-099. `re.sub(r"<...>", " ", page)` is not a tag stripper on a page in this
# kit: a page's JavaScript carries bare < and >, the regex pairs them off, and
# whole spans -- prose included -- disappear. It cost ADR-098 two assertions
# that failed for a reason unrelated to the page they named, and ADR-099
# measured eleven live assertions whose verdict rested on where a stray bracket
# happened to fall. _kit.prose / _kit.prose_of / _kit.raw each say which view
# they mean.
#
# The forbidden pattern is ASSEMBLED rather than written, because a rule that
# spells the thing it forbids trips on itself -- ADR-077, and the reason the
# probe-marker rule next door is phrased the way it is. COMMENTS are exempt and
# that is deliberate: a suite may explain the pattern, it may not use one.
# tools/publish_drift.py is out of scope and stays as it is -- it removes
# <script> and <style> BEFORE it strips, so its stripper only ever meets markup.
import tokenize as _tok
_BAD = "<[" + "^" + ">]+>"
_forms = tuple('re.%s(r"%s"' % (_fn, _BAD) for _fn in ("sub", "compile"))

def _code_only(path):
    """The file with its comment tokens blanked, so the rule reads code."""
    out = io.open(path, encoding="utf-8").read()
    try:
        with io.open(path, "rb") as fh:
            for t in _tok.tokenize(fh.readline):
                if t.type == _tok.COMMENT:
                    out = out.replace(t.string, " " * len(t.string))
    except Exception:
        return out
    return out

def _strippers(paths):
    return sorted(_os.path.basename(f) for f in paths
                  if any(form in _code_only(f) for form in _forms))

_suites = sorted(_glob.glob(_os.path.join(_here, "verify_*.py")))
ck(not _strippers(_suites),
   "no suite reads a page through a bracket-regex tag stripper: %s"
   % _strippers(_suites))

# and the rule can fail -- seeded both ways, because a lint nobody has watched
# fire is a lint nobody knows the shape of (ADR-069).
_cdir = "/tmp/_rdrcan"
os.makedirs(_cdir, exist_ok=True)
io.open(_os.path.join(_cdir, "verify_offender.py"), "w", encoding="utf-8").write(
    "import re" + chr(10) +
    'text = re.sub(r"' + _BAD + '", " ", open("p.html").read())' + chr(10))
io.open(_os.path.join(_cdir, "verify_talker.py"), "w", encoding="utf-8").write(
    '# a suite may explain re.sub(r"' + _BAD + '", " ", src) without using one' + chr(10) +
    "import _kit" + chr(10) + 'text = _kit.prose("p.html")' + chr(10))
_seeded = sorted(_glob.glob(_os.path.join(_cdir, "verify_*.py")))
ck(_strippers(_seeded) == ["verify_offender.py"],
   "canary: the rule catches a suite that uses one, and exempts a comment "
   "that only describes one: %s" % _strippers(_seeded))

# the two readers say different things about the same page, and the difference
# is exactly the case ADR-098 hit: a claim the page renders out of a script.
_cs_prose, _cs_raw = _k0.prose("collection-sheet.html"), _k0.raw("collection-sheet.html")
ck("The note under this log" in _cs_raw,
   "raw() sees a claim the page renders from a widget's help option")
ck("The note under this log" not in _cs_prose,
   "and prose() does not pretend to -- script is dropped, not mangled")
ck("conventional working compromise" in _cs_prose,
   "while prose() does see the page's own prose")

# ---- 6. the finder still finds ------------------------------------------
CAN = """<!doctype html><html><head><meta charset="utf-8"><title>c</title></head><body>
<p>Incubate the pile at 55 C for 3 days before turning it, then hold above 45 C for a further 10 days.</p>
<p>By convention the reading is taken at 30 s; this one is labelled and should not be reported.</p>
<p>Hold at 55 C for 3 days (40 CFR 503 Appendix B), which names its standard and should not be reported.</p>
</body></html>"""
os.makedirs("/tmp/_ccan", exist_ok=True)
io.open("/tmp/_ccan/c.html", "w", encoding="utf-8").write(CAN)
import _kit
probe = _kit.tool("audit_claims").PROBE
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

# ---- 7. the escape has a floor, and it is not a widened regex ------------
# `.cite`/`.src`/`.ref` used to exempt a block by EXISTING: an empty span
# silenced every number under it. And a named ORGANISATION in prose -- the
# commonest citation form in half these domains -- is still not provenance to
# the finder, deliberately: an organisation-name regex would match any two
# capitalised words (ADR-061). The page declares it with `.src` or it stays on
# the list, which is the route ADR-096 took for four claims.
CAN2 = """<!doctype html><html><head><meta charset="utf-8"><title>c</title></head><body>
<section><p id="a">Hold pile A above 55 C for at least 12 days. <span class="src"></span></p></section>
<section><p id="b">Hold pile B above 55 C for at least 12 days. <span class="src">California Carnivores</span></p></section>
<section><p id="c">California Carnivores state that water should stay below 160 ppm.</p></section>
</body></html>"""
io.open("/tmp/_ccan/c2.html", "w", encoding="utf-8").write(CAN2)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1100, "height": 900})
    pg.set_default_timeout(20000)
    _kit.offline(pg)
    pg.goto("file:///tmp/_ccan/c2.html", wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    h2 = pg.evaluate(probe)
    ck(len(h2) == 2, "canary: two of three are reported (got %d)" % len(h2))
    ck(any("pile A" in h for h in h2),
       "canary: an EMPTY .src no longer exempts the block it sits in")
    ck(not any("pile B" in h for h in h2),
       "canary: a .src that names something still exempts")
    ck(any(h.startswith("California Carnivores state") for h in h2),
       "canary: a named organisation in bare prose is still reported")
    b.close()

# ---- 9. the corrections of ADR-096 are on the pages ----------------------
eco = text("ecology.html")
ck('<span class="src">California Carnivores</span>' in
   io.open(DOCS + "ecology.html", encoding="utf-8").read(),
   "the hub's water card DECLARES its source, not merely writes it")

dep = io.open(DOCS + "deployment-log.html", encoding="utf-8").read()
ck('<span class="src">All three are from their two support' in dep,
   "the AudioMoth clock figures declare where the three came from")
ck("% duty)" in dep,
   "the duty legend prints its own arithmetic instead of taking an exemption")
ck(".echo" not in io.open(_os.path.join(ROOT, "tools", "audit_claims.py"), encoding="utf-8")
        .read().split("NOT an exemption")[0],
   "the withdrawn .echo exemption is not still live above the note that withdraws it")

bb = text("breeding-bench.html")
ck("rule of thumb" in bb, "the 20/100 floor is labelled a rule of thumb")
ck("Seed Savers Exchange" in bb, "and the chart that disagrees with it is named")
ck("10&ndash;20" in io.open(DOCS + "breeding-bench.html", encoding="utf-8").read()
   or "10\u2013" in bb, "with the numbers it gives, not just its name")
ck("deliberate simplification rather than\n        an oversight" in
   io.open(DOCS + "breeding-bench.html", encoding="utf-8").read().replace("\r", "")
   or "deliberate simplification" in bb,
   "and the single floor is declared a simplification, not left to look like an oversight")

cpc2, cpc2_src = text("cp-characters.html"), src_of("cp-characters.html")
ck("Taylor, 1989" in cpc2_src, "the Utricularia bladder range is cited")
# The absence is asserted against the SOURCE, not the rendered text: a string
# that is gone from the prose but still sitting in a script is not gone.
ck("0.2 to 5 mm" not in cpc2_src,
   "and the spliced range -- the genus minimum against the usual maximum -- is gone")

mb = src_of("micro-bench.html")
ck("The conventional volumes are" in mb, "the plating volumes are labelled a convention")
ck("fixed at 0.1 mL in" in mb and "FDA BAM" in mb,
   "and the spread volume names the standard that fixes it -- ADR-094 offered this "
   "claim as one no standard in the card covers, and FDA BAM Ch.23 states it outright")

fc2 = text("fungal-characters.html")
ck("Read at the conventional 30 s" in fc2,
   "the KOH reading times carry their label in the cell that states them")
ck("a practitioners" in fc2 and "not a measured threshold" in fc2,
   "and the 35 C drying floor says it is a rule of thumb")

# ---- 10. the selection intensities are checked where arithmetic is checked
# NOT recomputed here. verify_claims_math already recomputes both from the
# method (ADR-041), and ADR-096 strengthened it: the page now prints the
# substituted argument, so that suite checks x = Phi^-1(1-p) as well as i.
# Two suites recomputing one number is how the two disagree later.
ck("&phi;(1.2816) / 0.10" in io.open(DOCS + "breeding-bench.html", encoding="utf-8").read(),
   "the page shows the substitution, not just the answer")

print("---"); print("%d/%d" % (P, P+F))
raise SystemExit(1 if F else 0)
