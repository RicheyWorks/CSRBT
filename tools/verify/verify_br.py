# -*- coding: utf-8 -*-
import sys, math
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
    pg.goto(_u("breeding-bench.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(450)
    ck("no startup errors", not errs, errs[:3])
    ck("6 tabs", pg.eval_on_selector_all(".tab","e=>e.length")==6, "")
    ck("FEK v1.1.0", pg.evaluate("()=>FEK.version")=="1.1.0", "")

    def tile(lab, root):
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .fek-tile')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0);
            return t?t.querySelector('.v').textContent.trim():null;}""",[root,lab])
    def steps(root):
        return pg.evaluate("(r)=>[...document.querySelectorAll(r+' .fek-step .val')].map(i=>i.value)",root)
    def setstep(root,idx,val):
        pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
          s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(110)
    def pick(root,name):
        pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
          s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""",[root,name])
        pg.wait_for_timeout(120)
        pg.evaluate("(r)=>{document.querySelector(r+' .opt').click();}",root)
        pg.wait_for_timeout(160)

    # ---------------- POPULATION ----------------
    pick("#popPick","bean, common"); pg.wait_for_timeout(250)
    ck("bean min = 20", tile("published minimum","#popOut")=="20", tile("published minimum","#popOut"))
    ck("bean is self", tile("mating system","#popOut")=="self", tile("mating system","#popOut"))
    setstep("#popN",0,20); pg.wait_for_timeout(250)
    ck("20 beans meets floor", "Just above the floor" in pg.inner_text("#popOut"),
       pg.inner_text("#popOut")[:250])
    setstep("#popN",0,10); pg.wait_for_timeout(250)
    ck("10 beans below floor", "Below the published minimum of 20" in pg.inner_text("#popOut"),
       pg.inner_text("#popOut")[:200])
    pick("#popPick","corn, sweet"); pg.wait_for_timeout(250)
    ck("corn min shows 100 (200)", tile("published minimum","#popOut")=="100 (200)",
       tile("published minimum","#popOut"))
    ck("corn is cross", tile("mating system","#popOut")=="cross", "")
    ck("corn wind pollinated", tile("pollinated by","#popOut")=="wind", "")
    po=pg.inner_text("#popOut")
    ck("outbreeder cost explained", "recessive alleles" in po, po[:400])
    ck("crop note shown", "promiscuous" in po, "")
    pick("#popPick","carrot"); pg.wait_for_timeout(250)
    ck("carrot note names Queen Anne's lace", "Queen Anne" in pg.inner_text("#popOut"), "")

    # Ne known answer: 10 pollen / 90 seed -> 36.0, dF 1.39%
    setstep("#popN",1,10); setstep("#popN",2,90); pg.wait_for_timeout(300)
    ck("Ne = 36.0", tile("Nₑ","#neOut")=="36.0", tile("Nₑ","#neOut"))
    ck("dF = 1.39%", tile("ΔF per generation","#neOut")=="1.39%", tile("ΔF per generation","#neOut"))
    ck("10 generations = 13.9%", tile("after 10 generations","#neOut")=="13.9%",
       tile("after 10 generations","#neOut"))
    ck("rarer sex flagged", "rarer sex is capping you" in pg.inner_text("#neOut"),
       pg.inner_text("#neOut")[:300])
    setstep("#popN",1,50); setstep("#popN",2,50); pg.wait_for_timeout(300)
    ck("balanced Ne = 100.0", tile("Nₑ","#neOut")=="100.0", tile("Nₑ","#neOut"))
    ck("balanced contributions noted", "reasonably balanced" in pg.inner_text("#neOut"), "")

    # ---------------- ISOLATION ----------------
    pg.click('.tab[data-pane="p-iso"]'); pg.wait_for_timeout(250)
    ir=pg.inner_text("#isoRefuse")
    ck("refuses most isolation distances", "yours to enter" in ir, ir[:200])
    ck("refusal links ADR-031", pg.eval_on_selector_all('#isoRefuse a[href*="adr-031"]',"e=>e.length")>=1, "")
    pick("#isoPick","corn, sweet"); pg.wait_for_timeout(250)
    ck("corn cites two miles", tile("cited (NMSU H-262)","#isoOut")=="two miles",
       tile("cited (NMSU H-262)","#isoOut"))
    setstep("#isoEntry",0,100); pg.wait_for_timeout(250)
    ck("100 m short of corn distance", "Short of the cited two miles" in pg.inner_text("#isoOut"),
       pg.inner_text("#isoOut")[:250])
    ck("suggests time isolation", "time isolation" in pg.inner_text("#isoOut"), "")
    setstep("#isoEntry",0,3500); pg.wait_for_timeout(250)
    ck("3500 m meets corn distance", "Meets the cited two miles" in pg.inner_text("#isoOut"), "")
    pick("#isoPick","tomato"); pg.wait_for_timeout(250)
    io_=pg.inner_text("#isoOut")
    ck("tomato has no cited distance", "No cited distance" in io_, io_[:200])
    ck("tomato flagged self-pollinating", "self</b>-pollinating" in io_ or "self-pollinating" in io_, "")
    pick("#isoPick","brassica, B. oleracea"); pg.wait_for_timeout(250)
    ck("brassica species trap named", "ONE species" in pg.inner_text("#isoOut"),
       pg.inner_text("#isoOut")[-350:])

    # ---------------- SELECTION ----------------
    pg.click('.tab[data-pane="p-sel"]'); pg.wait_for_timeout(250)
    setstep("#selEntry",0,100); setstep("#selEntry",1,10); pg.wait_for_timeout(300)
    ck("i(0.10) = 1.755", tile("intensity i","#selOut")=="1.755", tile("intensity i","#selOut"))
    ck("proportion kept 10.0%", tile("proportion kept","#selOut")=="10.0%", tile("proportion kept","#selOut"))
    # R = 1.755 * 0.35 * 10 = 6.14
    ck("R = 6.14", tile("expected R","#selOut")=="6.14", tile("expected R","#selOut"))
    ck("Ne warning at 10 parents", "costs you a population" in pg.inner_text("#selOut"),
       pg.inner_text("#selOut")[:400])
    ck("h2 flagged as assumption", "assumption, not a measurement" in pg.inner_text("#selOut"), "")
    setstep("#selEntry",1,50); pg.wait_for_timeout(300)
    ck("i(0.50) = 0.798", tile("intensity i","#selOut")=="0.798", tile("intensity i","#selOut"))
    setstep("#selEntry",1,200); pg.wait_for_timeout(300)
    ck("kept > grown caught", "cannot keep more parents" in pg.inner_text("#selOut"),
       pg.inner_text("#selOut")[:150])
    setstep("#selEntry",1,10); pg.wait_for_timeout(250)
    # roguing
    pg.evaluate("""()=>{const s=[...document.querySelectorAll('#rogEntry .fek-step .val')];
      s[0].value='85'; s[0].dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.click("#rAdd"); pg.wait_for_timeout(300)
    ck("roguing total 85", tile("rogued in total","#rogOut")=="85", tile("rogued in total","#rogOut"))
    ck("left standing 15", tile("left standing","#rogOut")=="15", tile("left standing","#rogOut"))
    ck("roguing drops below floor", "below the inbreeder floor" in pg.inner_text("#rogOut"),
       pg.inner_text("#rogOut")[-250:])

    # ---------------- TRIAL: known answers ----------------
    pg.click('.tab[data-pane="p-tri"]'); pg.wait_for_timeout(250)
    pg.click("#tDemo"); pg.wait_for_timeout(400)
    ck("4 entries", tile("entries","#triOut")=="4", tile("entries","#triOut"))
    ck("3 blocks", tile("blocks","#triOut")=="3", tile("blocks","#triOut"))
    ck("grand mean 11.75 kg", tile("grand mean","#triOut")=="11.75 kg", tile("grand mean","#triOut"))
    ck("MSE 0.167", tile("MSE","#triOut")=="0.167", tile("MSE","#triOut"))
    ck("LSD 0.82 kg", tile("LSD","#triOut")=="0.82 kg", tile("LSD","#triOut"))
    ck("CV 3.5%", tile("CV","#triOut")=="3.5%", tile("CV","#triOut"))
    ck("CV called tidy", "tidy" in pg.inner_text("#triOut"), pg.inner_text("#triOut")[-300:])
    tt=pg.inner_text("#triTable")
    ck("entry means table present", "Entry means" in tt, "")
    ck("best entry mean 14.00", "14.00" in tt, tt[:250])
    ck("block means shown", "Block 1" in tt and "11.75" in tt, "")
    # 14.00 vs 10.00 = 4.00 > LSD -> differs; nothing within 0.82 of best except itself
    ck("entry 1 differs from best", tt.count("yes")>=1, tt[:400])
    ck("block gradient explained", "field gradient" in tt, "")
    # single-rep refusal
    pg.click("#tClear"); pg.wait_for_timeout(150)
    for e in (1,2,3):
        setstep("#triEntry",0,e); setstep("#triEntry",1,1); setstep("#triEntry",2,10+e)
        pg.click("#tAdd"); pg.wait_for_timeout(120)
    ck("one replicate refused", "One replicate is not a trial" in pg.inner_text("#triOut"),
       pg.inner_text("#triOut")[:250])
    # incomplete design
    setstep("#triEntry",0,1); setstep("#triEntry",1,2); setstep("#triEntry",2,11)
    pg.click("#tAdd"); pg.wait_for_timeout(250)
    ck("incomplete design refused", "design is not complete" in pg.inner_text("#triOut"),
       pg.inner_text("#triOut")[:250])

    # ---------------- SEED ----------------
    pg.click('.tab[data-pane="p-seed"]'); pg.wait_for_timeout(250)
    setstep("#germEntry",0,100); setstep("#germEntry",1,90); pg.wait_for_timeout(300)
    ck("germination 90.0%", tile("germination","#germOut")=="90.0%", tile("germination","#germOut"))
    ck("binomial SE 3.0%", tile("binomial SE","#germOut")=="±3.0%", tile("binomial SE","#germOut"))
    ck("95% interval shown", "–" in (tile("95% interval","#germOut") or ""), tile("95% interval","#germOut"))
    ck("sowing rate derived", "seeds per plant" in pg.inner_text("#germOut"), "")
    setstep("#germEntry",0,20); setstep("#germEntry",1,18); pg.wait_for_timeout(300)
    ck("20 seeds warns small sample", "Only 20 seeds tested" in pg.inner_text("#germOut"),
       pg.inner_text("#germOut")[-250:])
    setstep("#germEntry",1,30); pg.wait_for_timeout(250)
    ck("more germinated than sown caught", "More germinated than you sowed" in pg.inner_text("#germOut"), "")
    setstep("#germEntry",1,18); pg.wait_for_timeout(200)
    pg.evaluate("""()=>{const s=[...document.querySelectorAll('#storEntry .fek-step .val')];
      s[0].value='7'; s[0].dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(300)
    so=pg.inner_text("#storOut")
    ck("7 years past the window", "Past the conventional window" in so, so[:200])
    ck("3-5 years labelled a convention", "range and a convention" in so, "")
    ck("cool and dry rule given", "Cool and dry" in so, "")

    # ---------------- METHOD ----------------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace(" "," ")
    for t in ["effective population size","ΔF","truncation","LSD","CV%","NMSU","Learn Seed Saving","ADR-031"]:
        ck("method covers "+t, t in m, "")
    ck("multiple-comparison trap stated", "LSD lies when you have many entries" in m, "")
    ck("intensity-vs-population tension stated", "fights population size" in m, "")

    # ---------------- FEK + viewport ----------------
    small=pg.evaluate("""()=>{const bad=[];
      document.querySelectorAll('.fek-step button,.fek-dial button,.fek-chip,.fek-pick .opt').forEach(e=>{
        const r=e.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.height<44) bad.push(e.className);});
      return bad.slice(0,5);}""")
    ck("FEK targets >= 44px", not small, small)
    for w,hh in [(390,844),(768,1024)]:
        pg.set_viewport_size({"width":w,"height":hh})
        for t in ["p-pop","p-iso","p-sel","p-tri","p-seed","p-met"]:
            pg.click('.tab[data-pane="%s"]'%t); pg.wait_for_timeout(140)
            ow=pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            ck("no h-overflow %d %s"%(w,t), ow<=w+1, "%d > %d"%(ow,w))
    ck("no errors at end", not errs, errs[:3])
    b.close()
print("PASS %d"%len(P))
for x in F: print("FAIL:",x)
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
sys.exit(1 if F else 0)
