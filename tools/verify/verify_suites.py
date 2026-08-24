# -*- coding: utf-8 -*-
import os, re
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

SUITES=["cp-suite.html","soil-suite.html","breeding-suite.html"]
DOCS=DOCS_DIR

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1000,"height":1300})
    pg.set_default_timeout(15000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    def _con(m):
        if m.type!="error": return
        if "ERR_CONNECTION" in m.text or "ERR_FAILED" in m.text: return
        errs.append(m.text)
    pg.on("console",_con)

    for s in SUITES:
        errs.clear()
        pg.goto("file://"+DOCS+s, wait_until="domcontentloaded"); pg.wait_for_timeout(350)
        tag=s.replace("-suite.html","")
        ck("%s: no errors"%tag, not errs, errs[:2])
        ck("%s: wrap constrains layout"%tag,
           abs(pg.evaluate("()=>document.querySelector('.wrap').getBoundingClientRect().width")-1000+2*0)>0, "")
        ck("%s: 3 sections"%tag, pg.eval_on_selector_all("section","e=>e.length")==3,
           pg.eval_on_selector_all("section","e=>e.map(x=>x.id)"))
        ck("%s: sections are start/instruments/honesty"%tag,
           pg.eval_on_selector_all("section","e=>e.map(x=>x.id)")==["start","instruments","honesty"],
           pg.eval_on_selector_all("section","e=>e.map(x=>x.id)"))

        # nav: five chips, this page current, siblings reachable
        hrefs=pg.eval_on_selector_all(".kit-nav a","e=>e.map(a=>a.getAttribute('href'))")
        ck("%s: nav has 5 chips"%tag, len(hrefs)==5, hrefs)
        ck("%s: nav marks itself current"%tag,
           pg.eval_on_selector_all('.kit-nav a[aria-current="page"]',"e=>e.map(a=>a.getAttribute('href'))")==[s],
           pg.eval_on_selector_all('.kit-nav a[aria-current="page"]',"e=>e.map(a=>a.getAttribute('href'))"))
        for o in SUITES:
            ck("%s: nav reaches %s"%(tag,o), o in hrefs, hrefs)
        ck("%s: nav reaches the kit hub"%tag, "ecology.html" in hrefs, hrefs)
        ck("%s: nav reaches the ADR"%tag, "adr-031.html" in hrefs, hrefs)

        # the numbered path
        steps=pg.eval_on_selector_all(".st","e=>e.length")
        ck("%s: path has 5 or 6 steps"%tag, 5<=steps<=6, steps)
        ck("%s: every step links somewhere"%tag,
           pg.eval_on_selector_all(".st .to","e=>e.length")==steps, "")
        # numbering is a CSS counter; assert the mechanism and that each marker renders
        css=open(DOCS+s,encoding="utf-8").read()
        ck("%s: path resets the counter"%tag, "counter-reset: st" in css, "")
        ck("%s: each step increments it"%tag, "counter-increment: st" in css, "")
        ck("%s: each step renders a marker box"%tag,
           pg.evaluate("""()=>[...document.querySelectorAll('.st')].every(x=>{
             const b=getComputedStyle(x,'::before');
             return b.content && b.content!=='none' && parseFloat(b.width)>=20;})"""),
           pg.evaluate("()=>getComputedStyle(document.querySelector('.st'),'::before').width"))
        ck("%s: steps are ordered top to bottom"%tag,
           pg.evaluate("""()=>{const t=[...document.querySelectorAll('.st')].map(x=>x.getBoundingClientRect().top);
             return t.every((v,i)=>i===0||v>t[i-1]);}"""), "")

        # instruments
        cards=pg.eval_on_selector_all("#instruments .card","e=>e.length")
        ck("%s: 2 or more instrument cards"%tag, cards>=2, cards)
        ck("%s: every card has a step, title and cta"%tag,
           pg.eval_on_selector_all("#instruments .card .step","e=>e.length")==cards and
           pg.eval_on_selector_all("#instruments .card h3","e=>e.length")==cards and
           pg.eval_on_selector_all("#instruments .card .go","e=>e.length")==cards, "")

        # honesty: ships and refusals, and at least one of each
        sh=pg.eval_on_selector_all("#honesty .sh","e=>e.length")
        no=pg.eval_on_selector_all("#honesty .sh.no","e=>e.length")
        ck("%s: 6 honesty tiles"%tag, sh==6, sh)
        ck("%s: at least one refusal marked"%tag, no>=1, no)
        ck("%s: at least one thing shipped"%tag, sh-no>=3, (sh,no))
        ck("%s: refusal panel present"%tag, pg.eval_on_selector_all(".refuse","e=>e.length")==1, "")
        ck("%s: refusal panel links the ADR"%tag,
           pg.eval_on_selector_all('.refuse a[href="adr-031.html"]',"e=>e.length")>=1, "")
        ck("%s: gate named in the refusal panel"%tag,
           "gate" in pg.inner_text(".refuse"), pg.inner_text(".refuse")[-200:])

        # every internal link resolves to a real file
        links=set(pg.eval_on_selector_all("a","e=>e.map(a=>a.getAttribute('href'))"))
        missing=[l for l in links if l and not l.startswith("http") and not l.startswith("#")
                 and not os.path.exists(DOCS+l.split("#")[0])]
        ck("%s: every link resolves to a file"%tag, not missing, missing)

        # footer wiring
        f=pg.inner_text("footer")
        ck("%s: footer names the kit"%tag, "CSRBT science kit" in f, f[:120])
        ck("%s: footer links both siblings"%tag,
           sum(1 for o in SUITES if o!=s and
               pg.eval_on_selector_all('footer a[href="%s"]'%o,"e=>e.length")>=1)==2,
           pg.eval_on_selector_all("footer a","e=>e.map(a=>a.getAttribute('href'))"))

        # responsive
        for w in (390,768,1000):
            pg.set_viewport_size({"width":w,"height":1000}); pg.wait_for_timeout(180)
            over=pg.evaluate("""(w)=>{const bad=[];
              document.querySelectorAll('body *').forEach(e=>{
                const r=e.getBoundingClientRect();
                if(r.width>0&&r.right>w+1){
                  let p=e.parentElement,scroll=false;
                  while(p){const st=getComputedStyle(p);
                    if(st.overflowX==='auto'||st.overflowX==='scroll'){scroll=true;break;} p=p.parentElement;}
                  if(!scroll) bad.push(e.tagName+'.'+e.className);}});
              return bad.slice(0,3);}""",w)
            ck("%s: no overflow @%d"%(tag,w), not over, over)
        pg.set_viewport_size({"width":1000,"height":1300})

    # ---- suite-specific content, so these are not three copies of a template ----
    pg.goto("file://"+DOCS+"cp-suite.html", wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    t=pg.inner_text("body").replace(" "," ")
    ck("cp: water comes first", t.index("Fix the water")<t.index("Mix a medium"), "")
    ck("cp: tray accumulation explained", "as one watering at 500" in t, "")
    ck("cp: dormancy refused twice", t.count("Dormancy")>=2 and "No per-genus number" in t, "")
    ck("cp: the fact of dormancy still ships", "does ship" in t, "")
    ck("cp: provenance reasoned from poaching", "heavily poached" in t, "")
    ck("cp: links the card and the bench",
       pg.eval_on_selector_all('a[href="cp-characters.html"]',"e=>e.length")>=1 and
       pg.eval_on_selector_all('a[href="cp-bench.html"]',"e=>e.length")>=1, "")

    pg.goto("file://"+DOCS+"soil-suite.html", wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    t=pg.inner_text("body").replace(" "," ")
    ck("soil: C:N before the pile", t.index("C:N right")<t.index("Log the pile"), "")
    ck("soil: 40 CFR 503 cited", "40 CFR 503" in t, "")
    ck("soil: dry mass reasoning given", "bulk density varies eight-fold" in t, "")
    ck("soil: averaging mistake named", "averaging the individual ratios" in t, "")
    ck("soil: maturity vs pathogen distinction drawn",
       "pathogen criterion, not a maturity criterion" in t, t[-500:])
    ck("soil: indices called ranks", "ordinal" in t and "rank" in t.lower(), "")
    ck("soil: reaches the field instruments",
       pg.eval_on_selector_all('a[href="stand-sheet.html"]',"e=>e.length")>=1 and
       pg.eval_on_selector_all('a[href="releve.html"]',"e=>e.length")>=1, "")

    pg.goto("file://"+DOCS+"breeding-suite.html", wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    t=pg.inner_text("body").replace(" "," ")
    ck("breeding: population before selection", t.index("how many plants")<t.index("Select, and see"), "")
    ck("breeding: 20/100 rule stated", "20 for an inbreeder, 100 for an outbreeder" in t, "")
    ck("breeding: the two halves fail differently", "fail differently" in t, "")
    ck("breeding: species traps shipped", "one species" in t and "Queen Anne" in t, "")
    ck("breeding: isolation refused with the exception named", "NMSU H-262" in t, "")
    ck("breeding: h2 labelled an assumption", "assumption rather than a measurement" in t, "")
    ck("breeding: the trade-off is named not resolved",
       "Naming a trade-off honestly is worth more than resolving it dishonestly" in t, t[-400:])
    ck("breeding: borrows the selection engine",
       pg.eval_on_selector_all('a[href="selection-log.html"]',"e=>e.length")>=1, "")

    # ---- the three are genuinely different documents ----
    bodies={}
    for s in SUITES:
        pg.goto("file://"+DOCS+s, wait_until="domcontentloaded"); pg.wait_for_timeout(250)
        bodies[s]=pg.inner_text("#start")+pg.inner_text("#honesty")
    pairs=[("cp-suite.html","soil-suite.html"),("cp-suite.html","breeding-suite.html"),
           ("soil-suite.html","breeding-suite.html")]
    for a,c in pairs:
        A=set(bodies[a].split()); C=set(bodies[c].split())
        jac=len(A&C)/float(len(A|C))
        ck("content differs: %s vs %s (overlap %.0f%%)"%(a[:4],c[:4],100*jac), jac<0.35, round(jac,3))

    # ---- the kit hub reaches all three ----
    pg.goto("file://"+DOCS+"ecology.html", wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    for x in SUITES:
        ck("kit hub links %s"%x, pg.eval_on_selector_all('a[href="%s"]'%x,"e=>e.length")>=1,
           pg.eval_on_selector_all('#suites a',"e=>e.map(a=>a.getAttribute('href'))"))
    ck("kit hub suite cards lead to the suites, not straight to the benches",
       sorted(pg.eval_on_selector_all('#suites .card',"e=>e.map(a=>a.getAttribute('href'))"))==
       sorted(SUITES),
       pg.eval_on_selector_all('#suites .card',"e=>e.map(a=>a.getAttribute('href'))"))
    ck("the benches are still reachable from the bench group",
       all(pg.eval_on_selector_all('#field-tools a[href="%s"]'%bn,"e=>e.length")>=1
           for bn in ["cp-bench.html","soil-bench.html","breeding-bench.html"]),
       pg.eval_on_selector_all('#field-tools a[href*="bench"]',"e=>e.map(a=>a.getAttribute('href'))"))

    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
