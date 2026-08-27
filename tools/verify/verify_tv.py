# -*- coding: utf-8 -*-
"""The tree visualizer had no suite at all.

`docs/tree-visualizer.html` is a published page that reimplements four
balancing strategies -- Red-Black, AVL, Splay and BB[3,2] weight-balanced --
and shows their heights side by side. Its whole thesis is a comparison of
heights: "the teal card has the lowest height ... no single tree wins every
workload".

A mutation sweep scored it **0%**. Four mutants, none caught, because the only
suites naming the page are `verify_focus_slice` and `verify_print_slice` --
cross-cutting slices that check focus rings and print CSS. Nothing had ever
asserted that the trees are trees.

Two of the four were serious:

    n.h = 1 + Math.max(n.left.h, n.right.h)   ->  Math.min
    checkBST: if (a[i] <= a[i-1])             ->  a[i] < a[i-1]

The first is the same height recurrence that ADR-063 found broken-and-unnoticed
on tree-proofs. Every bound a reader would think to assert is an UPPER bound,
and a height computed too small satisfies all of them, so the floor is asserted
here too: no tree of n nodes fits below log2(n+1).

THE PAGE ALREADY HAD THE CHECKERS

`checkBST`, `checkSize`, `checkRB`, `checkAVL` and `checkWB` sit under a comment
reading "invariant checkers (for tests)", and nothing in the repo has ever
called one. They are good checkers shipped as dead code. This suite calls them,
which is cheaper and more honest than writing a second set that could disagree
with the page's own (ADR-039).

Run:  python3 tools/verify/verify_tv.py
"""
import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline
from playwright.sync_api import sync_playwright

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))

KEYS = [50, 20, 70, 10, 30, 60, 80, 5, 15, 25, 35, 65, 75, 85, 90]
STRATS = ["RB", "AVL", "Splay", "WB"]

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1200, "height": 1000})
    pg = ctx.new_page()
    offline(pg)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url("tree-visualizer.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(500)
    ck("the page loads without a script error", not errs, errs[:3])

    def build(strat, ks):
        pg.evaluate("""([s,ks])=>{
          setStrat(s); doClear();
          ks.forEach(k=>doInsert(k));
          refreshMetrics();}""", [strat, ks])
        pg.wait_for_timeout(180)

    ck("the page exposes the checkers it wrote for tests",
       pg.evaluate("()=>typeof checkBST==='function' && typeof checkSize==='function'"), "")

    for s in STRATS:
        build(s, KEYS)
        n = pg.evaluate("()=>keys.length")
        h = pg.evaluate("()=>height(T)")
        ck("%s: every key went in" % s, n == len(KEYS), (n, len(KEYS)))
        ck("%s: in-order walk is sorted" % s, pg.evaluate("()=>checkBST(T)") is None,
           pg.evaluate("()=>checkBST(T)"))
        ck("%s: every subtree size is its own subtree's count" % s,
           pg.evaluate("()=>checkSize(T)") is None, pg.evaluate("()=>checkSize(T)"))
        # The floor. Every bound below is an upper bound and a height computed
        # too SMALL satisfies all of them -- which is exactly how the min/max
        # mutation survived here and on tree-proofs (ADR-063).
        floor = math.ceil(math.log2(n + 1))
        ck("%s: height %d is at least the floor log2(%d+1) = %d" % (s, h, n, floor),
           h >= floor, (h, floor))
        ck("%s: the readout shows the height the tree has" % s,
           pg.inner_text("#mH").split()[0] == str(h), (pg.inner_text("#mH"), h))
        ck("%s: the optimal readout is that same floor" % s,
           pg.inner_text("#mOpt").strip() == str(floor), pg.inner_text("#mOpt"))

    # ---- strategy-specific invariants, each on its own tree ----
    build("RB", KEYS)
    ck("RB: no red-red, and every path has the same black-height",
       pg.evaluate("()=>checkRB(T)") is None, pg.evaluate("()=>checkRB(T)"))
    ck("RB: height within the classical 2*log2(n+1)",
       pg.evaluate("()=>height(T)") <= 2 * math.log2(len(KEYS) + 1) + 1e-9,
       pg.evaluate("()=>height(T)"))
    build("AVL", KEYS)
    ck("AVL: no node's subtree heights differ by more than 1",
       pg.evaluate("()=>checkAVL(T)") is None, pg.evaluate("()=>checkAVL(T)"))
    build("WB", KEYS)
    ck("WB: neither subtree exceeds 3x the other, by size",
       pg.evaluate("()=>checkWB(T,3)") is None, pg.evaluate("()=>checkWB(T,3)"))

    # ---- the page's own headline claim, asserted ----
    # "Try Insert 1..20 ascending: AVL and WB stay short, Red-Black stays within
    # 2x optimal, and Splay collapses to a spine."
    asc = list(range(1, 21))
    opt = math.ceil(math.log2(len(asc) + 1))
    build("Splay", asc)
    hs = pg.evaluate("()=>height(T)")
    ck("ascending inserts really do collapse Splay to a spine (h = n)",
       hs == len(asc), (hs, len(asc)))
    for s, cap in (("AVL", 5), ("WB", 6)):
        build(s, asc)
        ck("%s stays short on the same ascending run (h <= %d)" % (s, cap),
           pg.evaluate("()=>height(T)") <= cap, pg.evaluate("()=>height(T)"))
    build("RB", asc)
    hrb = pg.evaluate("()=>height(T)")
    ck("Red-Black stays within 2x optimal on the ascending run",
       hrb <= 2 * opt, (hrb, opt))
    ck("and the page's claim is ordered the way it says: Splay is the tallest",
       hs > hrb, (hs, hrb))

    # ---- order statistics, against an independent sort ----
    build("RB", KEYS)
    srt = sorted(KEYS)
    for k in (1, 4, len(srt)):
        ck("select %d returns the %dth smallest" % (k, k),
           pg.evaluate("(k)=>selectK(T,k)", k) == srt[k - 1],
           (pg.evaluate("(k)=>selectK(T,k)", k), srt[k - 1]))
    for v in (srt[0], srt[7], srt[-1]):
        ck("rank of %d is its position in sorted order" % v,
           pg.evaluate("(v)=>rankOf(T,v)", v) == srt.index(v) + 1,
           (pg.evaluate("(v)=>rankOf(T,v)", v), srt.index(v) + 1))
    ck("rank of an absent key is reported as absent",
       pg.evaluate("()=>rankOf(T,4242)") is None, pg.evaluate("()=>rankOf(T,4242)"))
    ck("the median readout is the middle of the sorted keys",
       pg.inner_text("#medOut").strip() == str(srt[(len(srt) + 1) // 2 - 1]),
       (pg.inner_text("#medOut"), srt[(len(srt) + 1) // 2 - 1]))

    # ---- DELETES, which the first version of this suite never did ----
    # Every check above inserts. A mutation sweep broke the red-black delete
    # fixup's loop condition -- `while (x !== T.root && !x.red)` became `||` --
    # and this suite passed, because it had never removed a key. An insert-only
    # suite for a structure whose hardest code is deletion is a suite that
    # measures the easy half.
    for s in STRATS:
        build(s, KEYS)
        gone = []
        for k in (10, 70, 50, 5, 85):          # a leaf, an internal node, the root
            pg.evaluate("(k)=>{doDelete(k); refreshMetrics();}", k)
            pg.wait_for_timeout(90)
            gone.append(k)
            left = sorted(x for x in KEYS if x not in gone)
            ck("%s: after deleting %d the keys are exactly what is left" % (s, k),
               pg.evaluate("()=>inorder(T)") == left,
               (pg.evaluate("()=>inorder(T)"), left))
            ck("%s: order still holds after deleting %d" % (s, k),
               pg.evaluate("()=>checkBST(T)") is None, pg.evaluate("()=>checkBST(T)"))
            ck("%s: sizes still hold after deleting %d" % (s, k),
               pg.evaluate("()=>checkSize(T)") is None, pg.evaluate("()=>checkSize(T)"))
        if s == "RB":
            ck("RB: the colouring still holds after five deletions",
               pg.evaluate("()=>checkRB(T)") is None, pg.evaluate("()=>checkRB(T)"))
        if s == "AVL":
            ck("AVL: balance still holds after five deletions",
               pg.evaluate("()=>checkAVL(T)") is None, pg.evaluate("()=>checkAVL(T)"))
        if s == "WB":
            ck("WB: the weight bound still holds after five deletions",
               pg.evaluate("()=>checkWB(T,3)") is None, pg.evaluate("()=>checkWB(T,3)"))
    ck("deleting an absent key is refused",
       pg.evaluate("()=>{const n=keys.length; doDelete(4242); return keys.length===n;}"), "")

    # ---- a duplicate is refused, which is why checkBST never sees one ----
    # Rebuilt first: the delete section above removes 50, and a "duplicate"
    # test on a key that is no longer there tests nothing. Caught by the suite
    # failing, which is what a suite is for.
    build("RB", KEYS)
    before = pg.evaluate("()=>keys.length")
    pg.evaluate("()=>{doInsert(50); refreshMetrics();}")
    pg.wait_for_timeout(120)
    ck("inserting a key already present adds nothing",
       pg.evaluate("()=>keys.length") == before, (before, pg.evaluate("()=>keys.length")))
    ck("and the page says so rather than silently doing nothing",
       "already present" in pg.inner_text("#msg"), pg.inner_text("#msg"))

    # ---- the keyboard shortcuts the page advertises ----
    # `e.key >= "1" && e.key <= "4"` -- a sweep made that `> "1"`, which leaves
    # the first strategy unreachable from the keyboard while 2-4 still work.
    for i, s in enumerate(STRATS, start=1):
        pg.evaluate("()=>setStrat('Splay')")
        pg.keyboard.press(str(i))
        pg.wait_for_timeout(120)
        ck("pressing %d selects %s" % (i, s), pg.evaluate("()=>curStrat") == s,
           pg.evaluate("()=>curStrat"))
    pg.evaluate("()=>setStrat('RB')")
    pg.keyboard.press("5")
    pg.wait_for_timeout(120)
    ck("and 5 is not a strategy, so it changes nothing",
       pg.evaluate("()=>curStrat") == "RB", pg.evaluate("()=>curStrat"))

    ck("no script error through the whole run", not errs, errs[:3])
    b.close()

for x in F: print("FAIL:", x)
print("PASS", len(P))
print("---"); print("%d/%d" % (len(P), len(P) + len(F)))
raise SystemExit(1 if F else 0)
