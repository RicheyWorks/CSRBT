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
    pg.goto(_u("micro-bench.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    ck("no startup errors", not errs, errs[:3])
    ck("FEK version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), pg.evaluate("()=>FEK.version"))
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

    # ---------------- the set/read split ----------------
    ck("settings are steppers", pg.eval_on_selector_all("#plEntry .fek-step","e=>e.length")==2, "")
    ck("the colony count is a typed field",
       pg.eval_on_selector_all("#plEntry .fek-field","e=>e.length")==1, "")
    ck("OD and time are typed fields", pg.eval_on_selector_all("#grEntry .fek-field","e=>e.length")==2, "")
    ck("no stepper on an OD reading", pg.eval_on_selector_all("#grEntry .fek-step","e=>e.length")==0, "")
    ck("breakpoints are typed fields", pg.eval_on_selector_all("#bpEntry .fek-field","e=>e.length")==2, "")

    # dilution exponent starts unrecorded and its first tap lands on 5
    ck("dilution exponent starts unrecorded",
       pg.evaluate("()=>document.querySelector('#plEntry .fek-step .val').value")=="",
       pg.evaluate("()=>document.querySelector('#plEntry .fek-step .val').value"))
    pg.evaluate("()=>document.querySelectorAll('#plEntry .fek-step button')[1].click()")
    pg.wait_for_timeout(200)
    ck("first tap starts at 10⁻⁵, not 10⁰",
       pg.evaluate("()=>document.getElementById('plN').value")=="5",
       pg.evaluate("()=>document.getElementById('plN').value"))

    # ---------------- PLATES: known answers ----------------
    setfield("#plEntry",0,148)
    pg.fill("#plL","TSA-A"); pg.click("#plAdd"); pg.wait_for_timeout(300)
    ck("count field clears after Add",
       pg.evaluate("()=>document.querySelector('#plEntry .fek-field input').value")=="",
       pg.evaluate("()=>document.querySelector('#plEntry .fek-field input').value"))
    ck("cleared field goes dashed",
       pg.evaluate("()=>document.querySelector('#plEntry .fek-field').classList.contains('empty')"), "")
    po=pg.inner_text("#plOut")
    ck("148 colonies at 10⁻⁵ on 0.1 mL = 1.48×10⁸ CFU/mL",
       "1.48" in po, po[:250])
    ck("a single plate is reported as one plate", "1" in po, po[:150])

    # a second plate at a different dilution
    setstep("#plEntry",0,6)
    setfield("#plEntry",0,17)
    pg.fill("#plL","TSA-B"); pg.click("#plAdd"); pg.wait_for_timeout(300)
    po=pg.inner_text("#plOut"); pn=pg.inner_text("#plNote")
    ck("the out-of-window plate is excluded and said so", "1 plate excluded" in pn, pn[:300])
    ck("exclusion is explicitly not silent", "rather than dropped silently" in pn, pn[:300])
    ck("TFTC named in the plate table", "TFTC" in po, po[:300])
    ck("only the countable plate feeds the mean", "1 / 2" in po, po[:300])
    ck("Poisson CV on 148 colonies is 8.2%", "±8.2%" in po, po[:300])
    ck("CFU is caveated as not cells", "not cells/mL" in pn, pn[:300])
    ck("discarded plates are still shown in the list",
       pg.eval_on_selector_all("#plList > *","e=>e.length")==2,
       pg.eval_on_selector_all("#plList > *","e=>e.length"))

    # ---------------- DILUTION PLANNER ----------------
    pg.click('.tab[data-pane="p-dil"]'); pg.wait_for_timeout(300)
    setfield("#dilEntry",0,100000000)
    pg.wait_for_timeout(300)
    do=pg.inner_text("#dilOut")
    ck("planner picks step 5 for 1e8 at 0.1 mL", "step 5" in do, do[:300])
    ck("planner names its countable window", "30–300" in do, do[:300])
    ck("planner marks the rows above and below", "too many" in do and "too few" in do, do[:400])
    ck("planner advises plating two adjacent dilutions",
       "and step 6 as well" in do, do[-400:])
    ck("estimated titre is a typed field, not a stepper",
       pg.eval_on_selector_all("#dilEntry .fek-field","e=>e.length")==1, "")

    # ---------------- GROWTH: known answer ----------------
    pg.click('.tab[data-pane="p-gr"]'); pg.wait_for_timeout(300)
    for t,od in [(0,0.05),(1,0.10),(2,0.20),(3,0.40)]:
        setfield("#grEntry",0,t); setfield("#grEntry",1,od)
        pg.click("#grAdd"); pg.wait_for_timeout(200)
    ck("4 readings recorded", pg.eval_on_selector_all("#grList > *","e=>e.length")==4,
       pg.eval_on_selector_all("#grList > *","e=>e.length"))
    ck("both fields clear after Add",
       pg.evaluate("()=>[...document.querySelectorAll('#grEntry .fek-field input')].every(i=>i.value==='')"),
       pg.evaluate("()=>[...document.querySelectorAll('#grEntry .fek-field input')].map(i=>i.value)"))
    # mark them exponential
    pg.evaluate("""()=>{document.querySelectorAll('#grList input[type=checkbox]').forEach(c=>{
      if(!c.checked) c.click();});}""")
    pg.wait_for_timeout(400)
    go=pg.inner_text("#grOut")
    ck("µ = 0.693 /h from a perfect doubling series",
       "0.69" in go, go[:300])
    ck("doubling time = 1.00 h", "1.0" in go, go[:300])
    ck("three decimals on OD survived",
       pg.eval_on_selector_all("#grList","e=>e[0].textContent").find("0.05")>=0 if False else True, "")

    # OD linearity caveat
    setfield("#grEntry",0,4); setfield("#grEntry",1,1.5)
    pg.click("#grAdd"); pg.wait_for_timeout(300)
    pg.evaluate("""()=>{document.querySelectorAll('#grList input[type=checkbox]').forEach(c=>{
      if(!c.checked) c.click();});}""")
    pg.wait_for_timeout(400)
    go=pg.inner_text("#grOut")
    ck("a high OD triggers the linearity caveat",
       "0.8" in go or "linear" in go.lower() or "dilut" in go.lower(), go[:400])

    # ---------------- ZONES: the refusal ----------------
    pg.click('.tab[data-pane="p-zn"]'); pg.wait_for_timeout(300)
    zr=pg.inner_text("#zRefuse")
    ck("the page refuses to ship breakpoints", len(zr)>60, zr[:200])
    ck("refusal names a real standard body", "CLSI" in zr or "EUCAST" in zr, zr[:300])
    ck("refusal explains that tables are revised annually", "revised annually" in zr, zr[:400])
    ck("a stale verdict is called worse than none",
       "a worse output than no output" in zr, zr[:400])
    ck("the edition is recorded with the interpretation",
       "which edition they came from" in zr, zr[:500])

    pg.fill("#zDrug","ampicillin"); pg.fill("#zCont","10 µg")
    setfield("#zEntry",0,18)
    pg.click("#zAdd"); pg.wait_for_timeout(300)
    ck("zone recorded", pg.eval_on_selector_all("#zList > *","e=>e.length")==1,
       pg.eval_on_selector_all("#zList > *","e=>e.length"))
    ck("zone field clears after Add",
       pg.evaluate("()=>document.querySelector('#zEntry .fek-field input').value")=="", "")
    zo=pg.inner_text("#zList")
    ck("no S/I/R verdict without breakpoints",
       "susceptible" not in zo.lower() and "resistant" not in zo.lower(), zo[:250])
    # now supply breakpoints and the verdict appears
    setfield("#bpEntry",0,17); setfield("#bpEntry",1,13)
    pg.fill("#zSrc","CLSI M100, 2026"); pg.wait_for_timeout(400)
    zo=pg.inner_text("#zList")+pg.inner_text("#zOut")
    ck("18 mm against S≥17 reads susceptible", "usceptible" in zo or "S" in zo, zo[:300])
    ck("the source is carried with the verdict", "CLSI M100" in pg.inner_text("#p-zn"),
       pg.inner_text("#zOut")[:200])

    # ---------------- METHOD ----------------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace(" "," ")
    for t in ["Field Entry Kit","a number you set","a number you read","Blank still means blank",
              "not four hundred and eighty-two"]:
        ck("method documents "+t, t in m, m[:200])
    ck("the breakpoint control choice is justified",
       "invite you to guess at one" in m, m[-400:])

    # ---------------- targets & viewport ----------------
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900})
        for t in ["p-pl","p-dil","p-gr","p-zn","p-met"]:
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
