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


def _fek_version():
    """The version FEK actually declares, read from its source rather than frozen
    here -- a bump is not a regression, and a suite that says otherwise gets
    ignored."""
    import re as _re
    src = open(_os.path.join(ROOT, "tools", "fek.py"), encoding="utf-8").read()
    m = _re.search(r'VERSION\s*=\s*"([\d.]+)"', src)
    return m.group(1) if m else None

P=[];F=[]
def ck(n,c,e=""):
    (P if c else F).append(n+(("  << "+str(e)) if (e and not c) else ""))

# ---- independent hand computation ----
x=[8,9,10,11,12,13]; W=[0,0,1,1,1,1]
n=len(x); mx=sum(x)/n; mW=sum(W)/n
after=sum(W[i]*x[i] for i in range(n))/sum(W)
S=after-mx
sd_pop=math.sqrt(sum((a-mx)**2 for a in x)/n)
sd_samp=math.sqrt(sum((a-mx)**2 for a in x)/(n-1))
i_=S/sd_pop
# repeatability: 3 individuals measured twice
rx={"R1":[10.0,10.2],"R2":[12.0,12.1],"R3":[14.0,13.9]}
def icc(g):
    ks=list(g); N=sum(len(g[k]) for k in ks); gm=sum(sum(g[k]) for k in ks)/N; k=len(ks)
    ssA=sum(len(g[q])*(sum(g[q])/len(g[q])-gm)**2 for q in ks)
    ssW=sum(sum((v-sum(g[q])/len(g[q]))**2 for v in g[q]) for q in ks)
    dfA=k-1; dfW=N-k; msA=ssA/dfA; msW=ssW/dfW
    n0=(N-sum(len(g[q])**2 for q in ks)/N)/dfA
    vA=(msA-msW)/n0
    return vA/(vA+msW)
R_hand=icc(rx)

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":880,"height":1200})
    pg.set_default_timeout(15000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    def _con(m):
        if m.type!="error": return
        if "ERR_CONNECTION" in m.text or "ERR_FAILED" in m.text: return
        errs.append(m.text)
    pg.on("console",_con)
    pg.goto(_u("selection-log.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(400)
    ck("no startup errors", not errs, errs[:3])
    ck("5 tabs", pg.eval_on_selector_all(".tab","e=>e.length")==5, "")

    def addInd(label, fit=None):
        pg.click('.tab[data-pane="p-ind"]'); pg.wait_for_timeout(80)
        pg.fill("#iId", label); pg.click("#iAdd"); pg.wait_for_timeout(80)
    def setFit(idx, v):
        """Fitness is a FEK control per row: a two-way dial for survival, a
        nullable stepper for a count."""
        kind=pg.evaluate("""(i)=>{const rows=[...document.querySelectorAll('#iList .row2')];
          return rows[i].querySelector('.fek-dial') ? 'dial' : 'step';}""",idx)
        if kind=="dial":
            pg.evaluate("""([i,v])=>{const rows=[...document.querySelectorAll('#iList .row2')];
              const bs=[...rows[i].querySelectorAll('.fek-dial button')];
              bs[v?1:0].click();}""",[idx, 1 if v else 0])
        else:
            pg.evaluate("""([i,v])=>{const rows=[...document.querySelectorAll('#iList .row2')];
              const inp=rows[i].querySelector('.fek-step .val'); inp.value=String(v);
              inp.dispatchEvent(new Event('input',{bubbles:true}));}""",[idx,v])
        pg.wait_for_timeout(90)
    def pickInd(root, label):
        pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
          s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""",[root,label])
        pg.wait_for_timeout(110)
        pg.evaluate("""([r,n])=>{const o=[...document.querySelectorAll(r+' .opt')]
          .find(x=>x.textContent.trim().indexOf(n)===0);
          if(!o) throw new Error('no individual '+n); o.click();}""",[root,label])
        pg.wait_for_timeout(110)
    def pickChip(root, name):
        pg.evaluate("""([r,n])=>{const c=[...document.querySelectorAll(r+' .fek-chip')]
          .find(x=>x.textContent.trim().indexOf(n)===0);
          if(!c) throw new Error('no chip '+n); c.click();}""",[root,name])
        pg.wait_for_timeout(110)
    def addMeas(indLabel, traitName, v, occ=""):
        pg.click('.tab[data-pane="p-mea"]'); pg.wait_for_timeout(90)
        pickInd("#meaEntry", indLabel)
        pickChip("#meaEntry", traitName)
        pg.evaluate("""(v)=>{const i=document.querySelector('#meaEntry .fek-field input');
          i.value=String(v); i.dispatchEvent(new Event('input',{bubbles:true}));}""", v)
        pg.wait_for_timeout(90)
        if occ: pg.fill("#mOcc", occ)
        pg.click("#mAdd"); pg.wait_for_timeout(90)

    labels=["A1","A2","A3","A4","A5","A6"]
    for L in labels: addInd(L)
    for L,v in zip(labels,x): addMeas(L,"bill depth",v)
    pg.click('.tab[data-pane="p-ind"]'); pg.wait_for_timeout(120)
    for idx,fv in enumerate(W): setFit(idx,fv)
    pg.wait_for_timeout(200)
    pg.fill("#fEp","test drought")

    pg.click('.tab[data-pane="p-sel"]'); pg.wait_for_timeout(300)
    def tile(lab, root="#selOut"):
        # labels append the trait unit ("mean before mm"), so match on prefix
        return pg.evaluate("""([r,l])=>{const t=[...document.querySelectorAll(r+' .st')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().indexOf(l)===0);
            return t?t.querySelector('.v').textContent.trim():null;}""",[root,lab])
    ck("measured n = 6", tile("measured")=="6", tile("measured"))
    ck("mean before = %.3f"%mx, tile("mean before")=="%.3f"%mx, tile("mean before"))
    ck("SD labelled sample n−1 = %.3f"%sd_samp, tile("SD before (sample, n−1)")=="%.3f"%sd_samp,
       tile("SD before (sample, n−1)"))
    ck("with fitness = 6", tile("with fitness")=="6", tile("with fitness"))
    ck("differential S = %.3f"%S, tile("differential S")=="%.3f"%S, tile("differential S"))
    ck("intensity i = %.3f"%i_, tile("intensity i (SD units)")=="%.3f"%i_, tile("intensity i (SD units)"))
    ck("gradient β = %.3f"%i_, tile("gradient β (univariate)")=="%.3f"%i_, tile("gradient β (univariate)"))
    ck("i and β now identical",
       tile("intensity i (SD units)")==tile("gradient β (univariate)"),
       (tile("intensity i (SD units)"), tile("gradient β (univariate)")))
    ck("mean after = %.3f"%after, tile("mean after")=="%.3f"%after, tile("mean after"))
    so=pg.inner_text("#selOut")
    ck("identity i=β explained", "not a coincidence" in so, so[:200])
    ck("upward selection named", "Directional selection upward" in so, "")
    ck("univariate caveat present", "univariate" in so.lower() and "indirect" in so.lower(), "")
    ck("small-n flagged at n=6", "n = 6" in so, "")
    ck("missing repeatability flagged", "No repeatability for this trait" in so, so[-300:])
    ck("histogram rendered", "Distribution" in pg.inner_text("#distBox"), "")
    ck("scatter + beta drawn", "β = " in pg.inner_text("#gradBox"), pg.inner_text("#gradBox")[:120])
    ck("low r2 defended", "low r² is normal" in pg.inner_text("#gradBox"), "")

    # ---------- repeatability, known answer ----------
    for L in ["R1","R2","R3"]: addInd(L)
    for L,vals in [("R1",[10.0,10.2]),("R2",[12.0,12.1]),("R3",[14.0,13.9])]:
        addMeas(L,"tarsus",vals[0],"rep 1"); addMeas(L,"tarsus",vals[1],"rep 2")
    pg.click('.tab[data-pane="p-mea"]'); pg.wait_for_timeout(200)
    pickChip("#meaEntry","tarsus")
    pg.wait_for_timeout(250)
    rb=pg.inner_text("#repBox")
    Rv=pg.evaluate("""()=>{const t=[...document.querySelectorAll('#repBox .st')]
        .find(x=>x.querySelector('.l').textContent.indexOf('repeatability')>=0);
        return t?t.querySelector('.v').textContent.trim():null;}""")
    ck("ICC = %.3f"%R_hand, Rv=="%.3f"%R_hand, (Rv,"%.3f"%R_hand))
    ck("high R gets no noise warning", "mostly noise" not in rb, rb[:200])
    ck("few-individuals warning at 3", "individuals with repeats" in rb, rb[:250])

    # ---------- low repeatability path ----------
    for L in ["N1","N2","N3"]: addInd(L)
    for L,vals in [("N1",[10.0,13.0]),("N2",[12.0,9.5]),("N3",[11.0,13.5])]:
        addMeas(L,"mass",vals[0],"rep 1"); addMeas(L,"mass",vals[1],"rep 2")
    pickChip("#meaEntry","mass")
    pg.wait_for_timeout(250)
    ck("low R triggers the method warning", "your own hand" in pg.inner_text("#repBox"),
       pg.inner_text("#repBox")[:250])

    # ---------- heritability: mid-parent slope known answer ----------
    # offspring = 0.5*midparent + c  -> h2 = 0.5 exactly
    # offspring = 0.5*midparent + 5  ->  mid-parent slope = h2 = 0.500 exactly
    fam=[(10,12,10.5),(12,14,11.5),(14,16,12.5),(16,18,13.5),(11,13,11.0),(13,15,12.0)]
    for k,(d,s_,o) in enumerate(fam):
        for nm,v in [("D%d"%k,d),("S%d"%k,s_),("O%d"%k,o)]:
            addInd(nm); addMeas(nm,"bill length",v)
    pg.click('.tab[data-pane="p-her"]'); pg.wait_for_timeout(200)
    for k in range(len(fam)):
        pickInd("#pedEntry", "O%d"%k)
        pg.evaluate("""([r,n])=>{const ps=[...document.querySelectorAll(r+' .fek-pick')];
          const s=ps[1].querySelector('.search'); s.value=n;
          s.dispatchEvent(new Event('input',{bubbles:true}));}""",["#pedEntry","D%d"%k])
        pg.wait_for_timeout(100)
        pg.evaluate("""([r,n])=>{const ps=[...document.querySelectorAll(r+' .fek-pick')];
          const o=[...ps[1].querySelectorAll('.opt')].find(x=>x.textContent.trim().indexOf(n)===0);
          if(!o) throw new Error('no dam '+n); o.click();}""",["#pedEntry","D%d"%k])
        pg.wait_for_timeout(100)
        pg.evaluate("""([r,n])=>{const ps=[...document.querySelectorAll(r+' .fek-pick')];
          const s=ps[2].querySelector('.search'); s.value=n;
          s.dispatchEvent(new Event('input',{bubbles:true}));}""",["#pedEntry","S%d"%k])
        pg.wait_for_timeout(100)
        pg.evaluate("""([r,n])=>{const ps=[...document.querySelectorAll(r+' .fek-pick')];
          const o=[...ps[2].querySelectorAll('.opt')].find(x=>x.textContent.trim().indexOf(n)===0);
          if(!o) throw new Error('no sire '+n); o.click();}""",["#pedEntry","S%d"%k])
        pg.wait_for_timeout(100)
        pg.click("#pAdd"); pg.wait_for_timeout(90)
    pickChip("#hTraitEntry","bill length")
    pg.wait_for_timeout(300)
    hv=pg.evaluate("""()=>{const t=[...document.querySelectorAll('#herOut .st')]
        .find(x=>x.querySelector('.l').textContent.indexOf('h²')>=0);
        return t?t.querySelector('.v').textContent.trim():null;}""")
    ck("h² from mid-parent = 0.500", hv=="0.500", hv)
    ho=pg.inner_text("#herOut")
    ck("6 families reported", "6" in ho, "")
    ck("shared-environment caveat", "upper bound on the genetic part" in ho, ho[-300:])
    ck("small-family warning at 6", "families" in ho and "noisy" in ho, "")

    # ---------- method ----------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(200)
    m=pg.inner_text("#p-met")
    for t in ["repeatability","attenuat","Lande","breeder","cross-foster","episode","divisor"]:
        ck("method covers "+t, t.lower() in m.lower(), "")
    ck("no p-values stated as policy", "p-value" in m.lower(), "")

    # ---------- viewport ----------
    for w,hh,lbl in [(390,844,"phone"),(768,1024,"tablet")]:
        pg.set_viewport_size({"width":w,"height":hh})
        for pane in ["p-ind","p-mea","p-sel","p-her","p-met"]:
            pg.click('.tab[data-pane="%s"]'%pane); pg.wait_for_timeout(130)
            ow=pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            ck("no h-overflow %s %s"%(lbl,pane), ow<=w+1, "%d > %d"%(ow,w))
    ck("no errors at end", not errs, errs[:3])
    # ---------------- FEK migration ----------------
    ck("FEK version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), pg.evaluate("()=>FEK.version"))
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.map(x=>x.id)"))
    ck("no raw number input outside FEK",
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).length""")==0,
       pg.evaluate("""()=>[...document.querySelectorAll('input[type=number]')]
         .filter(i=>!i.closest('.fek-step')&&!i.closest('.fek-field')).map(i=>i.id)"""))

    pg.click('.tab[data-pane="p-ind"]'); pg.wait_for_timeout(250)
    ck("sex and age are dials", pg.eval_on_selector_all("#indEntry .fek-dial","e=>e.length")==2, "")
    ck("age class ramp is ordinal",
       pg.evaluate("""()=>[...document.querySelectorAll('#indEntry .fek-dial')[1]
         .querySelectorAll('button')].map(b=>+b.getAttribute('data-r'))""")==[0,1,2,4],
       pg.evaluate("""()=>[...document.querySelectorAll('#indEntry .fek-dial')[1]
         .querySelectorAll('button')].map(b=>+b.getAttribute('data-r'))"""))
    ck("fitness component is chips", pg.eval_on_selector_all("#fitEntry .fek-chip","e=>e.length")==3, "")

    # survival is a two-way dial, and it says died / survived in words
    dl=pg.evaluate("""()=>{const r=document.querySelector('#iList .row2');
      return r&&r.querySelector('.fek-dial') ? [...r.querySelectorAll('.fek-dial button')]
        .map(b=>b.querySelector('span').textContent.trim()) : null;}""")
    ck("survival is recorded as died/survived, not 0/1", dl==["died","survived"], dl)
    ck("died is the hot end of the ramp",
       pg.evaluate("""()=>{const r=document.querySelector('#iList .row2');
         return [...r.querySelectorAll('.fek-dial button')].map(b=>+b.getAttribute('data-r'));}""")==[5,2],
       pg.evaluate("""()=>{const r=document.querySelector('#iList .row2');
         return [...r.querySelectorAll('.fek-dial button')].map(b=>+b.getAttribute('data-r'));}"""))

    # switching to a count swaps the control and starts it empty
    pickChip("#fitEntry","offspring recruited")
    pg.wait_for_timeout(300)
    ck("a count component gives steppers instead",
       pg.evaluate("()=>!!document.querySelector('#iList .row2 .fek-step')"), "")
    # values recorded under the previous component are NOT silently reinterpreted
    w=pg.inner_text("#fCompWarn")
    ck("switching component warns about values already recorded",
       "recorded under a different fitness component" in w, w[:250])
    ck("the warning explains why 1 is not 1 offspring",
       "is not one recruited" in w, w[:300])
    ck("it says the values were kept rather than converted", "kept, not reinterpreted" in w, w[:300])
    ck("and offers to clear them",
       pg.eval_on_selector_all("#fCompClear","e=>e.length")==1, "")
    # an individual with nothing recorded starts empty, not at zero
    empt=pg.evaluate("""()=>{const rows=[...document.querySelectorAll('#iList .row2')];
      const r=rows.find(x=>{const v=x.querySelector('.fek-step .val'); return v && v.value==='';});
      return !!r;}""")
    ck("an unrecorded individual's count starts empty, not at zero", empt,
       pg.evaluate("""()=>[...document.querySelectorAll('#iList .row2 .fek-step .val')].map(v=>v.value)"""))
    pg.evaluate("""()=>{const rows=[...document.querySelectorAll('#iList .row2')];
      const r=rows.find(x=>{const v=x.querySelector('.fek-step .val'); return v && v.value==='';});
      r.querySelectorAll('.fek-step button')[1].click();}""")
    pg.wait_for_timeout(250)
    ck("first tap on an empty count starts at 1, not 0",
       pg.evaluate("""()=>[...document.querySelectorAll('#iList .row2 .fek-step .val')]
         .some(v=>v.value==='1')"""),
       pg.evaluate("""()=>[...document.querySelectorAll('#iList .row2 .fek-step .val')].map(v=>v.value)"""))
    # clearing works and removes the warning
    pg.click("#fCompClear"); pg.wait_for_timeout(300)
    ck("clearing removes the warning", pg.inner_text("#fCompWarn").strip()=="",
       pg.inner_text("#fCompWarn")[:120])
    ck("clearing empties every recorded fitness",
       pg.evaluate("""()=>[...document.querySelectorAll('#iList .row2 .fek-step .val')]
         .every(v=>v.value==='')"""),
       pg.evaluate("""()=>[...document.querySelectorAll('#iList .row2 .fek-step .val')].map(v=>v.value)"""))
    pickChip("#fitEntry","survived the episode")
    pg.wait_for_timeout(300)

    # measurement value is a typed field
    pg.click('.tab[data-pane="p-mea"]'); pg.wait_for_timeout(250)
    ck("the trait value is a typed field",
       pg.eval_on_selector_all("#meaEntry .fek-field","e=>e.length")==1, "")
    ck("no stepper on a caliper reading",
       pg.eval_on_selector_all("#meaEntry .fek-step","e=>e.length")==0, "")
    ck("individual is a filterable picker",
       pg.eval_on_selector_all("#meaEntry .fek-pick","e=>e.length")==1, "")
    pg.evaluate("""()=>{const i=document.querySelector('#meaEntry .fek-field input');
      i.value='10.375'; i.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(150)
    ck("three decimals survive entry",
       pg.evaluate("()=>document.getElementById('mVal').value")=="10.375",
       pg.evaluate("()=>document.getElementById('mVal').value"))

    # method note
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace("\u00a0"," ")
    for t in ["Field Entry Kit","two taps","An unrecorded count is not a zero",
              "typed, not stepped","does not reinterpret what you already recorded"]:
        ck("method documents "+t, t in m, m[:200])
    ck("the silent-error argument is made", "nothing about the record looks wrong" in m, "")
    ck("the bias direction is named", "downward" in m, "")
    ck("the blast radius of a silent fitness error is spelled out",
       "all at once and all invisibly" in m, m[-500:])

    b.close()

print("PASS %d"%len(P))
for x_ in F: print("FAIL:",x_)
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
sys.exit(1 if F else 0)
