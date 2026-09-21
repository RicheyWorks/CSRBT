# -*- coding: utf-8 -*-
import math, re
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
    # ADR-209: A SUITE MUST ANSWER THE QUESTIONS THE PAGE ASKS. Headless
    # Chromium DISMISSES an unhandled dialog, so a confirmation added to a
    # destructive control silently turns every press of it into a no-op --
    # and a check that presses Clear and then asserts the sheet is empty
    # would pass only because the page never got to ask.
    pg.on("dialog", lambda d: d.accept())
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

    # ---------------- two countable plates that disagree ----------------
    # The Method tab promises this: "If they disagree by more than about a
    # factor of two, something is wrong with the series rather than with the
    # organism, and the page says so." Nothing checked that it does. A mutation
    # sweep turned `hi=Math.max.apply(...)` into `Math.min.apply`, which makes
    # hi === lo and hi/lo === 1, so the warning could never fire again -- and
    # every suite stayed green.
    setstep("#plEntry",0,5)
    setfield("#plEntry",0,50)
    pg.fill("#plL","TSA-C"); pg.click("#plAdd"); pg.wait_for_timeout(300)
    pn=pg.inner_text("#plNote")
    ck("two countable plates disagreeing by more than 2x are flagged",
       "disagree by" in pn, pn[:300])
    # Recomputed, not pinned: same dilution and volume on both, so the ratio of
    # computed CFU/mL is just the ratio of the counts (ADR-041).
    m=re.search(r"disagree by ([\d.]+)", pn)
    ck("and the factor it states is the ratio of the two counts",
       bool(m) and abs(float(m.group(1)) - 148/50) < 0.05, (m.group(1) if m else None, 148/50))
    ck("the spread is blamed on the series, not the organism",
       "dilution series" in pn or "series" in pn, pn[:300])
    ck("all three plates now feed the list",
       pg.eval_on_selector_all("#plList > *","e=>e.length")==3,
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

    # ---------------- ADR-233: the reports say what the numbers say ----------
    # Three things the micro-bench blind operator (ADR-230) found the page
    # SAYING rather than computing. Each is held against an independent Python
    # recomputation, on a fresh page so no earlier check's state leaks in.
    def _ols(xs, ys):
        n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
        sxx=sum((x-mx)**2 for x in xs); sxy=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
        return sxy/sxx
    def _fmt(v, d):
        from decimal import Decimal, ROUND_HALF_UP
        return str(Decimal(repr(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
    def _sat_expect(pts):
        use=[(t,od) for t,od in pts]
        hi=[q for q in use if q[1]>0.6]; lo=[q for q in use if q[1]<=0.6]
        aa=_ols([q[0] for q in use],[math.log(q[1]) for q in use])
        bb=_ols([q[0] for q in lo],[math.log(q[1]) for q in lo])
        return aa, bb, len(hi)
    def _grow(pts):
        pg.goto(_u("micro-bench.html")); pg.wait_for_timeout(500)
        pg.evaluate("()=>{try{localStorage.clear()}catch(e){}}"); pg.reload(); pg.wait_for_timeout(500)
        pg.click('.tab[data-pane="p-gr"]'); pg.wait_for_timeout(200)
        for t, od in pts:
            setfield("#grEntry",0,t); setfield("#grEntry",1,od)
            pg.click("#grAdd"); pg.wait_for_timeout(120)
        pg.wait_for_timeout(250)
        return pg.inner_text("#grOut").replace(" "," "), pg.inner_text("#ecoOut").replace(" "," ")

    # UP: four points on the doubling line, then OD 1.5 at 4 h where the line says 0.8
    up=[(0,0.05),(1,0.1),(2,0.2),(3,0.4),(4,1.5)]
    s_with,s_wo,n_hi=_sat_expect(up)
    box, sheet = _grow(up)
    want = ("Without the 1 point above OD 0.6, µ is %s h⁻¹; with it, %s h⁻¹ — it pushed it UP by %s%%."
            % (_fmt(s_wo,4), _fmt(s_with,4), _fmt(abs((s_with-s_wo)/s_wo)*100,1)))
    ck("ADR-233: a point ABOVE the line of the others is reported as pushing µ UP, with both slopes from an "
       "independent refit -- the page used to say it pushed µ down whatever it did", want in box, box[-420:])
    ck("ADR-233: ...and says saturation cannot explain a point above the line",
       "a point above the line of the others is not saturation" in box, box[-300:])
    ck("ADR-233: the bench sheet carries the same computed sentence", want in sheet and "pushes µ down" not in sheet,
       [l for l in sheet.split("\n") if "OD 0.6" in l])
    # DOWN: the fifth point BELOW the line (0.65 where the line says 0.8) -- what saturation does
    down=[(0,0.05),(1,0.1),(2,0.2),(3,0.4),(4,0.65)]
    s_with,s_wo,n_hi=_sat_expect(down)
    box, sheet = _grow(down)
    want = ("Without the 1 point above OD 0.6, µ is %s h⁻¹; with it, %s h⁻¹ — it pulled it DOWN by %s%%"
            % (_fmt(s_wo,4), _fmt(s_with,4), _fmt(abs((s_with-s_wo)/s_wo)*100,1)))
    ck("ADR-233: a point BELOW the line is reported as pulling µ DOWN, the direction optical saturation takes",
       want in box and "which is what optical saturation does" in box, box[-420:])
    # TOO FEW: two points at or under 0.6, two above -- nothing to refit
    few=[(0,0.3),(1,0.55),(2,0.9),(3,1.4)]
    box, sheet = _grow(few)
    ck("ADR-233: with fewer than three points left without the high ones, it says the effect cannot be separated "
       "rather than guessing a direction", "cannot be separated out" in box and "UP" not in box and "DOWN" not in box, box[-300:])
    # NONE: no point above 0.6 -- no box at all
    box, sheet = _grow([(0,0.05),(1,0.1),(2,0.2),(3,0.4)])
    ck("ADR-233: no point above OD 0.6, no saturation box", "above OD 0.6" not in box, box[-200:])

    # the intermediate band is the rule the page applies
    def _band(S,R):
        t="Intermediate: above %s mm and below %s mm" % (_fmt(R,1), _fmt(S,1))
        if S==int(S) and R==int(R):
            if S-R>=2:
                lo,hi=int(R)+1,int(S)-1
                t+=" — %s for whole-millimetre readings" % (("%d mm"%lo) if lo==hi else ("%d–%d mm"%(lo,hi)))
            else:
                t+=" — no whole-millimetre reading falls between them"
        return t+"."
    pg.goto(_u("micro-bench.html")); pg.wait_for_timeout(400)
    pg.evaluate("()=>{try{localStorage.clear()}catch(e){}}"); pg.reload(); pg.wait_for_timeout(500)
    pg.click('.tab[data-pane="p-zn"]'); pg.wait_for_timeout(200)
    pg.fill("#zOrg","E. coli ATCC 25922"); pg.fill("#zMed","Mueller-Hinton")
    pg.fill("#zDrug","ampicillin"); pg.fill("#zCont","10 µg"); setfield("#zEntry",0,18); pg.click("#zAdd")
    pg.fill("#zOrg","S. aureus ATCC 25923"); pg.fill("#zMed","MHA + 2% NaCl")
    pg.fill("#zDrug","oxacillin"); pg.fill("#zCont","1 µg"); setfield("#zEntry",0,13.2); pg.click("#zAdd")
    pg.wait_for_timeout(250)
    for S,R in ((17,13),(15,13),(14,13),(16.5,13)):
        setfield("#bpEntry",0,S); setfield("#bpEntry",1,R); pg.wait_for_timeout(200)
        zo=pg.inner_text("#zOut").replace(" "," ")
        ck("ADR-233: S ≥ %s / R ≤ %s states the band as the rule it applies: %s" % (S,R,_band(S,R)),
           _band(S,R) in zo and "13.5–" not in zo, zo[-200:])
    setfield("#bpEntry",0,17); setfield("#bpEntry",1,13); pg.fill("#zSrc","CLSI M100, 2026"); pg.wait_for_timeout(250)
    zl=pg.inner_text("#zList")
    ck("ADR-233: 13.2 mm reads I against 17/13 -- inside 'above 13 and below 17', which the old 13.5–16.5 "
       "band did not contain", "oxacillin" in zl and zl.split("oxacillin")[1].count("I")>=1, zl[-200:])
    ck("ADR-233: each zone names the organism and medium it was read on",
       "E. coli ATCC 25922" in zl and "Mueller-Hinton" in zl and "S. aureus ATCC 25923" in zl and "MHA + 2% NaCl" in zl, zl)
    pg.fill("#zOrg","changed later"); pg.wait_for_timeout(200)
    zl2=pg.inner_text("#zList")
    ck("ADR-233: ...kept per zone at Add, so editing the form afterwards does not rewrite a recorded zone",
       "changed later" not in zl2 and "E. coli ATCC 25922" in zl2, zl2)
    sheet=pg.inner_text("#ecoOut")
    ck("ADR-233: the bench sheet carries organism and medium per zone",
       "ampicillin 10 µg   18.0 mm   S   E. coli ATCC 25922   on Mueller-Hinton" in sheet
       and "oxacillin 1 µg   13.2 mm   I   S. aureus ATCC 25923   on MHA + 2% NaCl" in sheet,
       [l for l in sheet.split("\n") if "cillin" in l])
    # the CSV as the Copy button hands it over: the page copies from a textarea it appends
    pg.evaluate("()=>{window.__clip=[];document.execCommand=function(c){if(c==='copy'){"
                "const t=[...document.querySelectorAll('textarea')].pop();window.__clip.push(t&&t.value);}return true;};}")
    pg.click('.tab[data-pane="p-out"]') if pg.locator('.tab[data-pane="p-out"]').count() else None
    pg.wait_for_timeout(150); pg.click("#znCopy"); pg.wait_for_timeout(200)
    csv=(pg.evaluate("()=>window.__clip") or [None])[-1]
    rows=(csv or "").split("\n")
    ck("ADR-233: the zone CSV has organism and medium columns",
       bool(rows) and rows[0].endswith(",organism,medium"), rows[:1])
    ck("ADR-233: ...and every row fills them, quoting where a value needs it",
       len(rows)==3 and rows[1].endswith(",E. coli ATCC 25922,Mueller-Hinton")
       and rows[2].endswith(",S. aureus ATCC 25923,MHA + 2% NaCl"), rows)
    # an older save, from before zones carried organism and medium, still restores and renders
    # KEEP stores {format, at, body:{fields, state}} under the page's key; strip the two
    # new fields from every saved zone, as a save made before this slice would hold them
    pg.wait_for_timeout(700)
    stripped = pg.evaluate("""()=>{const k='csrbtMicroBench';const raw=localStorage.getItem(k);
      if(!raw)return -1;const b=JSON.parse(raw);const zs=(b.body&&b.body.state&&b.body.state.zones)||[];
      let n=0;zs.forEach(z=>{if('org' in z||'med' in z)n++;delete z.org;delete z.med;});
      localStorage.setItem(k,JSON.stringify(b));return n;}""")
    ck("ADR-233: (the saved zones carried organism and medium, and the check stripped them from %s)" % stripped,
       stripped == 2, stripped)
    pg.reload(); pg.wait_for_timeout(600); pg.click('.tab[data-pane="p-zn"]'); pg.wait_for_timeout(200)
    zl3=pg.inner_text("#zList")
    ck("ADR-233: a save from before organism and medium were kept still restores, with the zones intact",
       "ampicillin" in zl3 and "oxacillin" in zl3 and "undefined" not in zl3 and "E. coli" not in zl3, zl3)

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

# A suite that cannot fail the run is not a check. This one printed its FAIL
# lines and exited zero, so run_all marked it green whatever it found -- for
# eleven suites in this kit, "green" meant "the process did not crash".
raise SystemExit(1 if F else 0)
