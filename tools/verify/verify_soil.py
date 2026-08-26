# -*- coding: utf-8 -*-
import sys
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

# independent maths
FEED={'grass':dict(cn=20,N=2.4,moist=.80,dens=250),'straw':dict(cn=80,N=0.7,moist=.12,dens=60)}
def blend(items):
    C=N=wet=dry=0
    for m,vol in items:
        w=vol/1000*m['dens']; d=w*(1-m['moist']); n=d*(m['N']/100)
        C+=n*m['cn']; N+=n; wet+=w; dry+=d
    return C/N, wet, dry, (wet-dry)/wet
CN2,WET2,DRY2,MO2 = blend([(FEED['grass'],100),(FEED['straw'],200)])

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
    pg.goto(_u("soil-bench.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(400)
    ck("no startup errors", not errs, errs[:3])
    ck("5 tabs", pg.eval_on_selector_all(".tab","e=>e.length")==5, "")
    ck("FEK version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), pg.evaluate("()=>FEK.version"))

    def tile(lab, root):
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .fek-tile')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0);
            return t?t.querySelector('.v').textContent.trim():null;}""",[root,lab])

    # ---------- FEK controls present and large ----------
    ck("stepper rendered", pg.eval_on_selector_all("#cEntry .fek-step","e=>e.length")==1, "")
    ck("dial rendered", pg.eval_on_selector_all("#cEntry .fek-dial","e=>e.length")>=1, "")
    small=pg.evaluate("""()=>{const bad=[];
      document.querySelectorAll('.fek-step button,.fek-dial button,.fek-chip,.fek-pick .opt').forEach(e=>{
        const r=e.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.height<44) bad.push(e.className+' h='+Math.round(r.height));});
      return bad.slice(0,5);}""")
    ck("all FEK targets >= 44px tall", not small, small)
    bigv=pg.evaluate("""()=>{const v=document.querySelector('.fek-step .val');
      return v?parseFloat(getComputedStyle(v).fontSize):0;}""")
    ck("stepper value >= 26px type", bigv>=26, bigv)

    # stepper behaviour
    def stepv(): return pg.eval_on_selector("#cEntry .fek-step .val","e=>e.value")
    ck("stepper starts at 55", stepv()=="55", stepv())
    pg.evaluate("""()=>{document.querySelectorAll('#cEntry .fek-step button')[1].click();}""")
    pg.wait_for_timeout(80)
    ck("plus increments to 56", stepv()=="56", stepv())
    pg.evaluate("""()=>{const b=document.querySelectorAll('#cEntry .fek-step button')[0]; b.click(); b.click();}""")
    pg.wait_for_timeout(80)
    ck("minus decrements to 54", stepv()=="54", stepv())

    # ---------- compost compliance, known answer ----------
    pg.click("#cDemo"); pg.wait_for_timeout(350)
    # demo: 18 readings; count t>=55 and turns while hot
    seq=[[32,3,False],[48,3,False],[58,3,False],[62,3,True],[64,2,False],[61,3,True],
         [59,3,False],[57,3,True],[56,3,False],[58,2,True],[57,3,False],[56,3,True],
         [55,3,False],[56,3,False],[57,3,False],[55,3,False],[54,3,False],[49,3,False]]
    hot=sum(1 for s in seq if s[0]>=55); turns=sum(1 for s in seq if s[0]>=55 and s[2])
    ck("days at >=55C = %d"%hot, tile("days logged","#cOut")=="%d / 15"%hot, tile("days logged","#cOut"))
    ck("turnings while hot = %d"%turns, tile("turnings while hot","#cOut")=="%d / 5"%turns,
       tile("turnings while hot","#cOut"))
    co=pg.inner_text("#cOut")
    ck("windrow shortfall reported", "Not there yet" in co, co[:200])
    ck("names days still needed", "more day" in co, co[:300])
    ck("peak 64 flagged not over 66", "reading" not in co.split("Not there yet")[1][:200] or "66" not in co.split("above 66")[0][-5:], "")
    # the demo ends at 49 C, above the 40 C threshold -- log a genuinely cool
    # reading to exercise the cooled-below-40 branch
    pg.evaluate("""()=>{const v=document.querySelector('#cEntry .fek-step .val');
      v.value='34'; v.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.click("#cAdd"); pg.wait_for_timeout(300)
    ck("cooled-below-40 note", "cooled below 40" in pg.inner_text("#cOut"), pg.inner_text("#cOut")[-300:])
    pg.click("#cUndo"); pg.wait_for_timeout(250)
    co=pg.inner_text("#cOut")
    ck("chart drawn", pg.eval_on_selector_all("#cChart svg","e=>e.length")==1, "")
    # Each threshold line carries its own NUMBER, not one particular sentence.
    # Both of these pinned a phrase and both broke when the prose around them was
    # rewritten -- "thermophiles die off" became "conventional ceiling" and the
    # check reported the line UNLABELLED rather than relabelled. What the check
    # is for is that a reader can tell which line is which (ADR-041, ADR-060).
    chart = pg.inner_text("#cChart")
    ck("55C threshold line carries its value", "55 °C" in chart, chart[:160])
    ck("66C ceiling line carries its value", "66 °C" in chart, chart[:160])
    ck("and the two lines say different things, so neither is a copy of the other",
       len({l.strip() for l in chart.splitlines() if "°C" in l and l.strip()}) >= 2,
       [l for l in chart.splitlines() if "°C" in l])

    # switch to in-vessel -> 3 days needed -> should now pass
    pg.evaluate("""()=>{const b=[...document.querySelectorAll('#cSetup .fek-dial button')]
      .find(x=>x.textContent.indexOf('In-vessel')===0); b.click();}""")
    pg.wait_for_timeout(300)
    co2=pg.inner_text("#cOut")
    ck("in-vessel now passes", "meets the in-vessel" in co2, co2[:250])
    ck("pass still caveated", "certifier" in co2, "")
    ck("no turning requirement for in-vessel", "turnings while hot" not in co2, co2[:200])

    # over-66 warning
    pg.evaluate("""()=>{const b=[...document.querySelectorAll('#cSetup .fek-dial button')]
      .find(x=>x.textContent.indexOf('Windrow')===0); b.click();}""")
    pg.wait_for_timeout(200)
    pg.evaluate("""()=>{const v=document.querySelector('#cEntry .fek-step .val');
      v.value='72'; v.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.click("#cAdd"); pg.wait_for_timeout(300)
    ck("above-66 warning fires", "above 66" in pg.inner_text("#cOut"), pg.inner_text("#cOut")[:300])
    pg.click("#cUndo"); pg.wait_for_timeout(200)

    # ---------- recipe: known answer ----------
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(300)
    def pick(name):
        pg.evaluate("""(n)=>{const s=document.querySelector('#rPick .search');
          s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""",name)
        pg.wait_for_timeout(120)
        pg.evaluate("""()=>{document.querySelector('#rPick .opt').click();}""")
        pg.wait_for_timeout(120)
    def setvol(v):
        pg.evaluate("""(v)=>{const i=document.querySelector('#rAmt .fek-step .val');
          i.value=String(v); i.dispatchEvent(new Event('input',{bubbles:true}));}""",v)
        pg.wait_for_timeout(80)
    pick("grass"); setvol(100); pg.click("#rAdd"); pg.wait_for_timeout(200)
    ck("grass alone C:N 20.0", tile("blended C:N","#rOut")=="20.0:1", tile("blended C:N","#rOut"))
    ck("nitrogen-rich warning", "nitrogen-rich" in pg.inner_text("#rOut"), pg.inner_text("#rOut")[:250])
    pick("straw"); setvol(200); pg.click("#rAdd"); pg.wait_for_timeout(250)
    ck("blend C:N = %.1f"%CN2, tile("blended C:N","#rOut")=="%.1f:1"%CN2, (tile("blended C:N","#rOut"),CN2))
    ck("wet mass = %.0f kg"%WET2, tile("wet mass","#rOut")=="%.0f kg"%WET2, tile("wet mass","#rOut"))
    ck("dry mass = %.0f kg"%DRY2, tile("dry mass","#rOut")=="%.0f kg"%DRY2, tile("dry mass","#rOut"))
    ck("moisture = %.0f%%"%(MO2*100), tile("moisture as built","#rOut")=="%.0f%%"%(MO2*100),
       tile("moisture as built","#rOut"))
    ro=pg.inner_text("#rOut")
    ck("carbon-rich verdict at 42.9", "carbon-rich" in ro, ro[:250])
    ck("suggests litres of greens", "more L" in ro or "L more" in ro, ro[:400])
    ck("feedstock variability disclosed", "vary by a factor" in pg.inner_text("#rPick")+pg.inner_text("#rTypical"), "")

    # ---------- mix ----------
    pg.click('.tab[data-pane="p-mix"]'); pg.wait_for_timeout(250)
    def addComp(name,n=1):
        for _ in range(n):
            pg.evaluate("""(nm)=>{const b=[...document.querySelectorAll('#mGrid button')]
              .find(x=>x.querySelector('span').textContent.trim()===nm); b.click();}""",name)
            pg.wait_for_timeout(80)
    addComp("sphagnum peat",1); addComp("perlite",1)
    pg.wait_for_timeout(250)
    ck("nutrient load 0.00", tile("nutrient load","#mOut")=="0.00 / 5", tile("nutrient load","#mOut"))
    ck("nutrient-free banner", "Nutrient-free" in pg.inner_text("#mOut"), pg.inner_text("#mOut")[:200])
    ck("CP requirement named", "carnivorous" in pg.inner_text("#mOut"), "")
    addComp("finished compost",1); pg.wait_for_timeout(250)
    ck("carries-nutrients banner", "Carries nutrients" in pg.inner_text("#mOut"), "")
    ck("ordinal caveat present", "ranks, not measurements" in pg.inner_text("#mOut"), "")
    ck("3 components in table", pg.eval_on_selector_all("#mOut table tr","e=>e.length")==4,
       pg.eval_on_selector_all("#mOut table tr","e=>e.length"))

    # ---------- texture key ----------
    pg.click('.tab[data-pane="p-tex"]'); pg.wait_for_timeout(250)
    def texPick(txt):
        pg.evaluate("""(t)=>{const b=[...document.querySelectorAll('#tBox .fek-dial button')]
          .find(x=>x.textContent.indexOf(t)>=0); b.click();}""",txt)
        pg.wait_for_timeout(180)
    texPick("Yes — it holds"); texPick("Yes, a ribbon forms"); texPick("Over 5 cm"); texPick("Smooth")
    tx=pg.inner_text("#tBox")
    ck("strong ribbon + smooth -> SILTY CLAY", "SILTY CLAY" in tx, tx[:200])
    ck("path shown", "Path:" in tx, "")
    ck("texture-vs-structure stated", "not structure" in pg.inner_text("#tOut"), "")
    pg.evaluate("""()=>{[...document.querySelectorAll('#tBox button')].find(b=>b.textContent.indexOf('Start over')>=0).click();}""")
    pg.wait_for_timeout(200)
    texPick("No — it falls apart")
    ck("no ball -> SAND", "Texture class: SAND" in pg.inner_text("#tBox"), pg.inner_text("#tBox")[:150])

    # ---------- method sourcing ----------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace("\u00a0"," ")   # nbsp in "40 CFR 503"
    for t in ["40 CFR","503","PFRP","NOP","15 days","5 turnings","25:1","40:1","ΣC ÷ ΣN"]:
        ck("method cites "+t, t in m, "")
    ck("does not certify", "does not certify anything" in m, "")
    ck("averaging-ratios mistake named", "Averaging the ratios" in m, "")

    # ---------- viewport ----------
    for w,hh in [(390,844),(768,1024)]:
        pg.set_viewport_size({"width":w,"height":hh})
        for t in ["p-comp","p-rec","p-mix","p-tex","p-met"]:
            pg.click('.tab[data-pane="%s"]'%t); pg.wait_for_timeout(140)
            ow=pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            ck("no h-overflow %d %s"%(w,t), ow<=w+1, "%d > %d"%(ow,w))
    ck("no errors at end", not errs, errs[:3])
    b.close()
print("PASS %d"%len(P))
for x in F: print("FAIL:",x)
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
sys.exit(1 if F else 0)
