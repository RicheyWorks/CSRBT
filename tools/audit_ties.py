# -*- coding: utf-8 -*-
"""Which recorded figures are decided by a rounding rule rather than by the data?

ADR-087 found one: `meanStructural` is 0.575000, which is exactly 57.500 at the
zero decimal places the flagship page displayed. The page rendered 57 and two
other documents said 57, and they agreed only because the nearest double to
0.575 is 57.49999999999999. Had the value been representable the page would have
shown 58 while the prose still said 57, and nothing in a green kit would have
disagreed.

That record predicted few others, on the evidence of one instance, and said the
sweep should run before the expectation was repeated. This is the sweep.

WHAT IT REPORTS, AND WHY EACH COLUMN IS THERE

For every decimal literal in the recorded sessions, at each precision the kit
displays at:

  tie      the EXACT decimal lands on a .5 boundary. Read from the literal text,
           never from the double -- reading the double is how the first one hid.
  double   what the nearest double actually is. When it differs from the exact
           value, the displayed digit is decided by IEEE representation, not by
           the number: that is the coin flip, and it can fall either way.
  split    half-up (what JavaScript's toFixed and toLocaleString do) and
           half-to-even (what Python's round does, and therefore what a check
           written in Python does) give different digits. A check that rounds
           differently from the page it checks is a second source of truth
           (ADR-068), and this column is where that could bite.

WHAT IT DOES NOT DO

It does not claim any of these is displayed. Binding a fixture value to a call
site means resolving `f.meanStructural` or `a.observed` through page JS, and the
naive version of that -- match on key name -- reports `p`, `q` and `observed`
against every page that happens to use those names. That is a fact about names,
not about data flow (ADR-077), so this reports the QUESTION and leaves the
answer to a reader who can see the page.

    python3 tools/audit_ties.py

This is a finder, not a gate.
"""
import glob, io, os, re, sys
from decimal import Decimal

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")

LITERAL = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*(-?\d+\.\d+)')
FMT = re.compile(r"\bfmt\(\s*([^;]{0,80}?)\s*(?:,\s*(\d+)\s*)?\)")
TOFIXED = re.compile(r"\.toFixed\(\s*(\d+)\s*\)")


def precisions():
    """(scale, digits) pairs the kit actually formats at -- READ, not pinned.

    The first draft of this file hard-coded [(100,0),(100,1),(1,1),(1,2)],
    which is the set I happened to have in mind. The pages format at 0,1,2,3,4,5
    and 6 decimals; four of those would have been swept past in silence, and a
    sweep that quietly does not cover a precision is worse than one that covers
    the wrong precision, because nothing in the output disagrees with it
    (ADR-061). It was also a pinned constant standing in for a value that can be
    computed from the inputs, which is the thing ADR-041 is about -- committed in
    the tool written to check other people's numbers.

    So the set is derived: every `fmt(x, d)` (default 2) and every `.toFixed(d)`
    in docs/, with the percentage scale taken from whether the fmt argument
    multiplies by 100. toFixed sites are counted at both scales because the
    multiply, where there is one, is usually outside the call.
    """
    raw, pct = set(), set()
    for f in glob.glob(os.path.join(DOCS, "*.html")):
        src = io.open(f, encoding="utf-8").read()
        for m in FMT.finditer(src):
            d = int(m.group(2)) if m.group(2) else 2
            (pct if ("* 100" in m.group(1) or "*100" in m.group(1)) else raw).add(d)
        for m in TOFIXED.finditer(src):
            raw.add(int(m.group(1))); pct.add(int(m.group(1)))
    return sorted([(100, d) for d in pct] + [(1, d) for d in raw])


PRECISIONS = precisions()


def is_tie(exact, digits):
    """Does this EXACT decimal sit on a .5 boundary at `digits` places?"""
    q = Decimal(1).scaleb(-digits)
    return (exact / q) % 1 == Decimal("0.5")


def half_up(x, digits):
    """What JavaScript shows: round half away from zero, on the value given."""
    q = Decimal(1).scaleb(-digits)
    return (Decimal(x) / q).to_integral_value(rounding="ROUND_HALF_UP") * q


def half_even(x, digits):
    """What Python's round() gives, and so what a check written in Python gives."""
    q = Decimal(1).scaleb(-digits)
    return (Decimal(x) / q).to_integral_value(rounding="ROUND_HALF_EVEN") * q


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(DOCS, "*.json"))):
        src = io.open(f, encoding="utf-8").read()
        for m in LITERAL.finditer(src):
            key, lit = m.group(1), m.group(2)
            exact = Decimal(lit)
            for scale, digits in PRECISIONS:
                if scale == 100 and not (0 < exact <= 1):
                    continue                     # only a fraction is shown as a percent
                shown = exact * scale
                if not is_tie(shown, digits):
                    continue
                # The double is the thing the page actually rounds.
                dbl = Decimal(repr(float(lit) * scale))
                rows.append((os.path.basename(f), key, lit,
                             "x100" if scale == 100 else "raw", digits,
                             str(shown), str(dbl),
                             half_up(shown, digits) != half_even(shown, digits)))

    print("precisions read from the pages: %s"
          % ", ".join("%s%d dp" % ("%" if sc == 100 else "", d) for sc, d in PRECISIONS))
    if not rows:
        print("no recorded figure sits on a rounding tie at any precision the kit uses")
        return 0

    print("%-31s %-16s %-10s %-5s %-3s %-14s %s" %
          ("fixture", "key", "literal", "as", "dp", "exact", "the double / split"))
    print("-" * 118)
    seen = set()
    for fx, key, lit, how, dp, shown, dbl, split in rows:
        if (fx, key, lit, how, dp) in seen:
            continue
        seen.add((fx, key, lit, how, dp))
        note = dbl if Decimal(dbl) != Decimal(shown) else "exactly representable"
        print("%-31s %-16s %-10s %-5s %-3d %-14s %s%s" %
              (fx, key, lit, how, dp, shown, note,
               "   HALF-UP/HALF-EVEN SPLIT" if split else ""))
    print("-" * 118)
    print("%d distinct (figure, precision) pair(s) on a rounding tie" % len(seen))
    reps = sum(1 for k in seen
               if Decimal(next(r[6] for r in rows if r[:5] == k)) != Decimal(
                   next(r[5] for r in rows if r[:5] == k)))
    print("%d of them are decided by float representation rather than by the number" % reps)
    print("(this is a finder, not a gate -- none of these is claimed to be DISPLAYED;")
    print(" binding a figure to a call site needs the page, not a key name)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
