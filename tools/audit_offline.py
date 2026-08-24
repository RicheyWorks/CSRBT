# -*- coding: utf-8 -*-
"""Does the kit actually work in a field with no signal?

ADR-031 lists this as an inherited, non-negotiable constraint: "pages must work
offline in a field with no signal." Every page is a single self-contained file,
so the constraint looks satisfied by construction -- but every page also opens
with a <link rel=stylesheet> to a webfont CDN, and nobody had ever loaded one of
these pages with the network actually gone.

Four things measured, in the order they hurt in the field:

  STALL     a render-blocking external stylesheet. The nasty case is not "no
            network" -- DNS fails fast and the page paints. It is one bar of
            signal, where the request hangs and the browser holds the paint. This
            measures time-to-first-paint against a stylesheet that never answers,
            which is the phone-in-a-wet-meadow case.
  ERROR     a JS error thrown when an external resource is missing.
  FALLBACK  a font-family whose only entry is a webfont. Offline that resolves to
            the browser default, whose metrics are nothing like the intended
            face, and the layout it was tuned for goes with it.
  OVERFLOW  content past the viewport once fallback metrics apply. The touch and
            contrast audits already run with fonts aborted, so this is the one
            offline-specific layout check they do not cover.

Also prints every external host the kit reaches for, because a self-contained
page should know its own dependencies and nobody had written them down.

Run:  python3 tools/audit_offline.py
Exits non-zero on ERROR, FALLBACK or OVERFLOW. STALL is reported with its
measured seconds and does not fail the build on its own -- see the note it
prints, the fix is a judgement about how the kit wants to load.
"""
import glob, os, re, sys, collections
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs") + os.sep

# Faces the browser always has. A stack ending in one of these survives offline.
SAFE = re.compile(
    r"\b(serif|sans-serif|monospace|cursive|fantasy|system-ui|ui-monospace|ui-serif|"
    r"ui-sans-serif|-apple-system|BlinkMacSystemFont|Segoe UI|Roboto|Helvetica|Arial|"
    r"Georgia|Times New Roman|Courier|Menlo|Consolas|Monaco|Verdana|Tahoma|"
    r"SFMono-Regular|SF Mono|JetBrains Mono|emoji|"
    r"inherit|initial|unset|revert|revert-layer)\b", re.I)

FONT_DECL = re.compile(r"font-family\s*:\s*([^;}]+)", re.I)
FONT_SHORT = re.compile(r"(?<!-)\bfont\s*:\s*([^;}]+)", re.I)


def stacks(css):
    """Every font stack the page declares, as written."""
    out = []
    for m in FONT_DECL.finditer(css):
        out.append(m.group(1))
    for m in FONT_SHORT.finditer(css):
        v = m.group(1)
        # the shorthand's family list is everything after the size/line-height
        parts = v.split()
        if len(parts) > 1:
            out.append(" ".join(parts[1:]))
    return out


def main():
    pages = sorted(glob.glob(DOCS + "*.html"))
    hosts = collections.Counter()
    rows = []
    hard = 0

    with sync_playwright() as p:
        b = p.chromium.launch()

        for path in pages:
            nm = os.path.basename(path)
            src = open(path, encoding="utf-8").read()

            # ---- static: font stacks that have no offline fallback ----------
            bad_stacks = []
            for s in stacks(src):
                s = s.strip()
                if not s or "var(" in s:
                    continue                       # a token; checked where it is defined
                if SAFE.search(s):
                    continue
                bad_stacks.append(re.sub(r"\s+", " ", s)[:52])
            bad_stacks = sorted(set(bad_stacks))

            # every external host this page reaches for, from the source
            for m in re.finditer(r'(?:href|src)="(https?://[^"/]+)', src):
                h = m.group(1)
                if "w3.org" in h:                  # SVG/XML namespaces, never fetched
                    continue
                hosts[h] += 1

            # Only genuinely render-blocking ones. A link carrying media="print"
            # is fetched without holding the paint, and a copy inside <noscript>
            # applies only with scripting off -- counting either would report a
            # problem the page has already solved.
            body_only = re.sub(r"<noscript>.*?</noscript>", "", src, flags=re.S | re.I)
            blocking = 0
            for tag in re.findall(r'<link[^>]*>', body_only, re.I):
                if not re.search(r'rel=["\']?stylesheet', tag, re.I):
                    continue
                if not re.search(r'href="https?://', tag, re.I):
                    continue
                m = re.search(r'media=["\']([^"\']+)', tag, re.I)
                if m and "print" in m.group(1).lower() and "all" not in m.group(1).lower():
                    continue
                blocking += 1

            # ---- live: load with the whole network gone --------------------
            # Use the browser's real offline mode, not a route interceptor.
            # Two earlier versions of this measured paint through a broad
            # "https://**" route and both lied: the interception itself holds
            # first paint, so the audit reported a 12-second blank screen that
            # no real device ever sees. Measured side by side on the same page:
            # narrow route 44 ms, real offline 28 ms, broad route never paints.
            # If you are testing what happens with no network, turn the network
            # off; do not build a model of it.
            ctx = b.new_context(viewport={"width": 390, "height": 900})
            ctx.set_offline(True)
            pg = ctx.new_page()
            pg.set_default_timeout(20000)
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            try:
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(800)
                over = pg.evaluate(
                    "()=>Math.max(document.documentElement.scrollWidth,"
                    " document.body?document.body.scrollWidth:0)")
                painted = pg.evaluate(
                    "()=>{const t=performance.getEntriesByType('paint')"
                    ".find(e=>e.name==='first-contentful-paint'); return t?Math.round(t.startTime):null;}")
            except Exception as exc:
                rows.append((nm, None, str(exc)[:60])); ctx.close(); continue
            ctx.close()

            over_by = max(0, over - 391)
            n = len(errs) + len(bad_stacks) + (1 if over_by else 0)
            hard += n
            rows.append((nm, dict(errs=errs[:2], stacks=bad_stacks, over=over_by,
                                  blocking=blocking, paint=painted), None))

        # ---- the stall case, measured once on the worst page ---------------
        # A request that never answers, which is the one-bar-of-signal case and
        # the one that actually strands you. Navigate with commit (do not wait
        # for the load event, which is exactly what the hang delays), then ask
        # the page whether it ever painted.
        worst = max(pages, key=os.path.getsize)
        # Narrow routes here on purpose: a hanging request has to be simulated,
        # there is no browser switch for "connected but silent", and a narrow
        # pattern was verified not to distort paint (44 ms vs 28 ms offline).
        pg = b.new_page(viewport={"width": 390, "height": 900})
        pg.route("**://fonts.googleapis.com/**", lambda r: None)   # never answer, never fail
        pg.route("**://fonts.gstatic.com/**", lambda r: None)
        try:
            pg.goto("file://" + worst, wait_until="commit", timeout=20000)
            pg.wait_for_timeout(9000)
            stall = pg.evaluate(
                "()=>{const t=performance.getEntriesByType('paint')"
                ".find(e=>e.name==='first-contentful-paint');"
                " const txt=(document.body&&document.body.innerText||'').trim().length;"
                " return {paint:t?Math.round(t.startTime):null, visibleChars:txt};}")
            stall = ("no paint after 9 s -- the page is blank while the request hangs"
                     if stall["paint"] is None or stall["visibleChars"] < 50
                     else "painted at %d ms with %d characters visible"
                          % (stall["paint"], stall["visibleChars"]))
        except Exception as exc:
            stall = "navigation itself blocked: " + str(exc)[:50]
        # Release the routes that were deliberately never answered before closing,
        # or Playwright prints a CancelledError traceback at teardown that reads
        # like a failure and is only bookkeeping.
        try:
            pg.unroute("**://fonts.googleapis.com/**")
            pg.unroute("**://fonts.gstatic.com/**")
        except Exception:
            pass
        pg.close()
        b.close()

    print("%-30s %6s %6s %6s %8s" % ("PAGE", "ERR", "FONT", "OVER", "PAINT ms"))
    print("-" * 74)
    for nm, r, err in rows:
        if err:
            print("%-30s LOAD FAIL %s" % (nm, err)); continue
        flags = (len(r["errs"]) or "-", len(r["stacks"]) or "-", r["over"] or "-",
                 r["paint"] if r["paint"] is not None else "?")
        print("%-30s %6s %6s %6s %8s" % (nm, *flags))
        for e in r["errs"]:
            print("%-32s   js error   %s" % ("", e[:60]))
        for s in r["stacks"]:
            print("%-32s   no fallback  %s" % ("", s))
    print("-" * 74)

    print("external hosts this kit reaches for:")
    for h, c in hosts.most_common():
        print("   %-42s %d reference(s)" % (h, c))
    blocking_total = sum(r["blocking"] for _, r, e in rows if r)
    print()
    print("render-blocking external stylesheets: %d across %d pages%s"
          % (blocking_total, sum(1 for _, r, e in rows if r and r["blocking"]),
             "   (a webfont link deferred with media=print is not counted)" if not blocking_total else ""))
    ok_rows = [r for _, r, e in rows if r]
    paints = [r["paint"] for r in ok_rows if r["paint"] is not None]
    print("first paint with the network gone: %s"
          % ("%d-%d ms across %d pages" % (min(paints), max(paints), len(paints))
             if paints else "not measured"))
    print("first paint on the largest page, request hangs:     %s" % stall)
    print()
    print("hard faults (js errors + unfallback-ed fonts + overflow): %d" % hard)
    print("%d/%d pages clear" % (len(ok_rows) - sum(1 for r in ok_rows
          if r["errs"] or r["stacks"] or r["over"]), len(ok_rows)))
    return hard


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
