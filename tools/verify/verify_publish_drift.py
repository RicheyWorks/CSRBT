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

# ---- 8. when a saved copy stops being evidence (ADR-056) ----------------
# The rule these exercise is the one that was a footnote and got walked past
# twice. Every arm is asserted in BOTH directions, because the expensive
# failure here is not a wrong drift count -- it is a page ranked from a copy
# that predates it, which reads exactly like a page that is genuinely stale.
E = PD.evidence
CUR, OTHER = "a" * 64, "b" * 64
STAMP_AT = 1000                     # not "now": a fixture that moves with the
COPY_OLD, COPY_NEW = 999, 1001      # clock is ADR-041's frozen constant inverted

ck("repo hash == stamp hash is CURRENT whatever the copy's age",
   E({"sha": CUR, "at": STAMP_AT}, CUR, COPY_OLD) == "current"
   and E({"sha": CUR, "at": STAMP_AT}, CUR, COPY_NEW) == "current",
   E({"sha": CUR, "at": STAMP_AT}, CUR, COPY_OLD))
ck("a copy fetched AFTER the last stamp is rankable",
   E({"sha": OTHER, "at": STAMP_AT}, CUR, COPY_NEW) == "rankable",
   E({"sha": OTHER, "at": STAMP_AT}, CUR, COPY_NEW))
ck("a copy fetched BEFORE the last stamp is SUPERSEDED, not drift",
   E({"sha": OTHER, "at": STAMP_AT}, CUR, COPY_OLD) == "superseded",
   E({"sha": OTHER, "at": STAMP_AT}, CUR, COPY_OLD))
ck("a copy fetched at the very moment of the stamp is rankable, not superseded",
   E({"sha": OTHER, "at": STAMP_AT}, CUR, STAMP_AT) == "rankable",
   E({"sha": OTHER, "at": STAMP_AT}, CUR, STAMP_AT))

# The bucket that produced the phantom: unstamped, and stamped before stamps
# carried a time. Both are "no ordering exists", and neither may borrow the
# other buckets' answers -- an unstamped page is not superseded (that would
# hide real staleness) and is not rankable (that is the phantom).
ck("a page that was never stamped is UNORDERED, not rankable",
   E(None, CUR, COPY_NEW) == "unordered", E(None, CUR, COPY_NEW))
ck("and is not SUPERSEDED either -- absence of a stamp orders nothing",
   E(None, CUR, COPY_OLD) == "unordered", E(None, CUR, COPY_OLD))
ck("a pre-ADR-056 bare-string stamp is UNORDERED however old the copy",
   E(OTHER, CUR, COPY_OLD) == "unordered"
   and E(OTHER, CUR, COPY_NEW) == "unordered",
   E(OTHER, CUR, COPY_NEW))
ck("but a bare-string stamp still resolves CURRENT when the hash matches",
   E(CUR, CUR, COPY_OLD) == "current", E(CUR, CUR, COPY_OLD))

# The accessors underneath, in both formats. entry_at must not invent a time:
# 0 and None are different answers and only one of them is true.
PS = PD._pstate
ck("entry_sha reads the new format", PS.entry_sha({"sha": CUR, "at": 5}) == CUR)
ck("entry_sha reads the legacy bare string", PS.entry_sha(CUR) == CUR)
ck("entry_at reads the new format", PS.entry_at({"sha": CUR, "at": 5}) == 5)
ck("entry_at on a legacy entry is None, never 0",
   PS.entry_at(CUR) is None, PS.entry_at(CUR))
ck("entry_at on a missing entry is None, never 0",
   PS.entry_at(None) is None, PS.entry_at(None))

# The kit's own state file must be readable by both accessors, or the rule
# above is exercised only on fixtures (ADR-039).
import json
REAL = json.load(io.open(os.path.join(ROOT, "tools", "published.json"),
                         encoding="utf-8"))["pages"]
ck("every stamp in the real state file yields a 64-char sha",
   REAL and all(isinstance(PS.entry_sha(v), str) and len(PS.entry_sha(v)) == 64
                for v in REAL.values()), "")
ck("and a time that is an int or None, never anything else",
   all(PS.entry_at(v) is None or isinstance(PS.entry_at(v), int)
       for v in REAL.values()), "")

# ---- 9. the WRITER, not just the readers -------------------------------
# A mutation sweep deleted the timestamp from the stamp writer and all
# twenty-one fixtures above stayed green: they read entries, and every entry
# they read was hand-built. A rule whose only inputs are hand-built inputs is
# ADR-039 again. This runs the real --stamp path against a throwaway state file
# and reads back what it actually wrote.
import tempfile, time as _time, contextlib
_keep = PS.STATE
_tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
_tmp.write(json.dumps({"_comment": "fixture", "pages": {}})); _tmp.close()
try:
    PS.STATE = _tmp.name
    before = int(_time.time())
    with contextlib.redirect_stdout(io.StringIO()):
        rc = PS.main(["--stamp", "food-web.html"])
    after = int(_time.time())
    WROTE = json.load(io.open(_tmp.name, encoding="utf-8"))["pages"].get("food-web.html")
finally:
    PS.STATE = _keep
    os.unlink(_tmp.name)

ck("--stamp succeeds against a throwaway state file", rc == 0, rc)
ck("--stamp writes an entry the sha accessor can read",
   isinstance(PS.entry_sha(WROTE), str) and len(PS.entry_sha(WROTE)) == 64, WROTE)
ck("--stamp writes a TIME, not a bare hash", PS.entry_at(WROTE) is not None, WROTE)
# Bracketed, not pinned: an expected constant here is exactly the frozen
# assertion ADR-041 forbids -- it would fail every day after the one it was
# written on, and be deleted rather than believed.
# Guarded: with the time missing this comparison raises, and a suite that
# CRASHES on a mutant reports nothing about the checks after it -- which is a
# worse failure than the one being tested for.
_at = PS.entry_at(WROTE)
ck("and that time is the moment the stamp was taken",
   isinstance(_at, int) and before <= _at <= after, (before, _at, after))
ck("the sha it wrote is the sha of the bytes publish.py would emit now",
   PS.entry_sha(WROTE) == __import__("hashlib").sha256(
       PD.publish_bytes("food-web.html").encode("utf-8")).hexdigest(), "")
ck("and the real state file was not touched by the fixture",
   json.load(io.open(os.path.join(ROOT, "tools", "published.json"),
                     encoding="utf-8"))["pages"] == REAL, "")

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
