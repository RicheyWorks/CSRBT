# -*- coding: utf-8 -*-
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
    pg.goto(_u("cp-characters.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(500)
    ck("no startup errors", not errs, errs[:3])
    ck("title set", "CP Characters" in pg.title(), pg.title())

    # ---- layout: content is contained, not full bleed ----
    w=pg.evaluate("()=>{const e=document.querySelector('.wrap'); return e?e.getBoundingClientRect().width:null;}")
    ck("wrap constrains width to 900", w is not None and abs(w-900)<1, w)
    ck("9 sections", pg.eval_on_selector_all("section","e=>e.length")==9,
       pg.eval_on_selector_all("section","e=>e.length"))
    toc=pg.eval_on_selector_all(".toc li a","e=>e.map(a=>a.getAttribute('href'))")
    ids=pg.eval_on_selector_all("section","e=>e.map(s=>'#'+s.id)")
    ck("every TOC link resolves to a section", set(toc)==set(ids), (sorted(toc),sorted(ids)))

    # ---- section one: the criterion ----
    s1=pg.inner_text("#criterion").replace(" "," ")
    for t in ["Attract","Capture","Kill","Digest","Absorb","Roridula","Pameridea","70%",
              "Triphyophyllum","Philcoxia","Brocchinia","Ibicella"]:
        ck("criterion covers "+t, t in s1, s1[:150])
    ck("resin vs mucilage distinction made", "resin" in s1 and "mucilage" in s1.lower(), "")
    ck("the disputed step is named", "fails step 4" in s1, "")
    ck("step 5 named as the one that makes it pay", "fail step 5" in s1, "")

    # ---- section two: five traps, all drawn ----
    ck("5 trap cards", pg.eval_on_selector_all(".tr","e=>e.length")==5,
       pg.eval_on_selector_all(".tr","e=>e.length"))
    ck("every trap card has an SVG", pg.eval_on_selector_all(".tr svg","e=>e.length")==5, "")
    labs=pg.eval_on_selector_all(".tr svg","e=>e.map(s=>s.getAttribute('aria-label'))")
    ck("every trap SVG is labelled", all(l and len(l)>20 for l in labs), labs)
    s2=pg.inner_text("#traps")
    for t in ["Pitfall","Flypaper","Snap trap","Suction","Lobster-pot"]:
        ck("trap named: "+t, t in s2, "")
    ck("trap type is not a rank", "Trap type is not a taxonomic rank" in s2, "")

    # ---- section three: anatomy drawn ----
    ck("8 anatomy glyphs", pg.eval_on_selector_all(".an","e=>e.length")==8,
       pg.eval_on_selector_all(".an","e=>e.length"))
    ck("every anatomy glyph has an SVG", pg.eval_on_selector_all(".an svg","e=>e.length")==8, "")
    alabs=pg.eval_on_selector_all(".an svg","e=>e.map(s=>s.getAttribute('aria-label'))")
    ck("every anatomy SVG is labelled", all(l and len(l)>15 for l in alabs), alabs)
    s3=pg.inner_text("#anatomy")
    for t in ["Peristome","Operculum","Ala","Areoles","Tendril","Phyllodia","Waxy","Nectar spoon"]:
        ck("anatomy names "+t, t in s3, "")

    # ---- section five: every measured number carries a source ----
    s5=pg.inner_text("#timing").replace(" "," ")
    for t in ["100–300 ms","16–44 h","~7 days","0.5 ms","6.4 ms","1.5 m s","0.12–0.14 bar","37,000"]:
        ck("timing states "+t, t in s5, s5[:200])
    ck("two touches within ~30 s", "2 touches within ~30 s" in s5, s5[:200])
    ck("five signals switch on enzymes", "5 or more" in s5, "")
    srcs=pg.eval_on_selector_all("#timing .src","e=>e.map(x=>x.textContent.trim())")
    ck("every timing row names a source", len(srcs)>=13 and all(s for s in srcs), (len(srcs),srcs[:3]))
    ck("Bohm cited", any("Böhm" in s for s in srcs), srcs)
    ck("Poppinga cited", any("Poppinga" in s for s in srcs), srcs)
    ck("dormancy numbers explicitly refused", "no citable source" in s5, s5[-400:])
    ck("refusal links ADR-031",
       pg.eval_on_selector_all('#timing a[href*="adr-031"]',"e=>e.length")>=1, "")
    ck("the fact of dormancy still ships", "does ship" in s5, "")

    # ---- section six: the key ----
    ck("4 key questions", pg.eval_on_selector_all(".kq","e=>e.length")==4, "")
    ck("5 trap options", pg.eval_on_selector_all("#qTrap .kopt","e=>e.length")==5, "")
    ck("6 regions", pg.eval_on_selector_all("#qReg .kopt","e=>e.length")==6, "")
    ck("key starts empty", "candidates appear here" in pg.inner_text("#kRes"), pg.inner_text("#kRes")[:100])

    def click(host, text):
        pg.evaluate("""([h,t])=>{const b=[...document.querySelectorAll(h+' .kopt')]
          .find(x=>x.textContent.indexOf(t)>=0); if(!b) throw new Error('no option '+t); b.click();}""",[host,text])
        pg.wait_for_timeout(150)

    # snap trap + free floating -> Aldrovanda alone
    click("#qTrap","two lobes that clap shut")
    res=pg.inner_text("#kRes")
    ck("snap trap gives exactly 2 genera",
       pg.eval_on_selector_all("#kRes .cand:not(.part)","e=>e.length")==2,
       pg.eval_on_selector_all("#kRes .cand .ch b","e=>e.map(x=>x.textContent)"))
    ck("Dionaea offered", "Dionaea" in res, res[:200])
    ck("Aldrovanda offered", "Aldrovanda" in res, res[:200])
    click("#qHabit","free-floating in open water")
    names=pg.eval_on_selector_all("#kRes .cand:not(.part) .ch b","e=>e.map(x=>x.textContent)")
    ck("snap + open water resolves to Aldrovanda alone", names==["Aldrovanda"], names)
    ck("Dionaea now shown as a partial match",
       "Dionaea" in pg.eval_on_selector_all("#kRes .cand.part .ch b","e=>e.map(x=>x.textContent)"),
       pg.eval_on_selector_all("#kRes .cand.part .ch b","e=>e.map(x=>x.textContent)"))
    ck("partial match says what disagrees", "Disagrees on" in pg.inner_text("#kRes"), "")

    # a contradiction is reported honestly
    pg.click("#kReset"); pg.wait_for_timeout(200)
    click("#qTrap","small bladders on stolons or among leaves")
    click("#qHabit","the trap itself is underground")
    ck("a combination no genus satisfies is named as such",
       "No genus matches all of that" in pg.inner_text("#kRes"),
       pg.inner_text("#kRes")[:200])
    ck("and suggests the commonest error", "where it grows" in pg.inner_text("#kRes"), "")
    ck("but still ranks the near misses",
       pg.eval_on_selector_all("#kRes .cand.part","e=>e.length")>=1, "")
    ck("no full matches are claimed",
       pg.eval_on_selector_all("#kRes .cand:not(.part)","e=>e.length")==0,
       pg.eval_on_selector_all("#kRes .cand:not(.part) .ch b","e=>e.map(x=>x.textContent)"))

    pg.click("#kReset"); pg.wait_for_timeout(200)
    click("#qTrap","a pitcher or tube you could pour water into")
    click("#qReg","North America")
    names=pg.eval_on_selector_all("#kRes .cand:not(.part) .ch b","e=>e.map(x=>x.textContent)")
    ck("N American pitchers: Sarracenia, Darlingtonia, Catopsis",
       set(names)=={"Sarracenia","Darlingtonia","Catopsis"}, names)
    ck("key answers genus not species", "never \"which species\"" in pg.inner_text("#key"),
       pg.inner_text("#key")[-300:])
    pg.click("#kReset"); pg.wait_for_timeout(200)

    # ---- section seven: genus cards ----
    ck("18 genus cards", pg.eval_on_selector_all(".gn","e=>e.length")==18,
       pg.eval_on_selector_all(".gn","e=>e.length"))
    ck("3 boundary cases flagged", pg.eval_on_selector_all(".gn.proto","e=>e.length")==3,
       pg.eval_on_selector_all(".gn.proto .gh b","e=>e.map(x=>x.textContent)"))
    protos=set(pg.eval_on_selector_all(".gn.proto .gh b","e=>e.map(x=>x.textContent)"))
    ck("the right three are flagged", protos=={"Roridula","Triphyophyllum","Philcoxia"}, protos)
    gnames=pg.eval_on_selector_all(".gn .gh b","e=>e.map(x=>x.textContent)")
    ck("cards are alphabetical", gnames==sorted(gnames), gnames)
    ck("18 distinct genera", len(set(gnames))==18, len(set(gnames)))
    ck("every card has a tell", pg.eval_on_selector_all(".gn .tl","e=>e.length")==18, "")
    ck("every card names a family",
       all("aceae" in x for x in pg.eval_on_selector_all(".gn .gh span","e=>e.map(y=>y.textContent)")),
       pg.eval_on_selector_all(".gn .gh span","e=>e.map(y=>y.textContent)")[:3])

    # ---- section eight: confusions carry a cost ----
    ck("6 confusion cards", pg.eval_on_selector_all(".cf","e=>e.length")==6,
       pg.eval_on_selector_all(".cf","e=>e.length"))
    ck("every confusion states what it costs",
       pg.eval_on_selector_all(".cf .cost","e=>e.length")==6, "")
    ck("every confusion says how to separate them",
       pg.eval_on_selector_all(".cf .sep","e=>e.length")==6, "")
    s8=pg.inner_text("#confuse")
    ck("Nepenthes dimorphism is one plant", "one plant" in s8, "")
    ck("sticky is not carnivorous", "Sticky is step 2" in s8, "")

    # ---- section nine: CITES, exactly ----
    s9=pg.inner_text("#legal")
    for t in ["oreophila","jonesii","alabamensis","rajah","khasiana","Dionaea muscipula","#4 annotation"]:
        ck("CITES section names "+t, t in s9, s9[:200])
    ck("Appendix I and II distinguished", "Appendix I" in s9 and "Appendix II" in s9, "")
    ck("listings called a starting point, not a substitute",
       "not\na substitute" in s9 or "not a substitute" in s9, s9[-400:])
    ck("do-not-collect stated", "Do not collect wild carnivorous plants" in s9, "")
    ck("provenance checklist present", pg.eval_on_selector_all("#legal .chk li","e=>e.length")>=5,
       pg.eval_on_selector_all("#legal .chk li","e=>e.length"))
    ck("unknown provenance allowed", "say unknown" in s9, "")
    ck("points at CP Bench", pg.eval_on_selector_all('#legal a[href="cp-bench.html"]',"e=>e.length")>=1, "")

    # ---- footer sources ----
    f=pg.inner_text("footer")
    for t in ["Böhm","Poppinga","Current Biology","AoB PLANTS","Frontiers in Plant Science","Rice"]:
        ck("footer credits "+t, t in f, f[:200])
    ck("footer restates the refusal", "says so rather than filling the gap" in f, "")

    # ---- nav wiring ----
    ck("nav marks this page current",
       pg.eval_on_selector_all('.kit-nav a[aria-current="page"]',"e=>e.map(a=>a.getAttribute('href'))")==["cp-characters.html"],
       pg.eval_on_selector_all('.kit-nav a[aria-current="page"]',"e=>e.map(a=>a.getAttribute('href'))"))
    ck("links to both sibling cards",
       pg.eval_on_selector_all('a[href="plant-characters.html"]',"e=>e.length")>=1 and
       pg.eval_on_selector_all('a[href="fungal-characters.html"]',"e=>e.length")>=1, "")

    # ---- responsive: no horizontal overflow ----
    for w in (390,768,1000):
        pg.set_viewport_size({"width":w,"height":1000})
        pg.wait_for_timeout(200)
        over=pg.evaluate("""(w)=>{const bad=[];
          document.querySelectorAll('body *').forEach(e=>{
            const r=e.getBoundingClientRect();
            if(r.width>0&&r.right>w+1){
              let p=e.parentElement,scroll=false;
              while(p){const s=getComputedStyle(p);
                if(s.overflowX==='auto'||s.overflowX==='scroll'){scroll=true;break;} p=p.parentElement;}
              if(!scroll) bad.push(e.tagName+'.'+e.className);}});
          return bad.slice(0,4);}""",w)
        ck("no overflow @%d"%w, not over, over)
        ck("body does not scroll sideways @%d"%w,
           pg.evaluate("()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"),
           pg.evaluate("()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]"))
    pg.set_viewport_size({"width":390,"height":900})
    small=pg.evaluate("""()=>{const bad=[];
      document.querySelectorAll('.kopt,.kbtn').forEach(e=>{
        const r=e.getBoundingClientRect(); if(r.width>0&&r.height<44) bad.push(e.className+':'+r.height);});
      return bad.slice(0,4);}""")
    ck("key targets >= 44px @390", not small, small)

    # ---- the sibling card's layout bug is fixed too ----
    pg.set_viewport_size({"width":1000,"height":1300})
    pg.goto(_u("fungal-characters.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(400)
    fw=pg.evaluate("()=>{const e=document.querySelector('.wrap'); return e?e.getBoundingClientRect().width:null;}")
    ck("fungal-characters now has its wrap", fw is not None and abs(fw-900)<1, fw)
    ck("fungal-characters nav links to the new card",
       pg.eval_on_selector_all('.kit-nav a[href="cp-characters.html"]',"e=>e.length")>=1,
       pg.eval_on_selector_all('.kit-nav a',"e=>e.map(a=>a.getAttribute('href'))"))

    ck("no errors after the whole run", not errs, errs[:4])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))

# A suite that cannot fail the run is not a check. This one printed its FAIL
# lines and exited zero, so run_all marked it green whatever it found -- for
# eleven suites in this kit, "green" meant "the process did not crash".
raise SystemExit(1 if F else 0)
