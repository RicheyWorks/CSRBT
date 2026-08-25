# -*- coding: utf-8 -*-
"""Locks the offline slice, and keeps its measurement honest.

ADR-031 makes offline operation non-negotiable. The fault this slice fixed was
not "no network" -- that always worked -- but a webfont stylesheet request that
is accepted and never answered, which held first paint indefinitely with the
whole document already built and invisible. One bar of signal in a wet meadow.

The second half of this suite exists because the audit that found it lied twice
about paint timing before it was right, both times through the harness rather
than the page. So the harness is tested here too.
"""
import glob, io, os, re, sys

import _kit
from playwright.sync_api import sync_playwright

P = F = 0
def ck(c, m):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", m)

PAINT = ("()=>{const t=performance.getEntriesByType('paint')"
         ".find(e=>e.name==='first-contentful-paint');"
         " return {p:t?Math.round(t.startTime):null,"
         "  chars:(document.body&&document.body.innerText||'').trim().length};}")

pages = sorted(glob.glob(_kit.DOCS_DIR + "*.html"))
ck(len(pages) >= 33, "the kit still has all its pages (%d)" % len(pages))

# ---- 1. the markup says what it should ---------------------------------
withfont = [p for p in pages if "fonts.googleapis.com/css2" in io.open(p, encoding="utf-8").read()]
# Not a frozen count: what matters is that every page using webfonts defers
# them, and the per-page loop below asserts exactly that for each one.
ck(len(withfont) >= 32, "the pages using webfonts are all checked (%d)" % len(withfont))
ck(len(withfont) < len(pages), "at least one page needs no webfont at all")
for path in withfont:
    nm = os.path.basename(path)
    src = io.open(path, encoding="utf-8").read()
    body = re.sub(r"<noscript>.*?</noscript>", "", src, flags=re.S | re.I)
    blocking = [t for t in re.findall(r"<link[^>]*>", body, re.I)
                if re.search(r'rel=["\']?stylesheet', t, re.I)
                and re.search(r'href="https?://', t, re.I)
                and not re.search(r'media=["\']print', t, re.I)]
    ck(not blocking, "%s has no render-blocking external stylesheet" % nm)
    ck('media="print" data-webfont' in src, "%s defers its webfont link" % nm)
    ck("<noscript><link rel=\"stylesheet\"" in src, "%s keeps a noscript copy" % nm)
    ck(src.count("fonts.googleapis.com/css2") == 2,
       "%s: exactly two stylesheet URLs -- the deferred link and its noscript copy (%d)"
       % (nm, src.count("fonts.googleapis.com/css2")))

# ---- 2. what the browser actually does ---------------------------------
BIG = max(pages, key=os.path.getsize)
with sync_playwright() as pw:
    b = pw.chromium.launch()

    # (a) no network at all
    ctx = b.new_context(viewport={"width": 390, "height": 900})
    ctx.set_offline(True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file://" + BIG, wait_until="commit")
    pg.wait_for_timeout(2500)
    r = pg.evaluate(PAINT)
    ck(r["p"] is not None and r["p"] < 2000, "offline: paints promptly (%s ms)" % r["p"])
    ck(r["chars"] > 500, "offline: the document is actually on screen (%d chars)" % r["chars"])
    ck(not errs, "offline: no page errors (%s)" % errs[:1])
    fam = pg.evaluate("()=>getComputedStyle(document.body).fontFamily")
    ck(re.search(r"(serif|sans-serif|monospace|system-ui|-apple-system)", fam),
       "offline: the body font stack ends somewhere real (%s)" % fam[:60])
    ctx.close()

    # (b) the request hangs -- the case that was broken
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.route("**://fonts.googleapis.com/**", lambda route: None)
    pg.route("**://fonts.gstatic.com/**", lambda route: None)
    pg.goto("file://" + BIG, wait_until="commit")
    pg.wait_for_timeout(4000)
    r = pg.evaluate(PAINT)
    ck(r["p"] is not None, "hanging request: the page still paints (%s ms)" % r["p"])
    ck(r["chars"] > 500, "hanging request: content is visible, not just in the DOM (%d)" % r["chars"])
    try:
        pg.unroute("**://fonts.googleapis.com/**"); pg.unroute("**://fonts.gstatic.com/**")
    except Exception:
        pass
    pg.close()

    # (c) online still gets the fonts -- the fix must not be a silent removal
    CSS = "@media all { body { --webfont-probe: arrived; } }"
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.route("**://fonts.googleapis.com/**",
             lambda route: route.fulfill(status=200, content_type="text/css", body=CSS))
    pg.route("**://fonts.gstatic.com/**", lambda route: route.abort("namenotresolved"))
    pg.goto("file://" + BIG, wait_until="load")
    pg.wait_for_timeout(1200)
    ck(pg.evaluate("()=>{const l=document.querySelector('link[data-webfont]');return l&&l.media;}") == "all",
       "online: the deferred link is promoted to media=all")
    ck(pg.evaluate("()=>getComputedStyle(document.body).getPropertyValue('--webfont-probe').trim()") == "arrived",
       "online: the stylesheet actually applies once it arrives")
    pg.close()

    # (d) the harness itself. A broad route interceptor adds latency to every
    #     request it catches; when one of them is RENDER-BLOCKING, that latency
    #     lands on first paint and reads as a fault in the page. That is how the
    #     audit came to report a 12-second blank screen no device ever sees.
    #     The kit's own pages no longer block on anything, so the distortion has
    #     to be demonstrated on a page that still does -- written here rather
    #     than asserted from memory.
    import tempfile
    BLOCKING = ('<!doctype html><html><head><meta charset="utf-8"><title>b</title>'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fake">'
                '</head><body><p>text that has to wait for a stylesheet</p></body></html>')
    tmp = os.path.join(tempfile.mkdtemp(), "blocking.html")
    io.open(tmp, "w", encoding="utf-8").write(BLOCKING)

    def paint_under(path, setup):
        c = b.new_context(viewport={"width": 390, "height": 900})
        pp = c.new_page(); setup(c, pp)
        pp.goto("file://" + path, wait_until="commit"); pp.wait_for_timeout(2500)
        v = pp.evaluate(PAINT)["p"]; c.close(); return v

    real = paint_under(BIG, lambda c, pp: c.set_offline(True))
    ck(real is not None and real < 2000,
       "harness: real offline mode measures a prompt paint on a fixed page (%s ms)" % real)

    ctl = paint_under(tmp, lambda c, pp: c.set_offline(True))
    broad = paint_under(tmp, lambda c, pp: (pp.route("http://**", lambda r: r.abort("namenotresolved")),
                                            pp.route("https://**", lambda r: r.abort("namenotresolved"))))
    ck(ctl is not None, "harness: a render-blocking page paints fine under real offline mode (%s ms)" % ctl)
    ck(broad is None or (ctl is not None and broad > ctl * 5),
       "harness: the same page measured through a broad interceptor is distorted, "
       "which is why the audit does not use one (offline %s ms vs intercepted %s ms)" % (ctl, broad))
    b.close()

print("---"); print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
