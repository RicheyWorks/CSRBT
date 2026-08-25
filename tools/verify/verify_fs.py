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
    pg.goto(_u("farm-scout.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    ck("no startup errors", not errs, errs[:3])
    ck("FEK version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), pg.evaluate("()=>FEK.version"))
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.length"))
    ck("no raw number input outside FEK",
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).length""")==0,
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).map(i=>i.id)"""))

    def setfield(root, idx, val):
        pg.evaluate("""([r,i,v])=>{const f=[...document.querySelectorAll(r+' .fek-field input')];
          f[i].value=String(v); f[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(130)
    def setstep(root, idx, val):
        pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
          s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(130)

    # ---------------- SCOUT ----------------
    ck("threshold is a stepper", pg.eval_on_selector_all("#thrEntry .fek-step","e=>e.length")==1, "")
    ck("the default threshold is called a placeholder",
       "placeholder, not a recommendation" in pg.inner_text("#thrEntry"), pg.inner_text("#thrEntry")[:200])
    ck("it points at extension services",
       "extension service" in pg.inner_text("#thrEntry"), "")

    # 10 stops, one hot spot: mean 3.60, variance/mean 2.54 -> aggregated
    pts=[2,3,2,4,3,2,3,12,2,3]
    for v in pts:
        pg.click("#scAdd"); pg.wait_for_timeout(70)
    pg.evaluate("""(vals)=>{const cells=[...document.querySelectorAll('#scGrid .quad')];
      cells.forEach((c,i)=>{ if(i<vals.length){
        const inp=c.querySelector('input,.val'); if(inp){ inp.value=String(vals[i]);
          inp.dispatchEvent(new Event('input',{bubbles:true})); } }});}""", pts)
    pg.wait_for_timeout(300)
    sr=pg.inner_text("#scResults")
    ck("a scouting verdict appears once points exist", len(sr)>30, sr[:200])

    # ---------------- GERMINATION: known answers ----------------
    pg.click('.tab[data-pane="p-germ"]'); pg.wait_for_timeout(250)
    ck("counts are typed fields", pg.eval_on_selector_all("#germEntry .fek-field","e=>e.length")==2, "")
    ck("the target stand is a stepper", pg.eval_on_selector_all("#germEntry .fek-step","e=>e.length")==1, "")
    ck("the set/counted split is explained",
       "counts you made" in pg.inner_text("#germEntry"), pg.inner_text("#germEntry")[:250])
    setfield("#germEntry",0,40); setfield("#germEntry",1,33); setstep("#germEntry",0,120)
    pg.wait_for_timeout(300)
    go=pg.inner_text("#gOut")
    ck("33 of 40 = 83% germination", "83%" in go, go[:200])
    ck("146 seeds to sow for 120 plants", "146" in go, go[:200])
    ck("a 'decent lot' verdict at 83%", "Decent lot" in go, go[:250])
    # below the rules of thumb
    setfield("#germEntry",1,26); pg.wait_for_timeout(300)
    go=pg.inner_text("#gOut")
    ck("65% triggers the sow-thick advice", "65%" in go, go[:200])
    setfield("#germEntry",1,18); pg.wait_for_timeout(300)
    go=pg.inner_text("#gOut")
    ck("45% is called not worth the bed space",
       "45%" in go, go[:250])
    ck("the rules of thumb are labelled as such",
       "Rule of thumb" in pg.inner_text("#p-germ"), "")
    setfield("#germEntry",1,33); pg.wait_for_timeout(200)

    # ---------------- ROTATION ----------------
    pg.click('.tab[data-pane="p-rot"]'); pg.wait_for_timeout(300)
    ck("two starter beds", pg.eval_on_selector_all("#bedGrid .bed","e=>e.length")==2,
       pg.eval_on_selector_all("#bedGrid .bed","e=>e.length"))
    ck("three pickers per bed", pg.eval_on_selector_all("#bedGrid .fek-pick","e=>e.length")==6,
       pg.eval_on_selector_all("#bedGrid .fek-pick","e=>e.length"))
    ck("each family option carries its crops",
       pg.evaluate("()=>document.querySelectorAll('#bedGrid .opt small').length")>0, "")
    ck("nothing preselected", pg.eval_on_selector_all("#bedGrid .opt.on","e=>e.length")==0, "")

    def bedPick(bed, which, name):
        pg.evaluate("""([b,w,n])=>{const beds=[...document.querySelectorAll('#bedGrid .bed')];
          const ps=[...beds[b].querySelectorAll('.fek-pick')];
          const s=ps[w].querySelector('.search'); s.value=n;
          s.dispatchEvent(new Event('input',{bubbles:true}));}""",[bed,which,name])
        pg.wait_for_timeout(120)
        pg.evaluate("""([b,w,n])=>{const beds=[...document.querySelectorAll('#bedGrid .bed')];
          const ps=[...beds[b].querySelectorAll('.fek-pick')];
          const o=ps[w].querySelector('.opt'); if(!o) throw new Error('no family '+n); o.click();}""",[bed,which,name])
        pg.wait_for_timeout(250)

    # a genuine conflict: same family planned as last season
    bedPick(0,1,"Brassica")     # last season
    bedPick(0,2,"Brassica")     # planned now
    rot=pg.inner_text("#bedGrid")
    ck("repeating a family within 3 years is flagged", "within 3 years" in rot, rot[:300])
    ck("the flag names why it matters", "carry over" in rot, rot[:300])
    ck("alternatives are suggested", "Try:" in rot, rot[:300])
    ck("the conflict flag is the bad variant",
       pg.eval_on_selector_all("#bedGrid .flag.bad","e=>e.length")==1,
       pg.eval_on_selector_all("#bedGrid .flag","e=>e.map(f=>f.className)"))
    # clean it up
    bedPick(0,2,"Fabaceae")
    rot=pg.inner_text("#bedGrid")
    ck("a clean rotation is confirmed", "Clean rotation" in rot, rot[:300])
    ck("legumes get their own note", "feed the soil" in rot, rot[:400])
    ck("the clean flag replaced the bad one",
       pg.eval_on_selector_all("#bedGrid .flag.bad","e=>e.length")==0, "")
    ck("a picked family sticks after the re-render",
       pg.evaluate("""()=>{const beds=[...document.querySelectorAll('#bedGrid .bed')];
         return [...beds[0].querySelectorAll('.fek-pick')][1].querySelector('.opt.on')!==null;}"""), "")

    # ---------------- export ----------------
    eco=pg.evaluate("()=>{const e=document.getElementById('ecoOut'); return e?e.textContent:'';}")
    ck("export carries the germination test", "germination" in eco.lower() or "83" in eco, eco[:250])

    # ---------------- entry-layer note ----------------
    m=pg.inner_text("body").replace("\u00a0"," ")
    for t in ["Field Entry Kit","a stepper for a number you set","picker per season"]:
        ck("entry note documents "+t, t in m, "")
    ck("the real rotation mistake is named",
       "same family as last year" in m, "")

    # ---------------- targets & viewport ----------------
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900})
        for t in ["p-scout","p-poll","p-germ","p-rot"]:
            pg.click('.tab[data-pane="%s"]'%t); pg.wait_for_timeout(220)
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
          document.querySelectorAll('.pane.on .fek-step button,.pane.on .fek-field input,.pane.on .fek-dial button,.pane.on .fek-chip,.pane.on .fek-pick .opt').forEach(e=>{
            const r=e.getBoundingClientRect(); if(r.width>0&&r.height<44) bad.push(e.className+':'+r.height);});
          return bad.slice(0,3);}""")
        ck("FEK targets >= 44px @%d"%w, not small, small)
    pg.set_viewport_size({"width":880,"height":1250})
    ck("no errors after the whole run", not errs, errs[:4])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
