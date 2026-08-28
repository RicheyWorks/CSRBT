# -*- coding: utf-8 -*-
"""Does the tie sweep ask the right question, and does the kit round one way?

ADR-087 found a figure whose displayed digit was decided by IEEE representation
rather than by the number, and predicted few others on the evidence of that one.
tools/audit_ties.py is the sweep that tests the prediction; this file is what
keeps the sweep honest, because a finder nobody checks reports whatever it
happens to look at.

Two things are locked here:

  the QUESTION   the sweep's precision list is read from the pages, not pinned.
                 The first draft pinned four precisions; the pages use seven,
                 and the pinned list hid more than half the ties. A sweep that
                 quietly skips a precision is the ADR-061 failure -- nothing in
                 the output disagrees with it.

  the RULE       one rounding rule, in _kit.as_page_shows, matching what the
                 pages do. Python's round() is half-to-even and disagrees with
                 it on the kit's own figures; a check that used round() would
                 contradict the page while looking right.
"""

# Declared for tools/mutate.py: this suite reads the real docs/ tree and the
# real fixtures, and asserts about the tools that sweep them. The page names it
# contains are the fixtures' own, quoted as data.
MUTATE_ROLE = "subject"
import glob, io, os, re, sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import _kit
import audit_ties as T

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


# ---- 1. one rounding rule, and it is the pages' rule ----------------------
# Measured against Node: fmt(v,0) for each of these. Recomputed here from the
# inputs rather than pinned as a table of expected strings -- the point is the
# RULE, and a table would freeze today's answers (ADR-041).
CASES = [(138.5, 0, "139"), (103.5, 0, "104"), (40.5, 0, "41"), (205.5, 0, "206")]
for v, d, want in CASES:
    ck("the shared rule shows %s at %d dp as the page does" % (v, d),
       _kit.as_page_shows(v, d) == want, _kit.as_page_shows(v, d))
# The control the four need: a rule that always rounded UP would pass all of
# them, so check a case that must NOT move.
ck("CONTROL: a value below the boundary is not rounded up",
   _kit.as_page_shows(138.4, 0) == "138", _kit.as_page_shows(138.4, 0))
# And the reason the rule is written down at all: Python disagrees.
disagree = [v for v, d, want in CASES if str(round(v)) != want]
ck("Python's round() really does disagree on some of these -- otherwise this "
   "rule would not need writing down", len(disagree) >= 2, disagree)
ck("...and agrees on others, so the split is about the rule, not about Python",
   len(disagree) < len(CASES), disagree)
# The heredity pair from ADR-087, both precisions, through the shared rule.
ck("0.575 shows as 57 at 0 dp -- the digit the double gives, not the decimal",
   _kit.as_page_shows(0.575, 0, 100) == "57", _kit.as_page_shows(0.575, 0, 100))
ck("...and as 57.5 at the 1 dp the page now uses, where there is no tie",
   _kit.as_page_shows(0.575, 1, 100) == "57.5", _kit.as_page_shows(0.575, 1, 100))
ck("and 0.8 still reads 80 at 1 dp -- the trailing zero is dropped, which is "
   "why one decimal cost nothing",
   _kit.as_page_shows(0.8, 1, 100) == "80", _kit.as_page_shows(0.8, 1, 100))

# ---- 2. the tie test reads the decimal, not the double -------------------
ck("0.575 x100 is a tie at 0 dp -- read from the literal",
   T.is_tie(Decimal("0.575") * 100, 0), "")
ck("...which the DOUBLE would have denied, and that is the whole point",
   float("0.575") * 100 != 57.5, float("0.575") * 100)
ck("CONTROL: a value that is not on a boundary is not a tie",
   not T.is_tie(Decimal("0.576") * 100, 0), "")
ck("and a tie at one precision need not be a tie at another",
   T.is_tie(Decimal("0.575") * 100, 0) and not T.is_tie(Decimal("0.575") * 100, 1),
   "")

# ---- 3. the sweep covers every precision the pages format at -------------
# Read the pages independently of audit_ties, so this is a second opinion and
# not the tool agreeing with itself (ADR-068).
seen = set()
for f in glob.glob(os.path.join(_kit.DOCS_DIR, "*.html")):
    src = io.open(f, encoding="utf-8").read()
    for m in re.finditer(r"\bfmt\(\s*[^;]{0,80}?\s*(?:,\s*(\d+)\s*)?\)", src):
        seen.add(int(m.group(1)) if m.group(1) else 2)
    for m in re.finditer(r"\.toFixed\(\s*(\d+)\s*\)", src):
        seen.add(int(m.group(1)))
swept = set(d for _, d in T.PRECISIONS)
ck("the sweep covers every precision the pages actually format at",
   not (seen - swept), sorted(seen - swept))
ck("and the page set is not empty -- otherwise the check above is vacuous",
   len(seen) >= 5, sorted(seen))
ck("the precisions are DERIVED, not pinned: they change when the pages do",
   len(T.precisions()) == len(T.PRECISIONS) and T.precisions() == T.PRECISIONS, "")

# ---- 4. the sweep still finds the figure ADR-087 was about ---------------
found = set()
for f in sorted(glob.glob(os.path.join(_kit.DOCS_DIR, "*.json"))):
    src = io.open(f, encoding="utf-8").read()
    for m in T.LITERAL.finditer(src):
        for scale, digits in T.PRECISIONS:
            if scale == 100 and not (0 < Decimal(m.group(2)) <= 1):
                continue
            if T.is_tie(Decimal(m.group(2)) * scale, digits):
                found.add((os.path.basename(f), m.group(1)))
ck("the sweep still reports the figure ADR-087 was written about",
   ("ecology-lab-session.json", "meanStructural") in found, sorted(found)[:4])
ck("and it reports more than that one -- the prediction of 'few' was wrong",
   len(found) > 1, len(found))

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
