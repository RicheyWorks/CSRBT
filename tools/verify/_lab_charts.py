# -*- coding: utf-8 -*-
"""A port of docs/ecology-lab.html's chart primitives -- frame, barPath/barChart,
lineChart -- the arithmetic the page states, in Python (ADR-182, ADR-183).

verify_eco feeds it the shipped session (docs/ecology-lab-session.json) and the
workbench inputs its task types, and holds BOTH the live page's drawing and the
task's literals to what comes out. Not a suite: no verify_ prefix, nothing runs
it; it is imported. Numbers here are rounded the way read-report rounds them
(Math.round(v * 100) / 100, in the same doubles), and tick labels are formatted
the way the page's fmt() formats them (toLocaleString en-US, half-up, the
page's decimals rule), because the claim is equality with what the reader
returns, digit for digit.
"""
import math
from decimal import Decimal, ROUND_HALF_UP
ML, MR, MT, MB = 42, 10, 12, 34
def r2(v):
    """the reader's rounding, Math.round(v * 100) / 100, in the same IEEE doubles"""
    q = math.floor(float(v) * 100 + 0.5) / 100
    return int(q) if q.is_integer() else q
def fmt(x, d):
    q = Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    s = format(q, "f")
    if "." in s: s = s.rstrip("0").rstrip(".")
    ip, _, fp = s.partition("."); neg = ip.startswith("-"); ip = ip.lstrip("-")
    ip = "{:,}".format(int(ip))
    return ("-" if neg else "") + ip + ("." + fp if fp else "")
def _dec(yMax): return 2 if yMax <= 2 else 1 if yMax < 10 else 0
def _ticks(yMax): return list(reversed([fmt(yMax * i / 4, _dec(yMax)) for i in range(5)]))
def bar_chart(values, w, h):
    iw, ih = w - ML - MR, h - MT - MB
    yMax = max([1] + [v for v in values if math.isfinite(v)]) * 1.05
    n = len(values); gap = 2; bw = max(1, iw / n - gap)
    spans, at = [], []
    for i, v in enumerate(values):
        bh = ih * v / yMax; x = ML + i * iw / n + gap / 2; y = MT + ih - bh
        if v > 0: spans.append([r2(x), r2(y), r2(x + bw), r2(y + bh)])
        # the reader rounds a rect's x and width BEFORE halving (num() on each attribute), so the port does too
        at.append([r2(r2(ML + i * iw / n) + r2(iw / n) / 2), r2(MT + ih / 2)])
    return {"col": _ticks(yMax), "row": [], "spans": spans[:40], "at": at[:40],
            "marks": {"rect": n, "path": len(spans), "line": 6}, "longest": 6 if spans else 0}
def line_chart(series, w, h, yMax=None, xTicks=None, step=False):
    """series: list of point lists [[x, y], ...]; a series with a non-finite point is dropped."""
    series = [s for s in series if s and all(math.isfinite(p[0]) and math.isfinite(p[1]) for p in s)]
    iw, ih = w - ML - MR, h - MT - MB
    if yMax is None: yMax = max(p[1] for s in series for p in s) * 1.08
    if not yMax > 0: yMax = 1
    xs = [p[0] for p in series[0]]; xMin, xMax = min(xs), max(xs)
    X = lambda v: ML + iw * (v - xMin) / max(1, xMax - xMin)
    Y = lambda v: MT + ih - ih * min(v, yMax) / yMax
    spans, longest = [], 0
    for s in series:
        px = [X(p[0]) for p in s]; py = [Y(p[1]) for p in s]
        spans.append([r2(min(px)), r2(min(py)), r2(max(px)), r2(max(py))])
        longest = max(longest, 1 + (2 if step else 1) * (len(s) - 1))
    row = [fmt(v, 0) for v in (xTicks or [])]
    return {"col": _ticks(yMax), "row": row if len(row) >= 3 else [], "spans": spans, "longest": longest,
            "marks": {"circle": len(series), "rect": 1, "path": len(series), "line": 7},
            "at": [[r2(ML + iw / 2), r2(MT + ih / 2)]]}
def station_charts(S):
    """The station charts in DOM order, keyed as read-report keys them, from a session dict."""
    out = {}
    m = S["meadow"]
    for i, p in enumerate(m["phases"]):
        out["station-meadow" + ("" if i == 0 else " #%d" % (i + 1))] = bar_chart(p.get("rank") or [], 480, 180)
    rph = [p for p in m["phases"] if p.get("rarefaction")]
    if rph: out["station-meadow #%d" % (len(m["phases"]) + 1)] = line_chart([p["rarefaction"] for p in rph], 980, 190)
    d = S.get("demography"); g = S.get("growth"); k = 0
    if d:
        cw = d["classWidth"]; surv = d["survivorship"]
        out["station-demography"] = line_chart([[[x * cw, l] for x, l in enumerate(surv)]], 480, 190, yMax=1.05, step=True,
                                               xTicks=[x * cw for x in range(len(surv)) if x % 2 == 0]); k += 1
    if g and g.get("series"):
        fit = (lambda t: g["K"] / (1 + ((g["K"] - g["n0"]) / g["n0"]) * math.exp(-g["r"] * t))) if g["n0"] > 0 else (lambda t: 0)
        out["station-demography" + (" #%d" % (k + 1) if k else "")] = line_chart([g["series"], [[p[0], fit(p[0])] for p in g["series"]]], 480, 172)
    a = S.get("archipelago")
    if a and a.get("timeline"):
        out["station-archipelago"] = line_chart([[[p["survey"], p["occupancy"]] for p in a["timeline"]]], 980, 180, yMax=1.0, step=True,
                                                xTicks=[p["survey"] for p in a["timeline"]])
    f = S.get("fossils")
    if f and f.get("generations"):
        gens = [x for x in f["generations"] if "inherited" in x]
        out["station-fossils"] = bar_chart([x["inherited"] for x in gens], 980, 170)
    gr = S.get("grid"); k = 0
    if gr:
        for key in ("clustered", "spread"):
            q = gr.get(key)
            if not q or not q.get("counts"): continue
            out["station-grid" + (" #%d" % (k + 1) if k else "")] = bar_chart(q["counts"], 480, 170); k += 1
            lv = gr.get(key + "Leaves")
            if lv and lv.get("counts"):
                out["station-grid #%d" % (k + 1)] = bar_chart(lv["counts"], 480, 120); k += 1
    return out
