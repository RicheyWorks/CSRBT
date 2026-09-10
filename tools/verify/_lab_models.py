# -*- coding: utf-8 -*-
"""A port of docs/ecology-lab.html's terrarium and theory bench -- runMeadow,
runIsland and runTheory, the arithmetic the page states, in Python (ADR-186).

The terrarium is a seeded stream: mulberry32(42) drawn 4000 times decides the
meadow's counts, mulberry32(7) drawn 800 times decides which keys arrive on the
island. tools/mulberry32.py is that generator, bit for bit, so the meadow's
evenness, the island's immigrations and every bar in both charts have an oracle
that never read the page's answer. The theory bench is a model: the page
computes each curve itself (logistic and island in closed form, Levins by
iteration, competition and predation by Euler with 10 and 100 substeps), so the
port is the model, and what lineChart draws from it is _lab_charts's business.
Not a suite: no verify_ prefix, nothing runs it; verify_eco imports it and
holds the live page AND the lab task's literals to what comes out.
"""
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mulberry32 import Mulberry32
import _lab_charts as C

# ---------------- the terrarium ----------------
def shannon(counts):
    n = sum(counts)
    if not n: return 0
    return -sum((c / n) * math.log(c / n) for c in counts if c > 0)
def chao1(counts):
    s = sum(1 for c in counts if c > 0); f1 = sum(1 for c in counts if c == 1); f2 = sum(1 for c in counts if c == 2)
    if not f1: return s
    return s + f1 * f1 / (2 * f2) if f2 > 0 else s + f1 * (f1 - 1) / 2
def evenness(j):
    return ("very even — no key dominates" if j >= .85 else "moderately even — some keys busier than others" if j >= .55
            else "uneven — a few hot keys carry most of the traffic" if j >= .30
            else "strongly dominated — a handful of keys get nearly all the attention")
def meadow(hot_share, hot_set):
    """runMeadow: 4000 touches over 100 keys, a hot share of them over the hot set; the tiles and the rank list."""
    rnd = Mulberry32(42).random
    counts = [0] * 100
    for _ in range(4000):
        key = math.floor(rnd() * hot_set) if rnd() * 100 < hot_share else math.floor(rnd() * 100)
        counts[key] += 1
    H = shannon(counts); S = sum(1 for c in counts if c > 0)
    J = H / math.log(S) if S > 1 else 1
    rank = sorted([c for c in counts if c > 0], reverse=True)[:40]
    return {"counts": counts, "J": J, "effective": math.exp(H), "chao1": chao1(counts), "rank": rank,
            "tiles": {"evenness J′": C.fmt(J, 2), "effective species": C.fmt(math.exp(H), 1), "Chao1 est.": C.fmt(chao1(counts), 0)},
            "read": evenness(J) + "."}
def island(cap):
    """runIsland: 800 admissions to an LRU of `cap`; immigrations, extinctions, residence, and the turnover timeline."""
    rnd = Mulberry32(7).random
    order = []; birth = {}; ages = []; imm = ext = 0; timeline = []; li = le = 0
    for op in range(1, 801):
        key = math.floor(rnd() * 20) if rnd() < 0.5 else math.floor(rnd() * 80)
        if key in order: order.remove(key)
        else: imm += 1; birth[key] = op
        order.insert(0, key)
        if len(order) > cap:
            ev = order.pop(); ext += 1; ages.append(op - birth.pop(ev))
        if op % 80 == 0:
            timeline.append([op, (imm - li + ext - le) / 2]); li, le = imm, ext
    return {"residents": len(order), "cap": cap, "imm": imm, "ext": ext, "ages": ages, "timeline": timeline,
            "tiles": {"residents / capacity": "%d/%d" % (len(order), cap), "immigrations": str(imm), "extinctions": str(ext),
                      "mean residence": (C.fmt(sum(ages) / len(ages), 0) + " ops") if ages else "—"}}
def meadow_chart(hot_share, hot_set): return C.bar_chart(meadow(hot_share, hot_set)["rank"], 480, 150)
def island_chart(cap): return C.bar_chart([p[1] for p in island(cap)["timeline"]], 480, 150)

# ---------------- the theory bench ----------------
MODEL_PARAMS = {
    "logistic": [0.15, 120, 5, 60], "exponential": [0.1, 5, 40], "levins": [0.4, 0.1, 0.05, 40],
    "island": [0.3, 0.1, 100, 0, 40], "competition": [0.4, 100, 0.4, 80, 0.7, 1.1, 5, 5, 80],
    "predation": [0.5, 0.02, 0.3, 0.4, 40, 9, 200]}
def _js_round(v): return math.floor(v + 0.5)   # Math.round: ties toward +inf
def theory(kind, p, area=1, temp=1, wind=1, dist=0):
    """runTheory's series: the list of point lists it hands lineChart (one, or two for competition and predation)."""
    col = lambda c: c * wind * temp * math.exp(-dist)
    ext = lambda e: e / area
    steps = max(1, min(2000, _js_round(p[-1])))
    s1 = []; s2 = None
    if kind == "logistic":
        r = p[0] * temp; K = p[1] * area; n0 = p[2]
        for t in range(steps + 1): s1.append([t, 0 if n0 <= 0 else K / (1 + ((K - n0) / n0) * math.exp(-r * t))])
    elif kind == "exponential":
        r = p[0] * temp
        for t in range(steps + 1): s1.append([t, p[1] * math.exp(r * t)])
    elif kind == "levins":
        c = col(p[0]); e = ext(p[1]); occ = min(1, max(0, p[2]))
        for t in range(steps + 1):
            s1.append([t, occ]); occ = min(1, max(0, occ + c * occ * (1 - occ) - e * occ))
    elif kind == "island":
        c = col(p[0]); e = ext(p[1]); sStar = c / (c + e) * p[2] if c + e > 0 else 0
        for t in range(steps + 1): s1.append([t, sStar + (p[3] - sStar) * math.exp(-(c + e) * t)])
    elif kind == "competition":
        r1 = p[0] * temp; k1 = p[1] * area; r2 = p[2] * temp; k2 = p[3] * area
        x = max(0, p[6]); y = max(0, p[7]); s2 = []
        for t in range(steps + 1):
            s1.append([t, x]); s2.append([t, y])
            for _ in range(10):
                dx = r1 * x * (1 - (x + p[4] * y) / k1) * 0.1
                dy = r2 * y * (1 - (y + p[5] * x) / k2) * 0.1
                x = max(0, x + dx); y = max(0, y + dy)
    elif kind == "predation":
        r = p[0] * temp; n = max(0, p[4]); pr = max(0, p[5]); s2 = []
        for t in range(steps + 1):
            s1.append([t, n]); s2.append([t, pr])
            for _ in range(100):
                dn = (r * n - p[1] * n * pr) * 0.01
                dp = (p[2] * p[1] * n * pr - p[3] * pr) * 0.01
                n = max(0, n + dn); pr = max(0, pr + dp)
    else:
        raise ValueError(kind)
    return [s1] + ([s2] if s2 is not None else [])
def theory_note(kind, p, area=1, temp=1, wind=1, dist=0):
    """the reading the page prints above the chart"""
    col = lambda c: c * wind * temp * math.exp(-dist)
    ext = lambda e: e / area
    if kind == "logistic": return "effective r=%s, K=%s" % (C.fmt(p[0] * temp, 3), C.fmt(p[1] * area, 0))
    if kind == "exponential": return "effective r=%s" % C.fmt(p[0] * temp, 3)
    if kind == "levins":
        c, e = col(p[0]), ext(p[1])
        return "effective c=%s, e=%s, p* = %s" % (C.fmt(c, 3), C.fmt(e, 3), C.fmt(max(0, 1 - e / c) if c > 0 else 0, 3))
    if kind == "island":
        c, e = col(p[0]), ext(p[1])
        return "effective c=%s, e=%s, S* = %s" % (C.fmt(c, 3), C.fmt(e, 3), C.fmt(c / (c + e) * p[2] if c + e > 0 else 0, 1))
    if kind == "competition": return "effective K₁=%s, K₂=%s" % (C.fmt(p[1] * area, 0), C.fmt(p[3] * area, 0))
    return "effective r=%s" % C.fmt(p[0] * temp, 3)
def theory_chart(kind, p, **habitat): return C.line_chart(theory(kind, p, **habitat), 980, 190)
