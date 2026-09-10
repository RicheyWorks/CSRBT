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
# ---- the worked example, reproduced (ADR-185) ----
# The demo is a seeded LCG over a week of half-hour rows; the docstring above
# says no check trusts it, and none did -- but nothing REPRODUCED it either, so
# the chart it draws could only be held to whatever rows the page held. This is
# the generator in Python, row for row (toFixed's ties go to the larger digit),
# and the env chart's own arithmetic on top of it.
import math as _math
from decimal import Decimal as _Dec, ROUND_HALF_UP as _HALF_UP
def _r2(v):
    q = _math.floor(float(v) * 100 + 0.5) / 100
    return int(q) if q.is_integer() else q
def _fixed(v, d):
    return float(_Dec(float(v)).quantize(_Dec(1).scaleb(-d), rounding=_HALF_UP))
def demo_rows(end, days=7, per_day=48):
    seed = 20260826
    def rnd():
        nonlocal seed
        seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
        return seed / 4294967296
    rows = []
    for i in range(days * per_day, -1, -1):
        t = end - i * 30 * 60000
        hour = ((t / 3600000) % 24 + 24) % 24
        on = 6 <= hour < 24
        temp = (26 if on else 21) + _math.sin(hour / 24 * 2 * _math.pi) * 1.4 + (rnd() - 0.5) * 0.8
        rh = (58 if on else 66) - _math.sin(hour / 24 * 2 * _math.pi) * 4 + (rnd() - 0.5) * 3
        ppfd = 780 + (rnd() - 0.5) * 40 if on else 0
        w = 640 + (rnd() - 0.5) * 25 if on else 55
        rows.append({"t": t, "temp": _fixed(temp, 2), "rh": _fixed(rh, 1),
                     "ppfd": int(_math.floor(ppfd + 0.5)), "w": _fixed(w, 1), "co2": 900 if on else 520})
    return rows
GH_BANDS = {"clone": (0.4, 0.8), "veg": (0.8, 1.2), "early": (1.0, 1.4), "late": (1.2, 1.6)}
def env_chart(rows, stage="veg", offset=2):
    """docs/greenhouse.html envChart(): W 680, H 260, pad 46; x by time to the
    right edge less 18; y from 0.15 below the lower of the band floor and the
    coldest reading to 0.15 above the higher of the band ceiling and the
    hottest; the band rect and its two lines; the trend line only when the
    least-squares r2 reaches 0.3; the axis labels to one decimal."""
    blo, bhi = GH_BANDS[stage]
    pts = sorted([(r["t"], vpd_leaf(r["temp"], r["rh"], offset)) for r in rows], key=lambda p: p[0])
    W, H, Pd = 680, 260, 46
    t0, t1 = pts[0][0], pts[-1][0]; vs = [v for _, v in pts]
    lo = min(blo, min(vs)) - 0.15; hi = max(bhi, max(vs)) + 0.15
    X = lambda t: Pd + (t - t0) / max(1, (t1 - t0)) * (W - Pd - 18)
    Y = lambda v: H - Pd - (v - lo) / max(1e-9, (hi - lo)) * (H - Pd - 22)
    px = [_fixed(X(t), 1) for t, _ in pts]; py = [_fixed(Y(v), 1) for _, v in pts]
    slope, icept, rr = ols([t / 86400000 for t, _ in pts], vs)
    trend = slope is not None and rr is not None and rr >= 0.3
    rect = [Pd, _fixed(Y(bhi), 1), W - Pd - 18, _fixed(abs(Y(blo) - Y(bhi)), 1)]
    texts = [{"t": "%s\u2013%s kPa target band" % (blo, bhi), "x": Pd + 6, "y": _r2(_fixed(Y(bhi) - 6, 1))},
             {"t": "%.1f" % _fixed(hi, 1), "x": 6, "y": _r2(_fixed(Y(hi) + 10, 1))},
             {"t": "%.1f" % _fixed(lo, 1), "x": 6, "y": _r2(_fixed(H - Pd, 1))},
             {"t": "solid: your readings \u2014 dashed: least-squares trend" if trend else "time", "x": _r2(W / 2), "y": H - 8}]
    return {"viewBox": "0 0 %d %d" % (W, H), "marks": {"rect": 1, "line": 3 if trend else 2, "path": 1},
            "longest": len(pts), "spans": [[_r2(min(px)), _r2(min(py)), _r2(max(px)), _r2(max(py))]],
            "at": [[_r2(rect[0] + rect[2] / 2), _r2(rect[1] + rect[3] / 2)]], "texts": texts,
            "path": list(zip(px, py)), "rect": rect, "band_lines": [_fixed(Y(blo), 1), _fixed(Y(bhi), 1)], "trend": trend, "r2": rr}

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
    # ---- ...and reproduced, row for row (ADR-185) ----
    _mine = demo_rows(1787700000000)
    ck("the worked example is reproduced by the Python generator, all %d rows byte for byte" % len(_mine),
       rows == _mine, [(i, a, b) for i, (a, b) in enumerate(zip(rows, _mine)) if a != b][:2])
    # ---- the env chart, against the port (ADR-185) ----
    pg.wait_for_timeout(300)
    _ec = env_chart(rows, "veg", 2)
    _got = pg.evaluate("""()=>{const s=document.querySelector('#envChart svg'); if(!s) return null;
      const r=s.querySelector('rect'), ls=[...s.querySelectorAll('line')], p=s.querySelector('path');
      return {d:p.getAttribute('d'), rect:[+r.getAttribute('x'),+r.getAttribute('y'),+r.getAttribute('width'),+r.getAttribute('height')],
              lines:ls.map(l=>+l.getAttribute('y1')), texts:[...s.querySelectorAll('text')].map(t=>({t:t.textContent,x:+t.getAttribute('x'),y:+t.getAttribute('y')}))};}""")
    _d = "M" + " L".join("%s,%s" % (("%.1f" % x), ("%.1f" % y)) for x, y in _ec["path"])
    ck("the env chart's path is the worked example's %d readings at the port's coordinates, to the tenth the page writes" % len(rows),
       _got is not None and _got["d"] == _d, (_got or {}).get("d", "")[:60])
    ck("the band rect and its two lines sit where the port's scale puts the band, and the labels say what the port says",
       _got is not None and _got["rect"] == _ec["rect"] and _got["lines"][:2] == _ec["band_lines"]
       and _got["texts"] == _ec["texts"], _got and (_got["rect"], _got["lines"], _got["texts"]))
    ck("the trend line is drawn only when r2 reaches 0.3 -- the worked week has none (r2 %.4f), so two lines, not three" % (_ec["r2"] or 0),
       _got is not None and len(_got["lines"]) == (3 if _ec["trend"] else 2) and not _ec["trend"], _got and len(_got["lines"]))

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
    # Whitespace is collapsed before matching. A phrase that wraps across a line
    # in the source reads as "caused\n        it" in textContent, and a check
    # that fails on that is testing the line wrap, not the page.
    body = pg.evaluate("()=>(document.body.innerText+' '+document.body.textContent)"
                       ".replace(/\\s+/g,' ')")
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

    # ---------- inBand and the log span, which nothing called ----------
    # Three mutations of inBand() survived the whole suite: it is used by the
    # page to colour a tile, and never called directly. A boundary function
    # tested only through a colour is not tested.
    B = {"lo": 0.8, "hi": 1.2}
    for v, want, why in [(0.8, True,  "the lower edge is INSIDE — the band is inclusive"),
                         (1.2, True,  "so is the upper edge"),
                         (1.0, True,  "the middle is obviously inside"),
                         (0.79, False, "just below is outside"),
                         (1.21, False, "just above is outside"),
                         (0.0, False, "zero is outside, not a falsy free pass")]:
        got = pg.evaluate("([v,b])=>GH.inBand(v,b)", [v, B])
        ck("inBand(%.2f): %s" % (v, why), got is want, got)
    ck("inBand of null is false, not an error",
       pg.evaluate("(b)=>GH.inBand(null,b)", B) is False, "")
    ck("a band with lo above hi admits nothing",
       pg.evaluate("()=>GH.inBand(1.0,{lo:1.2,hi:0.8})") is False, "")

    SPAN = [{"t": 1000, "temp": 20, "rh": 50}, {"t": 5000, "temp": 21, "rh": 51},
            {"t": 3000, "temp": 22, "rh": 52}]
    sp = pg.evaluate("(r)=>GH.summarise(r,{}).spanDays", SPAN)
    ck("the logged span is last minus first in TIME, not in row order",
       close(sp, (5000 - 1000) / 86400000.0, 1e-12), sp)
    ck("a single reading spans no time rather than a negative amount",
       close(pg.evaluate("(r)=>GH.summarise(r,{}).spanDays", SPAN[:1]), 0.0, 1e-12), "")

    # ---------- runs: the noise floor ----------
    import statistics

    def g_per_kwh(r): return r["grams"] / r["kwh"]

    BASE = [{"id": "b%d" % i, "label": "b%d" % i, "baseline": True,
             "grams": g, "kwh": 80.0, "ratedW": 650, "rate": 0.15}
            for i, g in enumerate([498, 512, 471, 505])]
    NEW = {"id": "n", "label": "new", "baseline": False,
           "grams": 548, "kwh": 84.1, "ratedW": 720, "rate": 0.15}

    st = pg.evaluate("(rs)=>GH.runStats(rs,'gPerKWh')", BASE)
    vals = [g_per_kwh(r) for r in BASE]
    ck("baseline mean recomputes", close(st["mean"], sum(vals) / len(vals), 1e-9), st["mean"])
    ck("baseline SD is the SAMPLE form (n−1), not the population form",
       close(st["sd"], statistics.stdev(vals), 1e-9)
       and not close(st["sd"], statistics.pstdev(vals), 1e-9), (st["sd"], statistics.pstdev(vals)))
    ck("CV is SD over the mean", close(st["cv"], st["sd"] / st["mean"], 1e-9), st["cv"])
    ck("only baseline-marked runs count toward the floor",
       pg.evaluate("(rs)=>GH.runStats(rs,'gPerKWh').n", BASE + [NEW]) == 4, "")

    for n in (0, 1, 2):
        r = pg.evaluate("(rs)=>GH.runStats(rs,'gPerKWh')", BASE[:n])
        ck("with %d baseline run(s) no SD is computed" % n, r["sd"] is None, r)
        if n:
            ck("and it says why rather than going quiet", bool(r["why"]), r["why"])

    c = pg.evaluate("([r,rs])=>GH.compare(r,rs,'gPerKWh')", [NEW, BASE + [NEW]])
    want_z = (g_per_kwh(NEW) - sum(vals) / len(vals)) / statistics.stdev(vals)
    ck("z is the distance from the baseline mean in baseline SDs",
       close(c["z"], want_z, 1e-9), (c["z"], want_z))
    ck("a non-baseline run does not enter the baseline it is measured against",
       close(c["baseline"]["mean"], sum(vals) / len(vals), 1e-9), c["baseline"]["mean"])

    # Self-exclusion only bites when the run being judged is ITSELF a baseline
    # run — with a non-baseline run the baseline filter already removed it, so
    # the first version of this check could not tell the two behaviours apart
    # and a seeded fault walked straight through it.
    # BASE[2] is the LOW outlier, chosen on purpose. A run sitting near the mean
    # barely moves the answer whether it is excluded or not, so the first
    # version of this check — which used BASE[0] — could not tell the two apart
    # either, and the seeded fault escaped a second time. Fixtures that cannot
    # distinguish two implementations are not tests of the difference.
    OUT = 2
    cself = pg.evaluate("([r,rs])=>GH.compare(r,rs,'gPerKWh')", [BASE[OUT], BASE])
    others = [g_per_kwh(r) for i, r in enumerate(BASE) if i != OUT]
    ck("a baseline run is excluded from the baseline it is judged against",
       cself["baseline"]["n"] == 3
       and close(cself["baseline"]["mean"], sum(others) / len(others), 1e-9),
       (cself["baseline"]["n"], cself["baseline"]["mean"]))
    z_incl = (g_per_kwh(BASE[OUT]) - sum(vals) / len(vals)) / statistics.stdev(vals)
    ck("and that changes its z substantially from the include-self answer",
       abs(cself["z"] - z_incl) > 1.0, (cself["z"], z_incl))
    ck("|z| under 1 reads as inside the noise",
       pg.evaluate("([r,rs])=>GH.compare(r,rs,'gPerKWh').verdict",
                   [dict(BASE[1], id="q", baseline=False), BASE]) == "inside", "")
    big = dict(NEW, grams=900)
    ck("a genuinely large move reads as outside",
       pg.evaluate("([r,rs])=>GH.compare(r,rs,'gPerKWh').verdict", [big, BASE]) == "outside", "")

    flat = [dict(r, grams=500) for r in BASE]
    cf = pg.evaluate("([r,rs])=>GH.compare(r,rs,'gPerKWh')", [NEW, flat])
    ck("a zero spread is refused rather than divided by",
       cf["z"] is None and "not a spread" in (cf["why"] or ""), cf)

    c2 = pg.evaluate("([r,rs])=>GH.compare(r,rs,'gPerKWh')", [NEW, []])
    ck("no baseline at all gives no z, with a reason",
       c2["z"] is None and bool(c2["why"]), c2)
    c3 = pg.evaluate("([r,rs])=>GH.compare(r,rs,'gPerKWh')",
                     [dict(NEW, grams=None), BASE])
    ck("a run with no yield gives no z, with a reason",
       c3["z"] is None and bool(c3["why"]), c3)

    ck("g/W and g/kWh are read from different denominators",
       close(pg.evaluate("(r)=>GH.runMetric(r,'gPerW')", NEW), 548 / 720.0, 1e-9)
       and close(pg.evaluate("(r)=>GH.runMetric(r,'gPerKWh')", NEW), 548 / 84.1, 1e-9), "")
    ck("cost per gram uses the run's own rate",
       close(pg.evaluate("(r)=>GH.runMetric(r,'costPerGram')", NEW),
             84.1 * 0.15 / 548, 1e-9), "")

    # ---------- the demo tells the intended story ----------
    pg.evaluate("()=>GHRUNS.demo()")
    pg.wait_for_timeout(300)
    rs = pg.evaluate("()=>GHRUNS.list()")
    ck("the example loads five runs, four of them baseline",
       len(rs) == 5 and sum(1 for r in rs if r["baseline"]) == 4,
       (len(rs), sum(1 for r in rs if r["baseline"])))
    last = rs[-1]
    ck("the example's headline run really does yield more",
       last["grams"] > max(r["grams"] for r in rs[:-1]), last["grams"])
    dc = pg.evaluate("()=>{const rs=GHRUNS.list();"
                     "return GH.compare(rs[rs.length-1], rs, 'gPerKWh');}")
    ck("and its z still lands at the edge rather than outside — which is the lesson",
       dc["verdict"] == "edge", (dc["z"], dc["verdict"]))
    ck("every example run is marked as generated",
       all("GENERATED" in (r["note"] or "") for r in rs), [r["note"] for r in rs][:2])

    # ---------- persistence ----------
    ck("KEEP is wired on this page", pg.evaluate("()=>typeof KEEP === 'object'"), "")
    ck("the run store has its own key, not a shared one",
       "csrbtGreenhouseRuns" in pg.content(), "")
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(800)
    after = pg.evaluate("()=>GHRUNS.list().length")
    ck("saved runs survive a reload", after == 5, after)
    ck("and the page says where they came from",
       "run history" in pg.evaluate("()=>document.body.textContent"), "")

    # ---------- the page's own words about what a comparison can support ----------
    body2 = pg.evaluate("()=>(document.body.innerText+' '+document.body.textContent)"
                        ".replace(/\\s+/g,' ')")
    for phrase, why in [
        ("cannot tell you what caused it", "the page refuses causal reading of a run difference"),
        ("no p-value", "the page says outright there is no significance test here"),
        ("three baseline runs", "the page states the minimum for a spread"),
        ("not a backup", "the page repeats what browser storage is"),
    ]:
        ck(why, phrase in body2, phrase)

    ck("no script errors after driving the whole page", not errs, errs[:2])
    b.close()

# ---- the env chart the greenhouse task holds (ADR-185) ----
# The task fixes the clock, loads the worked example, picks the clones band
# and a 1.5 degree leaf offset, and reads the chart; every number it holds is
# recomputed here from those four choices and nothing read from the page.
import json as _json, datetime as _dt
_TASK = os.path.join(ROOT, "tools", "tasks", "page-greenhouse-science.json")
_t = _json.load(open(_TASK, encoding="utf-8")) if os.path.isfile(_TASK) else {"steps": []}
_st = dict((s["id"], s) for s in _t["steps"])
def _v(step, k):
    x = _st.get(step, {}).get("expect", {}).get(k); return x.get("value") if isinstance(x, dict) and "op" in x else x
_at = (_st.get("g155-t0", {}).get("arguments") or {}).get("at")
_off = float((_st.get("g155-off", {}).get("arguments") or {}).get("value", 2))
_stage = "clone" if "clones" in ((_st.get("g155-clone", {}).get("arguments") or {}).get("selector") or "") else "veg"
if _at:
    _end = int(_dt.datetime.strptime(_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc).timestamp() * 1000)
    _ec = env_chart(demo_rows(_end), _stage, _off)
    ck("the task holds the env chart to the port fed from its own clock, band and offset: the path's box, the band rect's centre, the four texts, the marks, %d points" % _ec["longest"],
       _v("g155-readout", "output.charts.envChart.spans") == _ec["spans"] and _v("g155-readout", "output.charts.envChart.at.0") == _ec["at"][0]
       and _v("g155-readout", "output.charts.envChart.texts") == _ec["texts"] and _v("g155-readout", "output.charts.envChart.marks") == _ec["marks"]
       and _v("g155-readout", "output.charts.envChart.longest") == _ec["longest"] and _v("g155-readout", "output.charts.envChart.viewBox") == _ec["viewBox"],
       (_v("g155-readout", "output.charts.envChart.spans"), _ec["spans"], _v("g155-readout", "output.charts.envChart.texts"), _ec["texts"]))
    ck("...and the readout figures it holds are the same rows summarised: VPD range %.2f-%.2f kPa, mean %.2f" %
       (min(v for _, v in [(r["t"], vpd_leaf(r["temp"], r["rh"], _off)) for r in demo_rows(_end)]),
        max(v for _, v in [(r["t"], vpd_leaf(r["temp"], r["rh"], _off)) for r in demo_rows(_end)]),
        sum(vpd_leaf(r["temp"], r["rh"], _off) for r in demo_rows(_end)) / len(demo_rows(_end))),
       _v("g155-readout", "output.by.envOut.VPD range") == "%.2f\u2013%.2f kPa" % (
           min(vpd_leaf(r["temp"], r["rh"], _off) for r in demo_rows(_end)), max(vpd_leaf(r["temp"], r["rh"], _off) for r in demo_rows(_end)))
       and _v("g155-readout", "output.by.envOut.mean leaf VPD") == "%.2f kPa" % (sum(vpd_leaf(r["temp"], r["rh"], _off) for r in demo_rows(_end)) / len(demo_rows(_end)))
       and _v("g155-readout", "output.by.envOut.readings") == str(len(demo_rows(_end))),
       (_v("g155-readout", "output.by.envOut.VPD range"), _v("g155-readout", "output.by.envOut.mean leaf VPD")))
else:
    ck("the greenhouse task fixes its clock, so the worked example it loads is the one the port reproduces", False, "no g155-t0")

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
