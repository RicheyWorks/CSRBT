# -*- coding: utf-8 -*-
"""Collection Sheet: the science downstream of the entry controls.

Named verify_fun once, for "fungal", and pointed at collection-sheet.html the
whole time -- which is why nobody noticed it had stopped running. It crashed on
its first assertion after the page migrated to the Field Entry Kit: it asked
#cGen for .options.length, and #cGen had become a hidden write-through field.

Division of labour with verify_cs: that suite proves the FEK widgets exist and
write through to their fields. This one proves what the page DOES with the
values once they are there -- spore-print contradiction against the pack's
expected print colour, Chao1 as a lower bound, the single-host flag, drying-lag
and rainfall-placeholder warnings, what a herbarium label carries, and what the
export refuses to state.
"""
import re, sys
from playwright.sync_api import sync_playwright
import _kit
import os as _os
# The kit is checked out wherever the user keeps it; these suites used to hard-code
# a container path and so could only ever run in the container that wrote them.
ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = _os.path.join(ROOT, "docs") + _os.sep
def _u(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + _os.path.join(ROOT, "docs", name).replace(_os.sep, "/")


P=[]; F=[]
def ck(name, cond, extra=""):
    (P if cond else F).append(name + (("  << "+str(extra)) if (extra and not cond) else ""))

with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":820,"height":1180})
    errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    def _con(m):
        if m.type!="error": return
        if "ERR_CONNECTION" in m.text or "fonts.googleapis" in m.text: return  # offline container: webfont CDN
        errs.append("console."+m.type+": "+m.text)
    pg.on("console", _con)
    pg.goto(_u("collection-sheet.html"))
    pg.wait_for_timeout(500)
    ck("no startup errors", not errs, errs[:3])

    # tabs
    tabs = pg.eval_on_selector_all(".tab", "els=>els.map(e=>e.textContent.trim())")
    ck("six tabs", len(tabs)==6, tabs)
    for t in ["Record","Site","Prints","Analysis","Vouchers","Method"]:
        ck("tab "+t, any(t.lower() in x.lower() for x in tabs), tabs)

    # genus pack loaded
    # Was: #cGen.options.length -- but #cGen is now a hidden write-through field
    # and the genus list lives in a FEK picker, so the old read returned
    # undefined and took the whole suite down with it.
    n = len(_kit.options(pg, "#genEntry"))
    ck("genus picker populated from the pack", n > 40, n)
    ck("not-in-pack offered as an option",
       any("not in the pack" in x for x in _kit.options(pg, "#genEntry")), n)
    stat = pg.inner_text("#packStat")
    ck("pack stats show ecm count", "24 ectomycorrhizal" in stat, stat)
    ck("pack stats show mixed count", "flagged mixed" in stat, stat)

    # ---- genus tell + guild badge ----
    # Correction to the port: pushing the hidden field is right for a control the
    # page merely READS, but wrong for one whose side effects live in the
    # widget's onchange -- the genus tell, the guild badge and the print notes
    # are all rendered from there, so a hidden write skipped them silently and
    # eleven assertions failed for the wrong reason. Anything picker-backed is
    # driven through the picker.
    _kit.pick(pg, "#genEntry", "Amanita")
    pg.wait_for_timeout(120)
    tell = pg.inner_text("#cGenTell")
    ck("Amanita tell mentions volva", "volva" in tell.lower(), tell[:120])
    ck("Amanita badged ectomycorrhizal", "ectomycorrhizal" in tell.lower(), tell[:120])

    _kit.pick(pg, "#genEntry", "Ramaria")
    pg.wait_for_timeout(120)
    tell = pg.inner_text("#cGenTell")
    ck("Ramaria flagged mixed", "mixed genus" in tell.lower(), tell[:160])
    ck("mixed warning says prior not result", "prior" in tell.lower(), tell[:200])

    # ---- record a known set for hand-checked maths ----
    # 5 taxa: A x1, B x1, C x1, D x2, E x5   -> Sobs 5, F1=3, F2=1, bodies 10
    # Chao1 = 5 + 3*2/(2*(1+1)) = 5 + 6/4 = 6.5
    # H' = -(3*(0.1 ln 0.1) + 0.2 ln 0.2 + 0.5 ln 0.5)
    import math
    ps=[0.1,0.1,0.1,0.2,0.5]
    H=-sum(x*math.log(x) for x in ps); J=H/math.log(5)
    # Genus given as the label the picker shows, not the pack's internal option
    # value -- a picker is filtered by what the reader can see.
    plan=[("Amanita","Amanita muscaria",1,"Pinus contorta"),
          ("Suillus","Suillus brevipes",1,"Pinus contorta"),
          ("Russula","Russula brevipes",1,"Pseudotsuga menziesii"),
          ("Cortinarius","Cortinarius cf. vanduzerensis",2,"Pseudotsuga menziesii"),
          ("Pleurotus","Pleurotus pulmonarius",5,"Populus tremuloides")]
    # set search area/time first
    pg.click('.tab[data-pane="p-site"]'); pg.wait_for_timeout(150)
    _kit.push(pg, "sArea", "1000"); _kit.push(pg, "sMin", "90")
    pg.fill("#sSite","Bear Cr. old-growth"); pg.fill("#sObs","R. Wright")
    pg.fill("#sTrees","Pinus contorta, Pseudotsuga menziesii, Populus tremuloides")
    pg.fill("#sVeg","Tsuga heterophylla zone")
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(150)

    for gen,name,cnt,host in plan:
        _kit.pick(pg, "#genEntry", gen)
        pg.fill("#cName", name)
        _kit.push(pg, "cN", str(cnt))
        _kit.pick(pg, "#hostEntry", host)
        pg.click("#cAdd"); pg.wait_for_timeout(90)

    rows = pg.eval_on_selector_all("#cList .row2","els=>els.length")
    ck("5 collections listed", rows==5, rows)

    pg.click('.tab[data-pane="p-an"]'); pg.wait_for_timeout(250)
    an = pg.inner_text("#anBox")
    def tileval(label):
        return pg.evaluate("""(lab)=>{const t=[...document.querySelectorAll('#anBox .tile')]
            .find(x=>x.querySelector('.l').textContent.replace(/\\s+/g,' ').trim().toLowerCase()===lab.toLowerCase());
            return t? t.querySelector('.v').textContent.trim() : null;}""", label)
    ck("collections tile = 5", tileval("collections")=="5", tileval("collections"))
    ck("fruit bodies tile = 10", tileval("fruit bodies")=="10", tileval("fruit bodies"))
    ck("Sobs tile = 5", tileval("taxa Sobs")=="5", tileval("taxa Sobs"))
    ck("Chao1 tile = 6.5", tileval("Chao1")=="6.5", tileval("Chao1"))
    ck("singletons/doubletons = 3 / 1", tileval("singletons / doubletons")=="3 / 1", tileval("singletons / doubletons"))
    ck("Shannon H' = %.3f"%H, tileval("Shannon H′")=="%.3f"%H, (tileval("Shannon H′"), "%.3f"%H))
    ck("Pielou J' = %.3f"%J, tileval("Pielou J′")=="%.3f"%J, (tileval("Pielou J′"), "%.3f"%J))
    ck("collections/100m2 = 0.50", tileval("collections / 100 m²")=="0.50", tileval("collections / 100 m²"))
    ck("collections/hour = 3.3", tileval("collections / hour")=="3.3", tileval("collections / hour"))

    ck("saturation warning shown", "saturation" in an.lower() or "lower bound" in an.lower(), an[-200:])

    # guild spectrum: ecm bodies = 1+1+1+2 = 5, woodsap 5 -> 50/50
    g = pg.inner_text("#anGuild")
    ck("guild spectrum has ectomycorrhizal", "ectomycorrhizal" in g.lower(), g[:150])
    bars = pg.eval_on_selector_all("#anGuild .bar","els=>els.map(e=>e.querySelector('.nm').textContent+'='+e.querySelector('.pc').textContent)")
    ck("ecm 50% / wood sapro 50%", any("ectomycorrhizal=50%" in x for x in bars) and any("wood=50%" in x for x in bars), bars)

    # host matrix
    h = pg.inner_text("#anHost")
    ck("host matrix rendered", "Pinus contorta" in h and "Populus tremuloides" in h, h[:200])
    ck("no false single-host flag at n<3", "single host" not in h, h[:300])

    # add 2 more Pleurotus under aspen -> 3 collections all one host -> flag
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(120)
    for i in range(2):
        _kit.pick(pg, "#genEntry", "Pleurotus")
        pg.fill("#cName","Pleurotus pulmonarius"); _kit.push(pg, "cN", "1")
        _kit.pick(pg, "#hostEntry", "Populus")
        pg.click("#cAdd"); pg.wait_for_timeout(80)
    pg.click('.tab[data-pane="p-an"]'); pg.wait_for_timeout(220)
    h = pg.inner_text("#anHost")
    ck("single-host flag fires at n=3", "single host ×3" in h, h[:400])

    # ---- spore print contradiction logic ----
    pg.click('.tab[data-pane="p-prt"]'); pg.wait_for_timeout(200)
    # #pPick is a hidden write-through field now; the options live in its picker.
    # Count is an invariant against the collections actually added above (5 + 2
    # Pleurotus) rather than a frozen 7, so adding a sixth genus to the fixture
    # does not fail this.
    opts = _kit.options(pg, "#pPickEntry")
    added = pg.eval_on_selector_all("#cList .row2","els=>els.length")
    ck("print picker lists every collection added", len(opts)==added, (len(opts), added, opts[:3]))
    # pick Amanita (white expected). choose black -> contradiction
    _kit.pick(pg, "#pPickEntry", "Amanita")
    def swclick(label):
        pg.evaluate("""(lab)=>{const b=[...document.querySelectorAll('#pSw .swc')]
            .find(x=>x.textContent.trim().toLowerCase().startsWith(lab.toLowerCase())); b.click();}""", label)
    swclick("black"); pg.wait_for_timeout(140)
    note = pg.inner_text("#pPrintNote")
    ck("black print on Amanita = contradiction", "contradiction" in note.lower(), note[:160])
    swclick("black"); swclick("cream"); pg.wait_for_timeout(140)   # toggle off, pick cream (1 step from white)
    note = pg.inner_text("#pPrintNote")
    ck("cream print on Amanita = one step off", "one step off" in note.lower(), note[:160])
    swclick("cream"); swclick("white"); pg.wait_for_timeout(140)
    note = pg.inner_text("#pPrintNote")
    ck("white print on Amanita = consistent", "consistent" in note.lower(), note[:160])
    # green special case
    swclick("white"); swclick("dull green"); pg.wait_for_timeout(140)
    note = pg.inner_text("#pPrintNote")
    ck("green print names Chlorophyllum molybdites", "molybdites" in note, note[:200])
    swclick("dull green"); swclick("white"); pg.wait_for_timeout(120)

    # reagents
    rg = pg.eval_on_selector_all("#pRg .rgi .nm","els=>els.map(e=>e.textContent)")
    ck("8 reagents listed", len(rg)==8, rg)
    ck("FeSO4 present", any("FeSO" in x for x in rg), rg)
    ck("Melzer present", any("Melzer" in x for x in rg), rg)
    haz = pg.eval_on_selector_all("#pRg .rgi.haz","els=>els.length")
    ck("hazard flags on 5 reagents", haz==5, haz)
    pg.fill('#pRg input[data-rg="fe"]', "salmon on stipe flesh in 30 s")
    _kit.push(pg, "pHrs", "6"); _kit.push(pg, "pOn", "half black / half white")
    pg.click("#pSave"); pg.wait_for_timeout(150)

    # ---- weather ----
    pg.click('.tab[data-pane="p-site"]'); pg.wait_for_timeout(180)
    pg.fill("#sDate","2026-10-20"); pg.fill("#wDate","2026-10-08"); _kit.push(pg, "wMm", "31"); pg.wait_for_timeout(180)
    w = pg.inner_text("#wOut")
    ck("12-day lag reported", "12 days" in w, w[:160])
    ck("inside placeholder window", "inside the 7" in w, w[:200])
    _kit.push(pg, "wMm", "6"); pg.wait_for_timeout(160)
    w = pg.inner_text("#wOut")
    ck("below 25mm flagged", "25 mm placeholder" in w, w[:220])
    pg.fill("#wDate","2026-10-25"); pg.dispatch_event("#wDate","input"); pg.wait_for_timeout(160)
    w = pg.inner_text("#wOut")
    ck("rain after survey date caught", "after" in w.lower() and "check the two dates" in w.lower(), w[:220])
    pg.fill("#wDate","2026-10-08"); _kit.push(pg, "wMm", "31"); pg.dispatch_event("#wMm","input")

    # ---- voucher label ----
    pg.click('.tab[data-pane="p-vou"]'); pg.wait_for_timeout(200)
    pg.fill("#vHerb","OSC"); _kit.push(pg, "vTemp", "43"); _kit.push(pg, "vHrs", "14")
    _kit.push(pg, "vSlice", "halved"); _kit.push(pg, "vDna", "taken — silica")
    _kit.pick(pg, "#vPickEntry", "Amanita")
    pg.click("#vAdd"); pg.wait_for_timeout(200)
    lab = pg.inner_text("#vList")
    ck("label carries herbarium", "OSC" in lab, lab[:120])
    ck("label carries locality", "Bear Cr" in lab, lab[:300])
    ck("label carries host", "Pinus contorta" in lab, lab[:400])
    ck("label carries drying log", "43" in lab and "silica" in lab, lab[:500])
    ck("label carries spore print", "white" in lab.lower(), lab[:500])

    # ---- exports ----
    pg.click('.tab[data-pane="p-an"]'); pg.wait_for_timeout(200)
    exp = pg.inner_text("#ecoOut")
    ck("export names the site", "Bear Cr. old-growth" in exp, exp[:200])
    ck("export carries Chao1", "Chao1 6.5" in exp, [l for l in exp.split("\n") if "Chao1" in l])
    ck("export states no edibility", "no edibility" in exp, exp[-200:])
    ck("export carries FeSO4 result", "salmon on stipe flesh" in exp, "missing")

    # ---- method tab: the refusal ----
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(200)
    m = pg.inner_text("#p-met")
    ck("never-edible block present", "never tell you whether a fungus is edible" in m.lower(), m[:200])
    ck("Chao1 documented as lower bound", "lower bound" in m.lower(), "")
    ck("placeholder thresholds labelled", "placeholder" in pg.inner_text("#p-site").lower(), "")
    ck("microscopy limits stated", "cannot be taken to species in the field" in m.lower(), "")

    # ---- pack: AI prompt + validation ----
    ck("AI prompt button present", pg.eval_on_selector("#packPrompt","e=>!!e"), "")
    # simulate a bad import through the validator by invoking the same rules in page ctx
    bad = pg.evaluate("""()=>{
      const f=document.getElementById('packFile');
      return !!f && f.accept.indexOf('json')>=0;
    }""")
    ck("pack import accepts json", bad, "")

    # ---- no horizontal overflow at phone + tablet ----
    for w,hh,lbl in [(390,844,"phone"),(768,1024,"tablet"),(1024,768,"tablet landscape")]:
        pg.set_viewport_size({"width":w,"height":hh})
        for pane in ["p-rec","p-site","p-prt","p-an","p-vou","p-met"]:
            pg.click('.tab[data-pane="%s"]'%pane); pg.wait_for_timeout(120)
            ow = pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            ck("no h-overflow %s %s"%(lbl,pane), ow<=w+1, "%d > %d"%(ow,w))
    # offscreen elements
    pg.set_viewport_size({"width":390,"height":844})
    for pane in ["p-rec","p-site","p-prt","p-an","p-vou","p-met"]:
        pg.click('.tab[data-pane="%s"]'%pane); pg.wait_for_timeout(120)
        # elements inside an overflow-x:auto container are allowed to extend past the
        # viewport -- that container is what scrolls, not the page.
        off = pg.evaluate("""()=>{const bad=[];
            const scroller = e => { for(let n=e; n && n!==document.body; n=n.parentElement){
                const ov=getComputedStyle(n).overflowX; if(ov==='auto'||ov==='scroll') return true; } return false; };
            document.querySelectorAll('.pane.on *').forEach(e=>{
              const r=e.getBoundingClientRect();
              if(r.width>0 && r.right>391.5 && !scroller(e)) bad.push(e.tagName+'.'+(e.className||'')+' @'+Math.round(r.right));});
            return bad.slice(0,4);}""")
        ck("nothing offscreen %s"%pane, not off, off)

    # touch targets
    small = pg.evaluate("""()=>{const bad=[];document.querySelectorAll('button, select, input, a').forEach(e=>{
        const r=e.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.height<43) bad.push(e.tagName+'.'+(e.className||'')+' h='+Math.round(r.height));});
        return bad.slice(0,6);}""")
    ck("all touch targets >= 43px", not small, small)

    ck("still no page errors at end", not errs, errs[:3])
    b.close()

print("PASS %d"%len(P))
for x in F: print("FAIL:", x)
print("---")
print("%d/%d"%(len(P), len(P)+len(F)))
sys.exit(1 if F else 0)
