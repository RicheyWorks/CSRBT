# -*- coding: utf-8 -*-
"""Recomputes every arithmetic claim in the kit from the page's OWN numbers.

ADR-031's first gate lets a number ship when the reader can check it. That is
only true if the number is actually right, and nothing was checking. Forty
claims sat on the audit_claims worklist; thirteen of them are arithmetic, which
means they can be settled rather than debated.

This is deliberately NOT a table of expected constants. A test that asserts
"the page says 7" fails the moment somebody legitimately changes 50 sample
points to 80 -- and an assertion that a legitimate change breaks is not a test,
it is a future ignored failure. Every case here pulls the INPUTS out of the
page and recomputes the ANSWER, so changing an input keeps the test green and
changing an answer without its input does not.

Each case therefore has to prove it can still read the page: a case whose
pattern stops matching is a FAILURE, not a skip, because a silent skip is how
a suite goes green by measuring nothing.

Run:  python3 tools/verify/verify_claims_math.py
"""
import io, math, os, re, sys
from statistics import NormalDist

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS = os.path.join(ROOT, "docs")
N = NormalDist()

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


def page(f):
    """Page text with entities resolved, so a formula written with &divide;
    reads the same as one written with the character."""
    s = io.open(os.path.join(DOCS, f), encoding="utf-8").read()
    for a, b in (("&nbsp;", " "), ("&divide;", "÷"), ("&times;", "×"), ("&radic;", "√"),
                 ("&minus;", "−"), ("&plusmn;", "±"), ("&asymp;", "≈"), ("&mdash;", "—"),
                 ("&sup2;", "²"), ("&sup3;", "³"), ("&phi;", "φ"), ("&Phi;", "Φ"),
                 ("&sigma;", "σ"), ("&deg;", "°"), ("&amp;", "&")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def grab(f, pattern, name):
    """Pull the numbers a claim states. A pattern that no longer matches means
    the claim was rewritten and this case is no longer reading it."""
    m = re.search(pattern, page(f))
    if not m:
        ck("%s: the claim is still on the page in a readable form" % name, False, pattern[:60])
        return None
    ck("%s: the claim is still on the page in a readable form" % name, True)
    # A trailing full stop belongs to the sentence, not the number: "i ≈ 0.798."
    # parsed as "0.798." and threw. Strip punctuation the pattern swept up.
    return [float(x.replace(",", "").rstrip(".")) for x in m.groups()]


def close(a, b, tol):
    return abs(a - b) <= tol


# ---------------------------------------------------------------- stand sheet
g = grab("stand-sheet.html",
         r"rise ÷ run × 100, so (\d+)% = a (\d+)° slope \(tan (\d+)° = (\d+)\)",
         "slope percent")
if g:
    pct, deg, deg2, tan = g
    ck("a %g%% slope really is %g°" % (pct, deg),
       close(math.degrees(math.atan(pct / 100.0)), deg, 1e-9) and deg2 == deg and tan == 1,
       math.degrees(math.atan(pct / 100.0)))

g = grab("stand-sheet.html",
         r"slope distance is √\(1 \+ ([\d.]+)²\) = ([\d.]+) times the horizontal, so it overestimates by about (\d+)%",
         "slope distance")
if g:
    grade, factor, pct = g
    real = math.hypot(1, grade)
    ck("√(1 + %g²) really is %g" % (grade, factor), close(real, factor, 0.005), real)
    ck("that really is about %g%% over" % pct, close(100 * (real - 1), pct, 0.5), 100 * (real - 1))

# Breast height moved from four hardcoded sentences into a control, because it
# is a method parameter and not a constant: 1.37 m is North American, 1.30 m is
# most of the world. This check moved with it, and now reads the option that
# states an imperial equivalent -- the one place on the page where two units
# claim to be the same length.
g = grab("stand-sheet.html",
         r'\{value:([\d.]+),label:"[\d.]+ m",sub:"N\. America \((\d+) ft (\d+) in\)"',
         "breast height, North American option")
if g:
    metres, ft, inch = g
    imperial = (ft + inch / 12.0) * 0.3048
    ck("%g m really is %g ft %g in" % (metres, ft, inch),
       close(metres, imperial, 0.005), imperial)

# And the choice offered is the set of conventions that actually exist, not one
# height presented as universal. Recomputed from the page, never pinned: the
# assertion is that each option's label agrees with its own value.
opts = re.findall(r'\{value:(1\.\d+),label:"([\d.]+) m"', page("stand-sheet.html"))
ck("the breast-height control offers more than one convention", len(opts) >= 2, opts)
ck("every option's label states its own value",
   all(close(float(v), float(lab), 1e-9) for v, lab in opts), opts)
ck("and 1.30 m -- the height most of the world uses -- is among them",
   any(abs(float(v) - 1.30) < 1e-9 for v, _ in opts), opts)

# --------------------------------------------------------------------- relevé
g = grab("releve.html",
         r"√\(p\(1−p\)/n\), so at (\d+)% cover on (\d+) points that is √\(([\d.]+) ÷ (\d+)\) ≈ (\d+) percentage points",
         "point-intercept SE at 50%")
if g:
    cover, n, numer, n2, pp = g
    p = cover / 100.0
    ck("p(1−p) at %g%% cover really is %g" % (cover, numer), close(p * (1 - p), numer, 1e-9), p * (1 - p))
    ck("the denominator is the sample size", n2 == n, (n2, n))
    ck("√(%g ÷ %g) really is about %g percentage points" % (numer, n, pp),
       close(100 * math.sqrt(numer / n), pp, 0.5), 100 * math.sqrt(numer / n))

g = grab("releve.html",
         r"At (\d+) points a (\d+)% cover estimate gives √\(([\d.]+) × ([\d.]+) ÷ (\d+)\) = ([\d.]+), so roughly ±(\d+) percentage points",
         "point-intercept SE at 20%")
if g:
    n, cover, a, b, n2, val, pp = g
    ck("the two factors are p and 1−p", close(a, cover / 100.0, 1e-9) and close(b, 1 - cover / 100.0, 1e-9), (a, b))
    ck("the denominator is the sample size", n2 == n, (n2, n))
    ck("√(%g × %g ÷ %g) really is %g" % (a, b, n, val), close(math.sqrt(a * b / n), val, 5e-4), math.sqrt(a * b / n))
    ck("%g really is ±%g percentage points" % (val, pp), close(100 * val, pp, 0.2), 100 * val)

# ---------------------------------------------------------------- micro bench
g = grab("micro-bench.html",
         r"variation is 1 ÷ √N: thirty colonies gives 1 ÷ √(\d+) ≈ (\d+)%, ten gives 1 ÷ √(\d+) ≈ (\d+)%",
         "Poisson CV")
if g:
    n1, cv1, n2, cv2 = g
    ck("1 ÷ √%g really is about %g%%" % (n1, cv1), close(100 / math.sqrt(n1), cv1, 0.5), 100 / math.sqrt(n1))
    ck("1 ÷ √%g really is about %g%%" % (n2, cv2), close(100 / math.sqrt(n2), cv2, 0.5), 100 / math.sqrt(n2))
    ck("the smaller plate really is the noisier one", cv2 > cv1, (cv1, cv2))

# ------------------------------------------------------------- breeding bench
g = grab("breeding-bench.html",
         r"Keeping the top (\d+)% gives i ≈ ([\d.]+); the top (\d+)% gives i ≈ ([\d.]+)\.",
         "selection intensity")
if g:
    p1, i1, p2, i2 = g
    for p, stated in ((p1 / 100.0, i1), (p2 / 100.0, i2)):
        want = N.pdf(N.inv_cdf(1 - p)) / p
        ck("i at the top %g%% really is %g" % (p * 100, stated), close(want, stated, 0.002), want)
    ck("the page states i = φ(x)/p, the formula those numbers come from",
       "i = φ(x) / p" in page("breeding-bench.html"), "formula missing")

# ----------------------------------------------------------------- cell bench
g = grab("cell-bench.html",
         r"chamber factor is 10⁴ for a standard Neubauer at ([\d.]+) mm depth, because one large square holds ([\d.]+) µL",
         "Neubauer chamber factor")
if g:
    depth_mm, vol_uL = g
    ck("a 1 mm × 1 mm square %g mm deep really holds %g µL" % (depth_mm, vol_uL),
       close(1.0 * 1.0 * depth_mm, vol_uL, 1e-9), 1.0 * 1.0 * depth_mm)
    ck("counting in %g µL and reporting per mL really is a factor of 10⁴" % vol_uL,
       close(1000.0 / vol_uL, 1e4, 1), 1000.0 / vol_uL)

# ----------------------------------------------------------------- soil bench
g = grab("soil-bench.html",
         r"straw is around (\d+) kg/m³ and fresh manure around (\d+) kg/m³, which is (\d+) ÷ (\d+) = (\d+)",
         "bulk density spread")
if g:
    straw, manure, a, b, ratio = g
    ck("the division shown uses the two densities stated", (a, b) == (manure, straw), (a, b))
    ck("%g ÷ %g really is %g" % (manure, straw, ratio), close(manure / straw, ratio, 1e-9), manure / straw)
    ck("the prose says ten-fold, which is what the division gives",
       "ten-fold" in page("soil-bench.html") and close(ratio, 10, 1e-9), ratio)

g = grab("soil-bench.html", r"at (\d+) °F \((\d+) °C\)", "NOP temperature cap")
if g:
    f, c = g
    ck("%g °F really is about %g °C" % (f, c), close((f - 32) * 5 / 9, c, 0.5), (f - 32) * 5 / 9)

# ------------------------------------------------------------------- cp bench
for f, name in (("cp-bench.html", "cp-bench"), ("cp-suite.html", "cp-suite")):
    # cp-suite writes "one watering at 500." with the unit carried by the first
    # number only, so ppm has to be optional on the second.
    g = grab(f, r"[Tt]en top-ups (?:with|at) (\d+) ppm.{0,90}?at (\d+)(?: ppm)?\b",
             "%s tray accumulation" % name)
    if g:
        each, total = g
        ck("%s: ten top-ups at %g ppm really equal one at %g ppm" % (name, each, total),
           close(10 * each, total, 1e-9), 10 * each)

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
