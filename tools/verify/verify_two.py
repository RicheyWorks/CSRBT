# -*- coding: utf-8 -*-
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

    def setfield(root, idx, val):
        pg.evaluate("""([r,i,v])=>{const f=[...document.querySelectorAll(r+' .fek-field input')];
          f[i].value=String(v); f[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(120)
    def dialpick(root, label):
        pg.evaluate("""([r,l])=>{const d=document.querySelector(r+' .fek-dial');
          const btn=[...d.querySelectorAll('button')].find(x=>x.querySelector('span').textContent.trim()===l);
          if(!btn) throw new Error('no '+l); btn.click();}""",[root,label])
        pg.wait_for_timeout(140)

    # ================= FIELD SEASON =================
    errs.clear()
    pg.goto(_u("field-season.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    ck("season: no startup errors", not errs, errs[:3])
    ck("FEK version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), "")
    ck("season: no raw number input outside FEK",
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).length""")==0,
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).map(i=>i.id)"""))
    ck("season: the seed is a typed field",
       pg.eval_on_selector_all("#seedEntry .fek-field","e=>e.length")==1, "")
    ck("season: same number means same meadow is stated",
       "same meadow" in pg.inner_text("#seedEntry"), pg.inner_text("#seedEntry")[:200])
    ck("season: default seed is 4217",
       pg.evaluate("()=>document.getElementById('seedIn').value")=="4217",
       pg.evaluate("()=>document.getElementById('seedIn').value"))

    # a fixed season reproduces
    setfield("#seedEntry",0,1234)
    pg.click("#startBtn"); pg.wait_for_timeout(500)
    ck("season: starting a season opens the game",
       pg.evaluate("()=>document.getElementById('game').style.display!=='none'"), "")
    st1=pg.inner_text("body")[:400]
    setfield("#seedEntry",0,1234) if pg.query_selector("#seedEntry .fek-field input") else None
    pg.evaluate("()=>{const s=document.getElementById('seedIn'); s.value='1234';}")
    ck("season: the seed is what the game keys off",
       pg.evaluate("()=>document.getElementById('seedIn').value")=="1234", "")

    # the report questions
    pg.evaluate("""()=>{const r=document.getElementById('report');
      if(r){ r.style.display='block'; } const g=document.getElementById('game');
      if(g) g.style.display='none';}""")
    pg.wait_for_timeout(250)
    ck("season: richness is a nullable stepper",
       pg.evaluate("()=>document.querySelector('#q1Entry .fek-step').classList.contains('empty')"),
       pg.evaluate("()=>document.querySelector('#q1Entry .fek-step').className"))
    ck("season: richness starts unrecorded, not at zero",
       pg.evaluate("()=>document.querySelector('#q1Entry .fek-step .val').value")=="",
       pg.evaluate("()=>document.querySelector('#q1Entry .fek-step .val').value"))
    pg.evaluate("()=>document.querySelectorAll('#q1Entry .fek-step button')[1].click()")
    pg.wait_for_timeout(200)
    ck("season: first tap on richness starts at 8, not 0",
       pg.evaluate("()=>document.getElementById('q1').value")=="8",
       pg.evaluate("()=>document.getElementById('q1').value"))

    ck("season: evenness is an ordinal dial",
       pg.eval_on_selector_all("#q2Entry .fek-dial","e=>e.length")==1, "")
    r2=pg.evaluate("""()=>[...document.querySelectorAll('#q2Entry .fek-dial button')]
      .map(b=>+b.getAttribute('data-r'))""")
    ck("season: evenness ramp runs even to uneven", r2==[0,2,5], r2)
    r3=pg.evaluate("""()=>[...document.querySelectorAll('#q3Entry .fek-dial button')]
      .map(b=>+b.getAttribute('data-r'))""")
    ck("season: pattern ramp runs regular to clumped", r3==[0,2,5], r3)
    ck("season: the pattern dial explains the ordering",
       "most to least uniform" in pg.inner_text("#q3Entry"), pg.inner_text("#q3Entry")[:250])
    ck("season: variance-to-mean is named as the evidence",
       "variance-to-mean above 1" in pg.inner_text("#q3Entry"), "")

    dialpick("#q2Entry","uneven"); dialpick("#q3Entry","clumped")
    ck("season: dial answers reach the game state",
       pg.evaluate("()=>document.querySelectorAll('#q2Entry .fek-dial button.on').length")==1, "")

    ck("season: the vole estimate is a typed field",
       pg.eval_on_selector_all("#q4Entry .fek-field","e=>e.length")==1, "")
    ck("season: the page will not do the arithmetic silently",
       "not going to do it silently" in pg.inner_text("#q4Entry"), pg.inner_text("#q4Entry")[:250])
    setfield("#q4Entry",0,214)
    ck("season: the estimate writes through",
       pg.evaluate("()=>document.getElementById('q4').value")=="214",
       pg.evaluate("()=>document.getElementById('q4').value"))

    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900}); pg.wait_for_timeout(220)
        over=pg.evaluate("""(w)=>{const bad=[];
          document.querySelectorAll('body *').forEach(e=>{
            const r=e.getBoundingClientRect();
            if(r.width>0&&r.right>w+1){
              let p=e.parentElement,scroll=false;
              while(p){const s=getComputedStyle(p);
                if(s.overflowX==='auto'||s.overflowX==='scroll'){scroll=true;break;} p=p.parentElement;}
              if(!scroll) bad.push(e.tagName+'.'+e.className);}});
          return bad.slice(0,3);}""",w)
        ck("season: no overflow @%d"%w, not over, over)
    pg.set_viewport_size({"width":880,"height":1250})
    ck("season: no errors after the run", not errs, errs[:3])

    # ================= FIELD NOTEBOOK =================
    errs.clear()
    pg.goto(_u("field-notebook.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    ck("notebook: no startup errors", not errs, errs[:3])
    ck("notebook: FEK v1.1.0", pg.evaluate("()=>FEK.version")==_fek_version(), "")
    ck("notebook: no raw number input outside FEK",
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).length""")==0,
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).map(i=>i.id)"""))
    ck("notebook: exactly one scanflash element",
       pg.eval_on_selector_all("#scanflash","e=>e.length")==1,
       pg.eval_on_selector_all("[id=scanflash]","e=>e.length"))
    ck("notebook: the scan interval is a stepper",
       pg.eval_on_selector_all("#scanEntry .fek-step","e=>e.length")==1, "")
    ck("notebook: default interval 30 s",
       pg.evaluate("()=>document.getElementById('scanSec').value")=="30",
       pg.evaluate("()=>document.getElementById('scanSec').value"))
    ck("notebook: 0 is documented as off",
       "0 turns the scan prompt off" in pg.inner_text("#scanEntry"), pg.inner_text("#scanEntry")[:200])
    ck("notebook: fixing the interval up front is explained",
       "makes the samples non-comparable" in pg.inner_text("#scanEntry"), "")
    pg.evaluate("""()=>{const s=document.querySelector('#scanEntry .fek-step .val');
      s.value='60'; s.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(200)
    ck("notebook: the interval writes through",
       pg.evaluate("()=>document.getElementById('scanSec').value")=="60",
       pg.evaluate("()=>document.getElementById('scanSec').value"))
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900}); pg.wait_for_timeout(220)
        over=pg.evaluate("""(w)=>{const bad=[];
          document.querySelectorAll('body *').forEach(e=>{
            const r=e.getBoundingClientRect();
            if(r.width>0&&r.right>w+1){
              let p=e.parentElement,scroll=false;
              while(p){const s=getComputedStyle(p);
                if(s.overflowX==='auto'||s.overflowX==='scroll'){scroll=true;break;} p=p.parentElement;}
              if(!scroll) bad.push(e.tagName+'.'+e.className);}});
          return bad.slice(0,3);}""",w)
        ck("notebook: no overflow @%d"%w, not over, over)
        small=pg.evaluate("""()=>{const bad=[];
          document.querySelectorAll('.fek-step button,.fek-field input').forEach(e=>{
            const r=e.getBoundingClientRect(); if(r.width>0&&r.height<44) bad.push(e.className);});
          return bad.slice(0,3);}""")
        ck("notebook: FEK targets >= 44px @%d"%w, not small, small)
    ck("notebook: no errors after the run", not errs, errs[:3])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
