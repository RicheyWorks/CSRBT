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
def ck(n,c,e=""):
    (P if c else F).append(n+(("  << "+str(e)) if (e and not c) else ""))

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":820,"height":1200})
    pg.set_default_timeout(15000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    def _con(m):
        if m.type!="error": return
        # the font CDN is unreachable here and this test aborts it deliberately
        if "ERR_CONNECTION" in m.text or "ERR_FAILED" in m.text or "fonts.g" in m.text: return
        errs.append(m.text)
    pg.on("console", _con)
    pg.goto(_u("ethogram.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(400)
    ck("no startup errors", not errs, errs[:3])

    tabs=pg.eval_on_selector_all(".tab","e=>e.map(x=>x.textContent.trim())")
    ck("5 tabs", len(tabs)==5, tabs)
    ck("default ethogram loaded",
       pg.eval_on_selector_all("#stateGrid .bb","e=>e.length")==7,
       pg.eval_on_selector_all("#stateGrid .bb","e=>e.length"))
    ck("8 events", pg.eval_on_selector_all("#eventGrid .bb","e=>e.length")==8,
       pg.eval_on_selector_all("#eventGrid .bb","e=>e.length"))
    ck("out-of-sight is a state", "out of sight" in pg.inner_text("#stateGrid"), "")

    # ---------- design coherence warnings ----------
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(200)
    def pick(host,label):
        pg.evaluate("""([h,l])=>{const b=[...document.querySelectorAll('#'+h+' .kopt')]
          .find(x=>x.textContent.toLowerCase().startsWith(l.toLowerCase())); if(!b) throw new Error('no '+l); b.click();}""",[host,label])
    pick("dSample","scan"); pick("dRecord","continuous"); pg.wait_for_timeout(150)
    ck("scan+continuous flagged incoherent",
       "Scan sampling cannot be continuous" in pg.inner_text("#coherence"), pg.inner_text("#coherence")[:120])
    pick("dRecord","one-zero"); pg.wait_for_timeout(150)
    ck("one-zero flagged biased", "biased number" in pg.inner_text("#coherence"), pg.inner_text("#coherence")[:150])
    pick("dSample","ad libitum"); pg.wait_for_timeout(150)
    ck("ad libitum flagged not-a-rate", "not a source of rates" in pg.inner_text("#coherence"), "")
    pick("dSample","focal"); pick("dRecord","continuous"); pg.wait_for_timeout(150)
    ck("focal+continuous is coherent", pg.inner_text("#coherence").strip()=="", pg.inner_text("#coherence")[:120])

    # ---------- continuous focal: known-answer time budget ----------
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(200)
    pg.click("#rStart"); pg.wait_for_timeout(50)
    def tapstate(name):
        pg.evaluate("""(n)=>{const b=[...document.querySelectorAll('#stateGrid .bb')]
          .find(x=>x.querySelector('.nm').textContent.trim()===n); b.click();}""", name)
    def tapevent(name):
        pg.evaluate("""(n)=>{const b=[...document.querySelectorAll('#eventGrid .bb')]
          .find(x=>x.querySelector('.nm').textContent.trim()===n); b.click();}""", name)
    tapstate("forage"); pg.wait_for_timeout(1000)
    tapstate("vigilant"); pg.wait_for_timeout(500)
    tapevent("alarm"); tapevent("alarm")
    tapstate("out of sight"); pg.wait_for_timeout(600)
    tapstate("forage"); pg.wait_for_timeout(900)
    pg.click("#rStop"); pg.wait_for_timeout(300)

    pg.click('.tab[data-pane="p-bud"]'); pg.wait_for_timeout(300)
    bud=pg.inner_text("#budBox")
    ck("budget lists forage", "forage" in bud, bud[:200])
    ck("budget lists vigilant", "vigilant" in bud, "")
    ck("out-of-sight excluded from denominator", "excluded from the denominator" in bud, bud[-300:])
    # forage ~1.9s of ~2.4s observed -> ~79%; vigilant ~0.5 -> ~21%; must sum to 100
    pcts = pg.evaluate("""()=>[...document.querySelectorAll('#budBox table tr')].slice(1)
        .map(r=>parseFloat(r.children[2].textContent))""")
    ck("budget percentages sum to 100", abs(sum(pcts)-100)<0.6, pcts)
    ck("forage is the largest share", pcts and pcts[0]>50, pcts)
    ck("oos not a budget row", "out of sight" not in bud.split("elapsed")[-1].split("Out-of-sight")[0], "")
    rate=pg.inner_text("#rateBox")
    ck("event rate computed for alarm", "alarm" in rate, rate[:200])
    ck("rates are per observed minute", "observed" in rate, "")
    ck("transitions rendered", "Transitions" in pg.inner_text("#transBox"), "")
    ck("transition diagonal struck out", "—" in pg.inner_text("#transBox"), "")
    ck("first-order caveat stated", "first-order" in pg.inner_text("#transBox"), "")
    ck("pseudoreplication warning (one subject)", "one individual" in pg.inner_text("#budBox"), pg.inner_text("#budBox")[-250:])

    # ---------- instantaneous: SE + no event rate ----------
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(150)
    pick("dSample","scan"); pick("dRecord","instantaneous"); pg.wait_for_timeout(150)
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(200)
    ck("scan box appears in point mode", "Scan" in pg.inner_text("#scanBox"), pg.inner_text("#scanBox")[:80])
    ck("point mode: rate guidance shown before any data",
       "cannot give a rate" in pg.inner_text("#rateBox"), pg.inner_text("#rateBox")[:150])
    # take two real point samples, then re-check
    pg.click("#rStart"); pg.wait_for_timeout(60)
    pg.evaluate("""()=>{const b=[...document.querySelectorAll('#stateGrid .bb')]
      .find(x=>x.querySelector('.nm').textContent.trim()==='forage'); b.click();}""")
    pg.click("#rStop"); pg.wait_for_timeout(200)
    pg.click('.tab[data-pane="p-bud"]'); pg.wait_for_timeout(250)
    ck("point mode: still no rate from points",
       "cannot give a rate" in pg.inner_text("#rateBox"), pg.inner_text("#rateBox")[:150])
    ck("point mode reports SE", "SE" in pg.inner_text("#budBox"), pg.inner_text("#budBox")[:250])

    # ---------- one-zero refuses to become a budget ----------
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(150)
    pick("dRecord","one-zero"); pg.wait_for_timeout(150)
    pg.click('.tab[data-pane="p-bud"]'); pg.wait_for_timeout(250)
    oz=pg.inner_text("#budBox")
    ck("one-zero labelled as such", "one-zero scores" in oz, oz[:200])
    ck("one-zero refuses budget/rate conversion", "not a time budget" in oz, oz[:400])

    # ---------- Cohen's kappa: known answer ----------
    # A: F F V R L F V V R F   B: F V V R L F V R R F
    # agree on 8/10 -> po=0.8
    # A marg: F4 V3 R2 L1 ; B marg: F3 V3 R3 L1
    # pe = (4*3 + 3*3 + 2*3 + 1*1)/100 = (12+9+6+1)/100 = 0.28
    # k = (0.8-0.28)/(1-0.28) = 0.52/0.72 = 0.72222
    pg.click('.tab[data-pane="p-rel"]'); pg.wait_for_timeout(200)
    pg.fill("#kA","F F V R L F V V R F")
    pg.fill("#kB","F V V R L F V R R F")
    pg.click("#kGo"); pg.wait_for_timeout(250)
    def tv(lab):
        return pg.evaluate("""(l)=>{const t=[...document.querySelectorAll('#kOut .tile')]
            .find(x=>x.querySelector('.l').textContent.trim()===l); return t?t.querySelector('.v').textContent.trim():null;}""",lab)
    ck("kappa = 0.722", tv("Cohen's κ")=="0.722", tv("Cohen's κ"))
    ck("raw agreement 80.0%", tv("raw agreement")=="80.0%", tv("raw agreement"))
    ck("expected by chance 28.0%", tv("expected by chance")=="28.0%", tv("expected by chance"))
    ck("n samples 10", tv("samples")=="10", tv("samples"))
    kout=pg.inner_text("#kOut")
    ck("Landis&Koch labelled a convention", "convention" in kout and "arbitrary" in kout, kout[:300])
    ck("small-n warning at n=10", "samples is few" in kout, kout[-200:])
    ck("confusion matrix rendered", "Confusion matrix" in pg.inner_text("#kMatrix"), "")
    ck("commonest disagreement named", "commonest disagreement" in pg.inner_text("#kMatrix"), "")
    # length mismatch
    pg.fill("#kB","F V V"); pg.click("#kGo"); pg.wait_for_timeout(200)
    ck("length mismatch caught", "Different lengths" in pg.inner_text("#kOut"), pg.inner_text("#kOut")[:120])

    # ---------- method tab ----------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(200)
    m=pg.inner_text("#p-met")
    for t in ["Altmann","ad libitum","focal animal","one-zero","Landis","pseudoreplication","first-order Markov"]:
        ck("method covers "+t, t.lower() in m.lower(), "")
    ck("observed-vs-elapsed explained", "Observed time is not elapsed time" in m, "")

    # ---------- ethogram import validation ----------
    ck("import accepts json", pg.eval_on_selector("#packFile","e=>e.accept.indexOf('json')>=0"), "")
    ck("AI prompt button present", pg.eval_on_selector("#packPrompt","e=>!!e"), "")

    # ---------- viewport ----------
    for w,hh,lbl in [(390,844,"phone"),(768,1024,"tablet")]:
        pg.set_viewport_size({"width":w,"height":hh})
        for pane in ["p-rec","p-des","p-bud","p-rel","p-met"]:
            pg.click('.tab[data-pane="%s"]'%pane); pg.wait_for_timeout(120)
            ow=pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            ck("no h-overflow %s %s"%(lbl,pane), ow<=w+1, "%d > %d"%(ow,w))
    pg.set_viewport_size({"width":390,"height":844})
    small=pg.evaluate("""()=>{const bad=[];document.querySelectorAll('button, select, input, a').forEach(e=>{
        const r=e.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.height<43) bad.push(e.tagName+'.'+(e.className||''));});
        return bad.slice(0,5);}""")
    ck("touch targets >= 43px", not small, small)
    ck("no errors at end", not errs, errs[:3])
    # ---------------- FEK migration ----------------
    ck("FEK v1.1.0 present", pg.evaluate("()=>typeof FEK!=='undefined'&&FEK.version")=="1.1.0", "")
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.map(x=>x.id)"))
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(300)
    ck("timing is FEK", pg.eval_on_selector_all("#timeEntry .fek-step","e=>e.length")==2, "")
    ck("behaviour kind is a FEK dial", pg.eval_on_selector_all("#kindEntry .fek-dial","e=>e.length")==1, "")
    ck("interval defaults to 30 s",
       pg.evaluate("()=>document.querySelectorAll('#timeEntry .fek-step .val')[0].value")=="30",
       pg.evaluate("()=>document.querySelectorAll('#timeEntry .fek-step .val')[0].value"))
    pg.evaluate("""()=>{const s=document.querySelectorAll('#timeEntry .fek-step .val')[0];
      s.value='15'; s.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(250)
    ck("interval writes through", pg.evaluate("()=>document.getElementById('dScan').value")=="15",
       pg.evaluate("()=>document.getElementById('dScan').value"))
    ck("interval is clamped above zero",
       pg.evaluate("""()=>{const s=document.querySelectorAll('#timeEntry .fek-step .val')[0];
         s.value='0'; s.dispatchEvent(new Event('input',{bubbles:true}));
         s.dispatchEvent(new Event('blur',{bubbles:true}));
         return document.getElementById('dScan').value;}""")!="0",
       pg.evaluate("()=>document.getElementById('dScan').value"))
    pg.evaluate("""()=>{const s=document.querySelectorAll('#timeEntry .fek-step .val')[0];
      s.value='30'; s.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(200)
    ck("state/event distinction carried in the control",
       "cannot give you a rate" in pg.inner_text("#kindEntry"), pg.inner_text("#kindEntry")[-160:])
    pg.evaluate("""()=>{const d=document.querySelector('#kindEntry .fek-dial');
      [...d.querySelectorAll('button')].find(b=>b.querySelector('span').textContent.trim()==='event').click();}""")
    pg.wait_for_timeout(200)
    ck("kind dial writes through", pg.evaluate("()=>document.getElementById('eKind').value")=="event",
       pg.evaluate("()=>document.getElementById('eKind').value"))
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace("\u00a0"," ")
    for t in ["Field Entry Kit","it is not a design","proportion of time","cannot give you a rate"]:
        ck("method documents "+t, t in m, m[:200])

    b.close()

print("PASS %d"%len(P))
for x in F: print("FAIL:",x)
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
sys.exit(1 if F else 0)
