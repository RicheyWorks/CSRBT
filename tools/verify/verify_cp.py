# -*- coding: utf-8 -*-
import re, sys
from playwright.sync_api import sync_playwright
import os as _os
# The kit is checked out wherever the user keeps it; these suites used to hard-code
# a container path and so could only ever run in the container that wrote them.
ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = _os.path.join(ROOT, "docs") + _os.sep
def _u(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + _os.path.join(ROOT, "docs", name).replace(_os.sep, "/")


def _fek_version():
    """The version FEK actually declares, read from its source rather than frozen
    here -- a bump is not a regression, and a suite that says otherwise gets
    ignored."""
    import re as _re
    src = open(_os.path.join(ROOT, "tools", "fek.py"), encoding="utf-8").read()
    m = _re.search(r'VERSION\s*=\s*"([\d.]+)"', src)
    return m.group(1) if m else None

P=[];F=[]
def ck(n,c,e=""): (P if c else F).append(n+(("  << "+str(e)) if (e and not c) else ""))

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":880,"height":1250})
    pg.set_default_timeout(15000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    def _con(m):
        if m.type!="error": return
        if "ERR_CONNECTION" in m.text or "ERR_FAILED" in m.text: return
        errs.append(m.text)
    pg.on("console",_con)
    pg.goto(_u("cp-bench.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(450)
    ck("no startup errors", not errs, errs[:3])
    ck("6 tabs", pg.eval_on_selector_all(".tab","e=>e.length")==6, "")
    ck("FEK version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), pg.evaluate("()=>FEK.version"))

    def tile(lab, root):
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .fek-tile')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0);
            return t?t.querySelector('.v').textContent.trim():null;}""",[root,lab])
    def setstep(root,val):
        pg.evaluate("""([r,v])=>{const i=document.querySelector(r+' .fek-step .val');
          i.value=String(v); i.dispatchEvent(new Event('input',{bubbles:true}));}""",[root,val])
        pg.wait_for_timeout(90)

    # ---------------- WATER: the three verdict bands ----------------
    setstep("#wEntry", 20); pg.click("#wAdd"); pg.wait_for_timeout(250)
    ck("20 ppm -> excellent", "Excellent" in pg.inner_text("#wOut"), pg.inner_text("#wOut")[:150])
    ck("50 ppm called a convention", "convention" in pg.inner_text("#wOut"), "")
    setstep("#wEntry", 120); pg.click("#wAdd"); pg.wait_for_timeout(250)
    ck("120 ppm -> usable", "Usable" in pg.inner_text("#wOut"), pg.inner_text("#wOut")[:150])
    ck("160 ppm figure cited", "160 ppm" in pg.inner_text("#wOut"), "")
    setstep("#wEntry", 300); pg.click("#wAdd"); pg.wait_for_timeout(250)
    ck("300 ppm -> too high", "Too high" in pg.inner_text("#wOut"), pg.inner_text("#wOut")[:150])
    ck("no amendment removes TDS stated", "no amendment" in pg.inner_text("#wOut"), "")
    ck("3 readings listed", pg.eval_on_selector_all("#wList .row2","e=>e.length")==3, "")

    # ---- the bands are named by their boundaries, so test the boundaries ----
    # 20, 120 and 300 are the middles of the three bands. A mutation sweep
    # turned `tds <= 50` into `tds < 50` and nothing here noticed, because 50
    # itself had never been entered -- and 50 is the number every grower reads,
    # the one the page names in its own sentence, and the one the stepper lands
    # on in tens. Same for 160.
    #
    # The row in the list carries the same two comparisons independently of the
    # verdict, so both are asserted: a page that agreed with itself only in the
    # middle of each band would be a page whose list and verdict can disagree at
    # the edge, which is where somebody actually looks.
    def _band(v):
        setstep("#wEntry", v); pg.click("#wAdd"); pg.wait_for_timeout(250)
        return pg.inner_text("#wOut"), pg.inner_text("#wList .row2")
    _o50, _r50 = _band(50)
    ck("exactly 50 ppm is inside the convention, not above it",
       "Excellent" in _o50 and "Usable" not in _o50, _o50[:160])
    ck("and the reading's own row says the same at 50",
       "inside the 50 ppm convention" in _r50, _r50[:160])
    _o160, _r160 = _band(160)
    ck("exactly 160 ppm is under the guidance, not over it",
       "Usable" in _o160 and "Too high" not in _o160, _o160[:160])
    ck("and the reading's own row says the same at 160",
       "under the 160 ppm guidance" in _r160, _r160[:160])
    # ...and one ppm past each boundary really does move, so the fixtures above
    # are not passing because the page ignores the number.
    _o51, _ = _band(51)
    ck("51 ppm has left the convention band", "Usable" in _o51, _o51[:160])
    _o161, _ = _band(161)
    ck("161 ppm has left the guidance band", "Too high" in _o161, _o161[:160])

    # RO creep: three RO readings climbing
    for v in (5,20,45):
        setstep("#wEntry", v); pg.click("#wAdd"); pg.wait_for_timeout(150)
    ck("RO membrane creep flagged", "membrane" in pg.inner_text("#wOut"), pg.inner_text("#wOut")[-300:])

    # ---------------- tray accumulation, known answer ----------------
    # 50 ppm, 10 top-ups, 250 mL  -> mg = 50 * 0.25 * 10 = 125 mg ; equiv = 500 ppm
    ck("accumulation mg = 125", tile("dissolved solids","#wAccumOut")=="125 mg",
       tile("dissolved solids","#wAccumOut"))
    ck("equivalent = 500 ppm", tile("same as one watering","#wAccumOut")=="500 ppm",
       tile("same as one watering","#wAccumOut"))
    ck("evaporated = 2.5 L", tile("water evaporated","#wAccumOut")=="2.5 L",
       tile("water evaporated","#wAccumOut"))
    ao=pg.inner_text("#wAccumOut")
    ck("500 ppm past the guidance", "past the published 160" in ao, ao[:250])
    ck("flush advice given", "Flush the pots" in ao, "")
    ck("upper bound stated", "upper bound" in ao, "")

    # ---------------- MEDIA ----------------
    pg.click('.tab[data-pane="p-mix"]'); pg.wait_for_timeout(250)
    ck("7 presets offered", pg.eval_on_selector_all("#mPresets .fek-chip","e=>e.length")==7,
       pg.eval_on_selector_all("#mPresets .fek-chip","e=>e.length"))
    ck("presets labelled conventions", "conventions" in pg.inner_text("#mPresets"), "")
    pg.evaluate("""()=>{[...document.querySelectorAll('#mPresets .fek-chip')]
      .find(b=>b.textContent.indexOf('Sarracenia · Dionaea')===0).click();}""")
    pg.wait_for_timeout(300)
    mo=pg.inner_text("#mOut")
    ck("preset loads 2 parts", "2 parts" in mo, mo[:150])
    ck("nutrient load 0.00", tile("nutrient load","#mOut")=="0.00 / 5", tile("nutrient load","#mOut"))
    ck("nutrient-free banner", "Nutrient-free" in mo, "")
    ck("preset note shown", "near-universal default" in mo, "")
    ck("silica sand warning always shown", "must be silica" in mo, "")
    # add coir -> not nutrient free
    pg.evaluate("""()=>{const b=[...document.querySelectorAll('#mGrid button')]
      .find(x=>x.querySelector('span').textContent.trim()==='coconut coir'); b.click();}""")
    pg.wait_for_timeout(300)
    ck("coir breaks nutrient-free", "not nutrient-free" in pg.inner_text("#mOut"),
       pg.inner_text("#mOut")[:250])
    ck("coir salts explained", "carries salts" in pg.inner_text("#mOut"), "")

    # ---------------- PLANTS ----------------
    pg.click('.tab[data-pane="p-pl"]'); pg.wait_for_timeout(250)
    def pickOpt(root,name):
        pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
          s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""",[root,name])
        pg.wait_for_timeout(120)
        pg.evaluate("""(r)=>{document.querySelector(r+' .opt').click();}""",root)
        pg.wait_for_timeout(120)
    pickOpt("#pNew","Sarracenia")
    ck("genus sub shows dormancy fact", "dormancy: all cultivated" in pg.inner_text("#pNew"),
       pg.inner_text("#pNew")[:250])
    pg.fill("#pnm","S. flava 'Claret'"); pg.click("#pAdd"); pg.wait_for_timeout(250)
    ck("plant added", pg.eval_on_selector_all("#pList .row2","e=>e.length")==1, "")
    ck("missing source flagged in list", "no source recorded" in pg.inner_text("#pList"), "")
    ck("missing source flagged in summary", "no source recorded" in pg.inner_text("#pOut"),
       pg.inner_text("#pOut")[-250:])
    ck("poaching context given", "poached" in pg.inner_text("#pOut"), "")
    # log a rising trap count
    for n in (4,6,9):
        pickOpt("#pObs","S. flava")
        setstep("#pObs", n)
        pg.click("#oAdd"); pg.wait_for_timeout(160)
    pg.wait_for_timeout(250)
    po=pg.inner_text("#pOut")
    ck("trap trend reported up 4->9", "Up from 4 to 9" in po, po[:300])
    ck("seasonality caveat on trap counts", "seasonal" in po, "")
    ck("trap chart drawn", pg.eval_on_selector_all("#pOut svg","e=>e.length")==1, "")

    # ---- ...and the line has to be inside the chart -----------------------
    # "an svg exists" was the whole of this page's chart coverage. A mutation
    # sweep replaced `hi = Math.max(series)` with a min: hi then equals lo, the
    # `hi === lo` guard bumps it to lo + 1, and every count above that is drawn
    # far above the top of the frame -- y around -456 in a 170-high viewBox for
    # this very 4/6/9 series. Nothing noticed, because nothing had ever read the
    # path.
    #
    # Same rule as the ordination plot: inside the frame, and using it. A scale
    # that collapsed the line onto one row would satisfy the first and not the
    # second.
    _vb = pg.eval_on_selector("#pOut svg", "e=>e.getAttribute('viewBox')")
    _W, _H = [float(x) for x in _vb.split()[2:4]]
    _d = pg.eval_on_selector("#pOut svg path", "e=>e.getAttribute('d')")
    _pts = [(float(a), float(b)) for a, b in
            re.findall(r"[ML]([-\d.]+),([-\d.]+)", _d or "")]
    ck("the trend line has a point per observation", len(_pts) == 3, (_d or "")[:120])
    ck("every point on the trend line is inside the chart",
       all(0 <= x <= _W for x, _ in _pts) and all(0 <= y <= _H for _, y in _pts),
       [(round(x, 1), round(y, 1)) for x, y in _pts])
    ck("and a rising count rises -- later points sit higher, so y decreases",
       [y for _, y in _pts] == sorted([y for _, y in _pts], reverse=True)
       and _pts[0][1] > _pts[-1][1],
       [round(y, 1) for _, y in _pts])

    # ---------------- DORMANCY: the gate-3 refusal ----------------
    pg.click('.tab[data-pane="p-sea"]'); pg.wait_for_timeout(250)
    sr=pg.inner_text("#sRefuse")
    ck("refuses to supply dormancy temp", "will not tell you your dormancy temperature" in sr, sr[:200])
    ck("refusal cites no citable source", "no citable source" in sr, "")
    ck("refusal links ADR-031", pg.eval_on_selector_all('#sRefuse a[href*="adr-031"]',"e=>e.length")>=1, "")
    pickOpt("#sTarget","Nepenthes"); pg.wait_for_timeout(250)
    ck("Nepenthes: no winter dormancy", "no winter dormancy" in pg.inner_text("#sOut"),
       pg.inner_text("#sOut")[:200])
    pickOpt("#sTarget","Sarracenia"); pg.wait_for_timeout(250)
    ck("Sarracenia: needs a dormancy", "needs a dormancy" in pg.inner_text("#sOut"),
       pg.inner_text("#sOut")[:200])
    ck("qualitative fact shipped, numbers not", "numbers are still yours" in pg.inner_text("#sOut"), "")
    pg.click("#sDemo"); pg.wait_for_timeout(400)
    demo=[12,10,9,7,5,4,6,8,3,2,4,5,7,6,9,11,8,6,4,3,5,7,9,12,14,11,9,7,6,8,
          5,4,3,6,8,10,7,5,4,6,9,11,13,10,8,6,5,7,9,12,14,16,13,11,9,12,15,17]
    at=sum(1 for t in demo if t<=10)
    run=best=0
    for t in demo:
        run = run+1 if t<=10 else 0
        best=max(best,run)
    ck("days at or below 10C = %d"%at, tile("days at or below","#sOut")=="%d / 84"%at,
       tile("days at or below","#sOut"))
    ck("longest run = %d"%best, tile("longest unbroken run","#sOut")==str(best),
       tile("longest unbroken run","#sOut"))
    ck("readings = %d"%len(demo), tile("readings","#sOut")==str(len(demo)), tile("readings","#sOut"))
    so=pg.inner_text("#sOut")
    ck("shortfall reported", "days short of your target" in so, so[-350:])
    ck("no opinion on the number", "cumulative cold" in so, "")
    ck("dormancy chart drawn", pg.eval_on_selector_all("#sChart svg","e=>e.length")==1, "")
    ck("target line labelled 'your target'", "your target" in pg.inner_text("#sChart"), "")

    # ---------------- CROSSES ----------------
    pg.click('.tab[data-pane="p-cro"]'); pg.wait_for_timeout(250)
    ck("pod parent labelled 'written first'", "written first" in pg.inner_text("#cNew"), "")
    pg.fill("#xpod","S. leucophylla 'Tarnok'"); pg.fill("#xpol","S. flava var. ornata")
    pg.click("#cAdd"); pg.wait_for_timeout(250)
    ck("cross recorded", pg.eval_on_selector_all("#cList .row2","e=>e.length")==1, "")
    pickOpt("#cUpd","Tarnok")
    pg.evaluate("""()=>{const s=[...document.querySelectorAll('#cUpd .fek-step .val')];
      s[0].value='200'; s[0].dispatchEvent(new Event('input',{bubbles:true}));
      s[1].value='80';  s[1].dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(120); pg.click("#cSave"); pg.wait_for_timeout(300)
    ck("germination 40.0%", tile("germination overall","#cOut")=="40.0%", tile("germination overall","#cOut"))
    ck("seed total 200", tile("seed collected","#cOut")=="200", tile("seed collected","#cOut"))
    co=pg.inner_text("#cOut")
    ck("germination caveated as method", "about your method" in co, co[:250])
    ck("reciprocal crosses noted", "Reciprocal" in co or "reciprocal" in co, "")
    ck("cannot verify parentage", "cannot verify parentage" in co, "")

    # ---------------- METHOD ----------------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace("\u00a0"," ")   # nbsp in "50 ppm", "160 ppm"
    for t in ["160","50 ppm","upper bound","gate 3","oreophila","CITES","felony","silica","MaxSea"]:
        ck("method covers "+t, t in m, "")
    ck("says why dormancy numbers absent", "no citable primary source" in m, "")

    # ---------------- FEK sizing + viewport ----------------
    small=pg.evaluate("""()=>{const bad=[];
      document.querySelectorAll('.fek-step button,.fek-dial button,.fek-chip,.fek-pick .opt').forEach(e=>{
        const r=e.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.height<44) bad.push(e.className);});
      return bad.slice(0,5);}""")
    ck("FEK targets >= 44px", not small, small)
    for w,hh in [(390,844),(768,1024)]:
        pg.set_viewport_size({"width":w,"height":hh})
        for t in ["p-wat","p-mix","p-pl","p-sea","p-cro","p-met"]:
            pg.click('.tab[data-pane="%s"]'%t); pg.wait_for_timeout(140)
            ow=pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            ck("no h-overflow %d %s"%(w,t), ow<=w+1, "%d > %d"%(ow,w))
    ck("no errors at end", not errs, errs[:3])
    b.close()
print("PASS %d"%len(P))
for x in F: print("FAIL:",x)
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
sys.exit(1 if F else 0)
