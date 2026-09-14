# -*- coding: utf-8 -*-
import math
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

    # ---- the field registry, which nothing touched until a mutation asked ----
    # reg() and setField() are what KEEP's restore path uses to put a saved
    # value back THROUGH the widget instead of only into a hidden input. Two
    # mutations survived here -- the registration guard and the lookup guard --
    # because the harness had no component declaring a `field` at all.
    ck("a component declaring a field is registered under it",
       "sElev" in pg.evaluate("()=>FEK.fields()"), pg.evaluate("()=>FEK.fields()"))
    ck("a dial declaring a field is registered too",
       "sCover" in pg.evaluate("()=>FEK.fields()"), pg.evaluate("()=>FEK.fields()"))
    ck("components WITHOUT a field stay out of the registry — the feature is additive",
       len(pg.evaluate("()=>FEK.fields()")) == 2, pg.evaluate("()=>FEK.fields()"))

    pg.evaluate("()=>{LOG.length=0; FEK.setField('sElev', 320);}")
    pg.wait_for_timeout(120)
    ck("setField reaches the widget's own value", pg.evaluate("()=>G.get()") == 320,
       pg.evaluate("()=>G.get()"))
    ck("and the widget REDRAWS — the whole point, not just the value behind it",
       pg.evaluate("()=>document.querySelector('#h6 .fek-step .val').value") == "320",
       pg.evaluate("()=>document.querySelector('#h6 .fek-step .val').value"))
    ck("setField reports success", pg.evaluate("()=>FEK.setField('sElev', 100)") is True, "")
    ck("setField on an unregistered id reports FAILURE rather than pretending",
       pg.evaluate("()=>FEK.setField('noSuchField', 5)") is False, "")
    ck("and does not invent a registry entry for it",
       "noSuchField" not in pg.evaluate("()=>FEK.fields()"), pg.evaluate("()=>FEK.fields()"))
    pg.evaluate("()=>FEK.setField('sCover','c')")
    pg.wait_for_timeout(120)
    ck("setField works on a dial as well as a stepper",
       pg.evaluate("()=>H.get()") == "c", pg.evaluate("()=>H.get()"))
    ck("and the dial shows the restored option as selected",
       pg.evaluate("""()=>{const b=[...document.querySelectorAll('#h7 .fek-dial button')]
         .find(x=>x.classList.contains('on')); return b?b.textContent:null;}""") == "lots",
       pg.evaluate("""()=>{const b=[...document.querySelectorAll('#h7 .fek-dial button')]
         .find(x=>x.classList.contains('on')); return b?b.textContent:null;}"""))
    ck("a restore does not fire onchange — it is not the user acting",
       pg.evaluate("()=>LOG.length") == 0, pg.evaluate("()=>LOG"))

    # ---- field() clamping, which had no test either ----
    ck("field() clamps above its max", pg.evaluate("()=>{C.set(99); return C.get();}") == 4, "")
    ck("field() clamps below its min", pg.evaluate("()=>{C.set(-7); return C.get();}") == 0, "")
    ck("a value inside the range is left alone",
       pg.evaluate("()=>{C.set(1.842); return C.get();}") == 1.842, "")
    ck("a non-number becomes null, not zero",
       pg.evaluate("()=>{C.set('abc'); return C.get();}") is None, "")
    ck("clearing it reaches null", pg.evaluate("()=>{C.clear(); return C.get();}") is None, "")
    ck("typing above the max clamps on input too",
       pg.evaluate("""()=>{const i=document.querySelector('#h3 .fek-field input');
         i.value='50'; i.dispatchEvent(new Event('input',{bubbles:true})); return C.get();}""") == 4,
       "")

    # ---- the default colour ramp on a dial ----
    # min(5, round(i*5/(n-1))). With five options the denominator is 4, so the
    # indices run 0,1,3,4,5. Dropping the -1 makes the denominator 5 and the
    # last option no longer reaches the top of the ramp -- which is what a
    # surviving mutation was doing silently.
    ramps = pg.evaluate("""()=>[...document.querySelectorAll('#h8 .fek-dial button')]
        .map(b=>b.getAttribute('data-r'))""")
    # Those four properties -- starts at 0, ends at 5, never exceeds 5, never
    # goes backwards -- are all TRUE of the sequence 0,5,5,5,5, which is what
    # mutating the divisor's guard produces. They passed, and the mutant
    # survived. Recompute the whole sequence from the same formula instead:
    # min(5, round(i*5/max(1, n-1))), with JavaScript's half-up rounding.
    n_opts = len(ramps)
    want = [str(min(5, int(math.floor(i * 5 / max(1, n_opts - 1) + 0.5))))
            for i in range(n_opts)]
    ck("every ramp index matches min(5, round(i*5/(n-1))) recomputed: %s" % ",".join(want),
       ramps == want, (ramps, want))
    ck("and that sequence really does have distinct middle values, so this test "
       "can tell a broken divisor from a working one",
       len(set(want)) == n_opts, want)
    ck("an explicit ramp overrides the computed one",
       pg.evaluate("""()=>{const d=FEK.dial({label:'x',options:[
           {value:'a',label:'a',ramp:5},{value:'b',label:'b',ramp:0}]});
         const h=document.createElement('div'); document.body.appendChild(h);
         h.appendChild(d.el);
         return [...h.querySelectorAll('button')].map(b=>b.getAttribute('data-r'));}""")
       == ["5", "0"], "")

    # ---- quiet vs loud set(), which a surviving mutation blurred ----
    pg.evaluate("()=>{LOG.length=0; B.set(42);}")
    pg.wait_for_timeout(100)
    ck("set() is quiet — restoring state is not the user changing it",
       pg.evaluate("()=>LOG.length") == 0, pg.evaluate("()=>LOG"))
    ck("but it did move the value", pg.evaluate("()=>B.get()") == 42, "")
    pg.evaluate("()=>{LOG.length=0;}")
    pg.evaluate("()=>document.querySelectorAll('#h2 .fek-step button')[1].click()")
    pg.wait_for_timeout(120)
    ck("a tap on the widget IS loud", pg.evaluate("()=>LOG.length") == 1,
       pg.evaluate("()=>LOG"))

    # ---- five more behaviours a wider mutation sample found untested ----

    # field() rounds to `dec` on blur, and only when it holds a real number.
    pg.evaluate("""()=>{const i=document.querySelector('#h3 .fek-field input');
      C.set(1.23456); i.value='1.23456';
      i.dispatchEvent(new Event('blur',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("field() formats to its declared decimals on blur",
       pg.evaluate("()=>document.querySelector('#h3 .fek-field input').value") == "1.235",
       pg.evaluate("()=>document.querySelector('#h3 .fek-field input').value"))
    pg.evaluate("""()=>{C.clear();
      document.querySelector('#h3 .fek-field input')
        .dispatchEvent(new Event('blur',{bubbles:true}));}""")
    pg.wait_for_timeout(120)
    ck("blurring an EMPTY field leaves it empty rather than printing a rounded null",
       pg.evaluate("()=>document.querySelector('#h3 .fek-field input').value") == "",
       pg.evaluate("()=>document.querySelector('#h3 .fek-field input').value"))

    # the unit box is drawn only when there is a unit AND it was not suppressed
    ck("a field with a unit shows the unit box",
       pg.evaluate("()=>!!document.querySelector('#h3 .fek-field .u')"), "")
    # `.u` is also the class of the unit span inside the LABEL, so a bare
    # querySelector('.u') finds that one and this check failed against working
    # code. Scope it to the field box, which is the thing under test.
    ck("unitBox:false suppresses the box even when a unit is given",
       pg.evaluate("""()=>{const f=FEK.field({label:'x',unit:'AU',unitBox:false});
         const h=document.createElement('div'); document.body.appendChild(h);
         h.appendChild(f.el); return !h.querySelector('.fek-field .u');}"""), "")
    ck("and a field with no unit has no box either",
       pg.evaluate("""()=>{const f=FEK.field({label:'x'});
         const h=document.createElement('div'); document.body.appendChild(h);
         h.appendChild(f.el); return !h.querySelector('.fek-field .u');}"""), "")

    # the dial's tap-the-same-option-again-to-clear, and clearable:false
    pg.evaluate("()=>{LOG.length=0; H.set(null);}")
    pg.evaluate("""()=>[...document.querySelectorAll('#h7 .fek-dial button')][1].click()""")
    pg.wait_for_timeout(120)
    ck("tapping a dial option selects it", pg.evaluate("()=>H.get()") == "b", "")
    pg.evaluate("""()=>[...document.querySelectorAll('#h7 .fek-dial button')][1].click()""")
    pg.wait_for_timeout(120)
    ck("tapping the SAME option again clears it, on a clearable dial",
       pg.evaluate("()=>H.get()") is None, pg.evaluate("()=>H.get()"))
    pg.evaluate("""()=>[...document.querySelectorAll('#h8 .fek-dial button')][2].click()""")
    pg.wait_for_timeout(100)
    pg.evaluate("""()=>[...document.querySelectorAll('#h8 .fek-dial button')][2].click()""")
    pg.wait_for_timeout(100)
    ck("clearable:false refuses to clear — the second tap leaves it selected",
       pg.evaluate("()=>I.get()") == "3", pg.evaluate("()=>I.get()"))

    # the nullable slider: empty is not zero, and the thumb still has to sit somewhere
    # Built fresh rather than read off the harness's D, which earlier checks in
    # this suite have already dragged. Asserting on a shared mutable fixture
    # after other tests have used it tests the test order, not the component.
    sl = pg.evaluate("""()=>{const s=FEK.slider({label:'fresh',unit:'%',nullable:true,
         min:20,max:80,step:5});
       const h=document.createElement('div'); h.id='hslide';
       document.body.appendChild(h); h.appendChild(s.el);
       window.__SL=s;
       return {v:s.get(), bub:h.querySelector('.bub').textContent,
               thumb:h.querySelector('input[type=range]').value};}""")
    ck("a nullable slider with no value reports null, not its minimum",
       sl["v"] is None, sl)
    ck("and says so on screen rather than showing a number",
       "not recorded" in sl["bub"], sl["bub"])
    ck("but the thumb is parked at the minimum, because a range input needs a position",
       sl["thumb"] == "20", sl["thumb"])
    ck("a NON-nullable slider with no value starts at its minimum as a real value",
       pg.evaluate("""()=>{const s=FEK.slider({label:'x',min:20,max:80,step:5});
         return s.get();}""") == 20, "")

    # ==================== PHOTOGRAPHS (ADR-201) ====================
    #
    # One page in this kit took a photograph and twenty did not, on a kit that
    # emits Darwin Core with `associatedMedia` empty everywhere. The component
    # is here rather than in a page because a file reader copied into ten
    # sheets is ten places for a checksum to be computed differently.

    # THE CHECK VALUE, not a value this suite made up. Every CRC-32
    # implementation in the world agrees that "123456789" is CBF43926; a
    # checksum this kit computed its own way would match nothing anybody else
    # computed, which is the entire point of writing it on a field sheet.
    ck("crc32 agrees with the standard check value: '123456789' is cbf43926",
       pg.evaluate("() => FEK.crc32(new TextEncoder().encode('123456789'))") == "cbf43926",
       pg.evaluate("() => FEK.crc32(new TextEncoder().encode('123456789'))"))
    ck("and it is eight hex digits ALWAYS -- a crc of 0x0000a1b2 written as 'a1b2' is a different "
       "string from the one the next reader computes",
       pg.evaluate("() => FEK.crc32(new Uint8Array([])).length") == 8
       and pg.evaluate("() => FEK.crc32(new Uint8Array([]))") == "00000000",
       pg.evaluate("() => FEK.crc32(new Uint8Array([]))"))
    ck("a single changed byte changes it",
       pg.evaluate("() => FEK.crc32(new Uint8Array([1,2,3]))")
       != pg.evaluate("() => FEK.crc32(new Uint8Array([1,2,4]))"), "")

    ph = pg.evaluate("""() => {
      const c = FEK.photos({label:'Photographs', dropId:'zzPh'});
      const h = document.createElement('div'); h.id='hph';
      document.body.appendChild(h); h.appendChild(c.el);
      window.__PH = c;
      return { zone: !!document.getElementById('zzPh'),
               live: !!h.querySelector('[role="status"][aria-live]'),
               empty: c.get().length, media: c.media(),
               fileInput: !!h.querySelector('input[type=file][accept*="image"]') }; }""")
    ck("the component builds a drop zone with an ADDRESS -- a drop listener leaves no mark a "
       "selector can find, and the only control its label offers is the hidden file input",
       ph["zone"], ph)
    ck("and a live region of its own, so a refusal is announced rather than swallowed (ADR-199)",
       ph["live"], ph)
    ck("with nothing in it, get() is empty and media() is the empty string -- not the word 'none'",
       ph["empty"] == 0 and ph["media"] == "", ph)
    ck("and its live region ships EMPTY, for the reason ADR-199 gave: a live region is in the "
       "accessibility tree whether or not anybody has pressed anything",
       pg.evaluate("""() => { const e = document.querySelector('#hph [role="status"]');
         return e ? e.textContent.trim() : '(absent)'; }""") == "", "")
    ck("and it offers a file input that accepts images, for the reader who has no drag to give",
       ph["fileInput"], ph)

    # Null-safe on purpose. A check whose element has gone should FAIL, naming
    # what is missing; a check that throws kills the suite and the mutant
    # runner reports "inconclusive", which is the one verdict that tells you
    # nothing at all.
    DROP = """async (bytes) => {
      const z = document.getElementById('zzPh');
      if (!z) return { err: 'the drop zone has no id, so nothing can address it' };
      const f = new File([new Uint8Array(bytes.b)], bytes.n,
                         {type: bytes.t, lastModified: Date.UTC(2026,0,2,3,4)});
      const dt = new DataTransfer(); dt.items.add(f);
      z.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true}));
      await new Promise(r => setTimeout(r, 250));
      const live = document.querySelector('#hph [role="status"]');
      return { recs: window.__PH.get(), media: window.__PH.media(),
               said: live ? live.textContent : null }; }"""
    rec = pg.evaluate(DROP, {"b": [49,50,51,52,53,54,55,56,57], "n": "IMG_7.jpg",
                             "t": "image/jpeg"})
    ck("the drop zone is addressable and the drop lands: %r" % (rec.get("err"),),
       not rec.get("err"), rec.get("err"))
    if rec.get("err"):
        rec = {"recs": [], "media": "", "said": ""}
    # One record, read once and defended once: every claim below is about THIS
    # dict, and a missing one is a failed check rather than an IndexError that
    # takes the whole suite with it.
    _r0 = (rec["recs"] or [{}])[0]
    ck("a dropped image becomes ONE record carrying the four things that let a row and a frame be "
       "put back together: name, bytes, capture time, checksum -- plus `have`, which says whether "
       "this browser is holding the bytes or only the reference (v1.6.0, ADR-206)",
       len(rec["recs"]) == 1 and sorted(_r0.keys())
       == ["bytes", "captured", "crc", "have", "label", "name", "note"], rec["recs"])
    ck("and a frame this browser HOLDS says so", _r0.get("have") is True, _r0)
    ck("and the checksum is of the FILE'S BYTES, not of its name or its size",
       _r0.get("crc") == "cbf43926", _r0)
    ck("`captured` is the file's own timestamp, not the moment it was dropped",
       str(_r0.get("captured")).startswith("2026-01-0"), _r0.get("captured"))
    ck("THE RECORD IS THE REFERENCE, NOT THE IMAGE: no base64, no data URL, nothing that would turn "
       "a 40 kB export into a 4 MB one",
       _r0 and not any(isinstance(v, str) and ("base64" in v or v.startswith("data:"))
                       for v in _r0.values()), _r0)
    ck("media() is Darwin Core shaped -- identifiers OF the media, ' | ' separated because a "
       "filename may hold a comma",
       rec["media"] == "IMG_7.jpg (crc32 cbf43926, " + str(_r0.get("captured")) + ")", rec["media"])
    ck("and the addition is SAID, in the component's own live region",
       isinstance(rec["said"], str) and "1 photograph added" in rec["said"], rec["said"])

    # TWO frames, because a separator is invisible with one -- and the
    # separator is the whole reason this column can hold a filename with a
    # comma in it.
    rec2 = pg.evaluate(DROP, {"b": [65, 66], "n": "DJI_0192,edited.JPG", "t": "image/jpeg"})
    ck("a second frame joins the first rather than replacing it",
       len(rec2.get("recs") or []) == 2, rec2.get("recs"))
    ck("AND THE SEPARATOR IS ' | ', NOT A COMMA. Darwin Core concatenates identifiers into one "
       "field, and a filename is allowed to contain a comma -- joining on one makes a two-frame "
       "record split into three, three tools downstream, silently",
       isinstance(rec2.get("media"), str) and rec2["media"].count(" | ") == 1
       and "DJI_0192,edited.JPG" in rec2["media"], rec2.get("media"))

    bad = pg.evaluate(DROP, {"b": [1], "n": "notes.txt", "t": "text/plain"})
    ck("a file that is not an image is not added",
       len(bad.get("recs") or []) == 2, bad.get("recs"))
    ck("AND THE REFUSAL IS SAID AND NAMES THE FILE. A reader who dropped six and got four has to be "
       "able to find out which two and why -- a silent drop is the fault this kit spent two slices on",
       isinstance(bad.get("said"), str) and "not an image" in bad["said"]
       and "notes.txt" in bad["said"], bad.get("said"))

    ck("set() cannot put a photograph back: a page cannot hand a File to a file input, and a "
       "component that pretended to restore one would be restoring a caption",
       pg.evaluate("() => window.__PH.set([{name:'x.jpg'}])") is False, "")
    ck("clear() empties it",
       pg.evaluate("() => { window.__PH.clear(); return window.__PH.get().length; }") == 0, "")

    # ---- A RESTORE CANNOT BRING A PHOTOGRAPH BACK, AND MUST SAY SO (ADR-206) --
    #
    # set() refusing is right and, on its own, is the quiet version of the same
    # loss: a sheet the autosave restored comes back one frame short and the
    # reader believes their morning is whole. So the RECORDS survive, the
    # component says which frames it is missing, and it takes them back BY
    # CHECKSUM -- which is what makes the caption the reader typed survivable.
    pg.evaluate("() => window.__PH.clear()")
    back = pg.evaluate("""() => {
      const n = window.__PH.restore([
        {name:'IMG_7.jpg', bytes:9, captured:'2026-01-02 03:04', crc:'cbf43926',
         label:'voucher 114', note:'cap from above'},
        {name:'gone.jpg', bytes:4, captured:'', crc:'11111111', label:'', note:''}]);
      const box = document.querySelector('#hph .fek-await');
      return { n: n, awaiting: window.__PH.awaiting().length,
               recs: window.__PH.get(), media: window.__PH.media(),
               shown: box ? box.innerText : null }; }""")
    ck("A RESTORED SHEET SAYS WHICH PHOTOGRAPHS IT NO LONGER HOLDS. A page cannot hand a File back "
       "to a file input; a restore that came back quietly one frame short would leave the reader "
       "believing their morning is whole, which is the more expensive of the two failures",
       back["n"] == 2 and back["awaiting"] == 2, back)
    ck("...and it names them, with the checksum, where the reader can see it",
       isinstance(back.get("shown"), str) and "not on this device" in back["shown"]
       and "IMG_7.jpg" in back["shown"] and "cbf43926" in back["shown"], (back.get("shown") or "")[:140])
    ck("A FRAME THAT WAS TAKEN IS IN THE RECORD WHETHER OR NOT THIS BROWSER HOLDS IT, and `have` "
       "says which is which -- an export that dropped it would break the only link between the row "
       "and a file sitting on a camera",
       len(back["recs"]) == 2 and all(r.get("have") is False for r in back["recs"]), back["recs"])
    ck("and media() names both, because Darwin Core asks for identifiers and an identifier does not "
       "stop being one when the bytes are on a card",
       back["media"].count(" | ") == 1 and "IMG_7.jpg" in back["media"]
       and "gone.jpg" in back["media"], back["media"])

    # THE COMPONENT ANNOUNCES ITSELF. Adding a frame fires no `input` and no
    # `change` -- the file input is hidden and a drop is neither -- so before
    # ADR-206 every autosave in this kit sat still while a reader photographed,
    # and a session that was ONLY photographs was saved by nothing at all.
    heard = pg.evaluate("""async () => {
        let n = 0;
        const on = () => { n++; };
        document.addEventListener('fek-change', on, true);
        const z = document.getElementById('zzPh');
        if (!z) { document.removeEventListener('fek-change', on, true); return -1; }
        const f = new File([new Uint8Array([7,7,7])], 'ping.jpg', {type:'image/jpeg'});
        const dt = new DataTransfer(); dt.items.add(f);
        z.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true}));
        await new Promise(r => setTimeout(r, 300));
        document.removeEventListener('fek-change', on, true);
        return n; }""")
    ck("ADDING A PHOTOGRAPH ANNOUNCES ITSELF, with one bubbling event. A hidden file input and a "
       "drop fire neither `input` nor `change`, so an autosave listening for those sat still while "
       "a reader photographed four stations -- and a session that was only photographs was saved "
       "by nothing at all",
       heard >= 1, heard)
    pg.evaluate("""() => { window.__PH.clear();
        window.__PH.restore([{name:'IMG_7.jpg', bytes:9, captured:'2026-01-02 03:04',
          crc:'cbf43926', label:'voucher 114', note:'cap from above'},
          {name:'gone.jpg', bytes:4, captured:'', crc:'11111111', label:'', note:''}]); }""")

    again = pg.evaluate(DROP, {"b": [49,50,51,52,53,54,55,56,57], "n": "IMG_7 (1).jpg",
                               "t": "image/jpeg"})
    ck("the drop zone is still addressable for the return: %r" % (again.get("err"),),
       not again.get("err"), again.get("err"))
    if again.get("err"):
        again = {"recs": [], "media": "", "said": ""}
    _held = [r for r in (again["recs"] or []) if r.get("have")]
    ck("DROPPING THE SAME FILE BACK RETURNS THE CAPTION, MATCHED BY CHECKSUM AND NOT BY NAME. A "
       "camera roll renames on export and two cards both start at DSC_0001; the checksum is the "
       "only thing that says this is the frame the caption was written about",
       len(_held) == 1 and _held[0].get("label") == "voucher 114"
       and _held[0].get("note") == "cap from above", again["recs"])
    ck("...and the component says it matched one rather than silently swapping the caption in",
       isinstance(again.get("said"), str) and "matched by checksum" in again["said"],
       again.get("said"))
    ck("and the frame that did NOT come back is still listed as missing, alone",
       pg.evaluate("() => window.__PH.awaiting().map(x => x.name)") == ["gone.jpg"],
       pg.evaluate("() => window.__PH.awaiting()"))
    ck("a file whose bytes differ does NOT claim the caption, whatever it is called",
       pg.evaluate("""async () => {
         const z = document.getElementById('zzPh');
         if (!z) return 'the drop zone has no id, so nothing can address it';
         const f = new File([new Uint8Array([9,9,9,9])], 'gone.jpg', {type:'image/jpeg'});
         const dt = new DataTransfer(); dt.items.add(f);
         z.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true}));
         await new Promise(r => setTimeout(r, 250));
         const got = window.__PH.get().filter(r => r.have && r.name === 'gone.jpg');
         return got.length === 1 && got[0].label === '' && window.__PH.awaiting().length === 1;
       }""") is True,
       "a same-named file with different bytes took a caption that was not about it")
    ck("clear() forgets the awaited frames too, or a cleared sheet would keep asking for a "
       "photograph that belongs to work nobody has any more",
       pg.evaluate("""() => { window.__PH.clear();
         return [window.__PH.awaiting().length, window.__PH.get().length,
                 document.querySelector('#hph .fek-await').style.display]; }""")
       == [0, 0, "none"], "")

    ck("no errors after the run", not errs, errs[:2])
    b.close()

for x in F: print("FAIL:",x)
print("PASS",len(P))
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))

# A suite that cannot fail the run is not a check. This one printed its FAIL
# lines and exited zero, so run_all marked it green whatever it found -- for
# eleven suites in this kit, "green" meant "the process did not crash".
raise SystemExit(1 if F else 0)
