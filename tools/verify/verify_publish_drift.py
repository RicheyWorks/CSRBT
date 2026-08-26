# -*- coding: utf-8 -*-
"""Fixtures for tools/publish_drift.py -- the tool that ranks stale pages.

WHY THIS SUITE IS LARGER THAN THE TOOL DESERVES

publish_drift decides which published pages get republished, and republishing
costs roughly four Read calls per page against the publish gate. A tool that
over-reports wastes that on pages nobody reads wrongly; a tool that
under-reports leaves a wrong number in front of a reader and reports the page
as clean. It fails expensively in both directions, so both directions get
fixtures.

Its first version was wrong in the expensive direction: it line-diffed and
called any line whose digits changed "numeric", and returned drift on 24 of 24
pages -- hex colours, artifact UIDs in new links, font weights in a Google
Fonts URL, and difflib zipping an INSERTED line against "" and reading it as a
number appearing. Every one of those is a fixture below, because a classifier
that cannot tell a contrast fix from a changed claim is not a weaker classifier,
it is measuring something else.

Run:  python3 tools/verify/verify_publish_drift.py
"""
import importlib.util, io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
_s = importlib.util.spec_from_file_location("_pd", os.path.join(ROOT, "tools", "publish_drift.py"))
PD = importlib.util.module_from_spec(_s); _s.loader.exec_module(PD)

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

def S(old, new):   return PD.numeric_sentence_drift(old, new)
def C(old, new):   return PD.code_num_drift(old, new)

PAGE = ('<style>:root{--ink:#23281F;font-weight:400}</style>'
        '<p>Straw is around 60 kg/m3 and manure around 600.</p>'
        '<a href="https://claude.ai/code/artifact/7ce205cb-286c-4d44-b054-2e7d39cfeaa4">Soil</a>'
        '<script>var pass=0; for(var i=0;i<n+1;i++){ mid=37.5; }</script>')

# ---- 1. the four false positives that sank the first version -------------
ck("a hex colour change is not a claim",
   not S(PAGE, PAGE.replace("#23281F", "#6B6B5E")),
   S(PAGE, PAGE.replace("#23281F", "#6B6B5E")))
ck("a font weight in a stylesheet is not a claim",
   not S(PAGE, PAGE.replace("font-weight:400", "font-weight:700")),
   S(PAGE, PAGE.replace("font-weight:400", "font-weight:700")))
ck("an artifact UID inside a new rail link is not a claim",
   not S(PAGE, PAGE + '<a href="https://claude.ai/code/artifact/'
                      '83012ca5-e604-4057-8b0d-07d347eb2d8e">Food Web</a>'),
   S(PAGE, PAGE + '<a href="https://claude.ai/code/artifact/83012ca5-e6">x</a>'))
INSERTED = PAGE.replace("<p>Straw", "<p>A new paragraph with no digits.</p><p>Straw")
ck("an inserted line is not a number changing from nothing to something",
   not S(PAGE, INSERTED), S(PAGE, INSERTED))

# ---- 1b. what a digit has to be attached to before it is a QUANTITY ------
# A mutation sweep replaced DIGIT's lookbehind with a bare \d and every fixture
# above still passed -- they all hid their hex inside <style>, which is stripped
# before DIGIT is ever reached. These three exercise it directly. Without the
# lookbehind a version bump or a new ADR reference ranks a page as misstating a
# figure, and the ranking is what this tool exists to produce.
ck("an ADR reference is not a quantity",
   not S("<p>See ADR-031 for the rule.</p>", "<p>See ADR-031 for the reasoning.</p>"),
   S("<p>See ADR-031 for the rule.</p>", "<p>See ADR-031 for the reasoning.</p>"))
ck("a version string is not a quantity",
   not S("<p>Field Entry Kit v1.1.0 ships here.</p>",
         "<p>Field Entry Kit v1.3.0 ships here.</p>"),
   S("<p>Field Entry Kit v1.1.0 ships here.</p>", "<p>Field Entry Kit v1.3.0 ships here.</p>"))
ck("a hex colour written in PROSE is not a quantity either",
   not S("<p>The ink is #23281F throughout.</p>", "<p>The ink is #6B6B5E throughout.</p>"),
   S("<p>The ink is #23281F throughout.</p>", "<p>The ink is #6B6B5E throughout.</p>"))
ck("but a bare figure in the same shape of sentence IS one",
   len(S("<p>The target is 50 ppm throughout.</p>",
         "<p>The target is 160 ppm throughout.</p>")) == 1,
   S("<p>The target is 50 ppm throughout.</p>", "<p>The target is 160 ppm throughout.</p>"))

# CODE_NUM carries the same guarantee for scripts, by the same lookbehind and
# with no explicit hex filter behind it. Asserted here rather than trusted.
ck("CODE_NUM finds no number at all in a hex colour",
   not PD.CODE_NUM.findall('var c="#334455";'), PD.CODE_NUM.findall('var c="#334455";'))
ck("and does find one in a bare literal",
   PD.CODE_NUM.findall("var x=99;") == ["99"], PD.CODE_NUM.findall("var x=99;"))

# ---- 2. and it still sees the thing it exists to see ---------------------
# The real soil-bench defect: the ratio 600/60 is ten-fold, and the published
# copy says eight-fold.
WRONG = '<p>Density varies eight-fold: straw 60 kg/m3, manure 600.</p>'
RIGHT = '<p>Density varies ten-fold: straw 60 kg/m3, manure 600, which is 600 / 60 = 10.</p>'
d = S(WRONG, RIGHT)
ck("a changed figure in prose IS reported", len(d) >= 1, d)
ck("and it is reported as one paired change, not a deletion plus an addition",
   len(d) == 1 and d[0][0] is not None and d[0][1] is not None, d)

# ---- 3. code literals ---------------------------------------------------
# The real food-web defect: a fixed-point loop bound that was one pass short.
OLDC = '<script>for(var p=0;p<species.length+1;p++){ step(); }</script>'
NEWC = '<script>for(var p=0;p<species.length+2;p++){ step(); }</script>'
ck("a changed numeric literal in a script IS reported", len(C(OLDC, NEWC)) == 1, C(OLDC, NEWC))
ck("identical code is not reported", not C(OLDC, OLDC), C(OLDC, OLDC))
# A genuinely NEW LINE of code. The first version of this fixture appended to
# the existing line instead, which is a modified line by any reading -- the
# fixture was wrong, not the tool, and pinning the tool to a bad fixture would
# have been the worse outcome of the two.
NEWLINE = OLDC.replace("</script>", "\nvar fresh=99;\n</script>")
ck("a genuinely new LINE of code is not reported as a changed number",
   not C(OLDC, NEWLINE), C(OLDC, NEWLINE))
# Appending to an existing line IS reported. That is a deliberate choice, not an
# oversight: this tool decides what gets republished, and over-reporting costs
# Read calls while under-reporting leaves a wrong number in front of a reader.
# It is written to fail toward reporting, and the asymmetry is worth stating in
# a check rather than leaving as behaviour nobody wrote down.
SAMELINE = OLDC.replace("step(); }", "step(); } var fresh=99;")
ck("appending to an existing code line IS reported -- it fails toward reporting",
   len(C(OLDC, SAMELINE)) == 1, C(OLDC, SAMELINE))
ck("a hex colour in code is not a numeric literal",
   not C('<script>var c="#334455";</script>', '<script>var c="#667788";</script>'),
   C('<script>var c="#334455";</script>', '<script>var c="#667788";</script>'))
# A UID's digits are already excluded by CODE_NUM's LOOKAHEAD -- "83012" is
# followed by "c", a word character. A purely numeric path segment is not, and
# URLISH is the only thing standing in front of it. A mutation sweep deleted
# URLISH and every fixture still passed, because none of them contained a URL
# shaped like this one.
ck("a purely numeric path segment in a URL is not a numeric literal",
   not C('<script>var u="https://x.org/2026/report";</script>',
         '<script>var u="https://x.org/2027/report";</script>'),
   C('<script>var u="https://x.org/2026/report";</script>',
     '<script>var u="https://x.org/2027/report";</script>'))
ck("a UID in code is not a numeric literal",
   not C('<script>var u="7ce205cb-286c-4d44-b054-2e7d39cfeaa4";</script>',
         '<script>var u="83012ca5-e604-4057-8b0d-07d347eb2d8e";</script>'),
   C('<script>var u="7ce205cb-286c-4d44";</script>', '<script>var u="83012ca5-e604-4057";</script>'))

# ---- 4. prose that changed but carries no number ------------------------
# Real, and NOT what this tool ranks on. Conflating the two is what made every
# page look urgent.
ck("a prose edit with no digits in it is not numeric drift",
   not S('<p>The specimen is the evidence.</p>', '<p>The specimen is the record.</p>'),
   S('<p>The specimen is the evidence.</p>', '<p>The specimen is the record.</p>'))

# ---- 5. the unwrapper ---------------------------------------------------
WRAPPED = ('<!doctype html><html><head><!-- frame-runtime --><script>junk(1234)</script>'
           '<!-- /frame-runtime --></head><body>\n<p>Real content 5.</p>\n</body></html>')
u = PD.unwrap(WRAPPED)
ck("the frame runtime is stripped before anything is compared",
   "junk" not in u and "frame-runtime" not in u, u[:80])
ck("and the page's own content survives it", "Real content 5." in u, u[:80])
ck("the publisher's closing tags are stripped",
   not u.rstrip().endswith("</html>"), u[-40:])
# A page whose body is identical must compare equal through the unwrapper,
# or every page would show drift from the wrapper alone.
ck("two copies wrapped by different runtime builds compare equal",
   PD.unwrap(WRAPPED) == PD.unwrap(WRAPPED.replace("junk(1234)", "other(9876)")), "")

# ---- 6. sentence extraction is not vacuous ------------------------------
sents = PD.sentences(PAGE)
ck("script and style contents never reach the sentence stream",
   not any("mid=37.5" in s or "--ink" in s for s in sents), sents)
ck("and rendered prose does", any("600" in s for s in sents), sents)

# ---- 7. the real pages, as an end-to-end check --------------------------
# A tool that passes synthetic fixtures and returns nothing on the kit is
# passing on nothing at all.
DOCS = os.path.join(ROOT, "docs")
sb = io.open(os.path.join(DOCS, "soil-bench.html"), encoding="utf-8").read()
ck("the repo's soil-bench states the corrected ratio",
   "600 / 60 = 10" in sb or "ten-fold" in sb, "")
ck("and no longer states the wrong one", "eight-fold" not in sb, "")
ck("comparing a page with itself yields no drift at all",
   not S(sb, sb) and not C(sb, sb), "")

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
