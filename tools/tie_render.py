# -*- coding: utf-8 -*-
"""Which of the recorded rounding ties does a reader actually SEE?

tools/audit_ties.py finds figures whose displayed digit is decided by a rounding
rule rather than by the data, and refuses to say which are displayed, because
binding a fixture value to a call site by key name reports `p`, `q` and
`observed` against every page that uses those names -- a fact about names, not
about data flow (ADR-077).

This answers the question the way the kit answers questions about pages:
by changing the input and looking at the output.

    for each tie value v shown at `digits` places:
        render the page
        render it again with v moved one full unit of the displayed place
        if the rendered text differs, v REACHES THE PAGE

No name matching, no JS parsing, no guessing which accessor reads which key. A
perturbation that changes nothing on screen is a value nobody sees; one that
changes something names the line it changed.

    python3 tools/tie_render.py

WHAT THIS DOES NOT COVER, NAMED RATHER THAN IMPLIED (ADR-061)

  * Only `docs/ecology-lab.html` is rendered. It is the one page that INLINES
    its session (`const SESSION = ...`); the other three recorded sessions
    holding ties are read by `demo/visualizer.html` and the protocol reference
    when a reader drops the file in, so rendering them means driving a file
    drop. Those fixtures are listed as not covered, not passed over.
  * A value drawn only into a <canvas> plot changes no text and will read as
    "not displayed" here. That is a real blind spot, and it is why the verdict
    below is "reaches the rendered TEXT", not "is invisible".

This is a finder, not a gate.
"""
import io, json, os, re, sys, tempfile
from decimal import Decimal

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "verify"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import _kit
import audit_ties as T

PAGE = os.path.join(ROOT, "docs", "ecology-lab.html")
FIXTURE = "ecology-lab-session.json"
NOT_RENDERED = ["arena-search-session.json", "ecology-experiment-session.json",
                "ecology-trace-session.json"]


def inline_session(src):
    """The page's own copy, by brace matching -- a regex sees braces in strings."""
    i = src.index("const SESSION = ")
    j = i + len("const SESSION = ")
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return j, k + 1
    raise ValueError("unterminated SESSION object")


def render(page_src, pw):
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "page.html")
        io.open(p, "w", encoding="utf-8").write(page_src)
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        _kit.offline(pg)
        pg.goto("file://" + p, wait_until="load")
        pg.wait_for_timeout(1500)
        txt = pg.evaluate("()=>document.body.innerText")
        b.close()
        return txt


def step(scale, digits):
    """One full unit of the displayed place, back in the value's own units."""
    return Decimal(1).scaleb(-digits) / scale


# Small enough that no honest display of the value changes, large enough to be
# on the other side of the exact .5 boundary. If a page's text moves when a
# figure is nudged this far, the page is rounding it AT the tie -- the digit a
# reader sees is the rounding rule's, not the number's.
#
# It must be nudged DOWN, and the first version nudged up. Under the pages'
# half-away-from-zero rounding, .5 and .5000000001 give the same digit, so a
# nudge upward can never flip a tie and the check could not fail on any input --
# ADR-084's wall a third time, and it reported a clean board (0 of 4) while
# doing it. Both directions are tried now, and the suite checks that the DOWN
# direction is the one that can distinguish them.
EPSILON = Decimal("0.000000001")


def ties_in(fixture=FIXTURE):
    """Every (key, literal, scale, digits) in a fixture that is an exact tie."""
    out = []
    src = io.open(os.path.join(ROOT, "docs", fixture), encoding="utf-8").read()
    for m in T.LITERAL.finditer(src):
        key, lit = m.group(1), m.group(2)
        for scale, digits in T.PRECISIONS:
            if scale == 100 and not (0 < Decimal(lit) <= 1):
                continue
            if T.is_tie(Decimal(lit) * scale, digits):
                out.append((key, lit, scale, digits))
    return sorted(set(out))


def scan(pw, page_src=None, directions=(-1, 1)):
    """[(key, lit, scale, digits, reaches_text, rounded_at_tie)] for one page.

    `directions` is a parameter so the suite can prove which nudge does the
    work: under half-away-from-zero, only a step DOWN can move a value off an
    exact .5 boundary, and a version of this that stepped up could never report
    anything (ADR-084's wall, third occurrence).
    """
    src = page_src if page_src is not None else io.open(PAGE, encoding="utf-8").read()
    a, b = inline_session(src)
    raw = src[a:b]
    base = render(src, pw)
    rows = []
    for key, lit, scale, digits in ties_in():
        pat = re.compile(r'("%s"\s*:\s*)%s\b' % (re.escape(key), re.escape(lit)))
        moved = str(Decimal(lit) + step(scale, digits))
        mutated = pat.sub(lambda mm: mm.group(1) + moved, raw)
        if mutated == raw:
            rows.append((key, lit, scale, digits, None, None))
            continue
        reaches = render(src[:a] + mutated + src[b:], pw) != base
        live = False
        if reaches:
            for sign in directions:
                nudged = pat.sub(
                    lambda mm: mm.group(1) + str(Decimal(lit) + sign * EPSILON), raw)
                if render(src[:a] + nudged + src[b:], pw) != base:
                    live = True
                    break
        rows.append((key, lit, scale, digits, reaches, live))
    return rows


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        rows = scan(pw)
    print("%-16s %-11s %-5s %-3s %s" % ("key", "literal", "as", "dp", "verdict"))
    print("-" * 96)
    hot = []
    shown = 0
    for key, lit, scale, digits, reaches, live in rows:
        as_ = "x100" if scale == 100 else "raw"
        if reaches is None:
            print("%-16s %-11s %-5s %-3d NOT IN THE PAGE'S INLINE COPY"
                  % (key, lit, as_, digits))
            continue
        shown += 1 if reaches else 0
        v = "REACHES THE RENDERED TEXT" if reaches else "no change on screen"
        if live:
            v += "  ** ROUNDED AT THE TIE **"
            hot.append((key, lit, scale, digits))
        print("%-16s %-11s %-5s %-3d %s" % (key, lit, as_, digits, v))
    print("-" * 96)
    print("%d of %d tie(s) in %s reach the rendered text" % (shown, len(rows), FIXTURE))
    print("%d of those are rounded at the tie -- a reader sees a digit the "
          "rounding rule chose%s" % (len(hot), ":" if hot else ""))
    for k, l, sc, dg in hot:
        print("      %-16s %-11s at %s%d dp" % (k, l, "%" if sc == 100 else "", dg))
    print("not rendered here (their pages read the file on a drop): %s"
          % ", ".join(NOT_RENDERED))
    print("(a value drawn only into a canvas would read as no-change -- see the docstring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
