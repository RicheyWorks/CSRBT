# -*- coding: utf-8 -*-
# Declared for tools/verify/verify_advertised.py: this suite is THE page suite
# for the page below -- the one whose size a hub page is entitled to advertise.
# Declared rather than inferred, for the reason the mutate role markers exist:
# deriving it from "which pages does this file mention" returns seven suites for
# the bench page below, because every cross-cutting suite mentions it. That is
# a fact about mentions, not about ownership -- and note that this comment may
# not NAME another page while making the point (ADR-077): a sentence about the
# rule that mentions a filename is itself a mention, and mutate.py reads
# mentions.
PAGE_SUITE_FOR = "stand-sheet.html"
import math
from playwright.sync_api import sync_playwright
import os as _os
# The kit is checked out wherever the user keeps it; these suites used to hard-code
# a container path and so could only ever run in the container that wrote them.
ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = _os.path.join(ROOT, "docs") + _os.sep
def _u(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + _os.path.join(ROOT, "docs", name).replace(_os.sep, "/")


def _figs(banner):
    """The two numbers the area banner prints, read back out of the sentence a
    field worker reads. ADR-198: the whole defect was that these two disagreed
    with the plot and agreed with each other, so a check that recomputes them
    from the page's own state would have missed it -- they have to come off
    the rendered text. Reads the banner's "Expansion factor 25.02" and the
    field sheet's terser "EF 25.02" alike, so the two can be compared."""
    import re as _re
    m = _re.search(r"([\d.]+)\s*m²", banner)
    e = _re.search(r"(?:Expansion factor|EF)\s*([\d.]+)", banner)
    return (float(m.group(1)) if m else None, float(e.group(1)) if e else None)


def _clip(pg, btn):
    """What the page's own copy button handed to the clipboard. The button is
    the real path -- a suite that calls the row builder directly would pass on
    a page whose button is wired to nothing."""
    pg.evaluate("""()=>{window.__clip=null;
      Object.defineProperty(navigator,'clipboard',{configurable:true,
        value:{writeText:function(t){window.__clip=t;return Promise.resolve();}}});}""")
    pane = pg.evaluate("""(s)=>{const e=document.querySelector(s); if(!e) return null;
      const p=e.closest('section.pane'); return p?p.id:null;}""", btn)
    if pane:
        pg.evaluate("""(p)=>{const t=document.querySelector('.tab[data-pane="'+p+'"]');
          if(t) t.click();}""", pane)
        pg.wait_for_timeout(200)
    pg.click(btn)
    pg.wait_for_timeout(250)
    return pg.evaluate("()=>window.__clip")


def _dwc(pg):
    """The Darwin Core rows the export button builds, caught at DWC.table --
    the same hook the cross-page deposit suite uses."""
    pg.evaluate("""()=>{window.__cap=null; var o=DWC.table;
      DWC.table=function(r){ window.__cap=r; return o(r); };}""")
    pane = pg.evaluate("""()=>{const e=document.querySelector('#dwcCopy');
      if(!e) return null; const p=e.closest('section.pane'); return p?p.id:null;}""")
    if pane:
        pg.evaluate("""(p)=>{const t=document.querySelector('.tab[data-pane="'+p+'"]');
          if(t) t.click();}""", pane)
        pg.wait_for_timeout(200)
    pg.click("#dwcCopy")
    pg.wait_for_timeout(250)
    return pg.evaluate("()=>window.__cap")


def _edge(pg, a, b, typename):
    """Record one interaction the way a thumb does."""
    pg.click('.tab[data-pane="p-web"]'); pg.wait_for_timeout(220)
    pg.fill("#iA", a); pg.fill("#iB", b)
    pg.evaluate("""(n)=>{const o=[...document.querySelectorAll('#intEntry .opt')]
      .find(x=>x.textContent.indexOf(n)>=0); if(o) o.click();}""", typename)
    pg.wait_for_timeout(150)
    pg.click("#iAdd"); pg.wait_for_timeout(220)


def _thlab(pg):
    """The top-height tile's label, or "" when the tile is not shown. ADR-198
    put the sample size in a tile of its own rather than in this label, so
    this is checked for STABILITY: a figure whose name moves with the data
    cannot be followed across a session."""
    return pg.evaluate("""()=>{const t=[...document.querySelectorAll('#tStats .tile .l')]
      .find(x=>x.textContent.indexOf('top height')>=0); return t?t.textContent:"";}""")


def _slack(area, ef):
    """How far a printed area times a printed factor may sit off 10,000 and
    still be nothing but the two roundings. Each is printed to two decimals,
    so each is within 0.005 of the truth."""
    return 0.005 * (area + ef) + 1e-9


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
    # ADR-209: A SUITE MUST ANSWER THE QUESTIONS THE PAGE ASKS. Headless
    # Chromium DISMISSES an unhandled dialog, so a confirmation added to a
    # destructive control silently turns every press of it into a no-op --
    # and a check that presses Clear and then asserts the sheet is empty
    # would pass only because the page never got to ask.
    pg.on("dialog", lambda d: d.accept())
    def _con(m):
        if m.type!="error": return
        if "ERR_CONNECTION" in m.text or "ERR_FAILED" in m.text: return
        errs.append(m.text)
    pg.on("console",_con)
    pg.goto(_u("stand-sheet.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    ck("no startup errors", not errs, errs[:3])
    ck("FEK version matches fek.py", pg.evaluate("()=>typeof FEK!=='undefined'&&FEK.version")==_fek_version(),
       pg.evaluate("()=>typeof FEK"))
    ck("6 tabs", pg.eval_on_selector_all(".tab","e=>e.length")==6, "")

    def tile(lab, root):
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .tile,'+r+' .fek-tile')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0);
            return t?t.querySelector('.v').textContent.trim():null;}""",[root,lab])
    def setstep(root,idx,val):
        pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
          s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(120)
    def dialclick(root,idx,label):
        pg.evaluate("""([r,i,l])=>{const d=[...document.querySelectorAll(r+' .fek-dial')][i];
          const b=[...d.querySelectorAll('button')].find(x=>x.querySelector('span').textContent.trim()===l);
          b.click();}""",[root,idx,label])
        pg.wait_for_timeout(150)
    def pick(root,name):
        pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
          s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""",[root,name])
        pg.wait_for_timeout(140)
        pg.evaluate("(r)=>{document.querySelector(r+' .opt').click();}",root)
        pg.wait_for_timeout(160)

    # -------------- TALLY: entry layer is FEK --------------
    pg.click('.tab[data-pane="p-trees"]'); pg.wait_for_timeout(300)
    ck("tally species is a FEK picker", pg.eval_on_selector_all("#tEntry .fek-pick","e=>e.length")==1, "")
    ck("tally has 2 FEK steppers", pg.eval_on_selector_all("#tEntry .fek-step","e=>e.length")==2, "")
    ck("tally has 2 FEK dials", pg.eval_on_selector_all("#tEntry .fek-dial","e=>e.length")==2, "")
    ck("no legacy select left on tally",
       pg.eval_on_selector_all("#p-trees select","e=>e.length")==0,
       pg.eval_on_selector_all("#p-trees select","e=>e.map(x=>x.id)"))
    ck("species list populated", pg.eval_on_selector_all("#tEntry .opt","e=>e.length")>10,
       pg.eval_on_selector_all("#tEntry .opt","e=>e.length"))
    ck("unknown option offered",
       pg.evaluate("()=>[...document.querySelectorAll('#tEntry .opt')].some(o=>o.textContent.indexOf('unknown')>=0)"),"")

    # add four stems: 30, 25, 40, 20 cm on the default 11.28 m plot
    pick("#tEntry","fir")
    sp=pg.evaluate("()=>document.querySelector('#tEntry .opt.on').textContent")
    ck("picker selection sticks", sp is not None and len(sp)>2, sp)
    for d in [30,25,40,20]:
        setstep("#tEntry",0,d)
        pg.click("#tAdd"); pg.wait_for_timeout(220)
    ck("4 live stems", tile("live stems","#tStats")=="4", tile("live stems","#tStats"))
    ck("DBH resets to 0 after add",
       pg.evaluate("()=>document.querySelectorAll('#tEntry .fek-step .val')[0].value")=="0.0",
       pg.evaluate("()=>document.querySelectorAll('#tEntry .fek-step .val')[0].value"))
    # known answers
    A=math.pi*11.28**2; E=10000/A
    ba=sum(0.00007854*d*d for d in [30,25,40,20])
    qmd=math.sqrt(sum(d*d for d in [30,25,40,20])/4)
    nha=4*E; sdi=nha*(qmd/25)**1.605
    ck("live stems/ha = %d"%round(nha), tile("live stems/ha","#tStats")==str(round(nha)),
       tile("live stems/ha","#tStats"))
    ck("live BA = %.1f m2/ha"%(ba*E), tile("live BA","#tStats")=="%.1f"%(ba*E),
       tile("live BA","#tStats"))
    ck("QMD = %.1f cm"%qmd, tile("QMD","#tStats")=="%.1f"%qmd, tile("QMD","#tStats"))
    ck("SDI = %d"%round(sdi), tile("SDI","#tStats")==str(round(sdi)), tile("SDI","#tStats"))

    # snag via the status dial
    setstep("#tEntry",0,35)
    dialclick("#tEntry",1,"snag 3")
    pg.click("#tAdd"); pg.wait_for_timeout(250)
    ck("snag counted separately", tile("snags","#tStats")=="1", tile("snags","#tStats"))
    ck("live count unchanged by snag", tile("live stems","#tStats")=="4", tile("live stems","#tStats"))
    dialclick("#tEntry",1,"live")
    pg.click("#tUndo"); pg.wait_for_timeout(250)
    ck("undo removes the snag", tile("snags","#tStats")=="0", tile("snags","#tStats"))

    # refuses a stem with no DBH
    setstep("#tEntry",0,0)
    pg.click("#tAdd"); pg.wait_for_timeout(300)
    ck("zero DBH refused", tile("live stems","#tStats")=="4", tile("live stems","#tStats"))
    ck("refusal is explained", "needs a DBH" in pg.inner_text("#toast"), pg.inner_text("#toast"))

    # -------------- HEIGHT FROM ANGLES --------------
    pg.click("#htToggle"); pg.wait_for_timeout(250)
    ck("height card uses FEK", pg.eval_on_selector_all("#htEntry .fek-step","e=>e.length")==3, "")
    setstep("#htEntry",0,20); setstep("#htEntry",1,42); setstep("#htEntry",2,-8)
    pg.wait_for_timeout(250)
    hexp=20*(math.tan(math.radians(42))-math.tan(math.radians(-8)))
    ho=pg.inner_text("#hOut")
    ck("height = %.1f m"%hexp, ("%.1f"%hexp) in ho, ho[:200])
    # A horizontal distance of ZERO is not a small distance, it is no distance,
    # and the formula divides the tree's height by it in effect: D * (tan t -
    # tan b) is 0 for every pair of angles. The page guards `D <= 0` and says
    # "enter a horizontal distance". A mutation sweep turned that into `D < 0`
    # and nothing here noticed: with D = 0 the guard stops firing, height()
    # returns 0 instead of null, and the page offers a SIGN diagnosis --
    # "check the signs, looking up is positive" -- for a reading whose problem
    # is not the signs at all. 0 is reachable: it is the bottom of the distance
    # stepper's own range.
    #
    # Asserted as an equivalence rather than as prose: zero distance must be
    # refused the same way a missing one is. That survives a rewording of the
    # message, which a pinned string does not (four suites in this kit have
    # broken that way).
    blank = pg.evaluate("""()=>{const e=document.getElementById('hD');
        e.value=''; e.dispatchEvent(new Event('input',{bubbles:true}));
        return document.getElementById('hOut').innerText.trim();}""")
    zero = pg.evaluate("""()=>{const e=document.getElementById('hD');
        e.value='0'; e.dispatchEvent(new Event('input',{bubbles:true}));
        return document.getElementById('hOut').innerText.trim();}""")
    ck("a zero horizontal distance is refused exactly as a missing one is",
       zero == blank and zero != "", (zero[:90], blank[:90]))
    ck("and it is not diagnosed as a sign error",
       "sign" not in zero.lower(), zero[:140])
    # ...and the fixture is not vacuous: a real distance still computes.
    setstep("#htEntry",0,20); pg.wait_for_timeout(250)
    ck("a real distance still gives a height",
       ("%.1f"%hexp) in pg.inner_text("#hOut"), pg.inner_text("#hOut")[:120])

    pg.click("#hUse"); pg.wait_for_timeout(250)
    ck("height copies into the tally stepper",
       pg.evaluate("()=>document.querySelectorAll('#tEntry .fek-step .val')[1].value")=="%.1f"%hexp,
       pg.evaluate("()=>document.querySelectorAll('#tEntry .fek-step .val')[1].value"))

    # -------------- PLOT --------------
    pg.click('.tab[data-pane="p-plot"]'); pg.wait_for_timeout(300)
    # Not a count. "== 3" was an assertion that a legitimate change breaks, and
    # it broke the moment breast height became a control instead of a constant
    # baked into four sentences (ADR-041). What the check means is that the
    # geometry block is built from the kit's components and carries the
    # parameters an expansion factor is meaningless without -- so it names them.
    geo_labels = pg.eval_on_selector_all(
        "#geoEntry .fek-lab", "e=>e.map(x=>x.textContent.toLowerCase())")
    ck("geometry is FEK", pg.eval_on_selector_all("#geoEntry .fek-row","e=>e.length")>=3,
       geo_labels)
    ck("geometry names its method parameters, not just its shape",
       any("breast height" in l for l in geo_labels)
       and any("min dbh" in l for l in geo_labels)
       and any("design" in l for l in geo_labels), geo_labels)
    ck("physiography is FEK", pg.eval_on_selector_all("#physEntry .fek-row","e=>e.length")==5, "")
    ck("cover is FEK", pg.eval_on_selector_all("#covEntry .fek-row","e=>e.length")==6, "")
    ck("no legacy select left on plot",
       pg.eval_on_selector_all("#p-plot select","e=>e.length")==0,
       pg.eval_on_selector_all("#p-plot select","e=>e.map(x=>x.id)"))
    sa=pg.inner_text("#sAreaOut")
    # ADR-198. The banner used to round the default circle to "400 m²" at
    # "EF 25.0" -- a pair that is internally consistent (10,000/400 IS 25.0)
    # and wrong about the plot, while the CSV scaled on the real 25.01681.
    # These check the printed figures against the geometry, and then against
    # each other, which is the property that failed.
    ck("default circle is printed as what it encloses, not as its nickname",
       "399.73 m²" in sa and "400 m²" not in sa, sa[:160])
    ck("expansion factor printed to the place that distinguishes it",
       "Expansion factor 25.02" in sa, sa[:160])
    pa, pe = _figs(sa)
    ck("printed area = πr² to the place printed", abs(pa-A) < 0.005, (pa, A))
    ck("printed EF = 10,000/area to the place printed", abs(pe-E) < 0.005, (pe, E))
    # Both figures are printed to two decimals, so each carries up to half a
    # hundredth of error and the product carries 0.005*(a+e) of it. Anything
    # beyond that is not rounding, it is two different plots.
    ck("printed EF and printed area reconcile to a hectare",
       abs(pa*pe-10000) <= _slack(pa, pe), (pa, pe, pa*pe, _slack(pa, pe)))
    ck("banner's hectares agree with its square metres",
       ("%.4f"%(pa/10000)) in sa, sa[:160])
    # switch to rectangle
    pg.evaluate("""()=>{const c=[...document.querySelectorAll('#geoEntry .fek-chip')]
      .find(x=>x.textContent.indexOf('rectangle')>=0); c.click();}""")
    pg.wait_for_timeout(300)
    ck("rectangle swaps in length and width",
       # The unit span sits inside the label element, so textContent reads
       # "lengthm" and "widthm" -- prefix, not equality.
       all(any(l.startswith(w) for l in pg.eval_on_selector_all(
           "#geoEntry .fek-lab","e=>e.map(x=>x.textContent.toLowerCase())"))
           for w in ("length","width")),
       pg.eval_on_selector_all("#geoEntry .fek-lab","e=>e.map(x=>x.textContent)"))
    ck("and the radius goes away with it",
       not any(l.startswith("radius") for l in pg.eval_on_selector_all(
           "#geoEntry .fek-lab","e=>e.map(x=>x.textContent.toLowerCase())")),
       pg.eval_on_selector_all("#geoEntry .fek-lab","e=>e.map(x=>x.textContent)"))
    ra=pg.inner_text("#sAreaOut")
    ck("20x20 = 400 m2", "400 m²" in ra, ra[:120])
    # A rectangle's 400 and 25.0 were never the bug -- they are exact -- so
    # ADR-198's trimming must leave them alone, decimal and all.
    ck("a rectangle keeps the factor's decimal", "Expansion factor 25.0 " in ra, ra[:160])
    ck("and does not grow one it has not earned", "25.00" not in ra, ra[:160])
    rpa, rpe = _figs(ra)
    ck("rectangle figures reconcile too", abs(rpa*rpe-10000) <= _slack(rpa, rpe), (rpa, rpe))
    # And the other radius the page argues about: it warned that 5.64 m is
    # "EF 100.1, not 100.0" while printing that plot's area as "100 m²".
    pg.eval_on_selector("#sDesign","e=>{e.value='circ';e.dispatchEvent(new Event('input',{bubbles:true}))}")
    pg.eval_on_selector("#sRad","e=>{e.value='5.64';e.dispatchEvent(new Event('input',{bubbles:true}))}")
    pg.wait_for_timeout(250)
    ha=pg.inner_text("#sAreaOut")
    hpa, hpe = _figs(ha)
    ck("the tenth-hectare plot stops calling itself 100 m2",
       abs(hpa-math.pi*5.64**2) < 0.005 and "100 m²" not in ha, (hpa, ha[:120]))
    ck("its factor is the one the page always insisted on",
       abs(hpe-10000/(math.pi*5.64**2)) < 0.005 and hpe > 100.0, (hpe,))
    ck("and that pair reconciles as well", abs(hpa*hpe-10000) <= _slack(hpa, hpe), (hpa, hpe))
    pg.eval_on_selector("#sRad","e=>{e.value='11.28';e.dispatchEvent(new Event('input',{bubbles:true}))}")
    pg.wait_for_timeout(250)
    pg.evaluate("""()=>{const c=[...document.querySelectorAll('#geoEntry .fek-chip')]
      .find(x=>x.textContent.indexOf('rectangle')>=0); c.click();}""")
    pg.wait_for_timeout(250)
    pg.evaluate("""()=>{const c=[...document.querySelectorAll('#geoEntry .fek-chip')]
      .find(x=>x.textContent.indexOf('circle')>=0); c.click();}""")
    pg.wait_for_timeout(300)

    # aspect: blank until touched, then folded correctly
    ck("aspect blank before entry", pg.inner_text("#sHeatOut").strip()=="",
       pg.inner_text("#sHeatOut")[:80])
    dialclick("#physEntry",0,"SW"); pg.wait_for_timeout(250)
    hl=pg.inner_text("#sHeatOut")
    ck("SW folds to 180", "180°" in hl, hl[:160])
    ck("SW reads as the drought end", "drought end" in hl, hl[:200])
    dialclick("#physEntry",0,"NE"); pg.wait_for_timeout(250)
    hl=pg.inner_text("#sHeatOut")
    ck("NE folds to 0", "0°" in hl, hl[:160])
    ck("NE reads as the moist end", "moist end" in hl, hl[:200])
    ck("McCune & Keon credited", "McCune" in hl, "")

    # cover sliders write through
    pg.evaluate("""()=>{const r=document.querySelectorAll('#covEntry input[type=range]')[0];
      r.value='60'; r.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(200)
    ck("canopy slider writes through", pg.evaluate("()=>document.getElementById('sCan').value")=="60",
       pg.evaluate("()=>document.getElementById('sCan').value"))

    # CWD known answer
    pg.fill("#cwdD","12 8 31 45 9"); pg.wait_for_timeout(300)
    s=sum(x*x for x in [12,8,31,45,9]); V=math.pi**2*s/(8*30)
    co=pg.inner_text("#cwdOut")
    ck("CWD volume = %.1f m3/ha"%V, ("%.1f"%V) in co, co[:250])
    ck("CWD pieces counted", tile("pieces crossed","#cwdOut")=="5", tile("pieces crossed","#cwdOut"))
    ck("van Wagner formula shown", "8L" in co or "8·30" in co, co[:200])
    setstep("#cwdEntry",0,60); pg.wait_for_timeout(300)
    V2=math.pi**2*s/(8*60)
    ck("doubling the transect halves the volume", ("%.1f"%V2) in pg.inner_text("#cwdOut"),
       pg.inner_text("#cwdOut")[:200])

    # -------------- EXPORT carries the FEK-entered values --------------
    eco=pg.evaluate("()=>document.getElementById('ecoOut').textContent")
    ck("export names the plot geometry", "circle r=11.28 m" in eco, eco[:300])
    # ADR-198. "EF %.1f" was a prefix of the right answer and of the wrong
    # one -- "EF 25.0" is in "EF 25.02" -- so it could not have caught this.
    # The line is read as a line, and reconciled the way the banner is.
    import re as _re
    _pl = [l for l in eco.split("\n") if l.startswith("# plot:")]
    ck("export carries a plot line", len(_pl)==1, _pl[:2])
    epa, epe = _figs(_pl[0]) if _pl else (None, None)
    ck("export carries the expansion factor", epe is not None and abs(epe-E) < 0.005, (epe, E))
    ck("export's area is the plot's, not its nickname",
       epa is not None and abs(epa-A) < 0.005, (epa, A))
    ck("export's own two figures reconcile",
       epa is not None and abs(epa*epe-10000) <= _slack(epa, epe), (epa, epe))
    ck("export agrees with the banner it was read off",
       (epa, epe) == (pa, pe), (epa, epe, pa, pe))
    ck("export carries min DBH", "min DBH 5" in eco, eco[:300])
    # Breast height is a method parameter: 1.37 m is North American, 1.30 m is
    # the rest of the world, and DBH is squared into basal area and QMD and
    # raised to 1.605 in SDI. Two sheets recorded at different heights are not
    # comparable, so the sheet has to SAY which it used -- exactly the rule it
    # already applies to the minimum tallied diameter. Checked on the export,
    # not on the control: a control nothing records is decoration.
    ck("export records the breast height used", "breast height 1.37 m" in eco, eco[:400])
    # Guarded. An unguarded .click() on a control that is not there raises, and
    # a check that raises has told you nothing -- worse, it aborts the run and
    # hides every check after it. A canary that removed the control crashed the
    # suite instead of failing the two checks that name it.
    def bhclick(text):
        return pg.evaluate("""(t)=>{const b=[...document.querySelectorAll(
          '#geoEntry .fek-dial button')].find(x=>x.textContent.indexOf(t)>=0);
          if(!b) return false; b.click(); return true;}""", text)

    ck("the breast-height control is a dial that can be changed", bhclick("1.30"), "")
    pg.wait_for_timeout(300)
    eco130=pg.evaluate("()=>document.getElementById('ecoOut').textContent")
    ck("and it follows the control rather than being hardcoded",
       "breast height 1.30 m" in eco130 and "breast height 1.37 m" not in eco130, eco130[:400])
    bhclick("1.37")
    pg.wait_for_timeout(300)
    eco=pg.evaluate("()=>document.getElementById('ecoOut').textContent")
    ck("export carries the folded-aspect entry", "aspect 45" in eco, eco[:400])
    ck("export carries canopy cover", "canopy 60%" in eco, eco[:500])
    ck("export carries CWD", "coarse woody debris %.1f m3/ha"%V2 in eco, eco[:600])
    ck("export aggregates by species", "Douglas-fir=4" in eco, eco[:500])
    ck("export gives species basal area", "%.2f m²/ha"%(ba*E) in eco, eco[:500])
    ck("export states the one-plot caveat", "point estimate with no variance" in eco, eco[-300:])

    # -------------- ADR-198: the deposits reconcile with the screen ----------
    # The stem CSV's per-hectare column is computed from the UNROUNDED factor.
    # That is the right number; the defect was that the sheet printed a factor
    # you could not get it back from. So the property is not "the column is
    # exact" -- it is "a reader who has only the printed factor recomputes the
    # column to within what that factor's own precision allows". Under the old
    # "EF 25.0" a 30 cm stem is out by 0.0012 m²/ha against a tolerance of
    # 0.0004, which is what makes this an oracle rather than a restatement.
    csv = _clip(pg, "#csvCopy")
    ck("stem CSV copies", csv is not None and csv.count("\n") >= 4, (csv or "")[:80])
    if csv:
        head = csv.split("\n")[0].split(",")
        ck("stem CSV names a per-hectare basal area column",
           "ba_m2_ha" in head and "ba_m2" in head, head)
        i_ba, i_ha = head.index("ba_m2"), head.index("ba_m2_ha")
        bad = []
        for _ln in csv.split("\n")[1:]:
            if not _ln.strip():
                continue
            _f = _ln.split(",")
            _ba, _bh = float(_f[i_ba]), float(_f[i_ha])
            # _ba is printed to 5 decimals and pe to 2, so _ba*pe carries
            # 0.005*_ba of factor error and a hundred-thousandth of area
            # error, and _bh itself is printed to 4.
            tol = 0.005 * _ba + 0.00001 * pe + 0.00005
            if abs(_bh - _ba * pe) > tol:
                bad.append((_f[0:2], _ba, _bh, _ba * pe, tol))
        ck("every per-hectare basal area is recomputable from the printed factor",
           not bad, bad[:2])
        # ...and it really is the unrounded factor underneath, recomputed from
        # the DBH in the same row rather than from the rounded ba_m2 beside it
        # -- that rounding alone moves the fourth decimal.
        i_d = head.index("dbh_cm")
        ck("and the column is not simply the printed factor rounded in",
           all(("%.4f" % (0.00007854 * float(_l.split(",")[i_d]) ** 2 * E))
               == _l.split(",")[i_ha]
               for _l in csv.split("\n")[1:] if _l.strip()),
           [(_l.split(",")[i_d], _l.split(",")[i_ha]) for _l in csv.split("\n")[1:] if _l.strip()][:3])

    # associatedTaxa was a Darwin Core column this sheet emitted and never
    # filled, on a sheet that records interactions naming the species it
    # tallies. Both directions of an edge, because the term cannot say which
    # end an occurrence sits at unless the value says it.
    # The species as the DEPOSIT names it, not as the picker renders it: the
    # option's textContent runs the common name into the scientific one.
    _r0 = _dwc(pg)
    me = (_r0[0].get("vernacularName") or "") if _r0 else ""
    ck("the sheet names its stems' species in the deposit", me != "", me)
    _edge(pg, "mule deer", me, "herbivory / browse")
    _edge(pg, me, "soil fungi", "mycorrhizal symbiosis")
    rows = _dwc(pg)
    ck("the sheet still exports one row per stem", rows is not None and len(rows) >= 4,
       None if rows is None else len(rows))
    if rows:
        at = rows[0].get("associatedTaxa", "")
        ck("associatedTaxa is populated from the edges the sheet recorded",
           at != "", (me, at))
        ck("an edge the species receives names the species as the recipient",
           "mule deer eats this taxon" in at, at)
        ck("an edge the species acts in names it as the actor",
           "this taxon exchanges with soil fungi" in at, at)
        ck("the two edges travel as one Darwin Core list", at.count(" | ") == 1, at)
        ck("and no stem claims an edge naming nobody",
           all("this taxon" in r.get("associatedTaxa", "") for r in rows),
           [r.get("associatedTaxa") for r in rows][:2])

    # A top height computed from one measured stem is not a stand figure, and
    # the tile said "top height m" whether it rested on one height or forty.
    pg.click('.tab[data-pane="p-trees"]'); pg.wait_for_timeout(250)
    setstep("#tEntry",0,35); setstep("#tEntry",1,30)
    pg.click("#tAdd"); pg.wait_for_timeout(250)
    ck("a top height off one stem says how many stems that is",
       tile("heights measured","#tStats")=="1", tile("heights measured","#tStats"))
    ck("and the top-height tile keeps a name that does not move with the data",
       _thlab(pg)=="top height m", _thlab(pg))
    setstep("#tEntry",0,36); setstep("#tEntry",1,31)
    pg.click("#tAdd"); pg.wait_for_timeout(250)
    ck("and off two it counts them",
       tile("heights measured","#tStats")=="2", tile("heights measured","#tStats"))
    ck("the count is not a constant", _thlab(pg)=="top height m", _thlab(pg))
    ck("a stem with no height is not counted as measured",
       tile("live stems","#tStats")=="6" and tile("heights measured","#tStats")=="2",
       (tile("live stems","#tStats"), tile("heights measured","#tStats")))

    # -------------- touch targets & viewport --------------
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900})
        for t in ["p-id","p-trees","p-plot","p-notes","p-web","p-method"]:
            pg.click('.tab[data-pane="%s"]'%t); pg.wait_for_timeout(220)
            over=pg.evaluate("""(w)=>{const bad=[];
              document.querySelectorAll('#'+CSS.escape(document.querySelector('.pane.on').id)+' *').forEach(e=>{
                const r=e.getBoundingClientRect();
                if(r.width>0&&r.right>w+1){
                  let p=e.parentElement,scroll=false;
                  while(p){const s=getComputedStyle(p);
                    if(s.overflowX==='auto'||s.overflowX==='scroll'){scroll=true;break;} p=p.parentElement;}
                  if(!scroll) bad.push(e.tagName+'.'+e.className);}});
              return bad.slice(0,4);}""",w)
            ck("no overflow %s @%d"%(t,w), not over, over)
        small=pg.evaluate("""()=>{const bad=[];
          document.querySelectorAll('.pane.on .fek-step button,.pane.on .fek-dial button,.pane.on .fek-chip,.pane.on .fek-pick .opt').forEach(e=>{
            const r=e.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.height<44) bad.push(e.className+':'+r.height);});
          return bad.slice(0,4);}""")
        ck("FEK targets >= 44px @%d"%w, not small, small)
    pg.set_viewport_size({"width":880,"height":1250})

    # -------------- METHOD: the entry-layer change is documented --------------
    pg.click('.tab[data-pane="p-method"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-method").replace("\u00a0"," ")
    for t in ["Field Entry Kit","eight compass points","McCune","5% steps",
              "Blank still means blank","Reineke","van Wagner"]:
        ck("method documents "+t, t in m, m[:200])
    ck("aspect precision claim is refused", "a precision you did not measure" in m, "")
    ck("observer variance stated", "between-observer variance" in m, "")

    ck("no errors after the whole run", not errs, errs[:4])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))

# A suite that cannot fail the run is not a check. This one printed its FAIL
# lines and exited zero, so run_all marked it green whatever it found -- for
# eleven suites in this kit, "green" meant "the process did not crash".
raise SystemExit(1 if F else 0)
