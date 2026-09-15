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

# FIXTURE-BUILDER (ADR-207). The temp directory this suite reaches for holds a
# CANARY -- two pages written here so the record-keeping rule can be watched
# firing on one and staying quiet on the other. They are fixtures, not kit
# pages, and nothing about them belongs in a coverage sweep.
MUTATE_ROLE = "fixture-builder"
import glob, importlib.util, io, os, re, shutil, sys, tempfile

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

# THE CONSUMER LIST IS THE EMITTER'S, NOT A SECOND ONE (ADR-204).
#
# It used to be five names written here. `keep_emit.py` inlines KEEP into
# EIGHT, so three pages -- the deployment log, the survey design and the
# greenhouse -- carried the autosave layer and this suite never opened them.
# That is ADR-141's defect again: a list only one reader reads. A page added to
# the kit tomorrow is covered on the day it is wired rather than on the day
# somebody remembers this file exists.
_kespec = importlib.util.spec_from_file_location(
    "keep_emit", os.path.join(TOOLS_DIR, "keep_emit.py"))
_ke = importlib.util.module_from_spec(_kespec)
_kespec.loader.exec_module(_ke)
CONSUMERS = list(_ke.CONSUMERS)

# READ OFF THE PAGES, NOT OFF A COUNT (ADR-207). The first version of this check
# asserted `len(CONSUMERS) >= 8`, which a mutant that dropped a page from the
# emitter's list walked straight past: sixteen is still at least eight. What the
# claim is actually about is whether the list COVERS the pages -- so it is
# compared against the pages that carry the block.
_inlined = sorted(os.path.basename(_p) for _p in
                  glob.glob(os.path.join(ROOT, "docs", "*.html"))
                  if "/* ---- Keep v" in io.open(_p, encoding="utf-8").read())
ck("EVERY PAGE THAT CARRIES THE AUTOSAVE IS A PAGE THIS SUITE OPENS, because the list is the "
   "emitter's rather than a second one kept here -- it was five against the emitter's eight, and "
   "the three it missed carried the layer untested: %s"
   % sorted(set(_inlined) - set(CONSUMERS)),
   sorted(CONSUMERS) == _inlined, (sorted(CONSUMERS), _inlined))

ck("tools/keep.py declares a version", bool(KEEPV), KEEPV)

# ---- the autosave banner may only ever print text WE wrote -----------------
# A mutation sweep dropped the esc() from `esc(lastErr)` in the failure banner
# and nothing caught it. That mutant is EQUIVALENT today, and the reason is the
# whole point: lastErr is never the exception's message. It is one of three
# string literals we chose, so there is nothing for esc() to escape and no
# runtime test can reach it -- I claimed in ADR-063 that forcing a
# markup-bearing throw would test it, and that was wrong, because the message
# never reaches the banner.
#
# What CAN go wrong is someone reaching for `e.message` to be more helpful. That
# single edit turns a constant into browser- and, through a crafted filename or
# URL, potentially attacker-influenced text on the same line the sweep just
# showed is unguarded. So the invariant is asserted where it lives: in the
# module, statically, once -- not in each of the pages that inline it.
KEEP_SRC = io.open(os.path.join(TOOLS_DIR, "keep.py"), encoding="utf-8").read()
def assignments(src):
    """Each `lastErr = ...` statement, whole, up to its terminating `;`.

    Scanned to the semicolon rather than to the newline because the
    QuotaExceededError ternary spans two lines, and a line-limited regex reads
    only its condition -- which would let `.message` on the second line through
    the check below."""
    out = []
    for m in re.finditer(r"lastErr\s*=", src):
        end = src.find(";", m.end())
        out.append(src[m.start(): end if end != -1 else len(src)])
    return out

ASSIGN = assignments(KEEP_SRC)
ck("keep.py assigns lastErr at all -- otherwise this check is vacuous",
   len(ASSIGN) >= 4, len(ASSIGN))
# The invariant, stated directly rather than by trying to decide what counts as
# a constant expression. A first cut wrote a constant() predicate and tripped
# over `var lastErr = null, savedAt = null, ...` and over the same ternary --
# writing a small JavaScript parser to check JavaScript, which ADR-062 is about.
LEAK = re.compile(r"\.\s*(message|stack|toString)\b")
leaks = [a.strip()[:70] for a in ASSIGN if LEAK.search(a)]
ck("no lastErr assignment reaches into the caught error's own text", not leaks, leaks)
# Both halves of the rule, asserted directly. Neither of these can be caught by
# mutating the tree: with keep.py clean there is nothing for the pattern to
# match and nothing spanning a line for the scanner to lose, so forcing either
# to fail changes no outcome (the ADR-059 shape). They are checked here instead.
ck("the leak pattern recognises a leak when it sees one",
   bool(LEAK.search("lastErr = e.message")) and bool(LEAK.search("lastErr = err.stack"))
   and not LEAK.search('lastErr = "storage is full"'), "")
ck("and the scanner takes a multi-line ternary whole, not just its first line",
   any("QuotaExceededError" in a and "refused the write" in a for a in ASSIGN),
   [a.strip()[:60] for a in ASSIGN])
ck("the banner still escapes it anyway, so the guard survives a future edit",
   "esc(lastErr)" in KEEP_SRC, "")
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
    for name in CONSUMERS:
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
        # v1.3.0 (ADR-209). THE LIVE HANDLE IS REACHABLE FROM OUTSIDE THE PAGE'S
        # OWN CLOSURE. Every page wires KEEP inside an IIFE and keeps the handle
        # in a local, so the one description of the page's state that the
        # autosave and the outbox both already read was reachable from nowhere
        # else -- and a reader that wanted to know how much a tap had just taken
        # had to count rows on the screen, where a record shown twice counts
        # twice. One description, read by everything that needs it (ADR-141).
        ck("%s exposes the live autosave handle" % name,
           pg.evaluate("()=>{try{ return typeof KEEP.live==='function' && !!KEEP.live(); }"
                       "catch(e){ return false; }}"), "")
        ck("%s answers the same description through the handle as the page keeps"
           % name,
           pg.evaluate("()=>{try{ var h=KEEP.live&&KEEP.live(); "
                       "return !!(h && typeof h.snapshot==='function' "
                       "&& typeof h.touch==='function'); }catch(e){ return false; }}"), "")

        # Nothing at all, rather than nothing under one known key: a page whose
        # storage key was renamed would pass a keyed check by writing somewhere
        # this suite was not looking.
        ck("%s saves nothing before anything is entered" % name,
           pg.evaluate("()=>Object.keys(localStorage).length") == 0,
           pg.evaluate("()=>Object.keys(localStorage)"))
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
    # Pressed only if it is there. A suite that TIMES OUT reaching for a control
    # reports nothing at all -- no pass, no fail, just a crash -- and a mutation
    # sweep that removes the button should be told what it broke rather than be
    # told the instrument fell over.
    have_forget = pg.eval_on_selector_all("#keepBox [data-keep-forget]", "e=>e.length") == 1
    ck("the button that removes the saved copy is there to be pressed",
       have_forget, "no [data-keep-forget] on the strip")
    if have_forget:
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

    # ---------------- A BROWSER THAT KEEPS NOTHING SAYS SO ----------------
    #
    # This is KEEP's most important sentence and, until ADR-204, the one thing
    # in this file that nothing asserted -- the suite's own comment eighty lines
    # down describes the behaviour and then uses it to explain a DIFFERENT
    # check. A private window, storage switched off, an enterprise policy and a
    # sandboxed frame all look identical to a page that only wraps setItem in a
    # try, and the entire reason this component exists is to tell those apart
    # from "saved" BEFORE the morning is lost rather than after.
    ctxn = b.new_context()
    pgn = ctxn.new_page()
    pgn.set_default_timeout(20000)
    offline(pgn)
    pgn.add_init_script("""Object.defineProperty(window,'localStorage',{get:function(){
        throw new Error('denied'); }});""")
    nerrs = []
    pgn.on("pageerror", lambda e: nerrs.append(str(e)))
    pgn.goto(url("releve.html"), wait_until="domcontentloaded")
    pgn.wait_for_timeout(900)
    strip = pgn.inner_text("#keepBox")
    ck("A BROWSER THAT IS KEEPING NOTHING SAYS SO, UP FRONT. Storage unavailable -- a private "
       "window, site data off, a policy -- must read as nothing being saved at the moment the page "
       "opens, not at the moment the work is lost",
       "not keeping anything" in strip, strip[:110])
    ck("and it says what to do instead, which is the only useful half of that news",
       "export before you close the tab" in strip.lower(), strip[:160])
    ck("and the strip is styled as the failure it is",
       pgn.eval_on_selector_all("#keepBox.bad", "e=>e.length") == 1, "")
    ck("KEEP.usable() answers honestly about a browser that throws on the accessor itself",
       pgn.evaluate("()=>KEEP.usable()") is False, "")
    ck("a page whose storage is gone still loads without throwing", not nerrs, nerrs[:2])
    pgn.close()
    ctxn.close()

    # ---------------- a tab closing mid-debounce -------------------------
    #
    # The case KEEP exists for, and nothing drove it. The write is debounced by
    # half a second, so a page hidden or closed in that window loses exactly the
    # edit the user made last -- which is the edit they remember making.
    pg, errs = page("releve.html")
    pg.evaluate("()=>localStorage.clear()")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(700)
    pg.click('.tab[data-pane="p-plot"]'); pg.wait_for_timeout(200)
    pg.evaluate(SET, ["sPlot", "PAGEHIDE-01"])
    pg.evaluate("()=>window.dispatchEvent(new Event('pagehide'))")
    pg.wait_for_timeout(80)
    raw = pg.evaluate("()=>localStorage.getItem('csrbtReleve')")
    ck("A TAB CLOSING MID-DEBOUNCE FLUSHES RATHER THAN LOSING THE LAST EDIT. The write waits half a "
       "second; a page hidden or closed inside that window would otherwise drop exactly the edit the "
       "user remembers making",
       raw is not None and "PAGEHIDE-01" in raw, (raw or "nothing was written")[:80])
    pg.evaluate("()=>localStorage.clear()")
    pg.close()

    # ---------------- a restore the page REFUSES -------------------------
    #
    # restore() returns false when the page cannot use the blob. The strip must
    # not then claim a restore that did not happen: "Restored your work from
    # today 09:14" over a sheet that is empty is the worst sentence this
    # component could produce.
    pg, errs = page("ordination.html")
    told = pg.evaluate("""()=>{
      const host=document.createElement('div'); host.id='__rbox';
      document.body.appendChild(host);
      localStorage.setItem("__r1", JSON.stringify({format:1, at:Date.now(), body:{v:1}}));
      KEEP.wire({key:"__r1", format:1, mount:"__rbox", noun:"a set",
        snapshot:function(){ return null; }, restore:function(){ return false; }});
      const t = host.innerText; host.remove(); localStorage.removeItem("__r1");
      return t; }""")
    ck("A RESTORE THE PAGE REFUSED IS NOT ANNOUNCED AS ONE. restore() returning false means the "
       "blob could not be used, and a strip that said `Restored your work` over a sheet that is "
       "still empty would be the worst sentence this component could produce",
       "Restored" not in told, told[:110])
    ck("and the refusing page is not left claiming a save either", "Saved on" not in told, told[:110])
    # ...and a restore that THREW is the same news. A page whose restore blew up
    # halfway has applied some unknown part of the blob; announcing that as a
    # restore is the same lie with a worse cause.
    threw = pg.evaluate("""()=>{
      const host=document.createElement('div'); host.id='__tbox';
      document.body.appendChild(host);
      localStorage.setItem("__t1", JSON.stringify({format:1, at:Date.now(), body:{v:1}}));
      KEEP.wire({key:"__t1", format:1, mount:"__tbox", noun:"a set",
        snapshot:function(){ return null; },
        restore:function(){ throw new Error("half-applied"); }});
      const t = host.innerText; host.remove(); localStorage.removeItem("__t1");
      return t; }""")
    ck("A RESTORE THAT THREW IS NOT ANNOUNCED AS ONE EITHER. A page whose restore blew up halfway "
       "has applied some unknown part of the blob, and calling that a restore is the same lie with "
       "a worse cause",
       "Restored" not in threw, threw[:110])
    ck("no page errors from the refused restore", not errs, errs[:2])
    pg.close()

    # ---------------- THE STRIP'S BUTTON SURVIVES A REPAINT (ADR-207) --------
    #
    # paint() wrote the whole strip with innerHTML, so the forget button was
    # destroyed and re-created every time the autosave changed state -- which is
    # every time it saves. A control that does not survive a repaint cannot be
    # stamped, addressed or kept in focus across one, and audit_focus reported
    # exactly that, intermittently, on whichever page happened to save while the
    # sweep was looking. An intermittent finding is the worst kind: it reads as
    # a flaky instrument rather than as the defect it is.
    pg, errs = page("releve.html")
    pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(700)
    del errs[:]
    same = pg.evaluate("""async () => {
        const b0 = document.querySelector('#keepBox [data-keep-forget]');
        if (!b0) return 'no forget button at rest';
        b0.dataset.marked = 'yes';
        const el = document.getElementById('sPlot');
        el.value = 'REPAINT-01';
        el.dispatchEvent(new Event('input', {bubbles:true}));
        await new Promise(r => setTimeout(r, 1200));
        const b1 = document.querySelector('#keepBox [data-keep-forget]');
        return { same: b0 === b1, marked: !!(b1 && b1.dataset.marked),
                 said: document.querySelector('#keepBox .st').textContent.slice(0, 40) }; }""")
    ck("THE STRIP'S BUTTON SURVIVES A REPAINT. Rewriting the strip with innerHTML destroys and "
       "re-creates it on every save, and a control that does not survive a repaint cannot be "
       "stamped, addressed or kept in focus across one -- which audit_focus reported as a page "
       "whose control could not be measured, intermittently, which reads as a flaky instrument "
       "rather than as the defect it is",
       isinstance(same, dict) and same.get("same") is True and same.get("marked") is True, same)
    ck("...and the words still changed, so this is not passing because nothing repainted",
       isinstance(same, dict) and "Saved on this device" in (same.get("said") or ""), same)
    ck("no errors from the repaint", not errs, errs[:2])
    pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
    pg.close()

    # ---------------- A PAGE THAT TAKES RECORDS KEEPS THEM (ADR-207) ---------
    #
    # Six pages accepted between eighteen and forty-seven typed values and kept
    # NONE of them: close the tab, lose the morning. One of them -- the
    # experiment guide, the page that takes more typed values than any other in
    # this kit -- carried the exact `try{ setItem }catch(e){}` that KEEP exists
    # to replace, and the check below that says "no silent setItem left" existed
    # the whole time and looked only at the pages that had ALREADY been
    # converted. A rule enforced over the converted set cannot find the
    # unconverted one.
    #
    # AND A RULE WITH NO VIOLATORS LEFT CANNOT SHOW THAT IT FIRES. Every page
    # keeps now, so the rule passes whether it is working or asleep -- which is
    # ADR-127's point about a refusal nobody has watched. It is run twice: over
    # the kit, where it must find nothing, and over a canary directory built
    # here, where it must find exactly the page that deserves it and leave the
    # one that does not.
    KEEPLESS = {
        "ecology-lab.html":
            "a workbench, not a record: every box ships with a worked example, and what a "
            "reader types into it is an exploration of the maths rather than something they "
            "made. The session files it charts come from the sheets, which keep.",
    }
    import harness as _H
    import harness_plugin_page as _PP
    _ENTRY = frozenset(_H.TYPED) | frozenset(["slider", "checkbox", "select"])
    _BAR = 4

    def keepless_in(dirpath):
        """Pages in a directory that take records and keep none. -> [(name, n)]"""
        out = []
        for _p in sorted(glob.glob(os.path.join(dirpath, "*.html"))):
            _n = os.path.basename(_p)
            _pg = ctx.new_page()
            _pg.set_default_timeout(20000)
            offline(_pg)
            _pg.goto("file://" + _p.replace(os.sep, "/"), wait_until="domcontentloaded")
            _pg.wait_for_timeout(400)
            try:
                _snap = _PP.PagePlugin(_pg, _n).observe(sensitive=True)
                _ent = len([c for c in _snap.get("controls", []) if c.get("kind") in _ENTRY])
            except Exception:
                _ent = 0
            _has = _pg.evaluate(
                "()=>typeof KEEP!=='undefined' && !!document.getElementById('keepBox')")
            _pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
            _pg.close()
            if _ent >= _BAR and not _has and _n not in KEEPLESS:
                out.append((_n, _ent))
        return out

    def silent_setitem_in(dirpath):
        """Pages whose own script still writes to storage without KEEP."""
        out = []
        for _p in sorted(glob.glob(os.path.join(dirpath, "*.html"))):
            src = io.open(_p, encoding="utf-8").read()
            if "localStorage.setItem" in src.split("/* ---- Keep v")[0]:
                out.append(os.path.basename(_p))
        return out

    # ---- the canary: a rule nobody has watched fire ----
    _cdir = tempfile.mkdtemp(prefix="keepcanary_")
    io.open(os.path.join(_cdir, "trap.html"), "w", encoding="utf-8").write(u"""<!doctype html>
<html><head><meta charset="utf-8"><title>trap</title></head><body>
<label>Plot <input type="text" id="a" aria-label="Plot"></label>
<label>Date <input type="date" id="b" aria-label="Date"></label>
<label>Count <input type="number" id="c" aria-label="Count"></label>
<label>Observer <input type="text" id="d" aria-label="Observer"></label>
<label>Notes <textarea id="e" aria-label="Notes"></textarea></label>
<script>try{ localStorage.setItem("trap", "1"); }catch(e){}</script>
</body></html>
""")
    io.open(os.path.join(_cdir, "quiet.html"), "w", encoding="utf-8").write(u"""<!doctype html>
<html><head><meta charset="utf-8"><title>quiet</title></head><body>
<label>Search <input type="text" id="q" aria-label="Search"></label>
<p>A reference page.</p>
</body></html>
""")
    _canary = keepless_in(_cdir)
    ck("THE RULE FIRES. A page that takes five typed values and mounts no autosave is named -- run "
       "against a canary built here, because every page in the kit keeps now and a rule with no "
       "violators left passes whether it is working or asleep",
       [n for n, _ in _canary] == ["trap.html"], _canary)
    ck("...and it does not name the page that is right to keep nothing. A rule that called every "
       "page without an autosave a loss would be switched off within a week, and then the real "
       "ones would be invisible again",
       "quiet.html" not in [n for n, _ in _canary], _canary)
    _csilent = silent_setitem_in(_cdir)
    ck("AND THE SILENT-setItem RULE FIRES TOO, against a page carrying the bare try/catch this "
       "component was built to replace -- the pattern that sat on the experiment guide for eleven "
       "slices beside a check that was looking somewhere else",
       _csilent == ["trap.html"], _csilent)
    shutil.rmtree(_cdir, ignore_errors=True)

    keepless = keepless_in(os.path.join(ROOT, "docs"))
    ck("EVERY PAGE THAT TAKES RECORDS KEEPS THEM. A page with %d or more controls you can put a "
       "value into either mounts the autosave or is named above with a reason -- six pages took "
       "between eighteen and forty-seven typed values and kept none of them, and the one with the "
       "most carried the bare try/catch this component was built to replace" % _BAR,
       not keepless, keepless)
    for _n, _why in KEEPLESS.items():
        ck("...and an exemption is a written judgement, not an absence: %s" % _n,
           len(_why) > 40 and os.path.exists(os.path.join(ROOT, "docs", _n)), _why[:60])

    # ---------------- A RESTORE CANNOT BRING A PHOTOGRAPH BACK (ADR-206) ------
    #
    # Four sheets mounted FEK.photos and kept nothing at all, so a reader could
    # photograph four stations, score an hour, take a phone call and lose the
    # lot. They keep now -- and a page cannot hand a File back to a file input,
    # so what survives is the RECORD of each frame. A sheet that came back
    # quietly one frame short would leave the reader believing their morning is
    # whole, which is the more expensive of the two failures.
    #
    # The wiring is checked on EVERY page that has both, statically, because
    # this is exactly the shape ADR-201 lost for a season: a page whose snapshot
    # forgot to carry the frames would restore perfectly and lose them, and
    # nothing on screen would say so.
    # DRIVEN, NOT SPELLED. The first version of this check looked for
    # `photos:PHOTOS.get()` in the source and failed three pages that carry the
    # frames through a local variable -- a check about spelling rather than
    # about behaviour, which is the kind that gets edited to match the code
    # instead of the other way round. Every page that mounts the component gets
    # a frame dropped on it, a save, a reload, and one question: does it say
    # what it no longer holds?
    SHOOT = """async (z) => {
        const el = document.getElementById(z);
        if (!el) return 'no drop zone #' + z;
        const f = new File([new Uint8Array([49,50,51,52,53,54,55,56,57])], 'KEEP_7.jpg',
                           {type:'image/jpeg', lastModified: Date.UTC(2026,0,2,3,4)});
        const dt = new DataTransfer(); dt.items.add(f);
        el.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true}));
        await new Promise(r => setTimeout(r, 350));
        return null; }"""
    for name in CONSUMERS:
        src = io.open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()
        m = re.search(r'FEK\.photos\(\{\s*dropId:"([A-Za-z0-9_]+)"', src)
        if not m:
            continue
        zone = m.group(1)
        pg, errs = page(name)
        pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
        pg.reload(wait_until="domcontentloaded")
        pg.wait_for_timeout(800)
        del errs[:]
        why = pg.evaluate(SHOOT, zone)
        pg.wait_for_timeout(1400)
        stored = pg.evaluate("()=>JSON.stringify(Object.keys(localStorage).map("
                             "function(k){return localStorage.getItem(k);}))")
        ck("%s CARRIES ITS PHOTOGRAPHS INTO THE AUTOSAVE. A snapshot that forgot them would "
           "restore perfectly and lose every frame, with nothing on screen saying so" % name,
           why is None and "cbf43926" in (stored or ""), why or (stored or "")[:80])
        pg.close()

        pg, errs = page(name)
        pg.wait_for_timeout(700)
        aw = pg.inner_text(".fek-await") if pg.eval_on_selector_all(".fek-await", "e=>e.length") \
            else "(no missing-frames block on the page)"
        ck("%s SAYS WHICH PHOTOGRAPH IT NO LONGER HOLDS, naming the file and its checksum. The "
           "bytes cannot come back; a sheet that came back quietly one frame short would leave "
           "the reader believing their morning is whole" % name,
           "not on this device" in aw and "KEEP_7.jpg" in aw and "cbf43926" in aw, aw[:130])
        ck("%s restores a photographed sheet without throwing" % name, not errs, errs[:2])
        pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
        pg.close()

    pg, errs = page("field-notebook.html")
    pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(800)
    del errs[:]
    pg.evaluate("""()=>{const bs=[...document.querySelectorAll('#ethoGrid .tally')];
        bs[0].click(); bs[0].click(); bs[1].click();}""")
    pg.evaluate("""async () => {
        const z = document.getElementById('fnPhotos');
        const f = new File([new Uint8Array([49,50,51,52,53,54,55,56,57])], 'IMG_44.jpg',
                           {type:'image/jpeg', lastModified: Date.UTC(2026,0,2,3,4)});
        const dt = new DataTransfer(); dt.items.add(f);
        z.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true}));
        await new Promise(r => setTimeout(r, 300)); }""")
    pg.evaluate("""()=>{const l=[...document.querySelectorAll('.fek-photo .m input[type=text]')];
        if(l[0]){ l[0].value='quadrat 3'; l[0].dispatchEvent(new Event('input',{bubbles:true})); }}""")
    pg.wait_for_timeout(1300)
    raw = pg.evaluate("()=>localStorage.getItem('csrbtFieldNotebook')")
    ck("a sheet with photographs on it saves the frames' RECORDS, checksum and caption included",
       raw and "cbf43926" in raw and "quadrat 3" in raw, (raw or "")[:120])
    pg.close()

    pg, errs = page("field-notebook.html")
    pg.wait_for_timeout(700)
    ck("what was tallied comes back",
       pg.evaluate("""()=>[...document.querySelectorAll('#ethoGrid .tally')]
           .slice(0,2).map(b=>b.querySelector('.count').textContent)""") == ["2", "1"],
       pg.evaluate("""()=>[...document.querySelectorAll('#ethoGrid .tally')]
           .slice(0,2).map(b=>b.querySelector('.count').textContent)"""))
    aw = pg.inner_text(".fek-await") if pg.eval_on_selector_all(".fek-await", "e=>e.length") else ""
    ck("AND THE PAGE SAYS, OUT LOUD, WHICH PHOTOGRAPH IT NO LONGER HOLDS, naming the file and its "
       "checksum. The bytes are gone; the record, the caption and the way to put them back together "
       "are not",
       "not on this device" in aw and "IMG_44.jpg" in aw and "cbf43926" in aw, aw[:150])
    ck("the restored sheet raises nothing", not errs, errs[:2])
    pg.evaluate("()=>localStorage.clear()")
    pg.close()

    # ---------------- A RESTORED SHEET KEEPS ITS OWN DATE (ADR-206) ---------
    #
    # Most of these pages date themselves from the clock at load. A sheet the
    # autosave brings back must NOT be re-dated: the observations were made on
    # the day the session was started, and a page that stamped today's date
    # over yesterday's fieldwork would be falsifying a record rather than
    # restoring one. The ethogram's kappa task had to drop its saved copy
    # before freezing the clock for exactly this reason; the behaviour it
    # worked around is asserted here rather than only avoided.
    pg, errs = page("ethogram.html")
    pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(800)
    del errs[:]
    pg.evaluate(SET, ["dDate", "2026-03-01"])
    pg.evaluate(SET, ["dObs", "R. Test"])
    pg.wait_for_timeout(1200)
    pg.close()
    pg, errs = page("ethogram.html")
    pg.wait_for_timeout(700)
    ck("A RESTORED SHEET KEEPS THE DATE IT WAS STARTED ON. These pages date themselves from the "
       "clock at load; stamping today over yesterday's fieldwork would be falsifying a record "
       "rather than restoring one",
       pg.input_value("#dDate") == "2026-03-01", pg.input_value("#dDate"))
    ck("and the observer with it", pg.input_value("#dObs") == "R. Test", pg.input_value("#dObs"))
    ck("restoring a dated sheet raises nothing", not errs, errs[:2])
    pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
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
    # EVERY PAGE, NOT EVERY CONSUMER (ADR-207) -- and the finder above is the
    # one doing the looking, so the canary that proves it fires proves this too.
    for _p in sorted(glob.glob(os.path.join(ROOT, "docs", "*.html"))):
        name = os.path.basename(_p)
        src = io.open(_p, encoding="utf-8").read()
        ck("%s no longer says it loses your data" % name,
           "closing the tab loses" not in src and "does not save your data" not in src, "")
    ck("NO PAGE IN THE KIT HAS A SILENT setItem LEFT. A full quota, a private window and storage "
       "disabled by policy all look identical to a page that only wraps setItem in a try -- nothing "
       "saved, nothing said, which is the whole bug KEEP exists to replace",
       not silent_setitem_in(os.path.join(ROOT, "docs")),
       silent_setitem_in(os.path.join(ROOT, "docs")))

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
