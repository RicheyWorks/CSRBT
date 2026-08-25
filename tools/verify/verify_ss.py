# -*- coding: utf-8 -*-
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
    pg.click("#hUse"); pg.wait_for_timeout(250)
    ck("height copies into the tally stepper",
       pg.evaluate("()=>document.querySelectorAll('#tEntry .fek-step .val')[1].value")=="%.1f"%hexp,
       pg.evaluate("()=>document.querySelectorAll('#tEntry .fek-step .val')[1].value"))

    # -------------- PLOT --------------
    pg.click('.tab[data-pane="p-plot"]'); pg.wait_for_timeout(300)
    ck("geometry is FEK", pg.eval_on_selector_all("#geoEntry .fek-row","e=>e.length")==3, "")
    ck("physiography is FEK", pg.eval_on_selector_all("#physEntry .fek-row","e=>e.length")==5, "")
    ck("cover is FEK", pg.eval_on_selector_all("#covEntry .fek-row","e=>e.length")==6, "")
    ck("no legacy select left on plot",
       pg.eval_on_selector_all("#p-plot select","e=>e.length")==0,
       pg.eval_on_selector_all("#p-plot select","e=>e.map(x=>x.id)"))
    sa=pg.inner_text("#sArea")
    ck("default plot = 400 m2", "400 m²" in sa, sa[:120])
    ck("expansion factor stated", "%.1f"%E in sa, sa[:160])
    # switch to rectangle
    pg.evaluate("""()=>{const c=[...document.querySelectorAll('#geoEntry .fek-chip')]
      .find(x=>x.textContent.indexOf('rectangle')>=0); c.click();}""")
    pg.wait_for_timeout(300)
    ck("rectangle swaps in length and width",
       pg.eval_on_selector_all("#geoEntry .fek-step","e=>e.length")==3, "")
    ck("20x20 = 400 m2", "400 m²" in pg.inner_text("#sArea"), pg.inner_text("#sArea")[:120])
    pg.evaluate("""()=>{const c=[...document.querySelectorAll('#geoEntry .fek-chip')]
      .find(x=>x.textContent.indexOf('circle')>=0); c.click();}""")
    pg.wait_for_timeout(300)

    # aspect: blank until touched, then folded correctly
    ck("aspect blank before entry", pg.inner_text("#sHeatload").strip()=="",
       pg.inner_text("#sHeatload")[:80])
    dialclick("#physEntry",0,"SW"); pg.wait_for_timeout(250)
    hl=pg.inner_text("#sHeatload")
    ck("SW folds to 180", "180°" in hl, hl[:160])
    ck("SW reads as the drought end", "drought end" in hl, hl[:200])
    dialclick("#physEntry",0,"NE"); pg.wait_for_timeout(250)
    hl=pg.inner_text("#sHeatload")
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
    ck("export carries the expansion factor", "EF %.1f"%E in eco, eco[:300])
    ck("export carries min DBH", "min DBH 5" in eco, eco[:300])
    ck("export carries the folded-aspect entry", "aspect 45" in eco, eco[:400])
    ck("export carries canopy cover", "canopy 60%" in eco, eco[:500])
    ck("export carries CWD", "coarse woody debris %.1f m3/ha"%V2 in eco, eco[:600])
    ck("export aggregates by species", "Douglas-fir=4" in eco, eco[:500])
    ck("export gives species basal area", "%.2f m²/ha"%(ba*E) in eco, eco[:500])
    ck("export states the one-plot caveat", "point estimate with no variance" in eco, eco[-300:])

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
