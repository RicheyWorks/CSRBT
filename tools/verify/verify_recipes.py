# -*- coding: utf-8 -*-
"""Verifies docs/soil-recipes.html — the transcribed grower soil recipes.

Two things have to hold on a page whose whole value is fidelity to a source.

1. THE SCALER IS ARITHMETIC, so it is checked by recomputation, not by a table
   of expected strings (ADR-041). Every quantity is read off the page at each
   multiplier and compared against the recipe's own base number times that
   multiplier -- with the unit conversions undone first, since the page shows
   3 tsp where the data says 1/16 cup.

2. TRANSCRIPTION FIDELITY. At 1x every quantity must read EXACTLY as its source
   printed it, ranges included. A published "25-50 lb" that scales to a single
   "6.3 lb" has silently halved the recipe and invented a precision the source
   never gave; both ends have to survive.

Run:  python3 tools/verify/verify_recipes.py
"""
import io, json, os, re, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "docs", "soil-recipes.html").replace(os.sep, "/")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

# cup -> the unit the page will actually print at this size
def to_cups(txt):
    """Parse a printed quantity back into cups. Returns None for other units."""
    m = re.match(r"^([\d.]+)\s*(cups?|tbsp|tsp)$", txt.strip())
    if not m: return None
    v, u = float(m.group(1)), m.group(2)
    return v if u.startswith("cup") else (v / 16.0 if u == "tbsp" else v / 48.0)

def to_number(txt):
    m = re.match(r"^([\d.]+)", txt.strip())
    return float(m.group(1)) if m else None

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 900})
    ctx.set_offline(True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(PAGE, wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(700)
    ck("the page loads with no script error", not errs, errs[:2])

    data = pg.evaluate("()=>RECIPES.map(r=>({id:r.id,name:r.name,url:r.url,who:r.who,"
                       "strength:r.strength,cook:r.cook,warn:r.warn,"
                       "items:r.items,base:r.base}))")
    ck("all four recipes are present", len(data) == 4, len(data))

    # ---- provenance: a transcription without its source is not one ----
    for r in data:
        ck("%s: names an author" % r["id"], bool(r["who"]) and len(r["who"]) > 12, r["who"])
        ck("%s: carries a source URL" % r["id"],
           r["url"].startswith("https://"), r["url"])
        ck("%s: states a cook time" % r["id"], bool(r["cook"]), r["cook"])
        ck("%s: names its own failure mode" % r["id"], bool(r["warn"]), r["warn"])

    body = pg.inner_text("body")
    ck("the page says outright these are not agronomic standards",
       "not agronomy" in body.lower() or "not an agronomic standard" in body.lower(), body[:80])
    ck("the page states no soil test, control or replication stands behind them",
       "replicat" in body.lower() and "control" in body.lower(), "")
    ck("the Subcool card carries the do-not-plant-into-it warning",
       "burn" in body.lower() and "clone" in body.lower(), "")

    def click_scale(sym):
        pg.evaluate("""(s)=>[...document.querySelectorAll('#recScale button')]
            .find(b=>b.textContent.indexOf(s)>=0).click()""", sym)
        pg.wait_for_timeout(300)

    def click_recipe(name):
        pg.evaluate("""(n)=>[...document.querySelectorAll('#recPick button')]
            .find(b=>b.textContent.indexOf(n)>=0).click()""", name)
        pg.wait_for_timeout(300)

    def printed(label):
        return pg.evaluate("""(l)=>{const r=[...document.querySelectorAll('#recOut .ing tr')]
            .find(tr=>tr.textContent.includes(l));
            return r?r.querySelector('.q').textContent.trim():null;}""", label)

    MULTS = [("¼", 0.25), ("½", 0.5), ("1×", 1.0), ("2×", 2.0), ("4×", 4.0)]

    for r in data:
        click_recipe(r["name"].split("'")[0].split(" ")[0])
        # ---- 1x must be the published string, verbatim ----
        click_scale("1×")
        for it in r["items"]:
            got = printed(it[1])
            ck("%s @1x: %r reads exactly as published" % (r["id"], it[1][:22]),
               got == it[0], (got, it[0]))

        # ---- scaled values must be the base number times the multiplier ----
        for sym, m in MULTS:
            if m == 1.0: continue
            click_scale(sym)
            for it in r["items"]:
                base, unit = it[2], it[3]
                hi = it[5] if len(it) > 5 else None
                got = printed(it[1])
                if got is None:
                    ck("%s @%s: %r still on the page" % (r["id"], sym, it[1][:20]), False, None)
                    continue
                if hi is not None:
                    ck("%s @%s: %r keeps BOTH ends of its published range"
                       % (r["id"], sym, it[1][:20]), "–" in got, got)
                    got = got.split("–")[-1]          # check the high end
                    base = hi
                if unit == "cup":
                    v = to_cups(got)
                    ck("%s @%s: %r = %g cup × %g" % (r["id"], sym, it[1][:20], base, m),
                       v is not None and abs(v - base * m) < 1e-3 * max(1, base * m),
                       (got, base * m))
                elif unit in ("lb", "gal", "tbsp"):
                    v = to_number(got)
                    want = base * m
                    if unit == "tbsp" and want < 1:      # printed as tsp
                        want *= 3
                    ck("%s @%s: %r = %g %s × %g" % (r["id"], sym, it[1][:20], base, unit, m),
                       v is not None and abs(v - want) <= 0.06 * max(1, want), (got, want))

    # ---- a measurable answer, not a fraction of a spoon ----
    click_recipe("Subcool")
    click_scale("¼")
    hum = printed("humic acid")
    ck("a quarter of 2 tbsp is printed in teaspoons, not half a tablespoon",
       "tsp" in hum, hum)

    # ---- the export, held to a port of the page's own scaling rules (ADR-176) ----
    # audit_outputs found Copy the list and the print read by nothing. The task
    # now presses both on Coot's quarter batch and holds the list byte for
    # byte; the literal is pinned HERE from the recipe data the page carries
    # and the rules its prose states: at 1x the published wording, scaled
    # values in a form a person can measure (a cup below one cup in tbsp, a
    # tablespoon below one in tsp, to one decimal), a published range keeping
    # both ends and dropping the first unit only when both agree.
    def round1(x):
        v = round(x * 10) / 10.0
        return ("%d" % v) if v == int(v) else ("%g" % v)
    def fmt_tbsp(t):
        return round1(t * 3) + " tsp" if t < 1 else round1(t) + " tbsp"
    def fmt_cup(c):
        if c <= 0: return "0"
        tb = c * 16
        if tb < 1: return fmt_tbsp(tb)
        if c < 1: return round1(tb) + " tbsp"
        return round1(c) + " cup" + ("s" if c >= 2 else "")
    def scale_one(n, unit, m):
        v = n * m
        if unit == "cup": return fmt_cup(v)
        if unit == "tbsp": return fmt_tbsp(v)
        if unit == "lb": return round1(v) + " lb"
        if unit == "gal": return round1(v) + " gal"
        if unit == "bags": return round1(v) + " bag" + ("s" if v >= 2 else "")
        if unit == "part": return "1 part"
        if unit == "pct": return "%d%% by volume" % round(v)
        return round1(v) + " " + unit
    def scale_qty(it, m):
        published, n, unit = it[0], it[2], it[3]
        hi = it[5] if len(it) > 5 else None
        if m == 1 and published: return published
        if hi is not None:
            a, b = scale_one(n, unit, m), scale_one(hi, unit, m)
            ua = re.sub(r"s$", "", re.sub(r"^[\d.]+\s*", "", a)); ub = re.sub(r"s$", "", re.sub(r"^[\d.]+\s*", "", b))
            return (re.sub(r"\s*[a-z]+s?$", "", a, flags=re.I) + "–" + b) if ua == ub else a + "–" + b
        return scale_one(n, unit, m)
    def export_of(r, m):
        L = ["# " + r["name"] + (("  (%g× batch)" % m) if m != 1 else ""), "# " + r["who"],
             "# source: " + r["url"], "# batch: " + r["batch"], "", "## base"]
        L += ["  " + scale_qty(it, m) + "  " + it[1] for it in r["base"]]
        L += ["", "## amendments"] + ["  " + scale_qty(it, m) + "  " + it[1] for it in r["items"]]
        L += ["", "## cook", "  " + r["cook"]]
        if r.get("warn"): L += ["", "## watch out", "  " + r["warn"]]
        L += ["", "# Transcribed from the source above without adjustment. A grower recipe,",
              "# not an agronomic standard: no soil test, no control, no replication."]
        return "\n".join(L)
    full = pg.evaluate("()=>RECIPES.map(r=>({id:r.id,name:r.name,url:r.url,who:r.who,batch:r.batch,"
                       "cook:r.cook,warn:r.warn,items:r.items,base:r.base}))")
    coot = next(r for r in full if r["id"] == "coot")
    click_recipe("Coot"); click_scale("¼")
    want_q = export_of(coot, 0.25)
    ck("Coot's quarter batch exports exactly what the port of the page's scaling rules says",
       pg.inner_text("#recExport") == want_q, pg.inner_text("#recExport")[:200])
    import json as _json
    _TASK = os.path.join(ROOT, "tools", "tasks", "page-soil-recipes-scaling.json")
    _task = _json.load(io.open(_TASK, encoding="utf-8")) if os.path.isfile(_TASK) else {"steps": []}
    _steps = dict((st["id"], st) for st in _task["steps"])
    ck("the task holds the copied list to that same text, byte for byte",
       _steps.get("g176-list", {}).get("expect", {}).get("output.payloads.0.text") == want_q
       and _steps.get("g176-list", {}).get("expect", {}).get("output.payloads.0.k") == "clipboard", _steps.get("g176-list"))
    ck("the task holds the print to a print, and nothing else leaving with it",
       _steps.get("g176-printed", {}).get("expect", {}).get("output.payloads.0.k") == "print"
       and _steps.get("g176-printed", {}).get("expect", {}).get("output.payloads.1") == {"op": "exists", "value": False},
       _steps.get("g176-printed"))

    # ---- the export carries the provenance ----
    click_recipe("Subcool"); click_scale("1×")
    exp = pg.inner_text("#recExport")
    ck("the export names the author", "SubCool" in exp, exp[:60])
    ck("the export carries the source URL", "https://" in exp, exp[:120])
    ck("the export repeats that this is a grower recipe, not a standard",
       "not an agronomic standard" in exp, exp[-200:])

    ck("no script errors after driving every control", not errs, errs[:2])
    b.close()

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
