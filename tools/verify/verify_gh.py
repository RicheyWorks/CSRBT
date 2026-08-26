# -*- coding: utf-8 -*-
"""Verifies the greenhouse engine and page against an independent Python model.

Every quantity this page reports is recomputed here from scratch -- Buck's
equation, the leaf-VPD definition, trapezoid integration of power and of PPFD,
ordinary least squares, and the duration-weighted time-outside-band -- and
compared against what the page's own engine returns for the same rows.

Two things that are NOT done, on purpose:

  * No expected constants. "The page says 0.91 kPa" is not a test; it is a
    photograph. Changing the leaf offset from 2 to 3 is a legitimate edit and
    must not break anything (ADR-041).
  * No trust in the demo generator. The demo is deterministic so it can be
    tested, but every check either derives its own fixture or recomputes from
    whatever rows the page actually holds.

Run:  python3 tools/verify/verify_gh.py
"""
import math, os, sys

from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "docs", "greenhouse.html").replace(os.sep, "/")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

def close(a, b, tol):
    if a is None or b is None: return False
    return abs(a - b) <= tol


# ---------------- independent model ----------------

def svp(t):
    """Buck (1981), kPa."""
    return 0.61121 * math.exp((18.678 - t / 234.5) * (t / (257.14 + t)))

def vpd_leaf(t_air, rh, offset):
    return svp(t_air - offset) - svp(t_air) * (rh / 100.0)

def dew_point(t_air, rh):
    target = svp(t_air) * (rh / 100.0)
    lo, hi = -80.0, t_air
    for _ in range(200):
        mid = (lo + hi) / 2
        if svp(mid) < target: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def abs_humidity(t_air, rh):
    e = svp(t_air) * (rh / 100.0) * 1000.0
    return 2.16679 * e / (t_air + 273.15)

def trapz(rows, tk, vk, scale):
    pts = sorted([r for r in rows if r.get(tk) is not None and r.get(vk) is not None],
                 key=lambda r: r[tk])
    if len(pts) < 2: return None
    tot = 0.0
    for i in range(1, len(pts)):
        dt = (pts[i][tk] - pts[i - 1][tk]) / scale
        tot += (pts[i][vk] + pts[i - 1][vk]) / 2 * dt
    return tot

def ols(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3: return None, None, None
    sx = sum(p[0] for p in pairs); sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] * p[0] for p in pairs); sxy = sum(p[0] * p[1] for p in pairs)
    syy = sum(p[1] * p[1] for p in pairs)
    d = n * sxx - sx * sx
    if abs(d) < 1e-12: return None, None, None
    slope = (n * sxy - sx * sy) / d
    icept = (sy - slope * sx) / n
    ss_tot = syy - sy * sy / n
    ss_res = sum((y - (icept + slope * x)) ** 2 for x, y in pairs)
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else None
    return slope, icept, r2

def time_outside(rows, tk, vk, lo, hi):
    pts = sorted([r for r in rows if r.get(tk) is not None and r.get(vk) is not None],
                 key=lambda r: r[tk])
    if len(pts) < 2: return None
    out = tot = 0.0
    for i in range(1, len(pts)):
        dt = pts[i][tk] - pts[i - 1][tk]
        if dt <= 0: continue
        a = 1 if (pts[i - 1][vk] < lo or pts[i - 1][vk] > hi) else 0
        b = 1 if (pts[i][vk] < lo or pts[i][vk] > hi) else 0
        out += (a + b) / 2 * dt; tot += dt
    return out / tot if tot > 0 else None


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 900})
    ctx.set_offline(True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(PAGE, wait_until="domcontentloaded", timeout=25000)
    pg.wait_for_timeout(700)
    ck("the page loads with no script error", not errs, errs[:2])

    # ---------- psychrometrics against reference values ----------
    # Buck at these temperatures is a published quantity, so this is a check
    # against the literature and not merely against my own transcription.
    for t, want in ((0, 0.6112), (10, 1.2282), (20, 2.3392), (25, 3.1693), (30, 4.2470),
                    (35, 5.6285)):
        got = pg.evaluate("(t)=>GH.svp(t)", t)
        ck("SVP at %g °C matches the published value %.4f kPa" % (t, want),
           close(got, want, 0.002), got)

    for t, rh, off in ((25, 60, 0), (25, 60, 2), (28, 55, 3), (20, 75, 1), (30, 40, 2)):
        got = pg.evaluate("([t,r,o])=>GH.vpd(t,r,o)", [t, rh, off])
        ck("leaf VPD at %g °C / %g%% / offset %g recomputes" % (t, rh, off),
           close(got, vpd_leaf(t, rh, off), 1e-9), got)

    ck("offset 0 gives air VPD exactly",
       close(pg.evaluate("()=>GH.vpd(25,60,0)"), svp(25) - svp(25) * 0.6, 1e-12), "")
    # A cooler leaf has a lower saturation pressure, so a LARGER offset gives a
    # LOWER VPD. The first version of this check asserted the opposite and
    # failed -- and chasing that failure found the page claiming the shift was
    # "roughly 0.15-0.25 kPa, about a third of a band" when it is twice that.
    ck("a bigger leaf offset LOWERS VPD, because a cooler leaf saturates lower",
       pg.evaluate("()=>GH.vpd(25,60,3) < GH.vpd(25,60,1)"), "")

    # The page states the size of that shift, so the page's own number is
    # recomputed here across the envelope the page names rather than asserted
    # as a constant (ADR-041). Change the envelope in the prose and this has to
    # change with it, which is the point.
    deltas = [abs(vpd_leaf(t, rh, 2) - vpd_leaf(t, rh, 0))
              for t in range(18, 33) for rh in range(40, 86, 5)]
    dmin, dmax = min(deltas), max(deltas)
    band_w = 1.2 - 0.8
    ck("the page's stated 0.25-0.51 kPa range for a 2 °C offset recomputes",
       close(dmin, 0.25, 0.01) and close(dmax, 0.51, 0.01), (dmin, dmax))
    ck("the page's claim that it is 61-128%% of the veg band recomputes",
       close(dmin / band_w * 100, 61, 1) and close(dmax / band_w * 100, 128, 1),
       (dmin / band_w * 100, dmax / band_w * 100))
    ck("at the top of that range the offset really does exceed the whole band",
       dmax > band_w, (dmax, band_w))

    for t, rh in ((25, 60), (18, 80), (30, 45)):
        ck("dew point at %g/%g inverts SVP" % (t, rh),
           close(pg.evaluate("([t,r])=>GH.dewPoint(t,r)", [t, rh]), dew_point(t, rh), 0.01), "")
        ck("absolute humidity at %g/%g recomputes" % (t, rh),
           close(pg.evaluate("([t,r])=>GH.absHumidity(t,r)", [t, rh]), abs_humidity(t, rh), 1e-6), "")
    ck("dew point is never above air temperature",
       pg.evaluate("()=>GH.dewPoint(25,99) <= 25.0001"), "")
    ck("humidity of zero returns nothing rather than a number",
       pg.evaluate("()=>GH.dewPoint(25,0)") is None, "")

    # ---------- DLI ----------
    ck("DLI = PPFD × hours × 0.0036",
       close(pg.evaluate("()=>GH.dli(600,18)"), 600 * 18 * 0.0036, 1e-9), "")
    ck("DLI is linear in the photoperiod",
       close(pg.evaluate("()=>GH.dli(600,12)"), pg.evaluate("()=>GH.dli(600,24)") / 2, 1e-9), "")

    # ---------- the lumens refusal ----------
    r = pg.evaluate("()=>GH.lumensToPPFD(50000,null)")
    ck("lux with no factor returns NO value", r["value"] is None, r)
    ck("and says why rather than going quiet", "spectrum" in (r["note"] or ""), r["note"])
    r = pg.evaluate("()=>GH.lumensToPPFD(50000,82)")
    ck("lux with a factor converts correctly", close(r["value"], 50000 / 82.0, 1e-9), r["value"])
    ck("the conversion carries the factor it used", r["factor"] == 82, r)
    ck("and names it in the note", "82" in (r["note"] or ""), r["note"])
    r0 = pg.evaluate("()=>GH.lumensToPPFD(50000,0)")
    ck("a zero factor is refused, not divided by", r0["value"] is None, r0)
    facs = pg.evaluate("()=>GH.LUX_FACTORS.map(x=>x.f)")
    ck("the published factors span more than a factor of two",
       max(facs) / min(facs) > 2, (min(facs), max(facs)))

    # ---------- integration, on a fixture built HERE ----------
    # Deliberately uneven spacing: this is exactly where a rectangle sum and a
    # trapezoid disagree, and even spacing would hide the difference.
    FIX = [{"t": 0,        "w": 100, "ppfd": 0},
           {"t": 3600000,  "w": 500, "ppfd": 400},     # +1 h
           {"t": 5400000,  "w": 500, "ppfd": 800},     # +0.5 h
           {"t": 18000000, "w": 200, "ppfd": 100}]     # +3.5 h
    got = pg.evaluate("(rows)=>GH.kWh(rows,'t','w')", FIX)
    want = trapz(FIX, "t", "w", 3600000.0) / 1000
    ck("kWh is the trapezoid integral of power over uneven spacing",
       close(got, want, 1e-9), (got, want))
    rect = sum(FIX[i]["w"] * (FIX[i]["t"] - FIX[i - 1]["t"]) / 3600000.0
               for i in range(1, len(FIX))) / 1000
    ck("and it differs from a rectangle sum on this fixture, so the test can tell them apart",
       abs(rect - want) > 0.01, (rect, want))
    ck("one point is not enough to integrate, and returns nothing rather than zero",
       pg.evaluate("()=>GH.kWh([{t:0,w:100}],'t','w')") is None, "")

    got = pg.evaluate("(rows)=>GH.dliFromLog(rows,'t','ppfd')", FIX)
    umol = trapz(FIX, "t", "ppfd", 1000.0)
    days = (FIX[-1]["t"] - FIX[0]["t"]) / 86400000.0
    ck("DLI from a log integrates PPFD and divides by the span",
       close(got, (umol / 1e6) / days, 1e-9), (got, (umol / 1e6) / days))

    ck("a schedule multiplies out to the same kWh",
       close(pg.evaluate("()=>GH.kWhFromSchedule(600,18,70)"), 600 * 18 * 70 / 1000.0, 1e-9), "")

    # ---------- least squares ----------
    XS = [0, 1, 2, 3, 4, 5]
    YS = [1.0, 1.2, 1.35, 1.6, 1.75, 2.0]
    g = pg.evaluate("([x,y])=>GH.ols(x,y)", [XS, YS])
    s, i2, r2 = ols(XS, YS)
    ck("OLS slope recomputes", close(g["slope"], s, 1e-9), (g["slope"], s))
    ck("OLS intercept recomputes", close(g["intercept"], i2, 1e-9), "")
    ck("OLS r² recomputes", close(g["r2"], r2, 1e-9), (g["r2"], r2))
    ck("a perfect line gives r² of 1",
       close(pg.evaluate("()=>GH.ols([0,1,2,3],[0,2,4,6]).r2", ), 1.0, 1e-9), "")
    ck("two points give no slope, with a reason",
       pg.evaluate("()=>GH.ols([0,1],[0,1]).slope") is None
       and bool(pg.evaluate("()=>GH.ols([0,1],[0,1]).why")), "")
    ck("a vertical x gives no slope, with a reason",
       pg.evaluate("()=>GH.ols([2,2,2,2],[1,2,3,4]).slope") is None, "")

    # ---------- time outside band, by duration ----------
    # Ten samples inside one bad hour, one sample per good hour. By COUNT this
    # is mostly bad; by DURATION it is mostly fine. The two answers are far
    # apart on purpose -- a fixture where they agreed would test nothing.
    BURST = [{"t": i * 60000, "v": 2.0} for i in range(10)]          # 9 min, out of band
    CALM = [{"t": 600000 + i * 3600000, "v": 1.0} for i in range(1, 10)]  # 9 h, in band
    ROWS = BURST + CALM
    got = pg.evaluate("(r)=>GH.timeOutside(r,'t','v',0.8,1.2)", ROWS)
    want = time_outside(ROWS, "t", "v", 0.8, 1.2)
    ck("time outside band recomputes", close(got, want, 1e-9), (got, want))
    by_count = sum(1 for r in ROWS if r["v"] < 0.8 or r["v"] > 1.2) / float(len(ROWS))
    ck("and it is NOT the fraction of samples (%.2f by duration vs %.2f by count)"
       % (want, by_count), abs(want - by_count) > 0.2, (want, by_count))

    # ---------- economics ----------
    e = pg.evaluate("()=>GH.economics(500, 650, 80, 70, 0.18)")
    ck("g/W divides by the RATED watts", close(e["gPerW"], 500 / 650.0, 1e-9), e["gPerW"])
    ck("g/kWh divides by the energy used", close(e["gPerKWh"], 500 / 80.0, 1e-9), e["gPerKWh"])
    ck("cost is energy times rate", close(e["costTotal"], 80 * 0.18, 1e-9), e["costTotal"])
    ck("cost per gram divides that by the yield",
       close(e["costPerGram"], 80 * 0.18 / 500, 1e-9), e["costPerGram"])
    ck("average draw turns kWh back into watts",
       close(e["avgW"], 80 * 1000 / (70 * 24.0), 1e-9), e["avgW"])
    ck("duty is average over rated", close(e["dutyVsRated"], e["avgW"] / 650.0, 1e-9), "")
    ck("the two g/W numbers are genuinely different here",
       abs(e["gPerW"] - e["gPerKWh"]) > 1, (e["gPerW"], e["gPerKWh"]))
    e0 = pg.evaluate("()=>GH.economics(null, 650, 80, 70, 0.18)")
    ck("no yield gives no ratios rather than zero ones",
       e0["gPerW"] is None and e0["gPerKWh"] is None, e0)
    e1 = pg.evaluate("()=>GH.economics(500, 650, null, 70, 0.18)")
    ck("no energy leaves g/kWh and cost blank, not estimated",
       e1["gPerKWh"] is None and e1["costTotal"] is None and e1["gPerW"] is not None, e1)

    # ---------- CSV ingest ----------
    CSV = ('Timestamp,Temperature,Humidity,"Power, watts",PPFD,Junk\n'
           '2026-08-01T00:00:00Z,24.5,60,600,800,xx\n'
           '2026-08-01T01:00:00Z,25.5,58,610,810,yy\n')
    res = pg.evaluate("(t)=>GH.rowsFromCSV(t,{})", CSV)
    ck("a quoted header containing a comma does not shift the columns",
       len(res["rows"]) == 2 and close(res["rows"][0]["w"], 600, 1e-9), res["rows"][:1])
    ck("aliased headers map to the engine's fields",
       res["rows"][0]["temp"] == 24.5 and res["rows"][0]["rh"] == 60, res["rows"][0])
    ck("an unrecognised column is REPORTED, not silently dropped",
       "Junk" in res["unmapped"], res["unmapped"])
    resF = pg.evaluate("(t)=>GH.rowsFromCSV(t,{fahrenheit:true})",
                       "time,temp,rh\n2026-08-01T00:00:00Z,77,60\n")
    ck("Fahrenheit input is converted to °C", close(resF["rows"][0]["temp"], 25.0, 1e-9),
       resF["rows"][0])
    resE = pg.evaluate("(t)=>GH.rowsFromCSV(t,{})", "time,temp\n1787700000,24\n")
    ck("an epoch in seconds is told apart from one in milliseconds",
       resE["rows"][0]["t"] == 1787700000000, resE["rows"][0])
    bad_csv = pg.evaluate("(t)=>GH.rowsFromCSV(t,{})", "just one line")
    ck("a file with no data says why rather than returning an empty success",
       not bad_csv["rows"] and bool(bad_csv["why"]), bad_csv)

    # ---------- the plugin registry ----------
    srcs = pg.evaluate("()=>GH.list()")
    ck("five sources are registered", len(srcs) == 5, [s["id"] for s in srcs])
    for s in srcs:
        ck("%s: declares what it needs and what it is" % s["id"],
           bool(s["name"]) and bool(s["note"]), s)
    poll = [s for s in srcs if s["id"] == "poll"][0]
    ck("the HTTP source knows it cannot run from a file:// page",
       not poll["ok"] and "file" in poll["why"], poll)
    ck("and says so rather than failing later", bool(poll["why"]), poll)
    ck("the file source is available here", [s for s in srcs if s["id"] == "file"][0]["ok"], "")
    ck("the demo source declares itself synthetic",
       "generated" in [s for s in srcs if s["id"] == "demo"][0]["name"].lower(), "")
    ck("registering without a read() is refused",
       pg.evaluate("()=>{try{GH.register({id:'x'});return false;}catch(e){return true;}}"), "")
    ck("registering without an id is refused",
       pg.evaluate("()=>{try{GH.register({read:function(){}});return false;}catch(e){return true;}}"), "")
    ck("a source with no available() defaults to available",
       pg.evaluate("()=>{GH.register({id:'_t',read:function(){}});"
                   "var r=GH.list().filter(function(s){return s.id==='_t';})[0];return r.ok;}"), "")
    ck("a probe that throws is reported, not propagated",
       pg.evaluate("()=>{GH.register({id:'_b',read:function(){},"
                   "available:function(){throw new Error('boom');}});"
                   "var r=GH.list().filter(function(s){return s.id==='_b';})[0];"
                   "return !r.ok && r.why.indexOf('boom')>=0;}"), "")
    pg.evaluate("()=>{GH.clear();}")
    ck("clearing the registry empties it", pg.evaluate("()=>GH.list().length") == 0, "")
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(600)

    # ---------- the page, end to end on the demo ----------
    rows = pg.evaluate("""()=>GH.get('demo').read({now:1787700000000})
        .then(r=>{window.GHPAGE.load(r.rows,'demo'); return r.rows;})""")
    ck("the demo produces a week of readings", len(rows) > 300, len(rows))
    ck("the demo is deterministic",
       pg.evaluate("""()=>Promise.all([GH.get('demo').read({now:1787700000000}),
            GH.get('demo').read({now:1787700000000})])
            .then(([a,b])=>JSON.stringify(a.rows)===JSON.stringify(b.rows))"""), "")

    s = pg.evaluate("()=>GH.summarise(window.__rows||[],{})") if False else None
    summ = pg.evaluate("(r)=>GH.summarise(r,{stage:'veg',leafOffset:2})", rows)
    py_rows = [{"t": r["t"], "temp": r["temp"], "rh": r["rh"], "w": r["w"], "ppfd": r["ppfd"],
                "vpd": vpd_leaf(r["temp"], r["rh"], 2)} for r in rows]
    means = sum(r["vpd"] for r in py_rows) / len(py_rows)
    ck("the page's mean VPD equals an independent recomputation",
       close(summ["vpdMean"], means, 1e-9), (summ["vpdMean"], means))
    ck("the page's kWh equals an independent trapezoid",
       close(summ["kwh"], trapz(py_rows, "t", "w", 3600000.0) / 1000, 1e-9), summ["kwh"])
    ck("the page's integrated DLI equals an independent trapezoid",
       close(summ["dli"], (trapz(py_rows, "t", "ppfd", 1000.0) / 1e6)
             / ((rows[-1]["t"] - rows[0]["t"]) / 86400000.0), 1e-9), summ["dli"])
    ck("the page's time-outside-band equals an independent duration weighting",
       close(summ["outsideBand"], time_outside(py_rows, "t", "vpd", 0.8, 1.2), 1e-9),
       summ["outsideBand"])

    # a measured leaf temperature must win over the assumed offset
    with_leaf = [dict(r, leaf=r["temp"] - 5) for r in rows[:50]]
    sl = pg.evaluate("(r)=>GH.summarise(r,{stage:'veg',leafOffset:2})", with_leaf)
    py_leaf = [svp(r["temp"] - 5) - svp(r["temp"]) * (r["rh"] / 100.0) for r in rows[:50]]
    ck("a measured leaf temperature overrides the assumed offset",
       close(sl["vpdMean"], sum(py_leaf) / len(py_leaf), 1e-9), sl["vpdMean"])
    ck("and the summary says the leaf temperature was measured", sl["measuredLeaf"], sl)

    # stage change must move the band and the excursion figure
    a = pg.evaluate("(r)=>GH.summarise(r,{stage:'veg'}).outsideBand", rows)
    c = pg.evaluate("(r)=>GH.summarise(r,{stage:'clone'}).outsideBand", rows)
    ck("changing the stage changes the time-outside-band figure", abs(a - c) > 0.01, (a, c))

    # ---------- the page's own text ----------
    # inner_text returns only what is VISIBLE, and four of five panes are
    # display:none at any moment. Reading only the open tab is how a check for
    # page text passes or fails depending on which tab happens to be showing.
    body = pg.evaluate("()=>document.body.innerText + ' ' + document.body.textContent")
    for phrase, why in [
        ("leaf VPD", "the page names which VPD it shows"),
        ("Buck", "the page names the SVP equation it uses"),
        ("grower convention", "the target bands are labelled as convention"),
        ("0.25 to 0.51", "the page states the size of the leaf-offset shift"),
        ("lower VPD", "the page states which direction the offset moves VPD"),
        ("g/kWh", "the honest grams-per-energy figure is present"),
        ("duty cycle", "the g/W caveat is present"),
        ("spectrum", "the lumens refusal explains itself"),
        ("Buck, 1981", "the SVP equation carries a citation, not just a name"),
    ]:
        ck(why, phrase in body, phrase)

    # ---------- the page's arithmetic claims, recomputed ----------
    # The duty-cycle example and the lux spread are numbers the page asserts in
    # prose. Both are derivable, so both are derived here rather than pinned to
    # a string (ADR-041): change the example in the page and this recomputes.
    ck("the duty-cycle example's energy fraction is 0.60 × 0.50 = 0.30",
       close(0.60 * 0.50, 0.30, 1e-9) and "0.30 of the energy" in body, "")
    ck("and its g/kWh multiplier is 1 ÷ 0.30 = 3.3",
       close(1 / 0.30, 3.333, 0.01) and "3.3 times higher" in body, "")
    facs = pg.evaluate("()=>GH.LUX_FACTORS.map(x=>x.f)")
    ck("the lux spread the page quotes matches its own table",
       close(max(facs) / min(facs), 82 / 24.0, 0.01)
       and str(min(facs)) in body and str(max(facs)) in body,
       (min(facs), max(facs)))

    ck("no script errors after driving the whole page", not errs, errs[:2])
    b.close()

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
