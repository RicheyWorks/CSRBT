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
    pg.goto(_u("pheno-tracker.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    # start from a clean slate regardless of any stored run
    pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(600)
    ck("no startup errors", not errs, errs[:3])
    ck("FEK version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), pg.evaluate("()=>FEK.version"))
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.map(x=>x.id)"))
    ck("no raw number input outside FEK",
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).length""")==0,
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).map(i=>i.id)"""))

    def setstep(root, idx, val):
        pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
          s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(120)
    def setfield(root, idx, val):
        pg.evaluate("""([r,i,v])=>{const f=[...document.querySelectorAll(r+' .fek-field input')];
          f[i].value=String(v); f[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(120)
    def score(traitIdx, v):
        pg.evaluate("""([t,v])=>{const d=[...document.querySelectorAll('#scoreDials .fek-dial')][t];
          const b=[...d.querySelectorAll('button')].find(x=>x.querySelector('span').textContent.trim()===String(v));
          if(!b) throw new Error('no score '+v); b.click();}""",[traitIdx,v])
        pg.wait_for_timeout(90)
    def pickPlant(n):
        pg.evaluate("""(n)=>{const b=[...document.querySelectorAll('#plantGrid button')]
          .find(x=>{const id=x.querySelector('.pid'); return id && id.textContent.trim()==='#'+n;});
          if(!b) throw new Error('no plant '+n); b.click();}""", n)
        pg.wait_for_timeout(200)

    # ---------------- the rating dial ----------------
    pg.click('.tab[data-pane="p-run"]'); pg.wait_for_timeout(200)
    ck("plants-in-run is a stepper", pg.eval_on_selector_all("#runEntry .fek-step","e=>e.length")==1, "")
    ck("trait weight is a stepper", pg.eval_on_selector_all("#wEntry .fek-step","e=>e.length")==1, "")
    ck("weighting is called a statement of intent",
       "before you score, not after" in pg.inner_text("#wEntry"), pg.inner_text("#wEntry")[:200])

    pg.click('.tab[data-pane="p-score"]'); pg.wait_for_timeout(250)
    pickPlant(1)
    nd=pg.eval_on_selector_all("#scoreDials .fek-dial","e=>e.length")
    ck("one rating dial per trait", nd>=3, nd)
    ck("each dial offers 1-5",
       pg.evaluate("()=>document.querySelectorAll('#scoreDials .fek-dial')[0].querySelectorAll('button').length")==5,
       pg.evaluate("()=>document.querySelectorAll('#scoreDials .fek-dial')[0].querySelectorAll('button').length"))
    r=pg.evaluate("""()=>[...document.querySelectorAll('#scoreDials .fek-dial')[0].querySelectorAll('button')]
      .map(b=>+b.getAttribute('data-r'))""")
    ck("the rating ramp runs low to high", r==[0,1,2,3,5], r)
    ck("nothing scored to begin with",
       pg.eval_on_selector_all("#scoreDials .fek-dial button.on","e=>e.length")==0, "")
    ck("the dial label carries the weight",
       "×" in pg.evaluate("()=>document.querySelector('#scoreDials .fek-lab').textContent"),
       pg.evaluate("()=>document.querySelector('#scoreDials .fek-lab').textContent"))

    # tap-again-to-unset, and unscored is dropped not counted as 1
    score(0,4)
    ck("a score registers",
       pg.evaluate("()=>document.querySelectorAll('#scoreDials .fek-dial')[0].querySelector('button.on').textContent.trim()")=="4",
       "")
    score(0,4)
    ck("tapping the same score again unsets it",
       pg.evaluate("()=>!document.querySelectorAll('#scoreDials .fek-dial')[0].querySelector('button.on')"), "")

    # ---------------- selection differential, known answer ----------------
    pg.click('.tab[data-pane="p-run"]'); pg.wait_for_timeout(200)
    setstep("#runEntry",0,8); pg.click("#runMake"); pg.wait_for_timeout(300)
    traits=pg.evaluate("()=>[...document.querySelectorAll('#traitChips .chip,#traitChips > *')].length")
    pg.click('.tab[data-pane="p-score"]'); pg.wait_for_timeout(250)
    pickPlant(1)
    nt=pg.eval_on_selector_all("#scoreDials .fek-dial","e=>e.length")
    # score every plant on every trait with a deterministic pattern
    pattern=[5,4,3,2,1,3,5,2]
    for i,base in enumerate(pattern, start=1):
        pickPlant(i)
        for t in range(nt):
            v=max(1,min(5, base - (1 if t>0 else 0)))
            score(t, v)
    pg.click('.tab[data-pane="p-sel"]'); pg.wait_for_timeout(400)
    sb=pg.inner_text("#selStats")
    ck("selection readout appears with no keepers yet", len(sb)>10, sb[:200])
    # keep the top three
    pg.evaluate("""()=>{const rows=[...document.querySelectorAll('#rankBoard .rankrow')];
      rows.slice(0,3).forEach(r=>{const k=r.querySelector('.kbtn'); if(k) k.click();});}""")
    pg.wait_for_timeout(400)
    sb=pg.inner_text("#selStats")
    # known answers, computed independently:
    #   weights 1,1,2,1.5 over the scored pattern give totals
    #   4.18 3.18 2.18 1.18 1.00 2.18 4.18 1.18
    #   run mean 2.41, top-3 keeper mean 3.85, S = +1.44
    def stat(lab):
        return pg.evaluate("""(l)=>{const t=[...document.querySelectorAll('#selStats .st,#selStats > div > div')]
            .find(x=>x.textContent.replace(/\s+/g,' ').indexOf(l)>=0);
            return t?t.textContent.replace(/\s+/g,' ').trim():null;}""", lab)
    ck("8 plants scored", "8" in sb.split("\n")[0] if sb else False, sb[:80])
    ck("run mean = 2.41", "2.41" in sb, sb[:250])
    ck("3 keepers counted", "3" in sb, sb[:250])
    ck("keeper mean = 3.85", "3.85" in sb, sb[:250])
    ck("selection differential S = +1.44", "+1.44" in sb, sb[:300])
    ck("S is stated on the 1-5 scale it was measured on", "on the 1–5 scale" in sb, sb[:400])
    ck("R = h2 x S given as the qualifier", "R = h² × S" in sb, sb[:400])
    ck("heritability is named as what decides the response",
       "depends on heritability" in sb, sb[:400])
    ck("the clone-before-crossing advice is given",
       "Clone your keepers before crossing" in sb, sb[-200:])
    ck("the ranked board agrees with the hand calculation",
       pg.evaluate("""()=>[...document.querySelectorAll('#rankBoard .rankrow .sc')]
         .map(x=>x.textContent.trim())""")[:3]==["4.18","4.18","3.18"],
       pg.evaluate("""()=>[...document.querySelectorAll('#rankBoard .rankrow .sc')]
         .map(x=>x.textContent.trim())"""))

    # ---------------- segregation, known answers ----------------
    pg.click('.tab[data-pane="p-seg"]'); pg.wait_for_timeout(250)
    ck("counts are typed fields", pg.eval_on_selector_all("#segEntry .fek-field","e=>e.length")==2, "")
    setfield("#segEntry",0,9); setfield("#segEntry",1,3)
    pg.wait_for_timeout(300)
    so=pg.inner_text("#segOut")
    ck("9:3 is a perfect fit to 3:1", "0.00" in so, so[:300])
    ck("3:1 named as single dominant gene", "3:1" in so, so[:300])
    ck("the 3.84 cutoff is stated", "3.84" in pg.inner_text("#p-seg"), "")
    setfield("#segEntry",0,9); setfield("#segEntry",1,7)
    pg.wait_for_timeout(300)
    so=pg.inner_text("#segOut")
    ck("9:7 is offered as a ratio to test", "9:7" in so, so[:300])
    setfield("#segEntry",0,60); setfield("#segEntry",1,20)
    pg.wait_for_timeout(300)
    so=pg.inner_text("#segOut")
    ck("a 60:20 run also fits 3:1 exactly", "0.00" in so, so[:250])
    ck("small-run weakness is stated somewhere", "30+" in pg.inner_text("#p-seg"), "")

    # ---------------- cross pickers ----------------
    pg.click('.tab[data-pane="p-sel"]'); pg.wait_for_timeout(300)
    ck("parents are filterable pickers",
       pg.eval_on_selector_all("#crossEntry .fek-pick","e=>e.length")==2,
       pg.eval_on_selector_all("#crossEntry .fek-pick","e=>e.length"))
    ck("only scored or kept plants are offered as parents",
       pg.eval_on_selector_all("#crossEntry .fek-pick","e=>e.length")==2 and
       pg.evaluate("()=>document.querySelectorAll('#crossEntry .opt').length")>0,
       pg.evaluate("()=>document.querySelectorAll('#crossEntry .opt').length"))
    ck("each parent option shows its weighted total",
       pg.evaluate("""()=>[...document.querySelectorAll('#crossEntry .opt small')].length>0"""), "")
    pg.evaluate("""()=>{const ps=[...document.querySelectorAll('#crossEntry .fek-pick')];
      ps[0].querySelector('.opt').click();}""")
    pg.wait_for_timeout(150)
    pg.evaluate("""()=>{const ps=[...document.querySelectorAll('#crossEntry .fek-pick')];
      const os=[...ps[1].querySelectorAll('.opt')]; os[Math.min(1,os.length-1)].click();}""")
    pg.wait_for_timeout(150)
    pg.click("#crossAdd"); pg.wait_for_timeout(300)
    ck("a planned cross is recorded",
       pg.eval_on_selector_all("#crossList .crossrow","e=>e.length")>=1,
       pg.inner_text("#crossList")[:150])
    ck("the clone caveat is stated",
       "doesn't advance the line" in pg.inner_text("#p-sel"), "")

    # ---------------- export ----------------
    eco=pg.evaluate("()=>document.getElementById('ecoOut').textContent")
    ck("export carries the run", len(eco)>60, eco[:150])
    ck("export names the scored plants", "#" in eco, eco[:200])

    # ---------------- the entry-layer note ----------------
    pg.click('.tab[data-pane="p-seg"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-seg").replace("\u00a0"," ")
    for t in ["Field Entry Kit","ordinal dial","Tap a score again to unset it",
              "typed fields"]:
        ck("entry note documents "+t, t in m, m[:200])
    ck("the unscored-vs-low distinction is spelled out",
       "does not silently rank below" in m, m[:400])
    ck("parents are planned against the number",
       "rather than against a memory" in m, m[-400:])

    # ---------------- targets & viewport ----------------
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900})
        for t in ["p-run","p-score","p-sel","p-seg"]:
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

# A suite that cannot fail the run is not a check. This one printed its FAIL
# lines and exited zero, so run_all marked it green whatever it found -- for
# eleven suites in this kit, "green" meant "the process did not crash".
raise SystemExit(1 if F else 0)
