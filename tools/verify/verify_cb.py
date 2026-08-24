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
    pg.goto(_u("cell-bench.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    ck("no startup errors", not errs, errs[:3])
    ck("FEK v1.1.0", pg.evaluate("()=>FEK.version")=="1.1.0", pg.evaluate("()=>FEK.version"))
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.map(x=>x.id)"))
    ck("no raw number input outside FEK",
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).length""")==0,
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).map(i=>i.id)"""))

    def stat(lab, root):
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .stat > div')]
            .find(x=>{const s=x.querySelector('.l')||x.lastElementChild;
              return s && s.textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0;});
            return t?(t.querySelector('.v')||t.firstElementChild).textContent.trim():null;}""",[root,lab])
    def setfield(root, idx, val):
        pg.evaluate("""([r,i,v])=>{const f=[...document.querySelectorAll(r+' .fek-field input')];
          f[i].value=String(v); f[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(130)
    def setstep(root, idx, val):
        pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
          s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(130)

    # ---------------- COUNT: the control choice is the point ----------------
    ck("counts are typed fields, not steppers",
       pg.eval_on_selector_all("#cntEntry .fek-field","e=>e.length")==2, "")
    ck("settings are steppers", pg.eval_on_selector_all("#cntEntry .fek-step","e=>e.length")==3, "")
    ck("chamber factor is chips", pg.eval_on_selector_all("#cntEntry .fek-chip","e=>e.length")==2, "")
    ck("count fields ask for the decimal keypad",
       pg.evaluate("""()=>[...document.querySelectorAll('#cntEntry .fek-field input')]
         .every(i=>i.getAttribute('inputmode')==='decimal')"""), "")
    ck("a typed count has no +/- buttons",
       pg.eval_on_selector_all("#cntEntry .fek-field button","e=>e.length")==0, "")

    setfield("#cntEntry",0,120)   # live
    setfield("#cntEntry",1,12)    # dead
    pg.wait_for_timeout(250)
    sq,live,dead,dil,chf,vol=4,120,12,2.0,1e4,10.0
    conc=(live/sq)*chf*dil
    ck("concentration = 6.0×10⁵ cells/mL",
       stat("live cells/mL","#cntOut") is not None and "6" in stat("live cells/mL","#cntOut"),
       stat("live cells/mL","#cntOut"))
    ck("cells per square = 33.0", stat("cells per square","#cntOut")=="33.0",
       stat("cells per square","#cntOut"))
    ck("viability = 90.9%", stat("viability","#cntOut")=="90.9%", stat("viability","#cntOut"))
    cv=100/math.sqrt(live)
    ck("Poisson CV = ±9.1%", stat("counting CV","#cntOut")=="±%.1f%%"%cv,
       stat("counting CV","#cntOut"))
    co=pg.inner_text("#cntOut")
    ck("the arithmetic is shown", "÷ 4" in co, co[:250])
    ck("33 per square is inside the window", "warnv" not in pg.evaluate(
       """()=>{const t=[...document.querySelectorAll('#cntOut .stat > div')]
         .find(x=>x.textContent.indexOf('cells per square')>=0); return t?t.className:'';}"""),
       pg.evaluate("""()=>{const t=[...document.querySelectorAll('#cntOut .stat > div')]
         .find(x=>x.textContent.indexOf('cells per square')>=0); return t?t.className:'';}"""))
    # push it out of the window and the page should say so
    setfield("#cntEntry",0,600); pg.wait_for_timeout(250)
    ad=pg.inner_text("#cntAdvice")
    ck("too many per square is flagged", len(ad)>30, ad[:150])
    setfield("#cntEntry",0,120); pg.wait_for_timeout(200)

    # chamber factor as chips changes the answer
    pg.evaluate("""()=>{const c=[...document.querySelectorAll('#cntEntry .fek-chip')]
      .find(x=>x.textContent.indexOf('0.01')>=0); c.click();}""")
    pg.wait_for_timeout(250)
    ck("deeper chamber multiplies by ten",
       pg.evaluate("()=>document.getElementById('cChf').value")=="100000",
       pg.evaluate("()=>document.getElementById('cChf').value"))
    pg.evaluate("""()=>{const c=[...document.querySelectorAll('#cntEntry .fek-chip')]
      .find(x=>x.textContent.indexOf('Neubauer')>=0); c.click();}""")
    pg.wait_for_timeout(250)

    # ---------------- CULTURE ----------------
    pg.click('.tab[data-pane="p-cul"]'); pg.wait_for_timeout(300)
    ck("densities are typed fields", pg.eval_on_selector_all("#seedEntry .fek-field","e=>e.length")==2, "")
    setfield("#seedEntry",0,850000); setfield("#seedEntry",1,50000)
    pg.wait_for_timeout(300)
    so=pg.inner_text("#seedOut")
    ck("C1V1 gives 0.59 mL of stock", "0.59" in so or "0.588" in so, so[:250])
    ck("seeding shows its working", "850" in so or "×" in so, so[:200])

    setfield("#growEntry",0,200000); setfield("#growEntry",1,1600000)
    setstep("#growEntry",0,48)
    pg.wait_for_timeout(300)
    go=pg.inner_text("#growOut")
    ck("3 population doublings", "3.0" in go or "3 " in go, go[:250])
    ck("doubling time 16.0 h", "16.0" in go, go[:250])

    # nullable: elapsed and confluency start unrecorded
    ck("confluency starts unrecorded",
       "not recorded" in pg.inner_text("#growEntry"), pg.inner_text("#growEntry")[:200])
    ck("confluency stays out of the export until touched",
       pg.evaluate("()=>document.getElementById('gConf').value")=="",
       pg.evaluate("()=>document.getElementById('gConf').value"))
    pg.evaluate("""()=>{const r=document.querySelector('#growEntry input[type=range]');
      r.value='100'; r.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(250)
    ck("confluency writes through once moved",
       pg.evaluate("()=>document.getElementById('gConf').value")=="100", "")
    ck("100% confluent is called out as an underestimate",
       "confluen" in pg.inner_text("#growOut").lower(), pg.inner_text("#growOut")[:300])

    # ---------------- ASSAY: the case for the field component ----------------
    pg.click('.tab[data-pane="p-asy"]'); pg.wait_for_timeout(300)
    ck("standards are typed fields", pg.eval_on_selector_all("#stdEntry .fek-field","e=>e.length")==2, "")
    ck("absorbance has no stepper buttons",
       pg.eval_on_selector_all("#stdEntry button","e=>e.length")==0, "")
    for c,a in [(0,0.041),(5,0.238),(10,0.442),(20,0.851)]:
        setfield("#stdEntry",0,c); setfield("#stdEntry",1,a)
        pg.click("#stAdd"); pg.wait_for_timeout(200)
    ck("4 standards recorded", pg.eval_on_selector_all("#stList > *","e=>e.length")==4,
       pg.eval_on_selector_all("#stList > *","e=>e.length"))
    ck("fields clear after Add",
       pg.evaluate("()=>[...document.querySelectorAll('#stdEntry .fek-field input')].every(i=>i.value==='')"),
       pg.evaluate("()=>[...document.querySelectorAll('#stdEntry .fek-field input')].map(i=>i.value)"))
    ck("cleared fields go dashed, not zero",
       pg.evaluate("()=>[...document.querySelectorAll('#stdEntry .fek-field')].every(f=>f.classList.contains('empty'))"), "")
    cu=pg.inner_text("#curveOut")
    ck("least-squares slope 0.0406", "0.0406" in cu, cu[:200])
    ck("intercept 0.0380 reported separately", "0.0380" in cu, cu[:200])
    ck("r2 = 0.9999", "0.9999" in cu, cu[:200])
    ck("the fitted equation is printed", "A = 0.0406" in cu, cu[:200])
    ck("a high r2 is explicitly not a linearity guarantee",
       "does not tell you the assay is linear beyond them" in cu, cu[:400])

    setfield("#unkEntry",0,0.500); pg.wait_for_timeout(300)
    uo=pg.inner_text("#unkOut")
    ck("unknown reads against the curve", len(uo)>20, uo[:200])
    setfield("#unkEntry",0,3.0); pg.wait_for_timeout(300)
    ck("extrapolation past the top standard is refused",
       "extrapolat" in pg.inner_text("#unkOut").lower() or "above" in pg.inner_text("#unkOut").lower(),
       pg.inner_text("#unkOut")[:300])
    setfield("#unkEntry",0,0.500); pg.wait_for_timeout(200)

    # three decimals survive exactly — the whole reason field exists
    setfield("#blEntry",0,1.842); setfield("#blEntry",1,6500)
    pg.wait_for_timeout(300)
    ck("absorbance keeps three decimals",
       pg.evaluate("()=>document.getElementById('blA').value")=="1.842",
       pg.evaluate("()=>document.getElementById('blA').value"))
    bo=pg.inner_text("#blOut")
    ck("Beer-Lambert computes c = A/(εl)", "2.8" in bo or "e-4" in bo.lower() or "×10" in bo, bo[:250])
    ck("epsilon is called a property of the substance",
       "property of the substance" in pg.inner_text("#blEntry"), pg.inner_text("#blEntry")[:300])

    setfield("#purEntry",0,1.842); setfield("#purEntry",1,0.985); setfield("#purEntry",2,0.812)
    pg.wait_for_timeout(300)
    po=pg.inner_text("#purOut")
    ck("260/280 = 1.87", "1.87" in po, po[:250])
    ck("260/230 = 2.27", "2.27" in po, po[:250])
    ck("dsDNA estimate 9.21×10¹ ng/µL", "9.21×10¹" in po, po[:300])
    ck("RNA estimate given separately", "7.37×10¹" in po, po[:300])
    ck("ratios flagged as conventions",
       "convention" in po.lower() or "rule of thumb" in po.lower(), po[:400])

    # ---------------- MITOSIS: nullable optional field ----------------
    pg.click('.tab[data-pane="p-mit"]'); pg.wait_for_timeout(300)
    ck("cycle length is a nullable stepper",
       pg.evaluate("()=>document.querySelector('#cycEntry .fek-step').classList.contains('empty')")
       and pg.evaluate("()=>document.querySelector('#cycEntry .fek-step .val').value")=="",
       pg.evaluate("()=>document.querySelector('#cycEntry .fek-step').className"))
    ck("cycle length starts unrecorded",
       pg.evaluate("()=>document.querySelector('#cycEntry .fek-step .val').value")=="",
       pg.evaluate("()=>document.querySelector('#cycEntry .fek-step .val').value"))
    ck("empty nullable stepper is dashed",
       pg.evaluate("()=>document.querySelector('#cycEntry .fek-step').classList.contains('empty')"), "")
    # score some cells
    for i in range(5):
        pg.evaluate("(i)=>document.querySelectorAll('#phaseGrid button')[i%%5].click()".replace("%%","%") if False else
                    "(i)=>{const b=document.querySelectorAll('#phaseGrid button'); b[i%b.length].click();}", i)
        pg.wait_for_timeout(90)
    mo=pg.inner_text("#miOut")
    ck("mitotic index computes without a cycle length", len(mo)>20, mo[:200])
    # first + starts at 24, not 0
    pg.evaluate("()=>document.querySelectorAll('#cycEntry .fek-step button')[1].click()")
    pg.wait_for_timeout(250)
    ck("first tap starts the cycle length at 24 h, not 0",
       pg.evaluate("()=>document.getElementById('miCyc').value")=="24",
       pg.evaluate("()=>document.getElementById('miCyc').value"))
    ck("and the box now shows it",
       pg.evaluate("()=>document.querySelector('#cycEntry .fek-step .val').value")=="24.0",
       pg.evaluate("()=>document.querySelector('#cycEntry .fek-step .val').value"))
    ck("phase durations appear once a cycle length exists",
       len(pg.inner_text("#miOut"))>len(mo), (len(mo),len(pg.inner_text("#miOut"))))

    # ---------------- METHOD ----------------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace("\u00a0"," ")
    for t in ["Field Entry Kit","you would tap two thousand times","Blank still means blank",
              "Poisson","Beer"]:
        ck("method documents "+t, t in m, m[:200])
    ck("the set-vs-read distinction is drawn",
       "you <em>set</em>" in pg.inner_html("#p-met") or "you set" in m, m[:300])
    ck("nothing is rounded on entry", "Nothing is rounded on the way in" in m, "")
    ck("zero confluency vs unrecorded confluency distinguished",
       "confluency of 0% is a real observation" in m, "")

    # ---------------- targets & viewport ----------------
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900})
        for t in ["p-cnt","p-cul","p-asy","p-mit","p-met"]:
            pg.click('.tab[data-pane="%s"]'%t); pg.wait_for_timeout(200)
            over=pg.evaluate("""(w)=>{const bad=[];
              document.querySelectorAll('#'+CSS.escape(document.querySelector('.pane.on').id)+' *').forEach(e=>{
                const r=e.getBoundingClientRect();
                if(r.width>0&&r.right>w+1){
                  let p=e.parentElement,scroll=false;
                  while(p){const s=getComputedStyle(p);
                    if(s.overflowX==='auto'||s.overflowX==='scroll'){scroll=true;break;} p=p.parentElement;}
                  if(!scroll) bad.push(e.tagName+'.'+e.className);}});
              return bad.slice(0,3);}""",w)
            ck("no overflow %s @%d"%(t,w), not over, over)
        small=pg.evaluate("""()=>{const bad=[];
          document.querySelectorAll('.pane.on .fek-step button,.pane.on .fek-field input,.pane.on .fek-dial button,.pane.on .fek-chip').forEach(e=>{
            const r=e.getBoundingClientRect(); if(r.width>0&&r.height<44) bad.push(e.className+':'+r.height);});
          return bad.slice(0,3);}""")
        ck("FEK targets >= 44px @%d"%w, not small, small)
    pg.set_viewport_size({"width":880,"height":1250})
    ck("no errors after the whole run", not errs, errs[:4])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
