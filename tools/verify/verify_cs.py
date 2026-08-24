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
    pg.goto(_u("collection-sheet.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(700)
    ck("no startup errors", not errs, errs[:3])
    ck("FEK v1.1.0 present", pg.evaluate("()=>typeof FEK!=='undefined'&&FEK.version")=="1.1.0", "")
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.map(x=>x.id)"))

    def tile(lab, root):
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .tile,'+r+' .fek-tile')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0);
            return t?t.querySelector('.v').textContent.trim():null;}""",[root,lab])
    def setstep(root,idx,val):
        pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
          s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(130)
    def dialpick(root,idx,label):
        pg.evaluate("""([r,i,l])=>{const d=[...document.querySelectorAll(r+' .fek-dial')][i];
          const bs=[...d.querySelectorAll('button')];
          const b=bs.find(x=>x.querySelector('span').textContent.trim()===l);
          if(!b) throw new Error('no option '+l+' in '+bs.map(x=>x.textContent).join('|'));
          b.click();}""",[root,idx,label])
        pg.wait_for_timeout(150)
    def pick(root,name):
        pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
          s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""",[root,name])
        pg.wait_for_timeout(140)
        pg.evaluate("(r)=>{const o=document.querySelector(r+' .opt'); if(!o) throw new Error('no match'); o.click();}",root)
        pg.wait_for_timeout(160)

    # ---------------- RECORD ----------------
    ck("genus is a FEK picker", pg.eval_on_selector_all("#genEntry .fek-pick","e=>e.length")==1, "")
    ck("count is a FEK stepper", pg.eval_on_selector_all("#cnEntry .fek-step","e=>e.length")==1, "")
    ck("host is a FEK picker", pg.eval_on_selector_all("#hostEntry .fek-pick","e=>e.length")==1, "")
    ck("dimensions are 4 FEK steppers", pg.eval_on_selector_all("#dimEntry .fek-step","e=>e.length")==4, "")
    ck("genus picker lists the pack",
       pg.eval_on_selector_all("#genEntry .opt","e=>e.length")>10,
       pg.eval_on_selector_all("#genEntry .opt","e=>e.length"))
    ck("guild shown as the picker subtitle",
       pg.evaluate("()=>!![...document.querySelectorAll('#genEntry .opt small')].length"),"")
    ck("not-in-pack offered",
       pg.evaluate("()=>[...document.querySelectorAll('#genEntry .opt')].some(o=>o.textContent.indexOf('not in the pack')>=0)"),"")

    # picking a genus fires the tell
    pick("#genEntry","Amanita")
    tell=pg.inner_text("#cGenTell")
    ck("genus tell appears on pick", len(tell)>20, tell[:120])
    ck("guild badge in the tell", "mycorrhiz" in tell.lower() or "saprotroph" in tell.lower(), tell[:160])

    # host list default, then from the stand
    ck("default host list offered",
       pg.evaluate("()=>[...document.querySelectorAll('#hostEntry .opt')].some(o=>o.textContent.indexOf('Pseudotsuga')>=0)"),"")
    ck("host uncertain offered",
       pg.evaluate("()=>[...document.querySelectorAll('#hostEntry .opt')].some(o=>o.textContent.indexOf('uncertain')>=0)"),"")
    pg.click('.tab[data-pane="p-site"]'); pg.wait_for_timeout(250)
    pg.fill("#sTrees","Quercus garryana; Arbutus menziesii"); pg.wait_for_timeout(300)
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(250)
    ck("host list follows the stand list",
       pg.evaluate("()=>[...document.querySelectorAll('#hostEntry .opt')].some(o=>o.textContent.indexOf('Arbutus')>=0)"),
       pg.evaluate("()=>[...document.querySelectorAll('#hostEntry .opt')].map(o=>o.textContent).slice(0,4)"))
    ck("stand-sourced hosts are labelled",
       pg.evaluate("()=>[...document.querySelectorAll('#hostEntry .opt small')].some(o=>o.textContent.indexOf('from your stand')>=0)"),"")

    # add four collections: genus A x2, B, C with counts 3,2,1,1
    def add(gen, n, name):
        pick("#genEntry", gen)
        setstep("#cnEntry",0,n)
        pg.fill("#cName", name)
        pg.click("#cAdd"); pg.wait_for_timeout(280)
    add("Amanita",3,"Amanita muscaria")
    ck("count resets to 1 after add",
       pg.evaluate("()=>document.querySelectorAll('#cnEntry .fek-step .val')[0].value")=="1",
       pg.evaluate("()=>document.querySelectorAll('#cnEntry .fek-step .val')[0].value"))
    ck("genus picker clears after add",
       pg.eval_on_selector_all("#genEntry .opt.on","e=>e.length")==0, "")
    add("Amanita",2,"Amanita muscaria")
    add("Suillus",1,"Suillus brevipes")
    add("Russula",1,"Russula sp.")

    pg.click('.tab[data-pane="p-an"]'); pg.wait_for_timeout(350)
    ck("4 collections", tile("collections","#anOut" if pg.query_selector("#anOut") else ".pane.on")=="4",
       tile("collections",".pane.on"))
    ck("7 fruit bodies", tile("fruit bodies",".pane.on")=="7", tile("fruit bodies",".pane.on"))
    c=[5,1,1]; tot=7
    H=-sum(x/tot*math.log(x/tot) for x in c); J=H/math.log(3)
    ck("3 taxa", tile("taxa",".pane.on")=="3", tile("taxa",".pane.on"))
    ck("Shannon H' = %.3f"%H, tile("Shannon",".pane.on")=="%.3f"%H, tile("Shannon",".pane.on"))
    ck("Pielou J' = %.3f"%J, tile("Pielou",".pane.on")=="%.3f"%J, tile("Pielou",".pane.on"))
    ck("Chao1 = 4.0", tile("Chao1",".pane.on")=="4.0", tile("Chao1",".pane.on"))
    ck("2 singletons / 0 doubletons", tile("singletons",".pane.on")=="2 / 0", tile("singletons",".pane.on"))
    ck("no-doubleton caveat fires", "No doubletons" in pg.inner_text(".pane.on"),
       pg.inner_text(".pane.on")[:300])

    # effort correction only once area and time are entered
    ck("no effort tile before area is entered", tile("collections / 100",".pane.on") is None,
       tile("collections / 100",".pane.on"))
    pg.click('.tab[data-pane="p-site"]'); pg.wait_for_timeout(250)
    setstep("#siteEntry",1,1000)   # area searched
    setstep("#siteEntry",2,90)     # search time
    pg.click('.tab[data-pane="p-an"]'); pg.wait_for_timeout(300)
    ck("collections / 100 m2 = 0.40", tile("collections / 100",".pane.on")=="0.40",
       tile("collections / 100",".pane.on"))
    ck("collections / hour = 2.7", tile("collections / hour",".pane.on")=="2.7",
       tile("collections / hour",".pane.on"))

    # ---------------- SITE: blank stays blank ----------------
    pg.click('.tab[data-pane="p-site"]'); pg.wait_for_timeout(250)
    ck("site entry is FEK", pg.eval_on_selector_all("#siteEntry .fek-row","e=>e.length")==6, "")
    ck("weather entry is FEK", pg.eval_on_selector_all("#wxEntry .fek-step","e=>e.length")==5, "")
    ck("duff blank until touched", pg.evaluate("()=>document.getElementById('sDuff').value")=="",
       pg.evaluate("()=>document.getElementById('sDuff').value"))
    setstep("#siteEntry",3,0)
    ck("a recorded zero duff is not blank", pg.evaluate("()=>document.getElementById('sDuff').value")=="0",
       pg.evaluate("()=>document.getElementById('sDuff').value"))
    dialpick("#siteEntry",1,"abundant")
    ck("CWD dial writes through", pg.evaluate("()=>document.getElementById('sCwd').value")=="abundant",
       pg.evaluate("()=>document.getElementById('sCwd').value"))

    # weather: the placeholder rule is labelled
    pg.fill("#wDate","2026-08-10")
    setstep("#wxEntry",0,30); pg.wait_for_timeout(300)
    w=pg.inner_text("#wOut")
    ck("wetting event read against the rule", len(w)>20, w[:200])
    ck("lag rule labelled a placeholder", "placeholder" in pg.inner_text("#p-site"), "")

    # ---------------- PRINTS ----------------
    pg.click('.tab[data-pane="p-prt"]'); pg.wait_for_timeout(300)
    ck("collection pick is a FEK picker", pg.eval_on_selector_all("#pPickEntry .fek-pick","e=>e.length")==1, "")
    ck("print duration is a stepper", pg.eval_on_selector_all("#prtEntry .fek-step","e=>e.length")==1, "")
    ck("print surface is a dial", pg.eval_on_selector_all("#prtEntry .fek-dial","e=>e.length")==1, "")
    ck("4 collections offered to print", pg.eval_on_selector_all("#pPickEntry .opt","e=>e.length")==4,
       pg.eval_on_selector_all("#pPickEntry .opt","e=>e.length"))
    ck("half-and-half surface reasoned", "invisible on white" in pg.inner_text("#prtEntry"),
       pg.inner_text("#prtEntry")[:200])
    pg.evaluate("()=>{document.querySelector('#pPickEntry .opt').click();}"); pg.wait_for_timeout(250)
    setstep("#prtEntry",0,6); dialpick("#prtEntry",0,"half & half")
    ck("print settings write through",
       pg.evaluate("()=>document.getElementById('pOn').value")=="half black / half white",
       pg.evaluate("()=>document.getElementById('pOn').value"))

    # ---------------- VOUCHERS ----------------
    pg.click('.tab[data-pane="p-vou"]'); pg.wait_for_timeout(300)
    ck("voucher pick is a FEK picker", pg.eval_on_selector_all("#vPickEntry .fek-pick","e=>e.length")==1, "")
    ck("drying log is FEK", pg.eval_on_selector_all("#dryEntry .fek-row","e=>e.length")==4, "")
    ck("dryer defaults to 43 C",
       pg.evaluate("()=>document.querySelectorAll('#dryEntry .fek-step .val')[0].value")=="43",
       pg.evaluate("()=>document.querySelectorAll('#dryEntry .fek-step .val')[0].value"))
    ck("DNA degradation warned in the control", "50 °C" in pg.inner_text("#dryEntry"),
       pg.inner_text("#dryEntry")[-200:])
    pg.evaluate("()=>{document.querySelector('#vPickEntry .opt').click();}"); pg.wait_for_timeout(200)
    dialpick("#dryEntry",1,"silica")
    ck("DNA choice writes through", pg.evaluate("()=>document.getElementById('vDna').value")=="taken — silica",
       pg.evaluate("()=>document.getElementById('vDna').value"))
    pg.click("#vAdd"); pg.wait_for_timeout(300)
    ck("voucher label built", len(pg.inner_text("#vList"))>40, pg.inner_text("#vList")[:120])

    # ---------------- touch targets & viewport ----------------
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900})
        for t in ["p-rec","p-site","p-prt","p-an","p-vou","p-met"]:
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
    # ---------------- METHOD ----------------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace("\u00a0"," ")
    ck("edibility refusal still leads the Method tab",
       m.index("never tell you whether a fungus is edible") < m.index("Field Entry Kit"), "")
    for t in ["Field Entry Kit","a prior to check","Host uncertain","Blank still means blank",
              "Chao1","Shannon"]:
        ck("method documents "+t, t in m, m[:200])
    ck("guessed host called worse than uncertainty",
       "a guessed host is worse than a recorded uncertainty" in m, "")
    ck("effort tiles justified", "would be a fabrication" in m, "")

    ck("no errors after the whole run", not errs, errs[:4])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
