# -*- coding: utf-8 -*-
"""Locks the print-fidelity slice.

Two kinds of assertion here. The first checks the fixes hold. The second checks
the AUDIT still has teeth -- a print audit that cannot report a fault would
report zero forever, so the canary is part of the suite rather than a thing I
ran once by hand.
"""
import io, os, tempfile
from pathlib import Path as _Path
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

CANARY = """<!doctype html><html><head><meta charset="utf-8"><title>c</title><style>
 body{margin:0;font-size:14px;background:#fff}
 @media print{.p{display:none}.n{display:none}.c{display:none}.m{display:none}.k{display:none}}
</style></head><body>
<div class="p">The standard clinometer method works on slopes, which the single-angle shortcut does not. Sign convention: looking up is positive, looking down negative. Standing below the tree you read a negative base angle; above it, positive, and the height is the difference, which is why both readings matter.</div>
<div class="n"><a href="a.html">Field Notebook page one</a><a href="b.html">Ethogram page two</a><a href="c.html">Selection Log three</a><a href="d.html">Stand Sheet page four</a><a href="e.html">Releve page five here</a></div>
<div class="c"><button>Copy the log as CSV right now</button><button>Copy the session sheet</button><button>Copy the budget CSV file</button><button>Export the whole ethogram</button><button>Load a saved study now</button></div>
<div class="m noprint">Drop a session file anywhere on this page to reload it, then run the gradle task to regenerate the report from the same data. Only means anything on a screen.</div>
<div class="k" data-print="mode">All four strategies receive the same operations. The teal card has the lowest height. This view only appears in comparison mode, so it is one arm of a pair of views.</div>
</body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 720, "height": 1000})
    pg.set_default_timeout(20000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    pg.emulate_media(media="print")

    # ---- 1. the audit still has teeth -------------------------------------
    # Scratch dir via tempfile, and the file URL via Path.as_uri() (ADR-106).
    # These were hardcoded Linux scratch paths written into a suite that has to
    # run wherever the kit is checked out. On Windows os.makedirs happily creates
    # the directory on the current drive while the browser resolves the absolute
    # file URL somewhere else entirely, so the canary died on
    # net::ERR_FILE_NOT_FOUND -- the suite CRASHED rather than reporting, and a
    # suite that crashes says nothing about the checks after it.
    _pcan = os.path.join(tempfile.mkdtemp(prefix="_pcan_"), "c.html")
    io.open(_pcan, "w", encoding="utf-8").write(CANARY)
    pg.goto(_Path(_pcan).as_uri(), wait_until="domcontentloaded"); pg.wait_for_timeout(400)
    import _kit
    probe = _kit.tool("audit_print").PROBE
    r = pg.evaluate(probe, 720)
    lost = [k for k, n in r["lost"]]
    ck(lost == ["div.p"], "canary: only the genuine prose is called lost (got %s)" % lost)
    ck("div.n" not in lost, "canary: a link list is read as navigation, not loss")
    ck("div.c" not in lost, "canary: a button panel is read as controls, not loss")
    ck("div.m" not in lost, "canary: an explicit .noprint marker is honoured")
    ck("div.k" not in lost, "canary: data-print=mode is honoured")

    # ---- 2. tree-visualizer prints on paper, not in ink --------------------
    pg.goto("file://" + DOCS + "tree-visualizer.html", wait_until="domcontentloaded")
    pg.wait_for_timeout(1000)
    for tok, want in (("--bg", "#fff"), ("--panel", "#fff"), ("--panel2", "#fff")):
        got = pg.evaluate("t=>getComputedStyle(document.documentElement).getPropertyValue(t).trim()", tok)
        ck(got == want, "print %s is paper white (got %r)" % (tok, got))
    bodybg = pg.evaluate("()=>getComputedStyle(document.body).backgroundColor")
    ck(bodybg == "rgb(255, 255, 255)", "print body is white (got %s)" % bodybg)
    ink = pg.evaluate("""()=>{const lum=c=>{const m=String(c).match(/rgba?\\(([^)]+)\\)/);if(!m)return null;
      const p=m[1].split(/[,\\s\\/]+/).filter(Boolean).map(Number); if(p.length>3&&p[3]<0.5)return null;
      const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
      return 0.2126*f(p[0])+0.7152*f(p[1])+0.0722*f(p[2]);};
      let d=0; const W=Math.min(720,document.documentElement.scrollWidth);
      const tot=W*document.documentElement.scrollHeight;
      document.querySelectorAll('body *').forEach(e=>{const s=getComputedStyle(e);
        if(s.display==='none'||s.visibility==='hidden')return;
        const l=lum(s.backgroundColor); if(l===null||l>0.35)return;
        const b=e.getBoundingClientRect();
        d+=Math.max(0,Math.min(b.width,W))*Math.max(0,b.height);});
      return tot?d/tot*100:0;}""")
    ck(ink < 5, "tree-visualizer ink coverage is under 5%% of the page (%.1f%%, was 103.9%%)" % ink)
    # the four strategies must stay tellable apart on paper
    seen = set()
    for tok in ("--teal", "--amber", "--rose", "--violet"):
        v = pg.evaluate("t=>getComputedStyle(document.documentElement).getPropertyValue(t).trim()", tok)
        seen.add(v.lower())
    ck(len(seen) == 4, "the four strategy accents stay four distinct colours on paper (%s)" % sorted(seen))

    # ---- 3. the clinometer method reaches the paper -----------------------
    pg.goto("file://" + DOCS + "stand-sheet.html", wait_until="domcontentloaded"); pg.wait_for_timeout(800)
    disp = pg.evaluate("()=>getComputedStyle(document.getElementById('htCard')).display")
    ck(disp != "none", "stand-sheet: the two-angle height card prints (display=%s)" % disp)
    txt = pg.evaluate("()=>document.getElementById('htCard').textContent")
    for phrase in ("Sign convention", "horizontal", "Leaning stems"):
        ck(phrase in txt, "stand-sheet: printed method still carries %r" % phrase)
    b.close()

    # and is still shut on screen, where the toggle wants it shut
    pg2 = b if False else None
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    pg.goto("file://" + DOCS + "stand-sheet.html", wait_until="domcontentloaded"); pg.wait_for_timeout(800)
    ck(pg.evaluate("()=>getComputedStyle(document.getElementById('htCard')).display") == "none",
       "stand-sheet: the card is still collapsed on screen, where the toggle owns it")
    b.close()

# ---- 4. intent is declared in the document, not guessed at ---------------
for f, ident, val in (("tree-visualizer.html", 'id="compareWrap"', "mode"),
                      ("field-season.html", 'id="report"', "mode"),
                      ("field-season.html", 'id="results"', "mode"),
                      ("ecology-lab.html", 'class="drophint"', "chrome")):
    s = io.open(DOCS + f, encoding="utf-8").read()
    i = s.find(ident)
    ck(i > 0 and 'data-print="%s"' % val in s[max(0, i-90):i+120],
       "%s: %s declares data-print=%s" % (f, ident, val))

print("---"); print("%d/%d" % (P, P+F))
raise SystemExit(1 if F else 0)
