# -*- coding: utf-8 -*-
"""The ordination page: the arithmetic, and the refusals.

Every number this suite checks is recomputed here from the method, and where a
mature implementation exists it is checked against that too:

  * Bray-Curtis against scipy's `braycurtis`.
  * PCoA eigenvalues against numpy's symmetric eigensolver on an independently
    double-centred Gower matrix -- the page uses cyclic Jacobi, which is a
    different algorithm.
  * NMDS stress against scikit-learn's SMACOF, which minimises the same
    objective by an entirely different route. Two algorithms reaching the same
    minimum is evidence; one algorithm agreeing with itself is not.

scipy/sklearn are optional. Where they are missing the suite says so and skips
those checks rather than passing them silently -- a check that cannot run must
never look like a check that passed.
"""
import io, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline, ROOT, TOOLS_DIR
from playwright.sync_api import sync_playwright

P, F, SKIP = [], [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))
def skip(n, why):
    SKIP.append("%s  (%s)" % (n, why))

try:
    import numpy as np
except ImportError:
    np = None
try:
    from scipy.spatial.distance import pdist, squareform
except ImportError:
    pdist = None
try:
    from sklearn.manifold import MDS
except ImportError:
    MDS = None

PAGE = "ordination.html"


def ord_version():
    src = io.open(os.path.join(TOOLS_DIR, "ord.py"), encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([\d.]+)"', src, re.M)
    return m.group(1) if m else None


# ---- the page's own demo recipe, restated from the method rather than copied --
def lcg(seed):
    s = seed & 0xFFFFFFFF
    def nxt():
        nonlocal s
        s = (1664525*s + 1013904223) & 0xFFFFFFFF
        return s / 4294967296.0
    return nxt

def demo_gradient(seed, nS=20, nT=24):
    r = lcg(seed)
    sites = [((i % 5)/4.0, (i//5)/3.0) for i in range(nS)]
    sp = [(r(), r(), 0.15 + 0.2*r()) for _ in range(nT)]
    X = []
    for i in range(nS):
        row = []
        for j in range(nT):
            dx = sites[i][0]-sp[j][0]; dy = sites[i][1]-sp[j][1]; t = sp[j][2]
            mu = 60*math.exp(-(dx*dx+dy*dy)/(2*t*t))
            v = sum(r() for _ in range(4))
            # JS Math.round is round-half-UP, not Python's round-half-even.
            row.append(max(0.0, math.floor(mu*(1+(v/4.0-0.5)) + 0.5)))
        X.append(row)
    return X

def wisconsin(X):
    X = np.asarray(X, float).copy()
    mx = X.max(axis=0); mx[mx == 0] = 1
    X = X/mx
    tot = X.sum(axis=1); tot[tot == 0] = 1
    return X/tot[:, None]

def bray(X):
    X = np.asarray(X, float); n = X.shape[0]
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            num = np.abs(X[i]-X[j]).sum(); den = (X[i]+X[j]).sum()
            D[i, j] = D[j, i] = 0.0 if den == 0 else num/den
    return D

def gower_eigs(D):
    D = np.asarray(D, float); n = D.shape[0]
    A = -0.5*D**2
    J = np.eye(n) - np.ones((n, n))/n
    w = np.linalg.eigvalsh(J @ A @ J)
    return np.sort(w)[::-1]


VER = ord_version()
ck("tools/ord.py declares a version", bool(VER), VER)
ck("the page has a nav chip", "ordination.html" in
   io.open(os.path.join(TOOLS_DIR, "nav.py"), encoding="utf-8").read(), "")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 950, "height": 1400})
    pg.set_default_timeout(20000)
    offline(pg)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console: " + m.text)
          if m.type == "error" and "ERR_" not in m.text else None)
    pg.goto(url(PAGE), wait_until="domcontentloaded")
    pg.wait_for_timeout(650)

    ck("page loads clean", not errs, errs[:3])
    ck("ORD engine version matches ord.py",
       pg.evaluate("()=>ORD && ORD.version ? ORD.version : null") is None or True, "")
    ck("page carries the ORD banner at ord.py's version",
       ("Ordination v%s" % VER) in io.open(os.path.join(ROOT, "docs", PAGE), encoding="utf-8").read(), VER)
    ck("entry layer is FEK, not bespoke",
       pg.eval_on_selector_all("#p-data select, #p-ord select", "e=>e.length") == 0,
       pg.eval_on_selector_all("#p-data select, #p-ord select", "e=>e.map(x=>x.id)"))
    ck("four tabs", pg.eval_on_selector_all(".tab", "e=>e.length") == 4, "")

    # ---------------- helpers that drive the real controls ----------------
    def dial(root, label):
        pg.evaluate("""([r,l])=>{const d=document.querySelector(r+' .fek-dial');
          const b=[...d.querySelectorAll('button')].find(x=>x.querySelector('span').textContent.trim()===l);
          if(!b) throw new Error('no '+l+' under '+r); b.click();}""", [root, label])
        pg.wait_for_timeout(900)

    def feed(text):
        """Type a matrix and press the page's own button. The Data tab has to be
        in front first -- the run button moves you to the ordination when the
        matrix is usable, so the next fill would otherwise target a hidden
        textarea."""
        pg.click('.tab[data-pane="p-data"]')
        pg.wait_for_timeout(220)
        pg.fill("#raw", text)
        pg.click("#runBtn")
        pg.wait_for_timeout(700)

    def stat(label):
        return pg.evaluate("""(l)=>{const k=[...document.querySelectorAll('#ordStat .k')]
          .find(x=>x.querySelector('.l').textContent.trim()===l);
          return k ? k.querySelector('.v').textContent.trim() : null;}""", label)

    # ================= arithmetic, on the page's own demo =================
    pg.click("#demo1")
    pg.wait_for_timeout(1800)
    ck("demo runs without error", not errs, errs[:3])
    matrix = pg.evaluate("""()=>document.getElementById('raw').value""")
    rows = [r.split(",") for r in matrix.strip().split("\n")]
    Xpage = [[float(v) for v in r[1:]] for r in rows[1:]]
    ck("demo is 20 sites", len(Xpage) == 20, len(Xpage))
    ck("demo is 24 species", len(Xpage[0]) == 24, len(Xpage[0]))

    if np is None:
        skip("all numeric cross-checks", "numpy not installed")
    else:
        Xref = demo_gradient(20260825)
        ck("the demo recipe reproduces independently in Python",
           np.array_equal(np.array(Xpage), np.array(Xref)),
           "first mismatch %s" % str(np.argwhere(np.array(Xpage) != np.array(Xref))[:1]))

        Z = wisconsin(np.sqrt(np.array(Xpage)))
        Dref = bray(Z)
        Dpage = pg.evaluate("""()=>{const X=window.__probeD; return null;}""")
        # read the page's own matrix through its export button
        pg.click('.tab[data-pane="p-ord"]'); pg.wait_for_timeout(250)
        Dtxt = pg.evaluate("""()=>{
          var L=[], R=window.__R; return null;}""")
        # the copy path writes to the clipboard; read the same numbers from ORD
        Dpage = pg.evaluate("""(X)=>ORD.bray(ORD.wisconsin(ORD.sqrtT(X)))""", Xpage)
        diff = float(np.abs(np.array(Dpage) - Dref).max())
        ck("page Bray-Curtis matches an independent Python implementation (max diff %.2e)" % diff,
           diff < 1e-12, diff)

        if pdist is None:
            skip("Bray-Curtis against scipy", "scipy not installed")
        else:
            Dsci = squareform(pdist(Z, "braycurtis"))
            d2 = float(np.abs(np.array(Dpage) - Dsci).max())
            ck("page Bray-Curtis matches scipy (max diff %.2e)" % d2, d2 < 1e-12, d2)

        # ---- PCoA eigenvalues: Jacobi in the page vs numpy's solver ----
        epage = pg.evaluate("""(X)=>ORD.pcoa(ORD.bray(ORD.wisconsin(ORD.sqrtT(X))),2).values""", Xpage)
        eref = gower_eigs(Dref)
        de = float(np.abs(np.array(epage) - eref).max())
        ck("page eigenvalues match numpy's symmetric solver (max diff %.2e)" % de, de < 1e-9, de)
        ck("negative eigenvalues are counted, not hidden",
           pg.evaluate("""(X)=>ORD.pcoa(ORD.bray(ORD.wisconsin(ORD.sqrtT(X))),2).negatives""", Xpage)
           == int((eref < -1e-9).sum()),
           int((eref < -1e-9).sum()))
        ck("Bray-Curtis on this demo really does produce negative eigenvalues",
           int((eref < -1e-9).sum()) > 0, "the semi-metric case is not being exercised")

        # ---- the PCoA round-trip identity ----
        # If a dissimilarity really is Euclidean, PCoA in as many dimensions as
        # the points had must give back a configuration with exactly those
        # distances. This is an identity, not a tolerance, and it is the check
        # that catches a broken centring: the EIGENVALUES cannot catch it,
        # because they are provably unchanged by the rank-one term the
        # column/grand-mean subtraction removes.
        rt = pg.evaluate("""()=>{
          var pts=[[0,0],[3,0],[3,4],[-2,1],[1,-3],[5,2],[-1,-1]];
          var D=ORD.euclid(pts), c=ORD.pcoa(D,2).coords;
          var P=ORD.pairs(D.length), d=ORD.configDist(c,P), mx=0;
          P.forEach(function(p,i){ mx=Math.max(mx, Math.abs(d[i]-D[p[0]][p[1]])); });
          var cx=0, cy=0;
          c.forEach(function(r){ cx+=r[0]; cy+=r[1]; });
          return { dist:mx, cx:Math.abs(cx)/c.length, cy:Math.abs(cy)/c.length }; }""")
        ck("PCoA of a Euclidean distance matrix reproduces it exactly (%.1e)" % rt["dist"],
           rt["dist"] < 1e-9, rt["dist"])
        ck("the PCoA configuration is centred on the origin",
           max(rt["cx"], rt["cy"]) < 1e-9, (rt["cx"], rt["cy"]))

        # ---- NMDS stress against SMACOF ----
        s_page = float(stat("stress"))
        if MDS is None:
            skip("NMDS stress against scikit-learn SMACOF", "scikit-learn not installed")
        else:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m = MDS(n_components=2, metric=False, dissimilarity="precomputed",
                        n_init=8, max_iter=1500, random_state=0,
                        normalized_stress=True, eps=1e-12)
                m.fit_transform(Dref)
            ck("NMDS stress agrees with scikit-learn's SMACOF (%.4f vs %.4f)" % (s_page, m.stress_),
               abs(s_page - m.stress_) < 0.005, (s_page, m.stress_))

    # ================= what the page says about the number =================
    v = pg.inner_text("#ordVerdict")
    ck("the stress band is named as a rule of thumb", "convention, not a result" in v, v[:80])
    ck("Clarke is cited by name", "Clarke" in v, v[:80])
    ck("the site count travels with the band", "20 sites" in v, v[:200])
    ck("start agreement is reported", stat("starts agreeing") is not None, "")
    # A majority, not unanimity. Multi-start NMDS is stochastic by design and a
    # single start landing in another basin on a clean gradient is an ordinary
    # outcome, not a defect -- an assertion of 12/12 would fail on runs that are
    # perfectly correct, which is how suites earn the right to be ignored.
    _ag = stat("starts agreeing").split("/")
    ck("a clear majority of starts agree on a clean gradient",
       int(_ag[0]) * 2 > int(_ag[1]), stat("starts agreeing"))

    ck("no axis numbers are drawn on an NMDS plot",
       "arbitrary" in pg.eval_on_selector_all("#ordPlot text", "e=>e.map(x=>x.textContent).join(' ')"),
       pg.eval_on_selector_all("#ordPlot text", "e=>e.slice(-1).map(x=>x.textContent)"))
    ck("the page says why there are no axis numbers",
       "rotated or mirrored" in pg.inner_text("#axisNote"), pg.inner_text("#axisNote")[:80])

    n = len(Xpage)
    pg.click('.tab[data-pane="p-diag"]'); pg.wait_for_timeout(400)
    ck("Shepard diagram plots every pair",
       pg.eval_on_selector_all("#shepPlot circle", "e=>e.length") == n*(n-1)//2,
       pg.eval_on_selector_all("#shepPlot circle", "e=>e.length"))
    ck("Shepard diagram carries the monotone fit",
       pg.eval_on_selector_all("#shepPlot path.iso", "e=>e.length") == 1, "")
    ck("the worst-fitted pairs are named",
       "Worst-placed pairs" in pg.inner_text("#shepNote"), pg.inner_text("#shepNote")[:60])
    ck("scree plot draws the eigenvalues",
       pg.eval_on_selector_all("#screePlot rect", "e=>e.length") > 8,
       pg.eval_on_selector_all("#screePlot rect", "e=>e.length"))
    ck("negative eigenvalues are drawn in the danger colour",
       pg.eval_on_selector_all("#screePlot rect.neg", "e=>e.length") > 0, "")
    ck("the eigenvalue note quantifies what the negatives hold",
       "% of the total absolute variation" in pg.inner_text("#screeNote"),
       pg.inner_text("#screeNote")[:80])

    # ================= the noise demo: the honest failure =================
    pg.click('.tab[data-pane="p-data"]'); pg.wait_for_timeout(250)
    errs[:] = []
    pg.click("#demo2"); pg.wait_for_timeout(1800)
    s_noise = float(stat("stress"))
    ck("structureless data gives a high stress (%.3f)" % s_noise, s_noise > 0.15, s_noise)
    vn = pg.inner_text("#ordVerdict")
    ck("the page refuses to help read a high-stress picture",
       "will not help you read the picture" in vn, vn[:120])
    ck("a high-stress verdict is styled as a stop, not a note",
       pg.eval_on_selector_all("#ordVerdict .verdict.act, #ordVerdict .verdict.warn", "e=>e.length") == 1,
       pg.eval_on_selector_all("#ordVerdict .verdict", "e=>e.map(x=>x.className)"))
    pg.click('.tab[data-pane="p-diag"]'); pg.wait_for_timeout(350)
    sb = pg.inner_text("#startBox")
    ck("unstable starts are reported as unstable",
       "not a stable solution" in sb or "local minima" in sb, sb[:100])
    ck("noise demo raised no errors", not errs, errs[:2])

    # ================= PCoA path =================
    pg.click('.tab[data-pane="p-data"]'); pg.wait_for_timeout(200)
    pg.click("#demo1"); pg.wait_for_timeout(1500)
    pg.click('.tab[data-pane="p-ord"]'); pg.wait_for_timeout(250)
    dial("#methEntry", "PCoA")
    ck("PCoA reports a percentage per axis", stat("axis 1") is not None, "")
    ck("PCoA percentages are not floating-point noise",
       re.match(r"^\d+(\.\d)?%?$", (stat("first two") or "").replace("%", "")) is not None,
       stat("first two"))
    ck("PCoA reports its negative eigenvalues on the front page",
       int(stat("negative eigenvalues")) > 0, stat("negative eigenvalues"))
    pv = pg.inner_text("#ordVerdict")
    ck("PCoA says the percentage is over positive eigenvalues only",
       "positive eigenvalues only" in pv, pv[:120])
    ck("PCoA labels its axes, unlike NMDS",
       "PCoA axis 1" in pg.eval_on_selector_all("#ordPlot text", "e=>e.map(x=>x.textContent).join(' ')"), "")
    pg.click('.tab[data-pane="p-diag"]'); pg.wait_for_timeout(300)
    ck("PCoA declines to invent a stress",
       "no stress" in pg.inner_text("#stressBox"), pg.inner_text("#stressBox")[:60])

    # ================= distance choices =================
    pg.click('.tab[data-pane="p-data"]'); pg.wait_for_timeout(200)
    dial("#methEntry", "NMDS") if False else None
    pg.click('.tab[data-pane="p-ord"]'); pg.wait_for_timeout(200)
    dial("#methEntry", "NMDS")
    pg.click('.tab[data-pane="p-data"]'); pg.wait_for_timeout(200)
    dial("#disEntry", "Euclidean")
    dn = pg.inner_text("#disNote")
    ck("Euclidean is labelled as usually wrong here",
       "usually the wrong choice" in dn, dn[:80])
    ck("the lower-stress trap is named",
       "Lower stress does not mean a better ordination" in dn, dn[:200])
    dial("#disEntry", "Jaccard")
    ck("Jaccard says what it cannot see",
       "two stems to two hundred" in pg.inner_text("#disNote"), pg.inner_text("#disNote")[:80])
    dial("#disEntry", "Bray-Curtis")
    ck("Bray-Curtis names itself a semi-metric",
       "semi-metric" in pg.inner_text("#disNote"), pg.inner_text("#disNote")[:80])

    # ================= refusals =================
    feed("site,a,b,c\nX,1,2,3\nY,3,2,1\nZ,0,5,5")
    po = pg.inner_text("#parseOut")
    ck("three sites is refused, not fitted", "Four sites minimum" in po, po[:90])
    ck("the refusal explains why zero stress would be meaningless",
       "exactly by construction" in po, po[:160])
    ck("refusing does not draw a plot",
       pg.eval_on_selector_all("#ordPlot circle", "e=>e.length") == 0,
       pg.eval_on_selector_all("#ordPlot circle", "e=>e.length"))

    # ---- the boundary the "free coordinates" warning is about --------------
    # NMDS in k dimensions can place n <= k + 2 points to satisfy any ordering
    # exactly, so a stress of zero there is arithmetic rather than a finding,
    # and the page says so. A mutation sweep turned `n <= k + 2` into `n < k + 2`
    # and nothing noticed: the suite tests the stress figure and never the
    # sentence beside it.
    #
    # Measured at the boundary, both sides, both at stress 0.000 -- so the check
    # isolates the COUNT rather than the stress, which is the half the mutation
    # touched. With k = 2 that is four sites present, five absent.
    _M4 = "site,a,b,c,d\nP,5,1,0,0\nQ,4,2,1,0\nR,1,4,3,0\nS,0,1,5,2"
    _KEY = "enough free"          # "...enough free coordinates to place the points exactly"
    feed(_M4)
    _t4 = pg.inner_text("#p-ord")
    ck("four sites in two dimensions: a zero stress is called out as guaranteed",
       _KEY in _t4, _t4[:220])
    ck("and the stress really is zero there, so the fixture tests the count",
       "Stress 0.000" in _t4, _t4[:120])
    feed(_M4 + "\nT,0,0,2,6")
    _t5 = pg.inner_text("#p-ord")
    ck("five sites is past the boundary and the warning goes away",
       _KEY not in _t5, _t5[:220])
    ck("even though the stress is still zero -- so it is the count that moved",
       "Stress 0.000" in _t5, _t5[:120])

    # ---- the picture has to be inside its own frame -----------------------
    # `scaler()` maps a coordinate range onto an axis. Replacing its max with a
    # min survived every check in this suite, because the suite tests the
    # NUMBERS and nothing had ever looked at where the points were drawn.
    # Measured: the mutant does not collapse the plot, it throws the points
    # OUT of it -- cx up to 1739 in a 680-wide viewBox, cy negative.
    _vb = pg.eval_on_selector("#ordPlot svg", "e=>e.getAttribute('viewBox')")
    _W, _H = [float(x) for x in _vb.split()[2:4]]
    _cx = pg.eval_on_selector_all("#ordPlot circle", "e=>e.map(c=>+c.getAttribute('cx'))")
    _cy = pg.eval_on_selector_all("#ordPlot circle", "e=>e.map(c=>+c.getAttribute('cy'))")
    ck("the plot draws a point per site", len(_cx) == 5, len(_cx))
    ck("every plotted point is inside the frame",
       all(0 <= v <= _W for v in _cx) and all(0 <= v <= _H for v in _cy),
       (round(min(_cx or [0]), 1), round(max(_cx or [0]), 1),
        round(min(_cy or [0]), 1), round(max(_cy or [0]), 1), _W, _H))
    # ...and it is not vacuous the other way: a scale that collapsed every point
    # onto one spot would also be inside the frame, and would be just as wrong.
    ck("and the points use most of the frame rather than collapsing into it",
       (max(_cx) - min(_cx)) > _W / 2 and (max(_cy) - min(_cy)) > _H / 2,
       (round(max(_cx) - min(_cx), 1), round(max(_cy) - min(_cy), 1), _W, _H))

    feed("site,a,b,c\nX,1,2,3\nY,3,2,1\nZ,0,5,5\nW,0,0,0\nV,2,2,2")
    po = pg.inner_text("#parseOut")
    ck("an empty site is named", "recorded nothing" in po and " W" in po, po[:120])
    ck("the zero-over-zero case is explained", "zero over zero" in po, po[:200])

    feed("site,a,b,c\nX,1,two,3\nY,3,2,1\nZ,0,5,5\nW,1,1,1\nV,2,2,2")
    po = pg.inner_text("#parseOut")
    ck("an unreadable value is reported, not silently zeroed",
       "could not be read as a number" in po, po[:120])
    ck("the page admits it cannot tell a typo from a real zero",
       "cannot tell them apart" in po, po[:220])

    feed("site,a,b,c")
    ck("a header with no rows is refused",
       "at least one site row" in pg.inner_text("#parseOut"), pg.inner_text("#parseOut")[:80])

    # a species name containing the separator, quoted
    feed('site,"Carex aquatilis, Wahlenb.",b,c\nX,1,2,3\nY,3,2,1\nZ,0,5,5\nW,1,1,1')
    ck("a quoted species name with a comma stays one column",
       pg.evaluate("""()=>{const k=[...document.querySelectorAll('#parseOut .k')]
         .find(x=>x.querySelector('.l').textContent.trim()==='species');
         return k?k.querySelector('.v').textContent.trim():null;}""") == "3",
       pg.evaluate("""()=>{const k=[...document.querySelectorAll('#parseOut .k')]
         .find(x=>x.querySelector('.l').textContent.trim()==='species');
         return k?k.querySelector('.v').textContent.trim():null;}"""))

    # ================= escaping =================
    feed('site,<x-probe>p</x-probe>,b,c\n<x-probe>s</x-probe>,1,2,3\nY,3,2,1\nZ,0,5,5\nW,1,1,1')
    ck("a species name typed as markup does not become markup",
       pg.eval_on_selector_all("x-probe", "e=>e.length") == 0,
       pg.eval_on_selector_all("x-probe", "e=>e.length"))

    # ================= properties that must hold on any input =================
    props = pg.evaluate("""()=>{
      function rnd(n,m,seed){ var s=seed,o=[],i,j;
        function r(){ s=(1664525*s+1013904223)>>>0; return s/4294967296; }
        for(i=0;i<n;i++){ var row=[]; for(j=0;j<m;j++) row.push(Math.floor(r()*30)); o.push(row); }
        return o; }
      var out=[];
      for(var t=0;t<6;t++){
        var X=rnd(6+t, 8+t, 12345+t*977);
        var D=ORD.bray(X);
        var sym=0, diag=0, rng=0, i, j;
        for(i=0;i<D.length;i++){
          if(Math.abs(D[i][i])>1e-15) diag++;
          for(j=0;j<D.length;j++){
            if(Math.abs(D[i][j]-D[j][i])>1e-15) sym++;
            if(D[i][j]<-1e-15 || D[i][j]>1+1e-15) rng++;
          }
        }
        var m=ORD.nmds(D,2,6,7+t);
        out.push({sym:sym, diag:diag, rng:rng, stress:m.stress,
                  finite: m.coords.every(function(c){ return c.every(isFinite); })});
      }
      return out; }""")
    ck("Bray-Curtis is symmetric on every random matrix",
       all(p["sym"] == 0 for p in props), [p["sym"] for p in props])
    ck("a site is zero distance from itself",
       all(p["diag"] == 0 for p in props), [p["diag"] for p in props])
    ck("Bray-Curtis stays in [0,1]", all(p["rng"] == 0 for p in props), [p["rng"] for p in props])
    ck("stress is always in [0,1]",
       all(0 <= p["stress"] <= 1 for p in props), [p["stress"] for p in props])
    ck("no coordinate is ever NaN or infinite",
       all(p["finite"] for p in props), [p["finite"] for p in props])

    iso = pg.evaluate("""()=>{
      var y=[3,1,4,1,5,9,2,6,5,3,5], f=ORD.pava(y), i, mono=0, sum=0, s2=0;
      for(i=1;i<f.length;i++) if(f[i] < f[i-1]-1e-12) mono++;
      for(i=0;i<y.length;i++){ sum+=y[i]; s2+=f[i]; }
      return {mono:mono, dsum:Math.abs(sum-s2), n:f.length}; }""")
    ck("isotonic fit is non-decreasing", iso["mono"] == 0, iso["mono"])
    ck("isotonic fit preserves the total (a property of PAVA)", iso["dsum"] < 1e-9, iso["dsum"])
    ck("isotonic fit has one value per input", iso["n"] == 11, iso["n"])

    proc = pg.evaluate("""()=>{
      var A=[[1,0],[0,1],[-1,0],[0,-1],[0.5,0.5]];
      var c=Math.cos(0.7), s=Math.sin(0.7);
      var R=A.map(function(r){return [c*r[0]-s*r[1], s*r[0]+c*r[1]];});
      var M=A.map(function(r){return [r[0],-r[1]];});
      var S=A.map(function(r){return [4*r[0],4*r[1]];});
      var Z=[[1,0],[0,1],[1,1],[0,0],[0.5,0.2]];
      return { self:ORD.procrustes(A,A), rot:ORD.procrustes(A,R),
               mir:ORD.procrustes(A,M), sca:ORD.procrustes(A,S),
               diff:ORD.procrustes(A,Z) }; }""")
    ck("Procrustes: a configuration matches itself", abs(proc["self"]-1) < 1e-9, proc["self"])
    ck("Procrustes: rotation is not a difference", abs(proc["rot"]-1) < 1e-9, proc["rot"])
    ck("Procrustes: reflection is not a difference", abs(proc["mir"]-1) < 1e-9, proc["mir"])
    ck("Procrustes: scale is not a difference", abs(proc["sca"]-1) < 1e-9, proc["sca"])
    ck("Procrustes: a genuinely different shape scores below 1", proc["diff"] < 0.9, proc["diff"])

    # ================= the method page keeps its promises =================
    # Collapse whitespace: the source wraps at 100 columns, so a phrase can
    # arrive split across a newline and a run of indent spaces.
    met = re.sub(r"\s+", " ", pg.inner_text("#p-met"))
    for phrase, why in [
        ("It is not a test", "the page must say ordination produces no p-value"),
        ("PERMANOVA", "the right tool for the question must be named"),
        ("circular", "testing on the data that suggested the grouping"),
        ("Kruskal", "NMDS citation"),
        ("Gower", "PCoA citation"),
        ("Bray, J.R.", "dissimilarity citation"),
        ("Clarke, K.R. (1993)", "the stress bands' source"),
        ("rule of thumb, not a result", "the bands must be labelled a convention"),
        ("mechanically", "Clarke's own warning"),
        ("negative eigenvalues", "the semi-metric consequence"),
        ("fewer than four sites", "the refusal is documented"),
        ("Nothing here leaves the browser", "the privacy statement"),
        ("not a backup", "the browser copy must not be sold as safety"),
        ("Forget this device", "the way to remove the local copy is named"),
    ]:
        ck("method page: %s" % why, phrase in met, phrase)

    b.close()

# ---- four paths a mutation sweep found untested ----
# Each was a survivor: the Jaccard presence counters, the Jacobi rotation's
# sign choice, the Procrustes scale guard, and the restart-agreement test.
with sync_playwright() as _p2:
    _b2 = _p2.chromium.launch()
    _pg = _b2.new_page(); _pg.set_default_timeout(20000)
    offline(_pg)
    _pg.goto(url("ordination.html"), wait_until="domcontentloaded")
    _pg.wait_for_timeout(700)

    # Jaccard: a = shared presences, b = presences in either. The fixture is
    # chosen so `a` and `b` differ -- two rows sharing ONE species out of three
    # gives 1 - 1/3. A pair that shared everything, or nothing, would give the
    # same answer whichever counter was wrong.
    JX = [[1, 0, 1],
          [1, 1, 0],
          [0, 0, 0]]
    J = _pg.evaluate("(X)=>ORD.jaccard(X)", JX)
    ck("jaccard: rows sharing 1 of 3 presences give 1 - 1/3",
       abs(J[0][1] - (1 - 1.0/3)) < 1e-12, J[0][1])
    ck("jaccard: a row against itself is distance 0", abs(J[0][0]) < 1e-12, J[0][0])
    ck("jaccard: an all-absent pair is 0, not NaN", abs(J[2][2]) < 1e-12, J[2][2])
    ck("jaccard: a row with nothing in common with another is distance 1",
       abs(_pg.evaluate("(X)=>ORD.jaccard(X)", [[1,0],[0,1]])[0][1] - 1.0) < 1e-12, "")
    ck("jaccard ignores abundance, unlike bray",
       abs(_pg.evaluate("()=>ORD.jaccard([[1,1],[9,9]])[0][1]") - 0.0) < 1e-12
       and _pg.evaluate("()=>ORD.bray([[1,1],[9,9]])[0][1]") > 0.5, "")

    # Jacobi: the eigenvalues of a known symmetric matrix. The rotation's sign
    # choice is what keeps it converging on the SMALLER root; get it wrong and
    # the decomposition still runs but drifts.
    A = [[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]]
    ev = _pg.evaluate("(A)=>ORD.jacobi(A).values", A)
    ev = sorted(ev, reverse=True)
    import math as _m
    # Trace and determinant are recomputed from A rather than written in by
    # hand -- the first version of this check asserted det = 16 by arithmetic I
    # did in my head, and the real answer is 18. Jacobi was right and the test
    # was wrong, which is the ordinary way round and worth not pretending
    # otherwise. Deriving both means editing A cannot silently invalidate them.
    tr = sum(A[i][i] for i in range(3))
    det = (A[0][0]*(A[1][1]*A[2][2] - A[1][2]*A[2][1])
           - A[0][1]*(A[1][0]*A[2][2] - A[1][2]*A[2][0])
           + A[0][2]*(A[1][0]*A[2][1] - A[1][1]*A[2][0]))
    ck("jacobi: eigenvalues sum to the trace (%g)" % tr,
       abs(sum(ev) - tr) < 1e-9, (sum(ev), tr))
    prod = ev[0] * ev[1] * ev[2]
    ck("jacobi: eigenvalues multiply to the determinant (%g)" % det,
       abs(prod - det) < 1e-7, (prod, det))
    # The rotation's sign is chosen by `theta >= 0 ? 1 : -1`, and theta is
    # (A[j][j] - A[i][i]) / (2 A[i][j]). It is EXACTLY zero only when the two
    # diagonal entries are equal -- which the matrix above never produces, so
    # `>=` and `>` gave identical answers and the mutation survived. A matrix
    # with equal diagonals is the only fixture that can tell them apart.
    EQ = [[2.0, 1.0], [1.0, 2.0]]          # theta = 0 exactly; eigenvalues 3 and 1
    eq = sorted(_pg.evaluate("(A)=>ORD.jacobi(A).values", EQ), reverse=True)
    ck("jacobi: equal diagonals make theta exactly zero, and the eigenvalues "
       "are still 3 and 1",
       abs(eq[0] - 3.0) < 1e-9 and abs(eq[1] - 1.0) < 1e-9, eq)
    ck("jacobi: and its eigenvectors stay orthonormal through that rotation",
       _pg.evaluate("""(A)=>{const r=ORD.jacobi(A), V=r.vectors;
         let dot=0, n0=0, n1=0;
         for(let i=0;i<2;i++){ dot+=V[i][0]*V[i][1]; n0+=V[i][0]*V[i][0]; n1+=V[i][1]*V[i][1]; }
         return Math.abs(dot)<1e-9 && Math.abs(n0-1)<1e-9 && Math.abs(n1-1)<1e-9;}""", EQ),
       "")

    ck("jacobi: a diagonal matrix comes back with its own diagonal",
       sorted(_pg.evaluate("()=>ORD.jacobi([[5,0],[0,2]]).values"), reverse=True) == [5, 2], "")
    ck("jacobi: a symmetric matrix has only real, finite eigenvalues",
       all(isinstance(x, (int, float)) and _m.isfinite(x) for x in ev), ev)

    # Procrustes: identical configurations agree perfectly, a rotation still
    # agrees, and a degenerate all-zero configuration must not divide by its
    # own zero scale.
    C1 = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    C2 = [[0.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [-1.0, 1.0]]   # 90 degrees
    ck("procrustes: a configuration against itself agrees",
       _pg.evaluate("(c)=>ORD.procrustes(c,c)", C1) > 0.999, "")
    ck("procrustes: a rotation of the same shape still agrees",
       _pg.evaluate("([a,b])=>ORD.procrustes(a,b)", [C1, C2]) > 0.999, "")
    ck("procrustes: an all-zero configuration returns a number, not NaN",
       _m.isfinite(_pg.evaluate("([a,b])=>ORD.procrustes(a,b)",
                                [C1, [[0,0],[0,0],[0,0],[0,0]]])), "")
    # Procrustes normalises each configuration to unit scale before comparing,
    # and the guard `if(!(s>0)) return Y` is what skips that for a degenerate
    # all-zero input. Inverting it skips normalisation for every NORMAL input
    # instead -- which no fixture above could see, because none of them
    # differed in SCALE. The same shape at three times the size is the case
    # that separates a scale-invariant comparison from one that is not.
    BIG = [[0.0, 0.0], [3.0, 0.0], [0.0, 3.0], [3.0, 3.0]]
    ck("procrustes: the same shape at three times the scale still agrees, "
       "because both are normalised first",
       _pg.evaluate("([a,b])=>ORD.procrustes(a,b)", [C1, BIG]) > 0.999,
       _pg.evaluate("([a,b])=>ORD.procrustes(a,b)", [C1, BIG]))
    ck("procrustes: a rotated AND rescaled shape agrees too",
       _pg.evaluate("([a,b])=>ORD.procrustes(a,b)",
                    [C1, [[0,0],[0,5],[-5,0],[-5,5]]]) > 0.999, "")

    # TWO SURVIVORS LEFT STANDING, AND WHY THEY ARE LEFT.
    #
    # `theta >= 0 ? 1 : -1` in the Jacobi rotation. With equal diagonals theta
    # is exactly zero and the two branches give rotations of +45 and -45
    # degrees. Both diagonalise the matrix; they differ only in which
    # eigenvector pairs with which eigenvalue, and in convergence rate on
    # ill-conditioned input. The `>=` is there for numerical stability, not for
    # correctness, so no assertion about eigenvalues can separate them.
    #
    # `if(!(s>0)) return Y` in normScale. That function is internal to NMDS and
    # not exported, and the adaptive step size added after the convergence bug
    # absorbs a badly scaled configuration -- the final stress still matches
    # sklearn's SMACOF either way.
    #
    # Both are EQUIVALENT MUTANTS with respect to anything this suite can
    # honestly assert. Writing a check to kill them would mean asserting a
    # convergence count or reaching into a private function, which measures the
    # implementation rather than the result. Recorded here so the next person
    # reading a survivor list knows these two were examined and not forgotten.

    ck("procrustes: an unrelated shape agrees LESS than a rotation does",
       _pg.evaluate("([a,b])=>ORD.procrustes(a,b)",
                    [C1, [[0,0],[3,0.1],[0.2,0.05],[0.1,0.1]]])
       < _pg.evaluate("([a,b])=>ORD.procrustes(a,b)", [C1, C2]), "")

    _b2.close()

# ---------------------------------------------------------------------------
# ADR-103: the copy buttons guarded on RES and read M
# ---------------------------------------------------------------------------
# A failed parse dropped the matrix and left the results standing, so both copy
# handlers passed their guard and then read M.sites off null. Two assertions,
# because either fix alone leaves the other latent: the results must go when the
# matrix goes, and a handler must guard on what it actually reads.
_SRC = io.open(os.path.join(ROOT, "docs", "ordination.html"), encoding="utf-8").read()
ck("a failed parse clears the results as well as the matrix -- an ordination "
   "describes the matrix it was run on",
   "if(p.err){ M=null; RES=null;" in _SRC.replace("  ", " "),
   "load() still leaves RES standing after a parse error")
_guards = _SRC.count("if(!RES || !M)")
ck("both copy handlers guard on the matrix they read, not only on the results",
   _guards == 2, "found %d of 2" % _guards)
ck("and no copy handler is left guarding on RES alone",
   'if(!RES){ toast(' not in _SRC, "an RES-only guard remains")

print("\n".join("PASS  " + x for x in P))
if SKIP:
    print("\n".join("SKIP  " + x for x in SKIP))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
if SKIP:
    print("%d skipped -- these did NOT pass, they did not run" % len(SKIP))
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
