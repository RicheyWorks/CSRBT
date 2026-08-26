# -*- coding: utf-8 -*-
"""Local autosave: does it save, does it come back, and does it lie.

The last question is the one that matters. Before KEEP, one page in the kit
saved anything and it did so with a bare `try{ setItem }catch(e){}` -- a full
quota, a private window and storage disabled by policy all produced silence,
and a user who had watched the page work for an hour had every reason to
believe their data was safe. A save layer that fails quietly is worse than none,
because it teaches trust it has not earned.

So the checks here are in three groups: it saves, it restores (the widget as
well as the value underneath it), and it says so out loud when it cannot.
"""
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline, ROOT, TOOLS_DIR
from playwright.sync_api import sync_playwright

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))

def ver(mod):
    src = io.open(os.path.join(TOOLS_DIR, mod), encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([\d.]+)"', src, re.M)
    return m.group(1) if m else None

KEEPV, FEKV = ver("keep.py"), ver("fek.py")
CONSUMERS = {
    "ordination.html":       "csrbtOrdination",
    "releve.html":           "csrbtReleve",
    "stand-sheet.html":      "csrbtStandSheet",
    "collection-sheet.html": "csrbtCollectionSheet",
    # Retrofitted: this page had the silent try/catch that KEEP exists to replace.
    "pheno-tracker.html":    "phenoTrackerRun1",
}

ck("tools/keep.py declares a version", bool(KEEPV), KEEPV)
ck("FEK is at or past the field registry (1.3.0)", FEKV >= "1.3.0", FEKV)

# Kit-wide, and static: a component that writes through to a hidden field must
# declare that field, or nothing can ever put a restored value back into it.
# Pages that keep their state in an object instead of hidden fields (Pheno
# Tracker does) register nothing and need to -- so the rule is conditional on
# the page actually using the write-through pattern, not on a count.
import glob
_CALL = re.compile(r"FEK\.(?:dial|chips|step|slider|tiles|picker|field)\(\{")
for _p in sorted(glob.glob(os.path.join(ROOT, "docs", "*.html"))):
    _src = io.open(_p, encoding="utf-8").read()
    if "Field Entry Kit" not in _src:
        continue
    _lines, _i, _missing = _src.split("\n"), 0, []
    while _i < len(_lines):
        if not _CALL.search(_lines[_i]):
            _i += 1; continue
        _j, _d = _i, 0
        while _j < len(_lines):
            _d += _lines[_j].count("{") - _lines[_j].count("}")
            if _d <= 0 and _j > _i:
                break
            _j += 1
        _blk = "\n".join(_lines[_i:_j+1])
        _ids = set(re.findall(r'push\("([A-Za-z0-9_]+)"', _blk))
        if len(_ids) == 1 and "field:" not in _blk:
            _missing.append(list(_ids)[0])
        _i = _j + 1
    ck("%s: every write-through component declares its field"
       % os.path.basename(_p), not _missing, _missing[:4])

SET = """([i,v])=>{var e=document.getElementById(i); if(!e) throw new Error('no #'+i);
  e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));
  e.dispatchEvent(new Event('change',{bubbles:true}));}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context()

    def page(name):
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        offline(pg)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url(name), wait_until="domcontentloaded")
        pg.wait_for_timeout(900)
        return pg, errs

    # ---------------- every consumer carries the same layer ----------------
    for name, key in CONSUMERS.items():
        pg, errs = page(name)
        ck("%s loads clean" % name, not errs, errs[:2])
        ck("%s carries KEEP" % name, pg.evaluate("()=>typeof KEEP!=='undefined'"), "")
        ck("%s KEEP version matches keep.py" % name,
           pg.evaluate("()=>KEEP.version") == KEEPV, pg.evaluate("()=>KEEP.version"))
        ck("%s mounts the status strip" % name,
           pg.eval_on_selector_all("#keepBox.keep", "e=>e.length") == 1, "")
        ck("%s offers a way to remove the saved copy" % name,
           pg.eval_on_selector_all("#keepBox [data-keep-forget]", "e=>e.length") == 1, "")
        ck("%s says browser storage is not a backup" % name,
           "not a backup" in pg.inner_text("#keepBox"), pg.inner_text("#keepBox")[:60])

        ck("%s saves nothing before anything is entered" % name,
           pg.evaluate("(k)=>localStorage.getItem(k)", key) is None,
           "an empty sheet wrote a saved copy")
        pg.close()

    # ---------------- it saves, and it comes back ----------------
    pg, _ = page("releve.html")
    pg.click('.tab[data-pane="p-plot"]'); pg.wait_for_timeout(250)
    for k, v in [("sPlot", "KEEP-01"), ("sObs", "R. Test"),
                 ("sComm", "wet meadow"), ("sElev", "310")]:
        pg.evaluate(SET, [k, v])
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(250)
    pg.fill("#rFree", "Carex aquatilis")
    pg.evaluate("""()=>{const d=document.querySelector('#rCov .fek-dial')||document.querySelector('#rCov');
      [...d.querySelectorAll('button')][2].click();}""")
    pg.wait_for_timeout(200)
    pg.click("#rAdd"); pg.wait_for_timeout(1200)
    ck("a filled sheet reports itself saved",
       "Saved on this device" in pg.inner_text("#keepBox"), pg.inner_text("#keepBox")[:70])
    raw = pg.evaluate("()=>localStorage.getItem('csrbtReleve')")
    ck("something was actually written", raw and len(raw) > 100, len(raw or ""))
    ck("the stored blob carries a format stamp", '"format":1' in (raw or ""), (raw or "")[:60])
    ck("the stored blob carries a timestamp", '"at":' in (raw or ""), (raw or "")[:60])
    pg.close()

    pg, errs = page("releve.html")
    ck("restoring raises no error", not errs, errs[:2])
    ck("the strip says it restored, and when",
       re.search(r"Restored .* from .*(today|\d{4}-\d\d-\d\d)", pg.inner_text("#keepBox")) is not None,
       pg.inner_text("#keepBox")[:80])
    ck("a typed text field comes back", pg.input_value("#sPlot") == "KEEP-01", pg.input_value("#sPlot"))
    ck("a hidden write-through field comes back",
       pg.input_value("#sElev") == "310", pg.input_value("#sElev"))
    # The point of the FEK registry: the widget, not just the value under it.
    ck("the WIDGET shows the restored value, not its construction default",
       "310" in pg.evaluate("""()=>[...document.querySelectorAll('#geoEntry .fek-step .val')]
         .map(x=>x.value)"""),
       pg.evaluate("""()=>[...document.querySelectorAll('#geoEntry .fek-step .val')].map(x=>x.value)"""))
    ck("the records come back", "Carex" in pg.inner_text("#ecoOut"), pg.inner_text("#ecoOut")[:80])

    # ---------------- forgetting really forgets ----------------
    # The strip lives on a different pane in each consumer; find it rather
    # than hard-coding four tab names.
    def show_keep(pg):
        pane = pg.evaluate("""()=>{const e=document.getElementById('keepBox');
          const p=e&&e.closest('section.pane'); return p?p.id:null;}""")
        if pane:
            pg.click('.tab[data-pane="%s"]' % pane)
            pg.wait_for_timeout(280)
    show_keep(pg)
    pg.click("#keepBox [data-keep-forget]"); pg.wait_for_timeout(400)
    ck("forget removes the stored copy",
       pg.evaluate("()=>localStorage.getItem('csrbtReleve')") is None, "still there")
    ck("forget resets the status strip",
       "Autosave is on" in pg.inner_text("#keepBox"), pg.inner_text("#keepBox")[:60])
    pg.close()
    pg, _ = page("releve.html")
    ck("a forgotten sheet comes back empty",
       pg.input_value("#sPlot") == "", pg.input_value("#sPlot"))
    pg.close()

    # ---------------- a stale format is not restored ----------------
    pg, _ = page("stand-sheet.html")
    pg.evaluate("""()=>localStorage.setItem('csrbtStandSheet', JSON.stringify(
      { format: 99, at: Date.now(), body: { fields:{sPlot:"FROM-THE-FUTURE"}, state:{} } }))""")
    pg.close()
    pg, errs = page("stand-sheet.html")
    ck("a blob from an unreadable format is ignored, not half-applied",
       pg.input_value("#sPlot") == "", pg.input_value("#sPlot"))
    ck("ignoring it raises no error", not errs, errs[:2])
    pg.evaluate("()=>localStorage.clear()")
    pg.close()

    # ---------------- corrupt storage does not break the page -------------
    pg, _ = page("collection-sheet.html")
    pg.evaluate("()=>localStorage.setItem('csrbtCollectionSheet','{not json at all')")
    pg.close()
    pg, errs = page("collection-sheet.html")
    ck("unparseable storage does not break the page", not errs, errs[:2])
    ck("unparseable storage leaves a usable sheet",
       pg.eval_on_selector_all("#cAdd", "e=>e.length") == 1, "")
    pg.evaluate("()=>localStorage.clear()")
    pg.close()

    # ---------------- it says so when it cannot save ----------------
    # A real failure, not a mocked one: fill the quota until setItem throws.
    pg, _ = page("ordination.html")
    pg.click("#demo1"); pg.wait_for_timeout(1600)
    pg.click('.tab[data-pane="p-data"]'); pg.wait_for_timeout(300)
    # Fill with big blocks until one is refused, then keep going with small
    # ones until even a small write fails -- otherwise the leftover space is
    # enough for the page's own blob and the failure path never runs.
    filled = pg.evaluate("""()=>{
      var big = new Array(200000).join("x"), i = 0, hit = false;
      try { for(i=0;i<400;i++) localStorage.setItem("__fill"+i, big); }
      catch(e){ hit = true; }
      if(!hit) return { hit:false, n:i };
      var small = new Array(2000).join("y");
      try { for(var j=0;j<20000;j++) localStorage.setItem("__pad"+j, small); }
      catch(e){}
      var tiny = new Array(200).join("z");
      try { for(var q=0;q<20000;q++) localStorage.setItem("__tiny"+q, tiny); }
      catch(e){ return { hit:true, n:i }; }
      return { hit:false, n:i, note:"never refused a tiny write" }; }""")
    if filled["hit"]:
        pg.evaluate(SET, ["raw", "site,a,b,c\nP,1,2,3\nQ,3,2,1\nR,0,5,5\nS,1,1,1\nT,9,9,9"])
        pg.wait_for_timeout(1200)
        strip = pg.inner_text("#keepBox")
        ck("a full quota is reported, not swallowed",
           "Autosave failed" in strip, strip[:100])
        ck("the failure tells the user what to do about it",
           "Export it now" in strip, strip[:140])
        ck("the failed strip is styled as a failure",
           pg.eval_on_selector_all("#keepBox.bad", "e=>e.length") == 1, "")
    else:
        ck("the quota could be filled to exercise the failure path", False,
           "storage never refused a write after %d attempts" % filled["n"])
    pg.evaluate("()=>localStorage.clear()")
    pg.close()

    # ---------------- the pages no longer claim they do not save ----------
    for name in CONSUMERS:
        src = io.open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()
        ck("%s no longer says it loses your data" % name,
           "closing the tab loses" not in src and "does not save your data" not in src, "")
        # The pattern KEEP replaced, gone for good: a bare setItem in a try that
        # swallows the error is the whole bug, and it must not creep back.
        ck("%s has no silent setItem left" % name,
           "localStorage.setItem" not in src.split("/* ---- Keep v")[0], "")

    pg, _ = page("ordination.html")
    met = re.sub(r"\s+", " ", pg.inner_text("#p-met"))
    ck("ordination still says nothing leaves the browser",
       "Nothing here leaves the browser" in met, met[:80])
    ck("ordination says the local copy is not a backup",
       "not a backup" in met, met[:120])
    ck("ordination points at the button that removes it",
       "Forget this device" in met, met[:160])
    pg.close()

    # ---- four behaviours a mutation sweep found untested ----
    pg, errs = page("ordination.html")

    # The banner ESCAPES what it renders, and both esc() calls survived a
    # mutation because nothing ever put a hostile string through them.
    #
    # `noun` is page-supplied and IS reachable -- checked below on both the
    # "autosave is on" branch and the "restored from" branch, which are
    # different esc() calls and need different setup to reach.
    #
    # `esc(lastErr)` is NOT reachable and is left uncovered on purpose:
    # lastErr is assigned one of two string literals by KEEP itself and can
    # never carry input. That mutation is an EQUIVALENT mutant, and writing a
    # check to kill it would be scoring the metric rather than testing the
    # module. The esc() call stays because the day lastErr carries a browser
    # message verbatim it will matter, and a comment is cheaper than the bug.
    inj = pg.evaluate("""()=>{
      const k = KEEP.wire({key:"__probe", format:1, mount:"keepBox",
        noun:"<x-keep-probe>a set</x-keep-probe>",
        snapshot:function(){ return {v:1}; }, restore:function(){ return true; }});
      return document.querySelector('#keepBox').innerHTML.indexOf('x-keep-probe');}""")
    pg.wait_for_timeout(200)
    ck("a noun containing markup does not become markup in the banner",
       pg.eval_on_selector_all("x-keep-probe", "e=>e.length") == 0,
       pg.eval_on_selector_all("x-keep-probe", "e=>e.length"))
    ck("and the angle brackets survive as text, so the noun still reads",
       "<x-keep-probe>" in pg.inner_text("#keepBox"), pg.inner_text("#keepBox")[:90])

    # That probe reaches the "autosave is on" branch. The RESTORED branch is a
    # different esc() call and needs something in storage first, or restore is
    # never called and the branch never renders. Seeding it is the difference
    # between exercising the escaper and walking past it.
    restored = pg.evaluate("""()=>{
      const key = "__probeRestore";
      localStorage.setItem(key, JSON.stringify(
        {format:1, at: Date.now() - 60000, body:{v:1}}));
      const host=document.createElement('div'); host.id='__rbox';
      document.body.appendChild(host);
      KEEP.wire({key:key, format:1, mount:"__rbox",
        noun:"<x-restore-probe>a set</x-restore-probe>",
        snapshot:function(){ return {v:1}; }, restore:function(){ return true; }});
      const out = {html: host.innerHTML, text: host.innerText};
      host.remove(); localStorage.removeItem(key);
      return out;}""")
    ck("the restored-from banner actually rendered, so this check is not a no-op",
       "Restored" in restored["text"], restored["text"][:100])
    ck("a noun containing markup is escaped on the RESTORED path too",
       "<x-restore-probe>" not in restored["html"].replace("&lt;", "<").replace("&gt;", ">")
       or "&lt;x-restore-probe&gt;" in restored["html"], restored["html"][:140])
    ck("and it survives as readable text there as well",
       "<x-restore-probe>" in restored["text"], restored["text"][:100])

    # 3. The quota message distinguishes a FULL store from a REFUSED write.
    # They call for different actions -- delete something, versus you are in a
    # private window -- and the classifier that tells them apart had no test.
    # The first version of this check reimplemented the classifier in the test
    # and compared it against itself -- a tautology that no mutation of keep.py
    # could ever fail. Drive KEEP's own write path instead: make setItem throw
    # with a named error and read the banner it produces.
    # Order matters, and getting it wrong is instructive: KEEP PROBES storage at
    # wire time, so breaking setItem first makes the probe fail and the banner
    # reads "this browser is not keeping anything" -- correct behaviour, and a
    # different message entirely. The classifier only runs on a write that
    # fails AFTER a store that worked. Wire first, then break it.
    def quota_banner(err_name):
        return pg.evaluate("""(n)=>{
          const host=document.createElement('div'); host.id='__qbox';
          document.body.appendChild(host);
          const k = KEEP.wire({key:"__q"+n, format:1, mount:"__qbox", noun:"a set",
            snapshot:function(){ return {v:Math.random()}; },
            restore:function(){ return false; }});
          const real = localStorage.setItem.bind(localStorage);
          localStorage.setItem = function(){ const e=new Error("no"); e.name=n; throw e; };
          try {
            k.touch(); k.flush();
            return host.innerText;
          } finally { localStorage.setItem = real; host.remove(); }}""", err_name)

    q = quota_banner("QuotaExceededError")
    ck("a real QuotaExceededError from setItem reports the store as FULL",
       "storage is full" in q, q[:110])
    sec = quota_banner("SecurityError")
    ck("any other write failure reports a REFUSED write, not a full store",
       "refused the write" in sec and "storage is full" not in sec, sec[:110])
    ck("the two messages differ, so this check can tell the classifier apart "
       "from a constant", q != sec, (q[:40], sec[:40]))
    ck("and a failed write says outright that what is on screen is not saved",
       "not saved" in q, q[:140])

    # 4. The FEK bridge is GUARDED. formRestore pushes values back through
    # FEK.setField when FEK is present, and must not throw on a page without
    # it -- the guard is `typeof FEK !== "undefined" && FEK.setField`, and
    # turning that && into || survived every check.
    ck("formRestore is exported, so the check below is not a no-op",
       pg.evaluate("()=>typeof KEEP.formRestore") == "function",
       pg.evaluate("()=>typeof KEEP.formRestore"))
    ck("formRestore still restores the input itself when FEK is absent",
       pg.evaluate("""()=>{
         const real = window.FEK;
         try {
           window.FEK = undefined;
           const d=document.createElement('input'); d.id='__kprobe'; d.type='text';
           document.body.appendChild(d);
           const n = KEEP.formRestore({__kprobe:"7"});
           const v = d.value; d.remove();
           return (n >= 1 && v === "7");
         } catch(e) { return "threw: " + e.message; }
         finally { window.FEK = real; }}""") is True, "")
    ck("and it DOES push through FEK when FEK is present",
       pg.evaluate("""()=>{
         const d=document.createElement('input'); d.id='__kprobe2'; d.type='text';
         document.body.appendChild(d);
         let seen = null;
         const realSet = FEK.setField;
         FEK.setField = function(id,v){ seen = [id,v]; return realSet(id,v); };
         try { KEEP.formRestore({__kprobe2:"12"}); }
         finally { FEK.setField = realSet; d.remove(); }
         return seen && seen[0]==='__kprobe2' && seen[1]===12;}""") is True, "")
    ck("and FEK is still there afterwards", pg.evaluate("()=>typeof FEK") == "object", "")
    ck("no page errors from any of that", not errs, errs[:2])
    pg.close()

    b.close()

print("\n".join("PASS  " + x for x in P))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
