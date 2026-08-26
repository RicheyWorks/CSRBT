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
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":700,"height":900})
    pg.set_default_timeout(10000)
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    # Built here, from tools/fek.py, so this suite can never test a stale copy
    # of the component -- which is exactly what it was doing.
    import importlib.util as _ilu
    _hs = _ilu.spec_from_file_location("fek_harness", _os.path.join(ROOT, "tools", "fek_harness.py"))
    _hm = _ilu.module_from_spec(_hs); _hs.loader.exec_module(_hm)
    HARNESS = _hm.build()
    pg.goto("file://" + HARNESS, wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    ck("no errors", not errs, errs[:2])
    ck("version matches fek.py", pg.evaluate("()=>FEK.version")==_fek_version(), pg.evaluate("()=>FEK.version"))
    ck("field is exported", pg.evaluate("()=>typeof FEK.field")=="function", "")
    for c in ("step","dial","chips","slider","picker","tiles","banner","mount","buzz"):
        ck("v1.0 component still exported: "+c, pg.evaluate("()=>typeof FEK.%s"%c)=="function", "")

    # ---- nullable stepper ----
    ck("nullable stepper starts null", pg.evaluate("()=>A.get()") is None, pg.evaluate("()=>A.get()"))
    ck("nullable stepper renders empty",
       pg.evaluate("()=>document.querySelectorAll('#h1 .fek-step .val')[0].value")=="", "")
    ck("empty nullable stepper is visually marked",
       pg.evaluate("()=>document.querySelector('#h1 .fek-step').classList.contains('empty')"), "")
    ck("null reported without firing onchange on construction",
       pg.evaluate("()=>LOG.length")==0, pg.evaluate("()=>LOG"))
    # first bump starts from `start`, not from zero
    pg.evaluate("()=>document.querySelectorAll('#h1 .fek-step button')[1].click()")
    pg.wait_for_timeout(150)
    ck("first + on an empty nullable stepper starts at start=5",
       pg.evaluate("()=>A.get()")==5, pg.evaluate("()=>A.get()"))
    ck("it is no longer marked empty",
       not pg.evaluate("()=>document.querySelector('#h1 .fek-step').classList.contains('empty')"), "")
    pg.evaluate("()=>document.querySelectorAll('#h1 .fek-step button')[1].click()")
    pg.wait_for_timeout(120)
    ck("subsequent + steps normally (5.5)", pg.evaluate("()=>A.get()")==5.5, pg.evaluate("()=>A.get()"))
    # clearing returns to null, not to zero
    pg.evaluate("()=>A.clear()")
    pg.wait_for_timeout(120)
    ck("clear() returns to null, not zero", pg.evaluate("()=>A.get()") is None, pg.evaluate("()=>A.get()"))
    ck("clear() fires onchange with null",
       pg.evaluate("()=>LOG[LOG.length-1]")==["A",None], pg.evaluate("()=>LOG[LOG.length-1]"))
    # typing then emptying the box
    pg.evaluate("""()=>{const i=document.querySelectorAll('#h1 .fek-step .val')[0];
      i.value='12'; i.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("typing sets the value", pg.evaluate("()=>A.get()")==12, pg.evaluate("()=>A.get()"))
    pg.evaluate("""()=>{const i=document.querySelectorAll('#h1 .fek-step .val')[0];
      i.value=''; i.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("emptying the box returns null", pg.evaluate("()=>A.get()") is None, pg.evaluate("()=>A.get()"))
    # a recorded zero is NOT null — the whole point
    pg.evaluate("()=>A.set(0)"); pg.wait_for_timeout(120)
    ck("a recorded zero is not null", pg.evaluate("()=>A.get()")==0, pg.evaluate("()=>A.get()"))
    ck("a recorded zero renders as 0.0",
       pg.evaluate("()=>document.querySelectorAll('#h1 .fek-step .val')[0].value")=="0.0",
       pg.evaluate("()=>document.querySelectorAll('#h1 .fek-step .val')[0].value"))
    ck("a recorded zero is not marked empty",
       not pg.evaluate("()=>document.querySelector('#h1 .fek-step').classList.contains('empty')"), "")

    # ---- plain (non-nullable) stepper is unchanged ----
    ck("plain stepper keeps its value", pg.evaluate("()=>B.get()")==10, pg.evaluate("()=>B.get()"))
    pg.evaluate("()=>document.querySelectorAll('#h2 .fek-step button')[0].click()")
    pg.wait_for_timeout(120)
    ck("plain stepper decrements", pg.evaluate("()=>B.get()")==9, pg.evaluate("()=>B.get()"))
    pg.evaluate("""()=>{const i=document.querySelectorAll('#h2 .fek-step .val')[0];
      i.value=''; i.dispatchEvent(new Event('input',{bubbles:true}));
      i.dispatchEvent(new Event('blur',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("emptying a non-nullable stepper does NOT produce null",
       pg.evaluate("()=>B.get()") is not None, pg.evaluate("()=>B.get()"))
    ck("non-nullable stepper reports nullable=false", pg.evaluate("()=>B.nullable")==False, "")

    # ---- field ----
    ck("field starts null", pg.evaluate("()=>C.get()") is None, pg.evaluate("()=>C.get()"))
    ck("field has no stepper buttons",
       pg.eval_on_selector_all("#h3 .fek-field button","e=>e.length")==0, "")
    ck("field requests the decimal keypad",
       pg.evaluate("()=>document.querySelector('#h3 .fek-field input').getAttribute('inputmode')")=="decimal", "")
    ck("field shows its unit",
       pg.evaluate("()=>document.querySelector('#h3 .fek-field .u').textContent")=="AU",
       pg.evaluate("()=>document.querySelector('#h3 .fek-field .u')&&document.querySelector('#h3 .fek-field .u').textContent"))
    pg.evaluate("""()=>{const i=document.querySelector('#h3 .fek-field input');
      i.value='1.842'; i.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("field takes three decimals exactly", pg.evaluate("()=>C.get()")==1.842, pg.evaluate("()=>C.get()"))
    pg.evaluate("""()=>{const i=document.querySelector('#h3 .fek-field input');
      i.value='9'; i.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("field clamps to max", pg.evaluate("()=>C.get()")==4, pg.evaluate("()=>C.get()"))
    pg.evaluate("""()=>{const i=document.querySelector('#h3 .fek-field input');
      i.value=''; i.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("emptying the field returns null", pg.evaluate("()=>C.get()") is None, pg.evaluate("()=>C.get()"))
    ck("empty field is dashed", pg.evaluate("()=>document.querySelector('#h3 .fek-field').classList.contains('empty')"), "")

    # ---- nullable slider ----
    ck("nullable slider starts null", pg.evaluate("()=>D.get()") is None, pg.evaluate("()=>D.get()"))
    ck("nullable slider says so rather than showing a number",
       "not recorded" in pg.inner_text("#h4 .bub"), pg.inner_text("#h4 .bub"))
    pg.evaluate("""()=>{const r=document.querySelector('#h4 input[type=range]');
      r.value='40'; r.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("moving the slider records a value", pg.evaluate("()=>D.get()")==40, pg.evaluate("()=>D.get()"))
    ck("bubble now shows the number", "40" in pg.inner_text("#h4 .bub"), pg.inner_text("#h4 .bub"))
    pg.evaluate("()=>D.clear()"); pg.wait_for_timeout(120)
    ck("slider clear() returns to not-recorded",
       pg.evaluate("()=>D.get()") is None and "not recorded" in pg.inner_text("#h4 .bub"),
       (pg.evaluate("()=>D.get()"), pg.inner_text("#h4 .bub")))

    # ---- sizing still driven by one token ----
    for w,tap in ((700,60),(390,56)):
        pg.set_viewport_size({"width":w,"height":900}); pg.wait_for_timeout(150)
        hs=pg.evaluate("""()=>{const o={};
          o.step=document.querySelector('.fek-step button').getBoundingClientRect().height;
          o.field=document.querySelector('.fek-field input').getBoundingClientRect().height;
          return o;}""")
        ck("step is --tap tall @%d"%w, abs(hs["step"]-tap)<1.5, hs)
        ck("field is --tap tall @%d"%w, abs(hs["field"]-tap)<1.5, hs)
        ck("every control clears 44px @%d"%w,
           pg.evaluate("""()=>[...document.querySelectorAll('.fek-step button,.fek-field input,.fek-slide input')]
             .every(e=>e.getBoundingClientRect().height>=44)"""), hs)
    # ---- the semantics that bit me in cell-bench, pinned ----
    ck("nullable with an explicit value:0 is a RECORDED zero, not null",
       pg.evaluate("()=>E.get()")==0, pg.evaluate("()=>E.get()"))
    ck("and it renders as 0 rather than blank",
       pg.evaluate("()=>document.querySelector('#h5 .fek-step .val').value")=="0",
       pg.evaluate("()=>document.querySelector('#h5 .fek-step .val').value"))
    ck("a recorded zero is not marked empty",
       not pg.evaluate("()=>document.querySelector('#h5 .fek-step').classList.contains('empty')"), "")
    ck("clearing it afterwards still reaches null",
       (pg.evaluate("()=>{E.clear(); return E.get();}") is None), "")
    ck("omitting value entirely is what starts null",
       pg.evaluate("()=>A.nullable")==True, "")

    # ---- the picker's FILTER, which nothing drove until a mutation sweep asked
    # A mutation changing the filter's `indexOf(qq) >= 0` to `> 0` survived this
    # whole suite. That single character breaks the picker for the normal case:
    # indexOf returns 0 when a query matches the START of an option, which is
    # what happens when anyone types the first letters of the thing they want.
    # The suite had one picker check -- that FEK.picker was a function.
    #
    # The fixture below is chosen to DISCRIMINATE: "may" matches "mayfly nymph"
    # at index 0 and "perch" at nowhere, so >=0 and >0 give different answers.
    # A query that matched mid-string would pass under either and test nothing.
    pg.evaluate("""()=>{
      window.__P = FEK.picker({label:"probe", options:[
        {value:"a", label:"mayfly nymph", sub:"insect"},
        {value:"b", label:"perch",        sub:"fish"},
        {value:"c", label:"water flea",   sub:"crustacean"}]});
      const h=document.createElement('div'); h.id='hpick';
      document.body.appendChild(h); h.appendChild(window.__P.el);
    }""")
    pg.wait_for_timeout(150)
    def shown():
        return pg.evaluate("()=>[...document.querySelectorAll('#hpick .opt')]"
                           ".map(b=>b.textContent)")
    ck("the picker lists every option before filtering", len(shown()) == 3, shown())

    def type_filter(q):
        pg.evaluate("""(q)=>{const s=document.querySelector('#hpick .search');
          s.value=q; s.dispatchEvent(new Event('input',{bubbles:true}));}""", q)
        pg.wait_for_timeout(120)

    type_filter("may")
    got = shown()
    ck("a query matching the START of a label still finds it — indexOf returns 0 there",
       len(got) == 1 and "mayfly" in got[0], got)
    type_filter("erc")
    got = shown()
    ck("a query matching mid-label finds it too", len(got) == 1 and "perch" in got[0], got)
    type_filter("fish")
    ck("the sub-label is searched as well as the label", len(shown()) == 1, shown())
    type_filter("MAY")
    ck("filtering is case-insensitive", len(shown()) == 1, shown())
    type_filter("zzz")
    ck("no match shows the empty state rather than an empty box",
       len(shown()) == 0
       and bool(pg.evaluate("()=>document.querySelector('#hpick .none')")), shown())
    ck("and the empty state says how many options there are",
       "3" in (pg.evaluate("()=>{const n=document.querySelector('#hpick .none');"
                           "return n?n.textContent:'';}") or ""), "")
    type_filter("")
    ck("clearing the filter brings every option back", len(shown()) == 3, shown())

    pg.evaluate("()=>[...document.querySelectorAll('#hpick .opt')][1].click()")
    pg.wait_for_timeout(120)
    ck("choosing an option reports its value, not its label",
       pg.evaluate("()=>window.__P.get()") == "b", pg.evaluate("()=>window.__P.get()"))
    ck("and the chosen option is marked",
       pg.evaluate("()=>!!document.querySelector('#hpick .opt.on')"), "")
    pg.evaluate("()=>window.__P.set('c')")
    pg.wait_for_timeout(120)
    ck("set() moves the selection", pg.evaluate("()=>window.__P.get()") == "c", "")

    ck("no errors after the run", not errs, errs[:2])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))

# A suite that cannot fail the run is not a check. This one printed its FAIL
# lines and exited zero, so run_all marked it green whatever it found -- for
# eleven suites in this kit, "green" meant "the process did not crash".
raise SystemExit(1 if F else 0)
