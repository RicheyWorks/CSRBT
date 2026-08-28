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
PAGE_SUITE_FOR = "releve.html"
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
    pg.goto(_u("releve.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(700)
    ck("no startup errors", not errs, errs[:3])
    ck("FEK version matches fek.py", pg.evaluate("()=>typeof FEK!=='undefined'&&FEK.version")==_fek_version(), "")
    ck("6 tabs", pg.eval_on_selector_all(".tab","e=>e.length")==6, "")
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.map(x=>x.id)"))

    def tile(lab, root):
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .tile,'+r+' .fek-tile')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0);
            return t?t.querySelector('.v').textContent.trim():null;}""",[root,lab])
    def dialpick(root,idx,label):
        pg.evaluate("""([r,i,l])=>{const d=[...document.querySelectorAll(r+' .fek-dial')][i];
          const b=[...d.querySelectorAll('button')].find(x=>x.querySelector('span').textContent.trim()===l);
          if(!b) throw new Error('no dial option '+l);
          b.click();}""",[root,idx,label])
        pg.wait_for_timeout(150)
    def pick(root,name):
        pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
          s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""",[root,name])
        pg.wait_for_timeout(140)
        pg.evaluate("(r)=>{const o=document.querySelector(r+' .opt'); if(!o) throw new Error('no match'); o.click();}",root)
        pg.wait_for_timeout(160)
    def setstep(root,idx,val):
        pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
          s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",[root,idx,val])
        pg.wait_for_timeout(130)

    # ---------------- RECORD ----------------
    ck("species is a FEK picker", pg.eval_on_selector_all("#recEntry .fek-pick","e=>e.length")==1, "")
    ck("stratum is a FEK dial", pg.eval_on_selector_all("#strEntry .fek-dial","e=>e.length")==1, "")
    ck("phenophase is a FEK dial", pg.eval_on_selector_all("#phenEntry .fek-dial","e=>e.length")==1, "")
    ck("cover class is a FEK dial", pg.eval_on_selector_all("#rCov .fek-dial","e=>e.length")==1, "")
    ck("Braun-Blanquet has 7 classes",
       pg.eval_on_selector_all("#rCov .fek-dial button","e=>e.length")==7,
       pg.eval_on_selector_all("#rCov .fek-dial button","e=>e.length"))
    # the ordinal ramp: r is the coolest stop, 5 the hottest
    ramps=pg.eval_on_selector_all("#rCov .fek-dial button","e=>e.map(x=>+x.getAttribute('data-r'))")
    ck("cover ramp is monotonic", ramps==sorted(ramps) and ramps[0]==0 and ramps[-1]==5, ramps)

    ck("stratum defaults to H", pg.evaluate("()=>document.getElementById('rStr').value")=="H", "")
    ck("6 strata offered", pg.eval_on_selector_all("#strEntry .fek-dial button","e=>e.length")==6, "")

    # three taxa: classes 4 (62.5), 2 (15), + (0.5)
    names=[]
    for nm,cls in [("sagebrush","4"),("wheatgrass","2"),("cheatgrass","+")]:
        try:
            pick("#recEntry",nm); names.append(nm)
        except Exception:
            pg.fill("#rFree",nm)
        dialpick("#rCov",0,cls)
        pg.click("#rAdd"); pg.wait_for_timeout(250)
    # ---- the stratum bars are read against a 100% scale ------------------
    # `Math.max.apply(null, totals.concat([100]))` -- the 100 is a FLOOR, so a
    # stratum covering 40% draws a bar 40% of the way across rather than filling
    # it. A mutation sweep turned that max into a min and nothing noticed: no
    # check in this kit had ever looked at how wide a bar was drawn.
    #
    # Asserted as the meaning of the floor rather than as a number: while the
    # total is under 100%, the bar width IS the total.
    _bars = pg.evaluate("""()=>[...document.querySelectorAll('#rStrataBox .bar')].map(x=>[
        x.querySelector('.fl').style.width, x.querySelector('.pc').textContent])""")
    ck("the strata chart draws a bar", len(_bars) >= 1, _bars)
    _w, _pc = (_bars[0] if _bars else ("", ""))
    _wv = float(_w[:-1]) if _w.endswith("%") else -1
    _pv = float(_pc.rstrip("%")) if _pc else -1
    ck("a stratum under 100%% cover draws a bar that wide, not a full one",
       0 < _wv < 100 and abs(_wv - _pv) <= 1.0, (_w, _pc))

    ck("cover dial clears after add",
       pg.eval_on_selector_all("#rCov .fek-dial button.on","e=>e.length")==0,
       pg.eval_on_selector_all("#rCov .fek-dial button.on","e=>e.length"))

    pg.click('.tab[data-pane="p-an"]'); pg.wait_for_timeout(300)
    cov=[62.5,15,0.5]; tot=sum(cov)
    H=-sum((x/tot)*math.log(x/tot) for x in cov); J=H/math.log(3)
    ck("3 taxa recorded", tile("taxa","#anStats")=="3", tile("taxa","#anStats"))
    ck("Shannon H' = %.2f"%H, tile("Shannon","#anStats")=="%.2f"%H, tile("Shannon","#anStats"))
    ck("evenness J' = %.2f"%J, tile("evenness","#anStats")=="%.2f"%J, tile("evenness","#anStats"))
    ck("effective taxa = %.1f"%math.exp(H), tile("effective taxa","#anStats")=="%.1f"%math.exp(H),
       tile("effective taxa","#anStats"))
    an=pg.inner_text("#anStats")
    ck("dominant share stated as 80%", "80%" in an, an[:200])
    ck("strong dominance named", "strongly dominated" in an, an[:300])

    # ---------------- refusal: no cover class ----------------
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(250)
    pg.fill("#rFree","test plant")
    pg.click("#rAdd"); pg.wait_for_timeout(250)
    ck("record with no cover class refused", "Tap a cover class" in pg.inner_text("#toast"),
       pg.inner_text("#toast"))

    # ---------------- scale change re-ramps ----------------
    pg.click('.tab[data-pane="p-plot"]'); pg.wait_for_timeout(250)
    pg.evaluate("""()=>{window.confirm=()=>true; const b=[...document.querySelectorAll('#sScale .kopt')]
      .find(x=>x.textContent.indexOf('Daubenmire')>=0); b.click();}""")
    pg.wait_for_timeout(350)
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(250)
    ck("Daubenmire has 6 classes",
       pg.eval_on_selector_all("#rCov .fek-dial button","e=>e.length")==6,
       pg.eval_on_selector_all("#rCov .fek-dial button","e=>e.length"))
    r2=pg.eval_on_selector_all("#rCov .fek-dial button","e=>e.map(x=>+x.getAttribute('data-r'))")
    ck("Daubenmire ramp still monotonic", r2==sorted(r2), r2)
    ck("ramp is keyed to midpoint, not position", r2[0]==1, r2)
    pg.evaluate("""()=>{window.confirm=()=>true;}""")
    pg.click('.tab[data-pane="p-plot"]'); pg.wait_for_timeout(200)
    pg.evaluate("""()=>{const b=[...document.querySelectorAll('#sScale .kopt')]
      .find(x=>x.textContent.indexOf('Braun')>=0); b.click();}""")
    pg.wait_for_timeout(300)

    # ---------------- PLOT ----------------
    ck("plot geometry is FEK", pg.eval_on_selector_all("#geoEntry .fek-step","e=>e.length")==2, "")
    ck("physiography is FEK", pg.eval_on_selector_all("#physEntry .fek-row","e=>e.length")==5, "")
    ck("aspect blank until touched", pg.evaluate("()=>document.getElementById('sAsp').value")=="",
       pg.evaluate("()=>document.getElementById('sAsp').value"))
    dialpick("#physEntry",0,"N")
    ck("north records as 0, not blank", pg.evaluate("()=>document.getElementById('sAsp').value")=="0",
       pg.evaluate("()=>document.getElementById('sAsp').value"))
    dialpick("#physEntry",0,"N")
    ck("tapping again clears it", pg.evaluate("()=>document.getElementById('sAsp').value")=="",
       pg.evaluate("()=>document.getElementById('sAsp').value"))
    ck("8 compass points", pg.eval_on_selector_all("#physEntry .fek-dial >>> nth=0 button","e=>e.length")==8
       if False else pg.evaluate("()=>document.querySelectorAll('#physEntry .fek-dial')[0].querySelectorAll('button').length")==8, "")

    # ---------------- LPI ----------------
    pg.click('.tab[data-pane="p-lpi"]'); pg.wait_for_timeout(300)
    ck("LPI design is FEK", pg.eval_on_selector_all("#lpiEntry .fek-step","e=>e.length")==3, "")
    ck("LPI hit entry is FEK",
       pg.eval_on_selector_all("#lhitEntry .fek-pick","e=>e.length")==1 and
       pg.eval_on_selector_all("#lhitEntry .fek-dial","e=>e.length")==1, "")
    plan=pg.inner_text("#lPlan")
    ck("25 m at 0.5 m = 50 points", "50" in plan, plan[:200])
    se=math.sqrt(0.2*0.8/50)*100
    ck("binomial SE stated (%.1f)"%se, ("%.1f"%se) in plan, plan[:250])
    setstep("#lpiEntry",2,4); pg.wait_for_timeout(250)
    plan=pg.inner_text("#lPlan")
    ck("4 transects = 200 points", "200" in plan, plan[:200])
    se4=math.sqrt(0.2*0.8/200)*100
    ck("SE halves on 4x the points (%.1f)"%se4, ("%.1f"%se4) in plan, plan[:250])
    ck("ground cover is offered in the LPI picker",
       pg.evaluate("()=>[...document.querySelectorAll('#lhitEntry .opt')].some(o=>o.textContent.indexOf('litter')>=0)"),"")

    # ---------------- VOUCHERS ----------------
    pg.click('.tab[data-pane="p-vou")]'.replace(')]',']')); pg.wait_for_timeout(300)
    ck("voucher species is a FEK picker", pg.eval_on_selector_all("#vouEntry .fek-pick","e=>e.length")==1, "")
    ck("duplicates is a stepper", pg.eval_on_selector_all("#vouEntry .fek-step","e=>e.length")==1, "")
    ck("material/phenophase/abundance are dials",
       pg.eval_on_selector_all("#vou2Entry .fek-dial","e=>e.length")==3, "")
    ck("sterile warned about",
       "undeterminable" in pg.inner_text("#vou2Entry"), pg.inner_text("#vou2Entry")[:200])

    # ---------------- WETLAND EDITOR: ordinal dials, blank stays blank ----------------
    pg.click('.tab[data-pane="p-an"]'); pg.wait_for_timeout(400)
    nd=pg.eval_on_selector_all("#wEditor .fek-dial","e=>e.length")
    ck("one wetland dial per taxon", nd==3, nd)
    ck("no select survives in the wetland editor",
       pg.eval_on_selector_all("#wEditor select","e=>e.length")==0, "")
    wr=pg.evaluate("()=>[...document.querySelectorAll('#wEditor .fek-dial')[0].querySelectorAll('button')].map(b=>+b.getAttribute('data-r'))")
    ck("indicator ramp runs wetland to upland", wr==[0,1,2,4,5], wr)
    ck("all five NWPL classes offered", len(wr)==5, wr)
    ck("nothing scored to begin with",
       pg.eval_on_selector_all("#wEditor .fek-dial button.on","e=>e.length")==0, "")
    an0=pg.inner_text("#anWet")
    ck("index withheld while nothing is scored",
       "unscored" in an0 or "No " in an0 or len(an0.strip())<400, an0[:200])
    # score two of three
    for i in (0,1):
        pg.evaluate("""(i)=>{const d=document.querySelectorAll('#wEditor .fek-dial')[i];
          d.querySelectorAll('button')[i].click();}""",i)
        pg.wait_for_timeout(200)
    aw=pg.inner_text("#anWet")
    ck("partial scoring is declared partial", "partial" in aw, aw[:300])
    ck("prevalence index appears once scored", "revalence" in aw, aw[:200])
    # clearing one puts it back to unscored rather than to a default
    pg.evaluate("""()=>{const d=document.querySelectorAll('#wEditor .fek-dial')[0];
      d.querySelector('button.on').click();}""")
    pg.wait_for_timeout(250)
    ck("tapping a scored taxon again clears it",
       pg.eval_on_selector_all("#wEditor .fek-dial","e=>e.filter(d=>d.querySelector('button.on')).length")==1,
       pg.eval_on_selector_all("#wEditor .fek-dial","e=>e.filter(d=>d.querySelector('button.on')).length"))
    ck("unscored explained on the page", "left out of the index" in pg.inner_text("#wEditor"),
       pg.inner_text("#wEditor")[:200])

    # ---- the threshold is INCLUSIVE, and 3.0 is where it is decided ---------
    # The Corps criterion is prevalence index <= 3.0 for hydrophytic vegetation.
    # A mutation sweep turned `PI <= 3.0` into `PI < 3.0` and nothing here
    # noticed: the suite checked that an index appears and never what it was
    # compared against. At exactly 3.00 the mutant flips a wetland determination
    # -- the boundary is not an edge case here, it IS the criterion.
    #
    # 3.00 exactly is easy to reach and reachable in the field: score every
    # taxon FAC, whose indicator value is 3, and the cover-weighted mean is 3
    # for any covers at all. So the fixture does not depend on the cover
    # classes, which is what makes it a test of the comparison.
    _n = pg.eval_on_selector_all("#wEditor .fek-dial", "e=>e.length")
    for _i in range(_n):
        pg.evaluate("""(i)=>{const d=document.querySelectorAll('#wEditor .fek-dial')[i];
          const b=[...d.querySelectorAll('button')].find(
            x=>x.querySelector('span').textContent.trim()==='FAC');
          if(!b) throw new Error('no FAC option'); if(!b.classList.contains('on')) b.click();}""", _i)
        pg.wait_for_timeout(150)
    _aw = pg.inner_text("#anWet")
    ck("all-FAC gives a prevalence index of exactly 3.00", "3.00" in _aw, _aw[:160])
    ck("and 3.00 is called hydrophytic -- the threshold includes its own boundary",
       "at or below" in _aw and "above 3.0" not in _aw, _aw[:260])
    ck("the determination is not claimed to be settled by vegetation alone",
       "one of three criteria" in _aw, _aw[:300])

    # ---------------- METHOD ----------------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace(" "," ")
    for t in ["midpoint","Braun-Blanquet","FQI","Swink","Shannon",
              "Field Entry Kit","eight compass points","Blank still means blank"]:
        ck("method covers "+t, t in m, m[:150])
    ck("ordinal colouring explained", "coloured by midpoint, not by position" in m, "")
    ck("cross-scale colour stability stated", "does not silently change what a" in m, "")
    ck("aspect precision refused", "a precision that was never measured" in m, "")

    # ---------------- touch targets & viewport ----------------
    for w in (390,768):
        pg.set_viewport_size({"width":w,"height":900})
        for t in ["p-rec","p-plot","p-lpi","p-an","p-vou","p-met"]:
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
    ck("no errors after the whole run", not errs, errs[:4])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))

# A suite that cannot fail the run is not a check. This one printed its FAIL
# lines and exited zero, so run_all marked it green whatever it found -- for
# eleven suites in this kit, "green" meant "the process did not crash".
raise SystemExit(1 if F else 0)
