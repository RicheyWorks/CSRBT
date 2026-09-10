# -*- coding: utf-8 -*-
"""The mathematics page: check the mathematics, not the markup.

Every claim on tree-proofs.html is computed in the browser from a live tree. So
this suite recomputes the same things independently -- Fibonacci in Python, the
sorted order as a plain list, the potential function from the DOM's own tree --
and fails if the page and the arithmetic disagree.

The one that matters most is the identity `amortized = actual + delta-Phi`. It is
not an approximation and it is not a bound; it is a definition, and if it ever
fails to hold exactly the page is lying about what it is measuring.
"""
import io, math, os, re, sys

import _kit
from playwright.sync_api import sync_playwright

P = F = 0
def ck(c, m):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", m)

def fib(k):
    a, b = 0, 1
    for _ in range(k):
        a, b = b, a + b
    return a

SRC = io.open(_kit.DOCS_DIR + "tree-proofs.html", encoding="utf-8").read()

# ---- the page keeps the kit's rules --------------------------------------
ck('media="print" data-webfont' in SRC, "webfont link is deferred, as every other page's is")
ck("@media print" in SRC, "the page has print CSS")
ck("--tap:44px" in SRC.replace(" ", ""), "controls are sized from the 44px token")
ck("Sleator" in SRC and "1985" in SRC, "the Access Lemma is cited, not claimed")
ck("Hirai" in SRC and "2011" in SRC, "the weight-balanced result is cited")
ck("watching a bound hold on one tree is evidence, not proof" in SRC,
   "the page says what a demonstration is and is not")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1200, "height": 950})
    ctx.set_offline(True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(_kit.url("tree-proofs.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(1100)
    ck(not errs, "loads without error (%s)" % errs[:1])

    # ---- 1. AVL: the page's built trees against Python's Fibonacci --------
    rows = pg.evaluate("""()=>[...document.querySelectorAll('#avTab tr')].slice(1)
        .map(r=>[...r.children].map(c=>c.textContent.trim()))""")
    ck(len(rows) == 12, "twelve heights tabulated (%d)" % len(rows))
    for r in rows:
        h, n, f = int(r[0]), int(r[1]), int(r[2])
        ck(n == fib(h + 2) - 1,
           "h=%d: the tree the page BUILT has %d nodes; F(h+2)-1 = %d" % (h, n, fib(h + 2) - 1))
        ck(n == f, "h=%d: the page's own Fibonacci column agrees (%d vs %d)" % (h, n, f))
        ck(h <= 1.4404 * math.log2(n + 2) - 0.3277 + 1e-9,
           "h=%d clears the classical AVL bound" % h)
        ck(r[4] == "✓", "h=%d row is marked as holding" % h)
        # Every bound above is an UPPER bound, so a height computed too SMALL
        # satisfies all of them. A mutation sweep turned the height recurrence
        # `1 + Math.max(left.h, right.h)` into `Math.min` and this whole section
        # stayed green. No tree of n nodes can be shorter than log2(n+1), and
        # that is recomputed from n rather than pinned (ADR-041).
        ck(h >= math.log2(n + 1) - 1e-9,
           "h=%d: %d nodes cannot fit in a tree shorter than log2(%d+1) = %.2f"
           % (h, n, n, math.log2(n + 1)))

    # ---- 2. red-black: the bound, over several random trees ---------------
    for i in range(6):
        note = pg.inner_text("#rbNote")
        m = re.search(r"(\d+) keys, measured height (\d+), black-height (\d+)", note)
        ck(bool(m), "the red-black note reports n, height and black-height (%r)" % note[:60])
        if m:
            n, h, bh = int(m.group(1)), int(m.group(2)), int(m.group(3))
            ck(h <= 2 * math.log2(n + 1) + 1e-9,
               "tree %d: height %d <= 2*log2(%d+1) = %.2f" % (i, h, n, 2 * math.log2(n + 1)))
            ck(bh <= h, "tree %d: black-height %d does not exceed height %d" % (i, bh, h))
            ck(h >= math.log2(n + 1) - 1e-9,
               "tree %d: %d keys cannot fit in a tree shorter than log2(%d+1) = %.2f"
               % (i, n, n, math.log2(n + 1)))
            ck("VIOLATED" not in note, "tree %d: the page does not report a violation" % i)
        pg.click("#rbNew"); pg.wait_for_timeout(160)
    # the 2-3-4 view must be the same tree, not a different one
    pg.click("#rbToggle"); pg.wait_for_timeout(250)
    ck("2-3-4 view" in pg.inner_text("#rbNote"), "the toggle reaches the 2-3-4 view")
    boxes = pg.eval_on_selector_all("#rbSvg rect", "e=>e.length")
    ck(boxes > 0, "the 2-3-4 view draws multi-key boxes (%d)" % boxes)
    keys234 = pg.evaluate("""()=>[...document.querySelectorAll('#rbSvg text')]
        .flatMap(t=>t.textContent.split('\\u00b7').map(s=>+s.trim())).sort((a,b)=>a-b)""")
    pg.click("#rbToggle"); pg.wait_for_timeout(250)
    keysRB = pg.evaluate("""()=>[...document.querySelectorAll('#rbSvg text')]
        .map(t=>+t.textContent.trim()).sort((a,b)=>a-b)""")
    ck(keys234 == keysRB,
       "absorbing the red nodes changes the drawing and not the keys (%d vs %d)"
       % (len(keys234), len(keysRB)))

    # ---- 3. order statistics: against the sorted order --------------------
    for k in (1, 2, 7, 16, 25, 31):
        pg.fill("#osK", str(k)); pg.click("#osGo"); pg.wait_for_timeout(140)
        note = pg.inner_text("#osNote")
        ck("correct" in note and "MISMATCH" not in note, "select(%d): %s" % (k, note[:70]))
        m = re.search(r"select\((\d+)\) = (\d+) in (\d+) steps out of (\d+)", note)
        ck(bool(m), "select(%d) reports its walk" % k)
        if m:
            got, steps, n = int(m.group(2)), int(m.group(3)), int(m.group(4))
            ck(got == k, "the tree holds 1..%d, so select(%d) must be %d (got %d)" % (n, k, k, got))
            ck(steps <= math.ceil(math.log2(n + 1)) + 1,
               "select(%d) took %d steps, within a root-to-leaf descent of %d keys" % (k, steps, n))

    # ---- 4. the potential identity, exactly -------------------------------
    pg.click("#spReset"); pg.wait_for_timeout(200)
    log = pg.evaluate("()=>SPLOG.map(e=>[e.actual,e.dphi,e.am])")
    pg.click("#spRand"); pg.wait_for_timeout(700)
    log = pg.evaluate("()=>SPLOG.map(e=>[e.actual,e.dphi,e.am])")
    ck(len(log) >= 15, "the random run logged operations (%d)" % len(log))
    worst = max((abs(a + d - m) for a, d, m in log), default=0)
    ck(worst < 1e-9, "amortized = actual + delta-Phi holds exactly (worst drift %.2e)" % worst)
    ck(all(a >= 1 for a, d, m in log), "every access costs at least 1")

    # ---- 5. the headline: a worst-case access with negative amortized cost -
    pg.click("#spWorst"); pg.wait_for_timeout(250)
    phi0 = float(pg.inner_text("#spPhi"))
    n = int(pg.inner_text("#spN"))
    ck(n == 63, "the worst case is built with 63 keys (%d)" % n)
    ck(phi0 > 250, "a path carries high potential (Phi = %.1f)" % phi0)
    pg.fill("#spK", "1"); pg.click("#spAccess"); pg.wait_for_timeout(300)
    actual = int(pg.inner_text("#spAct"))
    am = float(pg.inner_text("#spAm"))
    phi1 = float(pg.inner_text("#spPhi"))
    ck(actual >= 60, "reaching the bottom of the path really costs (%d rotations)" % actual)
    ck(phi1 < phi0 - 100, "and it really flattens the tree (Phi %.1f -> %.1f)" % (phi0, phi1))
    ck(am < 0, "so the amortized cost of the worst access is NEGATIVE (%.1f)" % am)
    ck(am <= 3 * math.log2(n) + 1,
       "and comfortably inside the Access-Lemma bound of %.1f" % (3 * math.log2(n) + 1))
    pg.click("#spAccess"); pg.wait_for_timeout(250)
    ck(int(pg.inner_text("#spAct")) == 1, "the very next access to the same key costs 1")

    # ---- 6. the page checks itself ----------------------------------------
    ck("INVARIANT FAILED" not in pg.inner_text("#spCheck"),
       "subtree sizes verified after every rotation")
    ck(not errs, "no errors raised by any of it (%s)" % errs[:1])
    ctx.close()
    b.close()

# ---- 6. the charts the task holds (ADR-181) --------------------------------
# The splay chart's scale is stated by its geometry: bars of width min(22, (W -
# 2 pad)/n - 3) spaced evenly across the frame, y linear from the baseline to a
# ceiling maxV = ceil(1.15 * the largest cost), ticks at quarters of maxV. The
# task holds the ticks the chart printed and the last access's actual cost (5),
# so the last bar's centre is recomputed HERE from those two figures and the
# task's literal held to it -- a literal transcribed from the page cannot pass
# a scale it does not fit. The 2-3-4 view is held to what a 2-3-4 tree IS: the
# leaves' keys strictly increasing left to right, the root's keys separating
# them, and 13 to 15 keys in all (13 + press mod 3, the page's own rule).
import json as _json
_TASK = os.path.join(_kit.ROOT, "tools", "tasks", "page-tree-proofs-science.json")
_task = _json.load(io.open(_TASK, encoding="utf-8")) if os.path.isfile(_TASK) else {"steps": []}
_e = dict((s["id"], s) for s in _task["steps"]).get("seededAccesses", {}).get("expect", {})
def _v(k):
    x = _e.get(k); return x.get("value") if isinstance(x, dict) and "op" in x else x
W_, H_, PAD, N_ = 720, 220, 34, 20
ticks = _v("output.charts.spChart.aligned.col") or []
maxV = int(ticks[0]) if ticks else 0
ck(ticks == ["%.0f" % (maxV * t / 4) for t in (4, 3, 2, 1, 0)] and maxV == 15,
   "the ticks the task holds are quarters of one ceiling, read top to bottom (%s)" % ticks)
last_actual = int(_e.get("output.figures.last actual", 0))
bw = max(4, min(22, (W_ - PAD * 2) / N_ - 3)); gap = ((W_ - PAD * 2) - bw * N_) / (N_ - 1)
def _y(v): return H_ - PAD - (v / maxV) * (H_ - PAD * 2)
x19 = round(PAD + 19 * (bw + gap), 1); y19 = round(_y(last_actual), 1); hh = round((H_ - PAD) - y19, 1)
ck(_v("output.charts.spChart.at.19") == [round(x19 + bw / 2, 2), round(y19 + hh / 2, 2)],
   "the last bar's centre in the task is where the scale puts an actual cost of %d: %s vs %s"
   % (last_actual, _v("output.charts.spChart.at.19"), [round(x19 + bw / 2, 2), round(y19 + hh / 2, 2)]))
ck(_v("output.charts.spChart.marks") == {"rect": N_, "line": 5, "polyline": 1} and _v("output.charts.spChart.longest") == N_,
   "twenty bars, five grid lines, one amortized line through twenty points: %s" % _v("output.charts.spChart.marks"))
row = _v("output.charts.rbSvg.aligned.row") or []
root = _v("output.charts.rbSvg.texts.0.t") or ""
def _keys(g): return [int(k) for k in g.split(" · ")]
leaves = [_keys(g) for g in row]; rk = _keys(root)
ck(len(row) == 4 and len(rk) == 3 and all(k == sorted(k) for k in leaves + [rk]),
   "the 2-3-4 view the task holds is a 4-node root over four leaves, every group sorted: %s / %s" % (root, row))
ck(all(max(leaves[i]) < rk[i] < min(leaves[i + 1]) for i in range(3)),
   "...and the root's keys separate the leaves in order, as a 2-3-4 tree's must: %s between %s" % (rk, row))
ck(len(rk) + sum(len(k) for k in leaves) in (13, 14, 15),
   "...holding 13 to 15 keys, the page's own take of 13 + press mod 3 (%d)" % (len(rk) + sum(len(k) for k in leaves)))

print("---"); print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
