# -*- coding: utf-8 -*-
"""The app-wide route contract: every place in the kit is named, reachable, and covered.

THE DEFECT THIS EXISTS FOR

douglas-explorer.html was added to docs/. The harness ran over forty pages. The
kit had forty-one. Every suite was green. Coverage had quietly become "whatever
the last run happened to visit", and nothing in the kit could tell the difference
between a page that passed and a page that was never opened -- the same shape as
ADR-106's audit that reported clean having examined nothing, one level up.

So this suite holds the kit to a published list (tools/routes.json):

  1. EVERY page in docs/ is routed. A new page fails until it is in the table.
  2. Route ids are globally unique -- an id that names two places is not an address.
  3. Every route RESOLVES ATOMICALLY in a real browser, and resolution refuses
     three ways: MISSING, AMBIGUOUS, DISABLED. A fourth, UNCONFIRMED, catches the
     click that happened and changed nothing.
  4. EVERY routed page appears in the harness ledger. This is the ratchet: an
     uncovered page fails the suite instead of passing by omission.
  5. The kit drives at least CONTROL_FLOOR affordances, so coverage cannot be
     quietly narrowed while still reporting green.
  6. The three rejection modes are CANARIED against seeded faults, because a
     refusal nobody has watched fire is a refusal nobody knows the shape of.

Run:  python3 tools/verify/verify_routes.py
"""
import glob, io, json, os, sys, tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import routes as R                                             # noqa: E402
from playwright.sync_api import sync_playwright                # noqa: E402

DOCS = os.path.join(ROOT, "docs")
LEDGER = os.path.join(ROOT, "tools", "harness_ledger.json")
TABLE = os.path.join(ROOT, "tools", "routes.json")

# The floor ratchets: coverage may grow, never quietly shrink.
CONTROL_FLOOR = 3000

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


def url_for(page):
    return Path(os.path.join(DOCS, page)).as_uri()


# ── 1-2. the table itself ────────────────────────────────────────────────────
ck("the route table is published", os.path.isfile(TABLE), TABLE)
table = json.load(io.open(TABLE, encoding="utf-8"))["routes"] if os.path.isfile(TABLE) else []
listed_pages = {r["page"] for r in table}
docs_pages = {os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "*.html"))}

ck("every page in docs/ is routed -- a new page cannot arrive unlisted",
   docs_pages <= listed_pages, sorted(docs_pages - listed_pages))
ck("and every routed page exists", listed_pages <= docs_pages, sorted(listed_pages - docs_pages))

ids = [r["id"] for r in table]
ck("route ids are globally unique", len(ids) == len(set(ids)),
   sorted({i for i in ids if ids.count(i) > 1}))
ck("the published table matches what the pages actually declare",
   ids == [r["id"] for r in R.table()], "routes.json is stale -- rerun tools/routes.py")

# ── 4-5. the coverage ratchet ────────────────────────────────────────────────
led = json.load(io.open(LEDGER, encoding="utf-8")) if os.path.isfile(LEDGER) else {}
covered = {p["page"] for p in led.get("pages", [])} if isinstance(led.get("pages"), list) \
    else set(led.get("pages", {}))
ck("the harness ledger exists", bool(led), LEDGER)
ck("EVERY routed page is covered by the harness -- uncovered fails, it does not pass quietly",
   listed_pages <= covered, sorted(listed_pages - covered))
discovered = led.get("totals", {}).get("discovered", 0)
ck("the kit drives at least %d affordances (ratchet)" % CONTROL_FLOOR,
   discovered >= CONTROL_FLOOR, discovered)
ck("the harness accounts for every affordance it discovered",
   discovered == sum(led.get("totals", {}).get(k, 0)
                     for k in ("driven", "dead", "hidden", "failed", "excluded")),
   led.get("totals"))

# ── 3 + 6. atomic resolution, and the canaries ───────────────────────────────
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 900, "height": 1000})
    pg.set_default_timeout(15000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())

    failures = []
    for r in table:
        try:
            R.navigate(pg, r, url_for)
        except R.RouteError as e:
            failures.append(str(e))
        except Exception as e:                                  # a crash is also a failure
            failures.append("%s: %s" % (r["id"], str(e)[:90]))
    ck("all %d routes resolve atomically and land where they say" % len(table),
       not failures, failures[:5])

    # The canaries. Each seeds one fault into a real page and requires the matching refusal.
    src = io.open(os.path.join(DOCS, "collection-sheet.html"), encoding="utf-8").read()
    with tempfile.TemporaryDirectory() as d:
        def seeded(name, mutate):
            q = os.path.join(d, name)
            io.open(q, "w", encoding="utf-8", newline="\n").write(mutate(src))
            return q

        def try_route(path, pane, expect):
            page = os.path.basename(path)
            route = {"id": "%s#%s" % (page, pane), "page": page, "pane": pane,
                     "selector": '.tab[data-pane="%s"]' % pane, "kind": "nested"}
            try:
                R.navigate(pg, route, lambda _p: Path(path).as_uri())
                return "no refusal"
            except R.RouteError as e:
                return str(e).split()[0]

        got = try_route(seeded("missing.html",
                               lambda s: s.replace('data-pane="p-vou"', 'data-pane="p-GONE"', 1)),
                        "p-vou", "MISSING")
        ck("canary: a route whose tab is absent is refused MISSING", got == "MISSING", got)

        got = try_route(seeded("ambiguous.html", lambda s: s.replace(
            '<button class="tab" data-pane="p-vou" type="button">',
            '<button class="tab" data-pane="p-vou" type="button">Vouchers</button>'
            '<button class="tab" data-pane="p-vou" type="button">', 1)),
            "p-vou", "AMBIGUOUS")
        ck("canary: a duplicated tab is refused AMBIGUOUS, never resolved to the first match",
           got == "AMBIGUOUS", got)

        got = try_route(seeded("hidden.html", lambda s: s.replace(
            '<button class="tab" data-pane="p-vou"',
            '<button class="tab" style="display:none" data-pane="p-vou"', 1)),
            "p-vou", "DISABLED")
        ck("canary: a tab a finger cannot reach is refused DISABLED", got == "DISABLED", got)

        got = try_route(seeded("inert.html", lambda s: s.replace(
            '<button class="tab" data-pane="p-vou"',
            '<button class="tab" data-pane="p-vou" onclick="event.stopImmediatePropagation()"', 1)),
            "p-vou", "UNCONFIRMED")
        ck("canary: a tab that clicks but does not switch the pane is refused UNCONFIRMED",
           got == "UNCONFIRMED", got)
    b.close()

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
