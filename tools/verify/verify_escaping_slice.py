# -*- coding: utf-8 -*-
"""Locks the escaping slice, in the component where the fix belongs.

A plant named `Sarracenia <hybrid>` used to become markup on the CP bench,
because FEK's el(tag, class, html) sets innerHTML and the picker handed it
op.label straight. The fix is in FEK v1.2.0 rather than at the fourteen call
sites: a component whose safety depends on every caller remembering is a
component that will bite somebody.

The interesting assertions here are the ones that would catch the fix being
undone quietly -- by a caller escaping twice, by the escape hatch spreading, or
by a future el() call reintroducing the hole.
"""
import glob, io, os, re, sys

import _kit
from playwright.sync_api import sync_playwright

P = F = 0
def ck(c, m):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", m)

PROBE = '<x-probe>p</x-probe>" data-x-probe="1'
FEK = io.open(os.path.join(_kit.TOOLS_DIR, "fek.py"), encoding="utf-8").read()

# ---- 1. the component escapes, and says which side of the line it is on ----
# Read the version rather than freeze it. Four suites in this kit have already
# been ignored-then-dead because they asserted a number that a legitimate bump
# invalidated; a version bump is not a regression.
FEKV = re.search(r'^VERSION\s*=\s*"([\d.]+)"', FEK, re.M).group(1)
ck(bool(FEKV), "fek.py declares a version (%s)" % FEKV)
ck("function escv(" in FEK, "fek.py carries its own escaper")
# The escape hatch this suite first asserted (labelHtml) was removed once it
# turned out nothing needed it: the one caller was a COMPONENT label, which is
# authored markup by design and never went through the option path at all. The
# contract is the simpler one -- option labels are data and are escaped,
# component labels are authored HTML -- and this checks that shape.
ck("labelHtml" not in FEK, "no escape hatch: option labels are always escaped")
ck(FEK.count("escv(op.label)") == 3, "dial, chips and picker all escape their option labels (%d)"
   % FEK.count("escv(op.label)"))
ck("esc:escv" in FEK, "FEK exports its escaper for pages building a component label")
ck("escv(t.v)" in FEK and "escv(t.l)" in FEK, "tile values and labels are escaped")
ck("escv(op.sub)" in FEK, "option sub-lines are escaped")
# the authored side stays HTML on purpose
ck('el("label","fek-lab",o.label||"")' in FEK,
   "a component's own label is still HTML -- pages put deliberate markup there")
# and the escaper must not be the version that could not survive emission
ck('{"&":"&amp;"' not in FEK.split("function escv")[1][:300],
   "escv uses comparisons, not an object literal needing an escaped quote key")

# ---- 2. every consumer actually carries 1.2.0 -----------------------------
pages = sorted(glob.glob(_kit.DOCS_DIR + "*.html"))
consumers = [p for p in pages if "Field Entry Kit v" in io.open(p, encoding="utf-8").read()]
# The invariant, not the count: a page that CALLS a FEK constructor must carry
# FEK, and a page that carries FEK must call one. That stays true as the kit
# grows; "exactly 14" broke the day a fifteenth page adopted the kit.
CALLS = re.compile(r"\bFEK\.(dial|picker|chips|slider|tiles|step|field|banner|mount)\(")
for path in pages:
    nm = os.path.basename(path)
    src = io.open(path, encoding="utf-8").read()
    carries, calls = path in consumers, bool(CALLS.search(src))
    if calls or carries:
        ck(calls == carries, "%s: carries FEK=%s but calls it=%s" % (nm, carries, calls))
ck(len(consumers) >= 14, "at least the 14 known FEK consumers (%d)" % len(consumers))
for path in consumers:
    nm = os.path.basename(path)
    src = io.open(path, encoding="utf-8").read()
    vers = sorted(set(re.findall(r"Field Entry Kit v([\d.]+)", src)))
    # Scope the runtime read to FEK's own return object. Other inlined modules
    # (the Darwin Core exporter, for one) declare a version:"..." of their own,
    # and a whole-file grep reported those as FEK disagreeing with itself.
    runtime = sorted(set(re.findall(r'version:"([\d.]+)",\s*esc:escv', src)))
    ck(vers == [FEKV], "%s banner says %s (%s)" % (nm, FEKV, vers))
    ck(runtime == [FEKV], "%s runtime version agrees with its banner (%s)" % (nm, runtime))
    ck("escv(op.label)" in src, "%s carries the escaping component" % nm)

# ---- 3. nobody escapes twice ---------------------------------------------
for path in consumers:
    nm = os.path.basename(path)
    src = io.open(path, encoding="utf-8").read()
    dbl = re.findall(r"\b(?:label|sub)\s*:\s*esc\(", src)
    ck(not dbl, "%s no longer escapes an option label at the call site (%d)" % (nm, len(dbl)))

# ---- 4. the escape hatch stays rare --------------------------------------
# `labelHtml:` as an object property, not the `op.labelHtml : ...` arm of the
# ternary inside the component -- which is in all fourteen consumers by design.
# `labelHtml:` or `.labelHtml` -- a code shape. The bare word also appears in
# ADR-031's prose, where it is describing the hatch that was removed; a record
# of a decision is not a caller reaching for it. (The same over-broad grep
# caught the ADR once before, over data-claim. Twice is a pattern: match the
# code, not the word.)
hatch = [os.path.basename(p) for p in pages
         if re.search(r"labelHtml\s*:|\.labelHtml\b", io.open(p, encoding="utf-8").read())]
ck(not hatch, "no page reaches for an escape hatch that no longer exists (%s)" % hatch)
# the one page that puts markup in a component label escapes the data inside it
pt = io.open(_kit.DOCS_DIR + "pheno-tracker.html", encoding="utf-8").read()
ck("label:FEK.esc(t.n)+" in pt,
   "pheno-tracker escapes the trait name inside its authored dial label")

# ---- 5. the component contract, asked of the component --------------------
# Driving each page's own add flow tests the page more than the fix, and half of
# them refuse an incomplete row anyway. This calls FEK directly on a page that
# has it, which is exactly the surface that changed.
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1100, "height": 900})
    ctx.set_offline(True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(_kit.url("cp-bench.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(800)
    ck(not errs, "cp-bench loads without error (%s)" % errs[:1])
    ck(pg.evaluate("()=>typeof FEK==='object' && FEK.version") == "1.2.0",
       "the page's own FEK reports 1.2.0")

    r = pg.evaluate("""(probe)=>{
      const host=document.createElement('div'); host.id='__esc_probe'; document.body.appendChild(host);
      const pick=FEK.picker({label:'probe', options:[
        {value:'a', label:probe},
        {value:'b', label:'plain', sub:probe}]});
      const chips=FEK.chips({label:'probe', options:[{value:'x', label:probe}]});
      const dial=FEK.dial({label:'probe', options:[{value:'y', label:probe, sub:probe}]});
      const tiles=FEK.tiles([{v:probe, l:probe}]);
      FEK.mount(host,[pick,chips,dial,tiles]);
      return {injected: host.querySelectorAll('x-probe').length,
              attrs: host.querySelectorAll('[data-x-probe]').length,
              escFn: typeof FEK.esc,
              shown: (host.innerText||'').split('<x-probe>').length-1};}""", PROBE)
    ck(r["injected"] == 0, "picker, chips, dial and tiles: markup in data never becomes markup (%d)" % r["injected"])
    ck(r["attrs"] == 0, "and it never breaks out of an attribute (%d)" % r["attrs"])
    ck(r["shown"] >= 4, "the reader still sees what they typed, as text (%d places)" % r["shown"])
    ck(r["escFn"] == "function", "FEK.esc is callable from the page (%s)" % r["escFn"])

    # the filter has to match what the reader sees, including through labelHtml
    f = pg.evaluate("""()=>{const host=document.getElementById('__esc_probe');
      const s=host.querySelector('.fek-pick .search');
      s.value='plain'; s.dispatchEvent(new Event('input',{bubbles:true}));
      return host.querySelectorAll('.fek-pick .opt').length;}""")
    ck(f == 1, "the picker filter still narrows to a matching option (%d)" % f)
    ck(not errs, "no errors raised by any of it (%s)" % errs[:1])
    ctx.close()
    b.close()

print("---"); print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
