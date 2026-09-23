# -*- coding: utf-8 -*-
import sys, math
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
def ck(n,c,e=""):
    (P if c else F).append(n+(("  << "+str(e)) if (e and not c) else ""))

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":820,"height":1200})
    pg.set_default_timeout(15000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    def _con(m):
        if m.type!="error": return
        # the font CDN is unreachable here and this test aborts it deliberately
        if "ERR_CONNECTION" in m.text or "ERR_FAILED" in m.text or "fonts.g" in m.text: return
        errs.append(m.text)
    pg.on("console", _con)
    pg.goto(_u("ethogram.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(400)
    ck("no startup errors", not errs, errs[:3])

    tabs=pg.eval_on_selector_all(".tab","e=>e.map(x=>x.textContent.trim())")
    ck("5 tabs", len(tabs)==5, tabs)
    ck("default ethogram loaded",
       pg.eval_on_selector_all("#stateGrid .bb","e=>e.length")==7,
       pg.eval_on_selector_all("#stateGrid .bb","e=>e.length"))
    ck("8 events", pg.eval_on_selector_all("#eventGrid .bb","e=>e.length")==8,
       pg.eval_on_selector_all("#eventGrid .bb","e=>e.length"))
    ck("out-of-sight is a state", "out of sight" in pg.inner_text("#stateGrid"), "")

    # ---------- design coherence warnings ----------
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(200)
    def pick(host,label):
        pg.evaluate("""([h,l])=>{const b=[...document.querySelectorAll('#'+h+' .kopt')]
          .find(x=>x.textContent.toLowerCase().startsWith(l.toLowerCase())); if(!b) throw new Error('no '+l); b.click();}""",[host,label])
    pick("dSample","scan"); pick("dRecord","continuous"); pg.wait_for_timeout(150)
    ck("scan+continuous flagged incoherent",
       "Scan sampling cannot be continuous" in pg.inner_text("#coherence"), pg.inner_text("#coherence")[:120])
    pick("dRecord","one-zero"); pg.wait_for_timeout(150)
    ck("one-zero flagged biased", "biased number" in pg.inner_text("#coherence"), pg.inner_text("#coherence")[:150])
    pick("dSample","ad libitum"); pg.wait_for_timeout(150)
    ck("ad libitum flagged not-a-rate", "not a source of rates" in pg.inner_text("#coherence"), "")
    pick("dSample","focal"); pick("dRecord","continuous"); pg.wait_for_timeout(150)
    ck("focal+continuous is coherent", pg.inner_text("#coherence").strip()=="", pg.inner_text("#coherence")[:120])

    # ---------- continuous focal: known-answer time budget ----------
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(200)
    pg.click("#rStart"); pg.wait_for_timeout(50)
    def tapstate(name):
        pg.evaluate("""(n)=>{const b=[...document.querySelectorAll('#stateGrid .bb')]
          .find(x=>x.querySelector('.nm').textContent.trim()===n); b.click();}""", name)
    def tapevent(name):
        pg.evaluate("""(n)=>{const b=[...document.querySelectorAll('#eventGrid .bb')]
          .find(x=>x.querySelector('.nm').textContent.trim()===n); b.click();}""", name)
    tapstate("forage"); pg.wait_for_timeout(1000)
    tapstate("vigilant"); pg.wait_for_timeout(500)
    tapevent("alarm"); tapevent("alarm")
    tapstate("out of sight"); pg.wait_for_timeout(600)
    tapstate("forage"); pg.wait_for_timeout(900)
    pg.click("#rStop"); pg.wait_for_timeout(300)

    pg.click('.tab[data-pane="p-bud"]'); pg.wait_for_timeout(300)
    # The budget pane recomputes the transition matrix on tab-switch, and that
    # render is heavy enough that a fixed 300ms settle raced the read under
    # -j2 CPU contention -- #transBox came back empty and every transBox claim
    # failed as a phantom regression (ADR-143: a flake is a measurement of the
    # test, not the page). Wait for the panes to be populated instead of
    # guessing a duration: a real regression that never renders them still
    # fails, now at the 15s default timeout rather than at 300ms.
    pg.wait_for_function(
        "() => { const t=document.querySelector('#transBox'),"
        " b=document.querySelector('#budBox');"
        " return t && b && /Transitions/.test(t.textContent)"
        " && /forage/.test(b.textContent); }")
    bud=pg.inner_text("#budBox")
    ck("budget lists forage", "forage" in bud, bud[:200])
    ck("budget lists vigilant", "vigilant" in bud, "")
    ck("out-of-sight excluded from denominator", "excluded from the denominator" in bud, bud[-300:])
    # forage ~1.9s of ~2.4s observed -> ~79%; vigilant ~0.5 -> ~21%; must sum to 100
    pcts = pg.evaluate("""()=>[...document.querySelectorAll('#budBox table tr')].slice(1)
        .map(r=>parseFloat(r.children[2].textContent))""")
    ck("budget percentages sum to 100", abs(sum(pcts)-100)<0.6, pcts)
    ck("forage is the largest share", pcts and pcts[0]>50, pcts)
    # ADR-240: read the table's rows, not a slice of the box text -- the old
    # slice ended at the last word "elapsed", which the fixed note no longer says.
    _rows0 = pg.evaluate("()=>[...document.querySelectorAll('#budBox table tr')].slice(1).map(r=>r.children[0].textContent)")
    ck("oos not a budget row", "out of sight" not in _rows0, _rows0)
    rate=pg.inner_text("#rateBox")
    ck("event rate computed for alarm", "alarm" in rate, rate[:200])
    ck("rates are per observed minute", "observed" in rate, "")
    ck("transitions rendered", "Transitions" in pg.inner_text("#transBox"), "")
    ck("transition diagonal struck out", "—" in pg.inner_text("#transBox"), "")
    ck("first-order caveat stated", "first-order" in pg.inner_text("#transBox"), "")
    ck("pseudoreplication warning (one subject)", "one individual" in pg.inner_text("#budBox"), pg.inner_text("#budBox")[-250:])

    # ---------- instantaneous: SE + no event rate ----------
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(150)
    pick("dSample","scan"); pick("dRecord","instantaneous"); pg.wait_for_timeout(150)
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(200)
    ck("scan box appears in point mode", "Scan" in pg.inner_text("#scanBox"), pg.inner_text("#scanBox")[:80])
    ck("point mode: rate guidance shown before any data",
       "cannot give a rate" in pg.inner_text("#rateBox"), pg.inner_text("#rateBox")[:150])
    # take two real point samples, then re-check
    pg.click("#rStart"); pg.wait_for_timeout(60)
    pg.evaluate("""()=>{const b=[...document.querySelectorAll('#stateGrid .bb')]
      .find(x=>x.querySelector('.nm').textContent.trim()==='forage'); b.click();}""")
    pg.click("#rStop"); pg.wait_for_timeout(200)
    pg.click('.tab[data-pane="p-bud"]'); pg.wait_for_timeout(250)
    ck("point mode: still no rate from points",
       "cannot give a rate" in pg.inner_text("#rateBox"), pg.inner_text("#rateBox")[:150])
    ck("point mode reports SE", "SE" in pg.inner_text("#budBox"), pg.inner_text("#budBox")[:250])

    # ---------- one-zero refuses to become a budget ----------
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(150)
    pick("dRecord","one-zero"); pg.wait_for_timeout(150)
    pg.click('.tab[data-pane="p-bud"]'); pg.wait_for_timeout(250)
    oz=pg.inner_text("#budBox")
    ck("one-zero labelled as such", "one-zero scores" in oz, oz[:200])
    ck("one-zero refuses budget/rate conversion", "not a time budget" in oz, oz[:400])

    # ---------- Cohen's kappa: known answer ----------
    # A: F F V R L F V V R F   B: F V V R L F V R R F
    # agree on 8/10 -> po=0.8
    # A marg: F4 V3 R2 L1 ; B marg: F3 V3 R3 L1
    # pe = (4*3 + 3*3 + 2*3 + 1*1)/100 = (12+9+6+1)/100 = 0.28
    # k = (0.8-0.28)/(1-0.28) = 0.52/0.72 = 0.72222
    pg.click('.tab[data-pane="p-rel"]'); pg.wait_for_timeout(200)
    pg.fill("#kA","F F V R L F V V R F")
    pg.fill("#kB","F V V R L F V R R F")
    pg.click("#kGo"); pg.wait_for_timeout(250)
    def tv(lab):
        return pg.evaluate("""(l)=>{const t=[...document.querySelectorAll('#kOut .tile')]
            .find(x=>x.querySelector('.l').textContent.trim()===l); return t?t.querySelector('.v').textContent.trim():null;}""",lab)
    ck("kappa = 0.722", tv("Cohen's κ")=="0.722", tv("Cohen's κ"))
    ck("raw agreement 80.0%", tv("raw agreement")=="80.0%", tv("raw agreement"))
    ck("expected by chance 28.0%", tv("expected by chance")=="28.0%", tv("expected by chance"))
    ck("n samples 10", tv("samples")=="10", tv("samples"))
    kout=pg.inner_text("#kOut")
    ck("Landis&Koch labelled a convention", "convention" in kout and "arbitrary" in kout, kout[:300])
    ck("small-n warning at n=10", "samples is few" in kout, kout[-200:])
    ck("confusion matrix rendered", "Confusion matrix" in pg.inner_text("#kMatrix"), "")
    ck("commonest disagreement named", "commonest disagreement" in pg.inner_text("#kMatrix"), "")
    # length mismatch
    pg.fill("#kB","F V V"); pg.click("#kGo"); pg.wait_for_timeout(200)
    ck("length mismatch caught", "Different lengths" in pg.inner_text("#kOut"), pg.inner_text("#kOut")[:120])

    # ---------- method tab ----------
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(200)
    m=pg.inner_text("#p-met")
    for t in ["Altmann","ad libitum","focal animal","one-zero","Landis","pseudoreplication","first-order Markov"]:
        ck("method covers "+t, t.lower() in m.lower(), "")
    ck("observed-vs-elapsed explained", "Observed time is not elapsed time" in m, "")

    # ---------- ethogram import validation ----------
    ck("import accepts json", pg.eval_on_selector("#packFile","e=>e.accept.indexOf('json')>=0"), "")
    ck("AI prompt button present", pg.eval_on_selector("#packPrompt","e=>!!e"), "")

    # ---------- viewport ----------
    for w,hh,lbl in [(390,844,"phone"),(768,1024,"tablet")]:
        pg.set_viewport_size({"width":w,"height":hh})
        for pane in ["p-rec","p-des","p-bud","p-rel","p-met"]:
            pg.click('.tab[data-pane="%s"]'%pane); pg.wait_for_timeout(120)
            ow=pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            ck("no h-overflow %s %s"%(lbl,pane), ow<=w+1, "%d > %d"%(ow,w))
    pg.set_viewport_size({"width":390,"height":844})
    small=pg.evaluate("""()=>{const bad=[];document.querySelectorAll('button, select, input, a').forEach(e=>{
        const r=e.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.height<43) bad.push(e.tagName+'.'+(e.className||''));});
        return bad.slice(0,5);}""")
    ck("touch targets >= 43px", not small, small)
    ck("no errors at end", not errs, errs[:3])
    # ---------------- FEK migration ----------------
    ck("FEK version matches fek.py", pg.evaluate("()=>typeof FEK!=='undefined'&&FEK.version")==_fek_version(), "")
    ck("no legacy select anywhere", pg.eval_on_selector_all("select","e=>e.length")==0,
       pg.eval_on_selector_all("select","e=>e.map(x=>x.id)"))
    pg.click('.tab[data-pane="p-des"]'); pg.wait_for_timeout(300)
    ck("timing is FEK", pg.eval_on_selector_all("#timeEntry .fek-step","e=>e.length")==2, "")
    ck("behaviour kind is a FEK dial", pg.eval_on_selector_all("#kindEntry .fek-dial","e=>e.length")==1, "")
    ck("interval defaults to 30 s",
       pg.evaluate("()=>document.querySelectorAll('#timeEntry .fek-step .val')[0].value")=="30",
       pg.evaluate("()=>document.querySelectorAll('#timeEntry .fek-step .val')[0].value"))
    pg.evaluate("""()=>{const s=document.querySelectorAll('#timeEntry .fek-step .val')[0];
      s.value='15'; s.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(250)
    ck("interval writes through", pg.evaluate("()=>document.getElementById('dScan').value")=="15",
       pg.evaluate("()=>document.getElementById('dScan').value"))
    ck("interval is clamped above zero",
       pg.evaluate("""()=>{const s=document.querySelectorAll('#timeEntry .fek-step .val')[0];
         s.value='0'; s.dispatchEvent(new Event('input',{bubbles:true}));
         s.dispatchEvent(new Event('blur',{bubbles:true}));
         return document.getElementById('dScan').value;}""")!="0",
       pg.evaluate("()=>document.getElementById('dScan').value"))
    pg.evaluate("""()=>{const s=document.querySelectorAll('#timeEntry .fek-step .val')[0];
      s.value='30'; s.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(200)
    ck("state/event distinction carried in the control",
       "cannot give you a rate" in pg.inner_text("#kindEntry"), pg.inner_text("#kindEntry")[-160:])
    pg.evaluate("""()=>{const d=document.querySelector('#kindEntry .fek-dial');
      [...d.querySelectorAll('button')].find(b=>b.querySelector('span').textContent.trim()==='event').click();}""")
    pg.wait_for_timeout(200)
    ck("kind dial writes through", pg.evaluate("()=>document.getElementById('eKind').value")=="event",
       pg.evaluate("()=>document.getElementById('eKind').value"))
    pg.click('.tab[data-pane="p-met"]'); pg.wait_for_timeout(250)
    m=pg.inner_text("#p-met").replace("\u00a0"," ")
    for t in ["Field Entry Kit","it is not a design","proportion of time","cannot give you a rate"]:
        ck("method documents "+t, t in m, m[:200])

    b.close()

# ---------- ADR-240: the budget's second number, the sheet's bouts, the CSV's whole ----------
# Driven through the door against a stepped clock, exactly as the task drives
# it, so every figure below is arithmetic on known durations and not on how
# long a click took. The statements are made HERE, from the durations, not read
# off the page: forage 20-95 and 155-230 (02:30), vigilant 95-155 and 320-380
# (02:00), out of sight 230-260 (00:30), rest 260-320 (01:00); aggress at 140,
# alarm at 200 and 350; stop at 380, so 00:20 of the session is in no state.
import io as _io, json as _json, re as _re
sys.path.insert(0, _os.path.join(ROOT, "tools"))
import harness_plugin_page as _PP
import harness as _H
_STATES = [(20, 95, "forage"), (95, 155, "vigilant"), (155, 230, "forage"), (230, 260, "out of sight"),
           (260, 320, "rest"), (320, 380, "vigilant")]
_TAPS = [(20, "state", "forage"), (95, "state", "vigilant"), (140, "event", "aggress"), (155, "state", "forage"),
         (200, "event", "alarm"), (230, "state", "out of sight"), (260, "state", "rest"), (320, "state", "vigilant"),
         (350, "event", "alarm")]
_STOP = 380
_obs = sum(t1 - t0 for t0, t1, n in _STATES if n != "out of sight")          # 330
_oos = sum(t1 - t0 for t0, t1, n in _STATES if n == "out of sight")          # 30
_gap = _STOP - (_obs + _oos)                                                  # 20
_bouts = {}
for t0, t1, n in _STATES:
    if n != "out of sight": _bouts[n] = _bouts.get(n, 0) + 1
_events = {}
for t, k, n in _TAPS:
    if k == "event": _events[n] = _events.get(n, 0) + 1
def _mmss(sec): return "%02d:%02d" % (sec // 60, sec % 60)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport=_H.VIEWPORT); ctx.set_offline(True)
    ctx.add_init_script(_H.STUBS); ctx.add_init_script(_H.DETERMINISM)   # the clock the door steps
    pg = ctx.new_page()
    plug = _PP.PagePlugin(pg, "ethogram.html")
    plug.execute("open", {"page": "ethogram.html"}); plug.observe()
    plug.execute("show-pane", {"pane": "p-des"})
    plug.execute("activate", {"selector": "@dSample/focal animal"})
    plug.execute("activate", {"selector": "@dRecord/continuous"})
    def _clock(sec, running=True):
        was = pg.evaluate("() => document.getElementById('clock').textContent")
        plug.execute("set-clock", {"at": "2026-09-07T09:%02d:%02dZ" % (sec // 60, sec % 60)})
        # the page reads the clock on its own 200 ms loop and re-renders the
        # grid at a scan boundary; wait until its clock has MOVED (the same
        # tick did the rebuild), or the tap races the rebuild -- a fixed wait
        # lost that race under -j2 contention. Before Start nothing ticks.
        if running:
            pg.wait_for_function("(w) => document.getElementById('clock').textContent !== w", arg=was, timeout=5000)
        pg.wait_for_timeout(50)
    _clock(0, running=False); plug.execute("show-pane", {"pane": "p-rec"}); plug.execute("activate", {"selector": "#rStart"})
    for t, k, n in _TAPS:
        _clock(t); plug.execute("activate", {"selector": "@%sGrid/%s" % (k, n)})
    _clock(_STOP); plug.execute("activate", {"selector": "#rStop"})
    plug.execute("show-pane", {"pane": "p-bud"})
    _ok, _m, rep = plug.execute("read-report", {})
    bud = rep["boxes"].get("budBox", "")
    ck("ADR-240 the budget note does not call the time in a state 'elapsed'",
       _re.search(r"not %s elapsed" % _mmss(_obs + _oos), bud) is None, bud[-400:])
    ck("ADR-240 the budget note names the second number as time in a state, observed plus out of sight",
       ("not the %s in a state (observed plus out of sight)" % _mmss(_obs + _oos)) in bud, bud[-400:])
    ck("ADR-240 ...and names the time the session ran, which is a third number",
       ("and not the %s the session ran" % _mmss(_STOP)) in bud and _STOP != _obs + _oos, bud[-400:])
    ck("ADR-240 the three numbers are the tiles' (elapsed / observed / out of sight)",
       rep["by"].get("budBox", {}).get("elapsed") == _mmss(_STOP)
       and rep["by"]["budBox"].get("observed") == _mmss(_obs)
       and rep["by"]["budBox"].get("out of sight") == _mmss(_oos), rep["by"].get("budBox"))
    # the session sheet
    plug.execute("activate", {"selector": "#ecoCopy"})
    _ok, _m, out = plug.execute("collect-output", {})
    sheet = (out["payloads"] or [{}])[0].get("text", "")
    ck("ADR-240 the sheet says 'bout' of one and 'bouts' of two",
       ("   %d bout\n" % 1 in sheet + "\n") and "   2 bouts" in sheet and "1 bouts" not in sheet,
       [l for l in sheet.split("\n") if "bout" in l])
    ck("ADR-240 every state's bout count on the sheet is the count of its segments",
       all(_re.search(r"^  %s\s+\S+\s+\S+\s+%d bouts?$" % (_re.escape(n), c), sheet, _re.M) for n, c in _bouts.items()),
       [l for l in sheet.split("\n") if "bout" in l])
    ck("ADR-240 the sheet names the out-of-sight time it excluded",
       ("  out of sight        %s   excluded from the denominator" % _mmss(_oos)) in sheet, sheet[:600])
    ck("ADR-240 ...and the time in no state, which is elapsed minus the time in a state",
       ("  in no state         %s   before the first state or after the last" % _mmss(_gap)) in sheet, sheet[:600])
    ck("ADR-240 so the sheet's lines add up to the clock",
       _mmss(_obs) in sheet and ("# elapsed %s   observed %s" % (_mmss(_STOP), _mmss(_obs))) in sheet, sheet[:300])
    # the budget CSV
    plug.execute("activate", {"selector": "#budCopy"})
    _ok, _m, out = plug.execute("collect-output", {})
    csv = (out["payloads"] or [{}])[0].get("text", "")
    rows = [l.split(",") for l in csv.split("\n")]
    ck("ADR-240 the budget CSV has an out-of-sight row carrying the seconds excluded and the in-a-state total",
       ["out of sight", "state", "seconds_excluded", "%.1f" % _oos, "%.1f s in a state" % (_obs + _oos)] in rows, rows)
    for n, c in _events.items():
        ck("ADR-240 the budget CSV carries %s's rate per observed minute, with its count and denominator" % n,
           [n, "event", "per_observed_min", "%.3f" % (c / (_obs / 60.0)), "%d events / %.1f min observed" % (c, _obs / 60.0)] in rows,
           [r for r in rows if r and r[0] == n])
    ck("ADR-240 the CSV's state percentages are of observed time and sum to 100",
       abs(sum(float(r[3]) for r in rows if len(r) > 3 and r[2] == "pct_observed_time") - 100) < 0.02
       and all(r[4] == "%.1f s observed" % _obs for r in rows if len(r) > 4 and r[2] == "pct_observed_time"), rows)
    ck("ADR-240 the rate the CSV carries is the rate the page shows",
       rep["tables"].get("rateBox", [[]])[1][2] == "%.3f" % (_events["alarm"] / (_obs / 60.0)),
       rep["tables"].get("rateBox"))
    # instantaneous: the excluded points are a row too
    plug.execute("show-pane", {"pane": "p-des"})
    plug.execute("activate", {"selector": "@dSample/scan"})
    plug.execute("activate", {"selector": "@dRecord/instantaneous"})
    _clock(400, running=False); plug.execute("show-pane", {"pane": "p-rec"}); plug.execute("activate", {"selector": "#rStart"})
    for t, n in [(401, "forage"), (461, "out of sight"), (521, "forage"), (581, "vigilant")]:   # one point per 60 s scan
        _clock(t); plug.execute("activate", {"selector": "@stateGrid/%s" % n})
    _clock(640); plug.execute("activate", {"selector": "#rStop"})
    plug.execute("show-pane", {"pane": "p-bud"})
    plug.execute("activate", {"selector": "#budCopy"})
    _ok, _m, out = plug.execute("collect-output", {})
    csv2 = (out["payloads"] or [{}])[0].get("text", "")
    rows2 = [l.split(",") for l in csv2.split("\n")]
    ck("ADR-240 in point mode the out-of-sight points dropped from n are a row of the budget CSV",
       ["out of sight", "state", "points_excluded", "1", "4 points taken"] in rows2
       and any(r[:3] == ["forage", "state", "pct_of_points"] and r[4] == "3 points" for r in rows2), rows2)
    b.close()

print("PASS %d"%len(P))
for x in F: print("FAIL:",x)
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
sys.exit(1 if F else 0)
