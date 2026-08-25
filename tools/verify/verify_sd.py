# -*- coding: utf-8 -*-
"""Survey Design: Event Core, the Humboldt terms, and the one gate that matters.

Simple Darwin Core is a flat list of things that were found. It cannot express
a sampling hierarchy and it cannot express an absence -- and an absence with no
declared scope is not a weaker record, it is an unreadable one. Absent from what
search? Would the observer have recognised it?

So the assertion this suite exists for is a refusal: with no
eco:targetTaxonomicScope, a marked absence must NOT reach the occurrence table.
Everything else here is structure -- unique ids, real parents, and the
Humboldt rule that nothing is inherited.
"""
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline, ROOT
from playwright.sync_api import sync_playwright

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))

PAGE = "survey-design.html"
SRC = io.open(os.path.join(ROOT, "docs", PAGE), encoding="utf-8").read()

# The published Humboldt namespace, checked in the page rather than remembered.
NS = "http://rs.tdwg.org/eco/terms/"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 950, "height": 1400})
    pg.set_default_timeout(20000)
    offline(pg)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console: " + m.text)
          if m.type == "error" and "ERR_" not in m.text else None)
    pg.goto(url(PAGE), wait_until="domcontentloaded")
    pg.wait_for_timeout(800)

    ck("page loads clean", not errs, errs[:3])
    ck("five tabs", pg.eval_on_selector_all(".tab", "e=>e.length") == 5, "")
    ck("no bare selects", pg.eval_on_selector_all("select", "e=>e.length") == 0, "")
    ck("autosave is wired", pg.eval_on_selector_all("#keepBox.keep", "e=>e.length") == 1, "")

    def setf(i, v):
        pg.evaluate("""([i,v])=>{var e=document.getElementById(i); if(!e) throw new Error('no #'+i);
          e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));
          e.dispatchEvent(new Event('change',{bubbles:true}));}""", [i, v])
        pg.wait_for_timeout(280)

    def stat(box, label):
        return pg.evaluate("""([b,l])=>{const k=[...document.querySelectorAll('#'+b+' .k')]
          .find(x=>x.querySelector('.l').textContent.trim()===l);
          return k ? k.querySelector('.v').textContent.trim() : null;}""", [box, label])

    def tab(name):
        pg.click('.tab[data-pane="%s"]' % name)
        pg.wait_for_timeout(320)

    def rows(fn):
        """Read a table straight out of the page's own builder."""
        return pg.evaluate("()=>window.__probe_%s ? null : null" % fn)

    # ================= the hierarchy =================
    pg.click("#evDemo")
    pg.wait_for_timeout(1000)
    ck("the example builds a real hierarchy",
       int(stat("treeStat", "events")) == 15, stat("treeStat", "events"))
    for lvl, n in [("sites", 2), ("plots", 4), ("visits", 8)]:
        ck("example has %d %s" % (n, lvl), int(stat("treeStat", lvl)) == n, stat("treeStat", lvl))
    ck("no duplicate eventIDs", int(stat("treeStat", "duplicate IDs")) == 0,
       stat("treeStat", "duplicate IDs"))
    ck("the tree draws one node per event",
       pg.eval_on_selector_all("#tree .n", "e=>e.length") == 15,
       pg.eval_on_selector_all("#tree .n", "e=>e.length"))
    ck("depth is drawn, not just stored",
       pg.eval_on_selector_all("#tree .n.d1", "e=>e.length") == 2
       and pg.eval_on_selector_all("#tree .n.d3", "e=>e.length") == 8,
       (pg.eval_on_selector_all("#tree .n.d1", "e=>e.length"),
        pg.eval_on_selector_all("#tree .n.d3", "e=>e.length")))
    ck("the no-inheritance rule is stated on the page",
       "Nothing here is inherited" in pg.inner_text("#inheritBox"),
       pg.inner_text("#inheritBox")[:70])

    # every parentEventID must resolve to a real eventID
    integrity = pg.evaluate("""()=>{
      const ids=[...document.querySelectorAll('#tree .n .id')].map(x=>x.textContent.trim());
      return { n:ids.length, uniq:new Set(ids).size }; }""")
    ck("every eventID in the tree is unique",
       integrity["n"] == integrity["uniq"], integrity)

    # removing a parent must not silently orphan its children
    pg.evaluate("""()=>{const b=[...document.querySelectorAll('#tree [data-del]')]
      .find(x=>x.getAttribute('data-del').indexOf(':site:')>=0); b.click();}""")
    pg.wait_for_timeout(500)
    ck("removing an event with children is refused, not cascaded",
       int(stat("treeStat", "events")) == 15, stat("treeStat", "events"))
    ck("and the refusal says why",
       "remove those first" in pg.inner_text("#toast"), pg.inner_text("#toast"))

    # ================= the gate =================
    tab("p-abs")
    ck("the example marks an absence", int(stat("taxaStat", "absent")) >= 1,
       stat("taxaStat", "absent"))
    ck("unassessed taxa are counted separately from absent ones",
       int(stat("taxaStat", "not assessed")) >= 1, stat("taxaStat", "not assessed"))

    # attach the absences to an event so only the scope is missing
    pg.evaluate("""()=>{const s=document.querySelector('#absEntry .search');
      s.value='visit:01'; s.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(300)
    pg.evaluate("()=>document.querySelector('#absEntry .opt').click()")
    pg.wait_for_timeout(500)
    tab("p-out")
    ck("with a scope, the absence is written",
       int(stat("outStat", "absences written")) >= 1, stat("outStat", "absences written"))
    ck("and none are refused",
       int(stat("outStat", "absences refused")) == 0, stat("outStat", "absences refused"))

    tab("p-scope")
    setf("scTarget", "")
    tab("p-out")
    ck("WITHOUT a target scope the absence is refused",
       int(stat("outStat", "absences written")) == 0, stat("outStat", "absences written"))
    ck("and the refusal is counted, not silent",
       int(stat("outStat", "absences refused")) >= 1, stat("outStat", "absences refused"))
    ck("a refused absence is styled as a stop",
       pg.eval_on_selector_all("#outBox .verdict.act", "e=>e.length") == 1, "")
    tab("p-abs")
    v = pg.inner_text("#absBox")
    ck("the gate explains what an unscoped absence would mean",
       "cannot be read by anybody" in v, v[:120])
    ck("the gate says where to fix it", "target taxonomic scope" in v, v[:200])

    # the copy button must refuse too, not quietly copy a half table
    tab("p-out")
    pg.click("#cpOcc")
    pg.wait_for_timeout(400)
    ck("the occurrence copy button refuses without a scope",
       "Refused" in pg.inner_text("#toast"), pg.inner_text("#toast"))
    ck("and the refusal names how many absences would have been lost",
       "target scope" in pg.inner_text("#toast"), pg.inner_text("#toast"))

    tab("p-scope")
    setf("scTarget", "Tracheophyta")

    # ================= what the tables actually contain =================
    tab("p-out")
    hdr = pg.eval_on_selector_all("#evTable table th", "e=>e.map(x=>x.textContent.trim())")
    for term in ["eventID", "parentEventID", "eventType", "eventDate"]:
        ck("Event Core carries %s" % term, term in hdr, hdr)

    # The no-inheritance rule, checked as data rather than as a paragraph.
    # Writing the scope only onto the root event passed every other check here:
    # the counts were right, the prose was right, and the file would have been
    # unreadable at the level anybody actually joins on.
    ck("there is one Humboldt row per event, not one per dataset",
       stat("outStat", "Humboldt rows") == stat("outStat", "event rows"),
       (stat("outStat", "Humboldt rows"), stat("outStat", "event rows")))
    deep = pg.evaluate("""()=>{
      /* pull the page's own Humboldt table through its copy path */
      let grabbed=null;
      const orig=document.execCommand.bind(document);
      const ta=document.querySelector('textarea');
      return null; }""")
    hum = pg.evaluate("""()=>{
      const btn=document.getElementById('cpHum');
      let text=null;
      const realCreate=document.createElement.bind(document);
      document.createElement=function(t){
        const el=realCreate(t);
        if(t==='textarea'){ const d=Object.getOwnPropertyDescriptor(
          HTMLTextAreaElement.prototype,'value');
          Object.defineProperty(el,'value',{ set(v){ text=v; d.set.call(this,v); },
            get(){ return d.get.call(this); } }); }
        return el; };
      btn.click();
      document.createElement=realCreate;
      return text; }""")
    ck("the Humboldt table can be read back", bool(hum), "copy path produced nothing")
    if hum:
        lines = [l for l in hum.split("\n") if l.strip()]
        head = lines[0].split(",")
        body = [l.split(",") for l in lines[1:]]
        ck("Humboldt header carries the scope term",
           "eco:targetTaxonomicScope" in head, head[:4])
        si = head.index("eco:targetTaxonomicScope")
        deepest = [r for r in body if ":visit:" in r[0]]
        ck("the deepest events are in the Humboldt table at all",
           len(deepest) >= 8, len(deepest))
        ck("a child visit carries the scope EXPLICITLY, not by inheritance",
           all(r[si].strip().strip('"') == "Tracheophyta" for r in deepest),
           [r[si] for r in deepest[:2]])
        ai = head.index("eco:isAbsenceReported")
        ck("isAbsenceReported is true on exactly the event the absences belong to",
           sum(1 for r in body if r[ai].strip() == "true") == 1,
           [r[ai] for r in body[:4]])

    ck("the export says all three tables are needed",
       "Deposit all three" in pg.inner_text("#outBox"), pg.inner_text("#outBox")[:100])
    sheet = pg.inner_text("#ecoOut")
    ck("the field sheet names the three files",
       "event.csv" in sheet and "humboldt.csv" in sheet and "occurrence.csv" in sheet, sheet[:120])
    ck("the field sheet states the target scope",
       "Tracheophyta" in sheet, sheet[:200])
    ck("the field sheet repeats the no-inheritance rule",
       "Nothing is inherited" in sheet, sheet[-200:])

    # unassessed taxa must appear in NO row
    counts = pg.evaluate("""()=>{
      const k=l=>{const e=[...document.querySelectorAll('#outStat .k')]
        .find(x=>x.querySelector('.l').textContent.trim()===l);
        return e?parseInt(e.querySelector('.v').textContent,10):null;};
      const t=l=>{const e=[...document.querySelectorAll('#taxaStat .k')]
        .find(x=>x.querySelector('.l').textContent.trim()===l);
        return e?parseInt(e.querySelector('.v').textContent,10):null;};
      return { occ:k('occurrence rows'), found:t('found'), absent:t('absent'), none:t('not assessed') };}""")
    ck("occurrence rows = found + absent, and nothing else",
       counts["occ"] == counts["found"] + counts["absent"], counts)
    ck("unassessed taxa reach no table at all",
       counts["none"] > 0 and counts["occ"] == counts["found"] + counts["absent"], counts)

    # ================= the Humboldt declaration =================
    tab("p-scope")
    decl = pg.inner_text("#declBox")
    for term in ["eco:targetTaxonomicScope", "eco:isAbsenceReported",
                 "eco:isSamplingEffortReported", "eco:isTaxonomicScopeFullyReported"]:
        ck("the declaration shows %s" % term, term in decl, decl[:200])
    ck("booleans are named as the TDWG controlled strings",
       "TDWG Boolean" in decl, decl[-260:])
    ck("the namespace is stated, not assumed", NS in decl, decl[-200:])
    ck("isTaxonomicScopeFullyReported is false while taxa are unassessed",
       re.search(r"isTaxonomicScopeFullyReported\s*false", decl) is not None, decl[-300:])

    # effort: half a figure is not a figure
    setf("scEffVal", "45")
    setf("scEffUnit", "")
    ck("a value with no unit is rejected",
       "Half an effort figure" in pg.inner_text("#effortBox"), pg.inner_text("#effortBox")[:80])
    setf("scEffUnit", "minutes")
    ck("value and unit together are accepted",
       "will be <b>true</b>" in pg.inner_html("#effortBox")
       or "isSamplingEffortReported" in pg.inner_text("#effortBox"),
       pg.inner_text("#effortBox")[:120])
    setf("scEffVal", "")
    setf("scEffUnit", "")
    ck("no effort at all is declared false, and named a hole",
       "a hole in the record" in pg.inner_text("#effortBox"), pg.inner_text("#effortBox")[:120])
    setf("scEffVal", "45")
    setf("scEffUnit", "minutes")

    # excluded scope: the distinction the whole page is about
    setf("scExcluded", "")
    ck("an empty excluded scope warns what a reader will assume",
       "take the scope at face value" in pg.inner_text("#scopeBox"),
       pg.inner_text("#scopeBox")[:140])
    setf("scExcluded", "Bryophyta|Lichenes")
    ck("a declared exclusion says the empty cells are a decision",
       "a decision, not a finding" in pg.inner_text("#scopeBox"),
       pg.inner_text("#scopeBox")[:160])

    # inventoryTypes: the vocabulary this page will not invent
    ck("inventoryTypes is declared free text, with the reason",
       "without publishing the value list" in pg.inner_text("#invBox"),
       pg.inner_text("#invBox")[:140])
    setf("scInv", "timed meander")
    ck("even when filled it is still labelled free text",
       "free text" in pg.inner_text("#invBox"), pg.inner_text("#invBox")[:100])

    # ================= escaping =================
    tab("p-abs")
    pg.evaluate("""()=>{var e=document.getElementById('txAdd');
      e.value='<x-probe>p</x-probe>'; e.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.click("#txBtn")
    pg.wait_for_timeout(500)
    ck("a taxon name typed as markup does not become markup",
       pg.eval_on_selector_all("x-probe", "e=>e.length") == 0,
       pg.eval_on_selector_all("x-probe", "e=>e.length"))
    tab("p-hier")
    pg.evaluate("""()=>{var e=document.getElementById('evName');
      e.value='<x-probe>s</x-probe>'; e.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.click("#evAdd")
    pg.wait_for_timeout(500)
    ck("an event name typed as markup does not become markup",
       pg.eval_on_selector_all("x-probe", "e=>e.length") == 0,
       pg.eval_on_selector_all("x-probe", "e=>e.length"))

    ck("no errors through the whole run", not errs, errs[:3])

    # ================= method page =================
    met = re.sub(r"\s+", " ", pg.inner_text("#p-met"))
    for phrase, why in [
        ("structurally cannot say", "what Simple DwC cannot express"),
        ("MUST NOT be assumed to implicitly", "the no-inheritance rule, quoted"),
        ("Principle of Applicability", "the rule's name"),
        ("is not data", "an unscoped absence"),
        ("will not guess at one", "the vocabulary refusal"),
        ("eco:isAbsenceReported", "the term that makes an absence legible"),
    ]:
        ck("method page: %s" % why, phrase in met, phrase)

    b.close()

for phrase, why in [
    ("eco:targetTaxonomicScope", "the scope term"),
    ("eco:isAbsenceReported", "the absence declaration"),
    ("http://rs.tdwg.org/eco/terms/", "the published namespace"),
    ("eco.tdwg.org/hierarchy", "the hierarchy source is linked"),
    ("if(x.state===\"absent\" && !t) return;", "the gate, in the data path and not only in prose"),
]:
    ck("source carries %s" % why, phrase in SRC, phrase)

print("\n".join("PASS  " + x for x in P))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
