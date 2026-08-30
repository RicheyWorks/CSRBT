# -*- coding: utf-8 -*-
"""The kit's route table, published rather than rediscovered.

WHY THIS EXISTS

tools/harness.py discovers what is on a page and drives it, and it accounts for
every affordance it finds. What neither it nor any per-page suite could answer
was the question one level up: *what are all the places in this kit?* Coverage
was therefore whatever the last run happened to visit. It failed exactly the way
that arrangement always fails -- douglas-explorer.html was added, the harness ran
over forty pages, the kit had forty-one, and the suite was green. A page nobody
had listed was covered by nobody, and nothing said so.

So the route table is a published artifact with a name for every reachable
place, and tools/verify/verify_routes.py holds the kit to it: a page that is not
routed, or a route that is not covered, FAILS. New pages cannot arrive quietly.

WHAT A ROUTE IS

    page.html            the page in its landing state (a primary route)
    page.html#pane-id    a pane reached by pressing its tab (a nested route)

Panes follow the kit's own convention -- `.tab[data-pane="x"]` reveals
`.pane#x`, and exactly one pane is visible at a time -- which is the same
convention harness.py drives and the per-page suites assert.

ATOMIC RESOLUTION

navigate() is exact and refuses three ways, because a navigation that half
succeeds is worse than one that fails:

    MISSING    no element matches the route's selector
    AMBIGUOUS  more than one does -- a selector that is not unique is not an
               address, and acting on "the first match" is how a harness
               silently drives the wrong control
    DISABLED   the target exists but cannot be operated

and after the click it CONFIRMS the pane actually became the visible one rather
than trusting that the click meant anything.

    python3 tools/routes.py            # publish tools/routes.json
    python3 tools/routes.py --check    # report without writing
"""
import argparse, glob, io, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
OUT = os.path.join(ROOT, "tools", "routes.json")

TAB = re.compile(r'<[^>]*class="[^"]*\btab\b[^"]*"[^>]*data-pane="([A-Za-z0-9_-]+)"[^>]*>(.*?)</',
                 re.S | re.I)
TAB_ALT = re.compile(r'<[^>]*data-pane="([A-Za-z0-9_-]+)"[^>]*class="[^"]*\btab\b[^"]*"[^>]*>(.*?)</',
                     re.S | re.I)
TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def pages():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "*.html")))


def discover(name):
    """Routes for one page: the page itself, then one per pane tab, in document order."""
    src = io.open(os.path.join(DOCS, name), encoding="utf-8").read()
    t = TITLE.search(src)
    title = TAG.sub("", t.group(1)).strip() if t else name
    out = [{"id": name, "page": name, "pane": None, "selector": None, "label": title,
            "kind": "primary"}]
    seen = []
    for m in list(TAB.finditer(src)) + list(TAB_ALT.finditer(src)):
        pane, label = m.group(1), TAG.sub("", m.group(2)).strip()
        if pane in seen:
            continue
        seen.append(pane)
        out.append({"id": "%s#%s" % (name, pane), "page": name, "pane": pane,
                    "selector": '.tab[data-pane="%s"]' % pane,
                    "label": label or pane, "kind": "nested"})
    return out


def table():
    routes = []
    for n in pages():
        routes.extend(discover(n))
    return routes


# ── atomic navigation ────────────────────────────────────────────────────────

class RouteError(RuntimeError):
    """A navigation that could not be performed exactly."""


def navigate(pg, route, url_for):
    """Open a route exactly, or raise RouteError saying which of the three ways it failed.

    Returns the pane now showing (None for a primary route).
    """
    if pg.url != url_for(route["page"]):
        pg.goto(url_for(route["page"]), wait_until="domcontentloaded")
        pg.wait_for_timeout(60)
    if not route["pane"]:
        return None
    els = pg.query_selector_all(route["selector"])
    if not els:
        raise RouteError("MISSING %s: no element matches %s" % (route["id"], route["selector"]))
    if len(els) > 1:
        raise RouteError("AMBIGUOUS %s: %d elements match %s -- a selector that is not unique "
                         "is not an address" % (route["id"], len(els), route["selector"]))
    el = els[0]
    if not el.is_enabled():
        raise RouteError("DISABLED %s: the tab exists but cannot be operated" % route["id"])
    if not el.is_visible():
        raise RouteError("DISABLED %s: the tab exists but is not visible" % route["id"])
    el.click(timeout=8000)
    pg.wait_for_timeout(60)
    active = pg.evaluate(
        "() => { const p = document.querySelector('.pane.on'); return p ? p.id : null; }")
    if active != route["pane"]:
        raise RouteError("UNCONFIRMED %s: clicked the tab but the visible pane is %r"
                         % (route["id"], active))
    return active


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    a = ap.parse_args(argv)

    routes = table()
    ids = [r["id"] for r in routes]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    primary = [r for r in routes if r["kind"] == "primary"]
    nested = [r for r in routes if r["kind"] == "nested"]

    print("routes: %d (%d primary, %d nested) over %d page(s)"
          % (len(routes), len(primary), len(nested), len(pages())))
    if dupes:
        print("DUPLICATE ROUTE IDS: %s" % dupes)
        return 1
    by_page = {}
    for r in nested:
        by_page.setdefault(r["page"], []).append(r["pane"])
    for n in sorted(by_page):
        print("  %-30s %s" % (n, " ".join(by_page[n])))

    if a.check:
        return 0
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(
        {"_comment": ("The kit's route table. A route is a reachable place: a page, or a pane "
                      "within one. Published so coverage can be checked against a list rather "
                      "than against whatever the last run happened to visit -- see "
                      "tools/verify/verify_routes.py, which fails when a page is unrouted or a "
                      "route uncovered."),
         "at": int(time.time()), "count": len(routes), "routes": routes},
        indent=1, sort_keys=True) + "\n")
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
