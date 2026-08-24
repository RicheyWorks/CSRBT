# -*- coding: utf-8 -*-
"""Locks the AA palette in place.

The contrast audit proves the kit passes today. This proves the specific values
that make it pass are the ones intended, so a future palette edit that drifts
back under the threshold fails a named test rather than only a sweep.
Every expected ratio here is computed in Python from the WCAG formula, not
copied out of the browser.
"""
import glob, os, colorsys
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

def lum(h):
    h = h.lstrip('#'); rgb = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    f = lambda v: v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4
    r, g, b = [f(v) for v in rgb]
    return 0.2126*r + 0.7152*g + 0.0722*b
def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb)+0.05) / (min(la, lb)+0.05)
def hue(h):
    r, g, b = [int(h.lstrip('#')[i:i+2], 16)/255 for i in (0, 2, 4)]
    return colorsys.rgb_to_hls(r, g, b)

# ---- 1. the token values, and the ratios they must clear ----------------
SURFACES = ["#fffdf7", "#f5f1e6", "#f3eee0", "#e9f0e7"]
for name, old, new, need in [("--muted", "#8b8b7b", "#6b6b5e", 4.5),
                             ("--s1",    "#2e7d4f", "#2c784c", 4.5),
                             ("--s2",    "#c0592b", "#a94f26", 4.5)]:
    worst_old = min(ratio(old, s) for s in SURFACES)
    worst_new = min(ratio(new, s) for s in SURFACES)
    ck(worst_old < need, "%s was genuinely failing before (%.2f:1)" % (name, worst_old))
    ck(worst_new >= need, "%s clears AA on every surface (%.2f:1 >= %.1f)" % (name, worst_new, need))
    # hue and saturation held: only lightness was allowed to move
    ho, lo, so = hue(old); hn, ln, sn = hue(new)
    ck(abs(ho-hn) < 0.02, "%s keeps its hue (%.3f -> %.3f)" % (name, ho, hn))
    ck(abs(so-sn) < 0.06, "%s keeps its saturation (%.2f -> %.2f)" % (name, so, sn))
    ck(ln < lo, "%s only moved darker (%.2f -> %.2f)" % (name, lo, ln))

ck(ratio("#8e8160", "#fffdf7") >= 3, "field-edge clears the 1.4.11 floor on the lightest surface (%.2f:1)" % ratio("#8e8160", "#fffdf7"))
ck(ratio("#8e8160", "#f3eee0") >= 3, "field-edge clears it on the darkest surface too (%.2f:1)" % ratio("#8e8160", "#f3eee0"))
ck(ratio("#e3dcc9", "#fffdf7") < 3, "the decorative card border was deliberately NOT raised (%.2f:1)" % ratio("#e3dcc9", "#fffdf7"))

# selected-chip label: .85 white was the failure, .92 is the fix
def comp(a, bg):
    br = [int(bg.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(round(255*a + c*(1-a)) for c in br)
for bg, what in (("#2c784c", "the selected green"), ("#8a6408", "the selected gold")):
    ck(ratio(comp(.85, bg), bg) < 4.5, "85%% white on %s did fail (%.2f:1)" % (what, ratio(comp(.85, bg), bg)))
    ck(ratio(comp(.92, bg), bg) >= 4.5, "92%% white on %s passes (%.2f:1)" % (what, ratio(comp(.92, bg), bg)))

# ---- 2. the old values are gone from every page ------------------------
pages = sorted(glob.glob(DOCS + "*.html"))
ck(len(pages) == 33, "all 33 pages present (%d)" % len(pages))
import io, re
for old, new in [("8b8b7b", "6b6b5e"), ("2e7d4f", "2c784c"), ("c0592b", "a94f26"),
                 ("b8860b", "8a6408"), ("5a6675", "7a8798")]:
    stale = [os.path.basename(p) for p in pages
             if re.search("#"+old, io.open(p, encoding="utf-8").read(), re.I)]
    ck(not stale, "no page still carries #%s: %s" % (old, stale[:4]))
    live = [p for p in pages if re.search("#"+new, io.open(p, encoding="utf-8").read(), re.I)]
    ck(live, "#%s is actually in use (%d pages)" % (new, len(live)))
rgba_stale = [os.path.basename(p) for p in pages
              if re.search(r"rgba\(46,\s*125,\s*79", io.open(p, encoding="utf-8").read())]
ck(not rgba_stale, "no page still carries the old green as rgba(): %s" % rgba_stale[:4])

src = io.open(_os.path.join(ROOT, "tools", "fek.py"), encoding="utf-8").read()
ck('VERSION = "1.1.1"' in src, "fek.py version bumped to 1.1.1")
ck("rgba(255,255,255,.85)" not in src, "fek.py no longer emits the failing .85 label")
ck(sum('Field Entry Kit v1.1.1' in io.open(p, encoding="utf-8").read() for p in pages) == 14,
   "all 14 FEK consumers report v1.1.1")

# ---- 3. what the browser actually paints -------------------------------
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.set_default_timeout(20000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    for f in ("releve.html", "stand-sheet.html", "soil-bench.html"):
        pg.goto("file://" + DOCS + f, wait_until="domcontentloaded"); pg.wait_for_timeout(600)
        edge = pg.evaluate("""()=>{const e=document.querySelector('input:not([type=checkbox]):not([type=radio])');
            return e?getComputedStyle(e).borderTopColor:null;}""")
        ck(edge == "rgb(142, 129, 96)", "%s paints the field edge as #8e8160 (got %s)" % (f, edge))
        muted = pg.evaluate("()=>getComputedStyle(document.documentElement).getPropertyValue('--muted').trim()")
        ck(muted.lower() in ("#6b6b5e", ""), "%s --muted token is the AA value (got %r)" % (f, muted))
    b.close()

print("---"); print("%d/%d" % (P, P+F))
raise SystemExit(1 if F else 0)
