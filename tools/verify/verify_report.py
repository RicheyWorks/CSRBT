# -*- coding: utf-8 -*-
"""The report, read (ADR-128).

A task about a data-entry page ends by reading the page's report and holding
its figures to a hand-checked oracle. That is only as good as the reading:
a figure the reader skips is an arithmetic error nobody can catch, a picker
that takes the wrong option is data entered under the wrong name, a control
a task cannot name is a field the harness cannot enter. This suite seeds the
reader on fixture pages whose report is known and asserts every clause of
read-report, pick and the snapshot's naming, in process (one browser, no
gateway child), so the mutant runner can afford to run it many times.

  A. read-report: every .l/.v pair is a figure whatever its class, flat
     (first wins, then " #2") and by the box it sits in; a value's <small>
     unit is spaced off; boxes are the kit's id conventions -- an*, *Out,
     *Box, *Stats, *Note, *List, *Table, hyphenated and lower-case names,
     toast -- read whether or not their pane is open, with the visible ones
     named; every table's cells; every .row2 list's count; the headings in
     order; nothing outside the conventions
  B. pick: exact label first, then prefix, then the sole option the filter
     left; two or more left is refused as ambiguous, none as no match; the
     option's <small> sub-line never matches; the snapshot publishes each
     picker's option labels as an argument-set pool
  C. naming: a control carries its id, its nearest identified ancestor and
     the label a finger reads -- aria-label, a .nm child, or the text with
     <small>/<kbd> removed -- so "@control:rCov/4" can be formed
  D. on a real page: the collection sheet's analysis is read behind its
     closed tab, a genus picked by prefix is the genus the sheet records,
     and the experiment guide's aria-controls tabs open their panes
  F. addresses (ADR-188): every control publishes the shortest name that
     resolves back to it, the door accepts that name wherever it takes a
     selector and answers exactly as the runner's find_control does, a
     positional selector may be stamped with the snapshot it came from and
     is refused when the numbering has moved, and a name that resolves is
     never raised to DESTRUCTIVE for being unresolvable
  G. settling (ADR-189): a page that has just been navigated to is stamped
     and waited on before the first call touches it, so a session's FIRST
     action can be an act rather than a look, the risk read of that first
     action sees the page the act will see, and the wait is per document
  H. the manual (ADR-190): a picker's pool is what it offers rather than a
     sample of it and the snapshot says shown-of-how-many; read-control
     answers with the address to call the control by; a box's text is also
     published split where the page splits it, beside the run of text every
     task holds; and the prose the page writes about its own arithmetic is
     handed over as the page wrote it
  I. the session (ADR-191): a page snapshot carries the observation's own
     stamp beside the numbering's; a page nobody touched answers `nothing
     changed` in a line; and an act answers with what it DID -- the controls
     that moved, keyed by address so a rebuild reads as renumbering rather
     than as three hundred controls being replaced -- in a tenth of the bytes
     of the snapshot every blind operator re-read after every act
  E. the environment as an argument (ADR-134): with nothing set, Date and
     Math.random are the real ones; set-clock freezes what "now" answers and
     leaves every other Date form alone; set-seed makes Math.random the
     kit's own mulberry32, agreeing bit for bit with the Python port; a
     dialog is answered by policy and recorded by text; all of it survives a
     reload, and the snapshot publishes it

Run:  python3 tools/verify/verify_report.py
"""
# Declared for tools/mutate.py: this suite writes its own fixture pages and
# asserts about tools/harness_plugin_page.py -- a subject.
MUTATE_ROLE = "subject"
import time
import io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import harness_plugin_page as PP
import harness_contract as C
from harness_contract import HarnessError

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>report fixture</title>
<style>.pane{display:none}.pane.on{display:block}</style></head><body>
<nav><button class="tab on" data-pane="p-rec">Record</button><button class="tab" data-pane="p-an">Analysis</button></nav>
<section class="pane on" id="p-rec">
  <div id="genEntry"><div class="fek-pick"><input class="search" aria-label="genus filter">
    <div class="opts">
      <button class="opt" type="button">Amanita muscaria<small>the fly agaric</small></button>
      <button class="opt" type="button">Amanita<small>amanita muscaria's genus, ectomycorrhizal</small></button>
      <button class="opt" type="button">Suillus<small>with pines</small></button>
      <button class="opt" type="button">Pleurotus<small>wood saprotroph, oyster</small></button>
    </div></div></div>
  <div id="genEntry2"><div class="fek-pick"><input class="search" aria-label="strict filter">
    <div class="opts">
      <button class="opt" type="button">Boletus</button>
      <button class="opt" type="button">Butyriboletus</button>
    </div></div></div>
  <div id="rCov"><div class="fek-dial">
    <button type="button"><span>+</span><small>under 1%</small></button>
    <button type="button"><span>4</span><small>50-75%</small></button>
    <button type="button"><span>5</span><small>over 75%</small></button></div></div>
  <div class="fek-row"><label class="fek-lab">area searched</label><div class="fek-step">
    <button type="button">&minus;</button><input class="val" type="number" aria-label="area searched" value="0"><button type="button">+</button></div></div>
  <div id="stateGrid"><button class="bb" type="button"><span class="nm">forage</span><span class="cd">F</span><kbd>f</kbd></button></div>
  <input type="text" id="cName">
  <div id="cList"><div class="row2">a</div><div class="row2">b</div><div class="row2">c</div></div>
  <div id="packStat" class="stat"><div class="k"><span class="l">families</span><span class="v">23</span></div></div>
  <div id="mStats"><div class="stat"><span class="k">Nodes</span><span class="v">13</span></div>
    <div class="stat"><span class="k">Height</span><span class="v" id="mH">4</span></div></div>
  <div class="tile" id="tCount"><div class="v">7</div><div class="l">count</div></div>
  <div id="rankBoard">1 #1 4.18</div>
  <div id="tree"><div class="n d0"><span class="ty">survey</span><span class="id">SGH:survey:01</span><button type="button">copy ID</button></div></div>
  <div id="ignored-plain">not a box</div>
  <div id="actBar">
    <button type="button" id="bAdd">Add stem</button>
    <button type="button" id="bClear">Clear trial</button>
    <button type="button" id="bWipe">Clear all runs</button>
    <button type="button" id="bUndo">&#8617; Undo</button>
    <button type="button" id="bX">&#10005;</button>
    <button type="button" id="bForget">Forget this device&#39;s copy</button>
    <button type="button" id="bSave">Record collection</button>
    <button type="button" id="bNuclear">Nuclear count</button>
    <button type="button" id="bTimes">2&#215;</button>
    <button type="button" id="bMatrix">Copy host &#215; taxon matrix</button>
    <button type="button" id="bClose">&#215;</button>
    <button type="button" id="bChip">&#10005;honeybee0</button>
    <button type="button" id="bCross">Tally A &#10005; B cross</button>
    <button type="button"></button>
  </div>
  <div id="toast">saved</div>
</section>
<section class="pane" id="p-an">
  <div id="anBox">
    <div class="tile"><div class="v">5</div><div class="l">collections</div></div>
    <div class="tile"><div class="v">2</div><div class="l">families</div></div>
    <div class="tile"><div class="v">38.9<small>mol/m²/d</small></div><div class="l">DLI</div></div>
    <div class="tile"><div class="v">1.000 h</div><div class="l">doubling time</div></div>
    <div class="tile"><div class="v">60.0 min</div><div class="l">doubling time</div></div>
    <p class="verdict">Chao1 is a lower bound.</p>
  </div>
  <div id="selOut"><div class="stat"><div class="st"><div class="v">10.500</div><div class="l">mean before</div></div></div></div>
  <div id="eco-out">name: x</div>
  <div id="triTable"><table><tr><th>entry</th><th>mean</th></tr><tr><td>4</td><td>14.00</td></tr></table></div>
  <div id="kMatrix">Confusion matrix</div>
  <div id="lPlan">50 points</div>
  <div id="keybox"><div id="kres">2 families</div></div><div id="msg">inserted 42</div><div id="spCheck">bound holds</div>
  <h2>Analysis</h2><h3>Richness</h3>
  <div id="plotBox"><svg id="theChart" viewBox="0 0 200 100" role="img">
    <line x1="20" y1="80" x2="190" y2="80"/><line x1="20" y1="10" x2="20" y2="80"/>
    <polyline points="20,70 60,50 100,40 140,20" fill="none"/>
    <path d="M20,75 L60,60 L100,55 L140,50 L160,45 L180,40"/>
    <circle cx="60" cy="50" r="3"/><circle cx="100" cy="40" r="3"/><circle cx="140" cy="20" r="3"/>
    <rect x="165" y="57" width="10" height="6"/>
    <text x="62" y="46">alpha</text><text x="102" y="36">beta</text><text x="142" y="16">gamma</text>
    <text x="20" y="92">2021</text><text x="100" y="92">2022</text><text x="180" y="92">2023</text>
    <text x="8" y="80">0</text><text x="8" y="45">5</text><text x="8" y="12">10</text>
    <text x="40" y="6">key</text><text x="90" y="6">obs</text><text x="190" y="6">fit</text>
  </svg>
  <svg id="theTrend" viewBox="0 0 100 50" role="img">
    <polyline points="0,40 10,35 20,30 30,28 40,20 50,15 60,10" fill="none"/></svg></div>
  <div id="hiddenPlot" style="display:none"><svg viewBox="0 0 10 10"><circle cx="1" cy="1" r="1"/></svg></div>
  <svg id="theBars" viewBox="0 0 100 60" role="img">
    <path d="M10,50 V14 Q10,10 14,10 H26 Q30,10 30,14 V50 Z"/>
    <path d="m40,50 v-20 q0,-4 4,-4 h12 q4,0 4,4 v20 z"/>
    <path d="M70,40 H74 V36 H78 V32 H82 V28 H86 V24 H90 V20"/>
    <rect x="0.1" y="5" width="0.4" height="3"/>
    <circle r="4"/><circle cx="90" cy="20" r="2"/>
  </svg>
</section>
<script>
  document.querySelectorAll('.tab').forEach(function(t){ t.addEventListener('click', function(){
    document.querySelectorAll('.tab').forEach(function(x){ x.classList.remove('on'); });
    document.querySelectorAll('.pane').forEach(function(x){ x.classList.remove('on'); });
    t.classList.add('on'); document.getElementById(t.getAttribute('data-pane')).classList.add('on'); }); });
  window.picked = null;
  // A picker that REMOVES what does not match, rather than hiding it -- the
  // collection sheet's own behaviour, and the case that made ADR-145's guard
  // wrong. The option list is rebuilt from a template on every keystroke.
  (function(){
    var box = document.querySelector('#genEntry2 .opts');
    var all = [].slice.call(box.querySelectorAll('.opt')).map(function(o){ return o.textContent; });
    var s2 = document.querySelector('#genEntry2 .search');
    window.picked2 = null;
    function paint(){
      var q = s2.value.toLowerCase(); box.innerHTML = '';
      all.filter(function(t){ return !q || t.toLowerCase().indexOf(q) >= 0; }).forEach(function(t){
        var b = document.createElement('button'); b.type = 'button'; b.className = 'opt';
        b.textContent = t;
        b.addEventListener('click', function(){ window.picked2 = t; });
        box.appendChild(b); });
    }
    s2.addEventListener('input', paint);
    [].slice.call(box.querySelectorAll('.opt')).forEach(function(o){
      o.addEventListener('click', function(){ window.picked2 = o.textContent; }); });
  })();
  var s = document.querySelector('#genEntry .search'), opts = [].slice.call(document.querySelectorAll('#genEntry .opt'));
  function paint(){ var q = s.value.toLowerCase();
    opts.forEach(function(o){ o.style.display = (!q || o.textContent.toLowerCase().indexOf(q) >= 0) ? '' : 'none'; }); }
  s.addEventListener('input', paint);
  opts.forEach(function(o){ o.addEventListener('click', function(){ window.picked = o.firstChild.textContent; }); });
</script></body></html>
"""

tmp = tempfile.mkdtemp(prefix="report_")
fx = os.path.join(tmp, "fixture.html")
io.open(fx, "w", encoding="utf-8").write(FIXTURE)

from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=H.VIEWPORT)
    ctx.add_init_script(H.STUBS)
    pg = ctx.new_page()
    pg.goto("file://" + fx.replace(os.sep, "/"), wait_until="domcontentloaded")
    try:
        from swarm import SWARM_KINDS
    except Exception:
        SWARM_KINDS = None
    plug = PP.PagePlugin(pg, "fixture.html", kinds=SWARM_KINDS)

    # ---- A. read-report ---------------------------------------------------
    snap = plug.observe(sensitive=True)
    ok, msg, r = plug.execute("read-report", {})
    ck(ok and r["figures"].get("collections") == "5" and r["figures"].get("mean before") == "10.500",
       "a .tile and a .stat .st are both figures: the .l/.v pair is the convention, not the class: %s" % r["figures"])
    ck(r["by"].get("mStats", {}).get("Nodes") == "13", "a bare .k beside the .v is the label too (the visualizer's stats): %s" % r["by"].get("mStats"))
    ck(r["figures"].get("families") == "23" and r["figures"].get("families #2") == "2",
       "flat figures: the first label wins and a second carries #2: %s" % r["figures"])
    ck(r["by"].get("packStat", {}).get("families") == "23" and r["by"].get("anBox", {}).get("families") == "2",
       "and by the box: a label is a fact of its box: %s" % r["by"])
    ck(r["by"]["anBox"].get("doubling time") == "1.000 h" and r["by"]["anBox"].get("doubling time #2") == "60.0 min",
       "the same label twice in one box keeps both: %s" % r["by"]["anBox"])
    ck(r["by"]["anBox"].get("DLI") == "38.9 mol/m²/d", "a <small> unit inside the value is spaced off: %r" % r["by"]["anBox"].get("DLI"))
    ck(r["order"][:5] == ["families", "Nodes", "Height", "count", "collections"],
       "figures are in document order: %s" % r["order"][:5])
    boxes = r["boxes"]
    ck("anBox" in boxes and "lower bound" in boxes["anBox"] and "selOut" in boxes and "eco-out" in boxes and
       "triTable" in boxes and "kMatrix" in boxes and "lPlan" in boxes and "toast" in boxes and "packStat" in boxes
       and "cList" in boxes,
       "boxes follow the kit's naming -- an*, *Out, *Box, *Stat, *Matrix, *Plan, *Table, *List, hyphenated, toast: %s" % sorted(boxes))
    ck("kres" in boxes and "msg" in boxes and "spCheck" in boxes,
       "the keys' result, the visualizer's message and the proofs' check are boxes too (ADR-129): %s" % sorted(boxes))
    ck("rankBoard" in boxes,
       "and a *Board is a box (ADR-171): the pheno tracker's ranked run and its mothers are figures: %s" % sorted(boxes))
    ck("tree" in boxes and "SGH:survey:01" in boxes["tree"],
       "and the event tree is a box (ADR-180): the survey's generated IDs are a figure with buttons in it, read whole: %s" % boxes.get("tree"))
    # WHERE EACH FIGURE WAS READ FROM (ADR-171): the value element's own id
    # when it has one, else the pair's, else the box -- so the readable-figures
    # audit, which counts written elements by id, can credit a figure the
    # figures channel reads under an id that is not named like a box.
    srcs = r.get("sources") or {}
    ck(srcs.get("Height") == "mH",
       "a figure names the element it was read from: the value's own id when it has one: %s" % srcs)
    ck(srcs.get("count") == "tCount",
       "...else the id of the pair it sits in (a .tile with an id): %s" % srcs)
    ck(srcs.get("Nodes") == "mStats" and srcs.get("families") == "packStat",
       "...else the box around it, so provenance is never coarser than by: %s" % srcs)
    ck(set(srcs) <= set(r["figures"]) and all(srcs[k] for k in srcs),
       "every source is keyed like the figure it belongs to, and none is empty: %s" % srcs)
    ck(r["headings"] == ["Analysis", "Richness"], "the page's headings, in order: %s" % r["headings"])
    ck("ignored-plain" not in boxes and "p-rec" not in boxes and "genEntry" not in boxes,
       "and nothing outside the conventions: %s" % sorted(boxes))
    ck("anBox" in boxes and "anBox" not in r["shown"] and "toast" in r["shown"] and "cList" in r["shown"],
       "a box behind a closed tab is read, and which boxes a reader could see is named beside them: shown %s" % r["shown"])
    ck(r["rows"].get("#cList") == 3, "every .row2 list is counted under its parent: %s" % r["rows"])
    ck(r["tables"].get("triTable") == [["entry", "mean"], ["4", "14.00"]], "every table's cells, by its host: %s" % r["tables"])
    ck("figure(s)" in msg and "table(s)" in msg, "the message counts what was read: %s" % msg)
    plug.execute("show-pane", {"pane": "p-an"})
    ok, msg, r2 = plug.execute("read-report", {})
    ck("anBox" in r2["shown"] and "toast" not in r2["shown"] and r2["by"]["anBox"] == r["by"]["anBox"],
       "opening the pane changes what is shown, not what is read")
    plug.execute("show-pane", {"pane": "p-rec"})

    # ---- B. pick -----------------------------------------------------------
    snap = plug.observe(sensitive=True)
    sel = next(c["selector"] for c in snap["controls"] if c["kind"] == "pick_search")

    def pick(v):
        try:
            ok, msg, out = plug.execute("pick", {"selector": sel, "value": v})
            return out.get("chose"), pg.evaluate("() => window.picked")
        except HarnessError as e:
            return "refused: " + str(e), None
    ck(pick("Amanita")[1] == "Amanita", "an exact label wins over the longer one it prefixes, listed first")
    ck(pick("amanita m")[1] == "Amanita muscaria",
       "a prefix, case-insensitively, takes the option it starts even when the filter left two")
    ck(pick("oyster")[1] == "Pleurotus", "a fragment the filter narrows to one option takes that one (the sub-line filters)")
    c, p = pick("pines")
    ck(p == "Suillus", "the sub-line narrows the filter: %s" % c)
    c, p = pick("ita")
    ck(c.startswith("refused") and "ambiguous" in c and "2 options" in c,
       "two options left is a guess and is refused as ambiguous, naming the count: %s" % c)
    c, p = pick("Zzzz")
    ck(c.startswith("refused") and "no option matches" in c, "nothing left is refused as no match: %s" % c)
    c, p = pick("ectomycorrhizal")
    ck(c.startswith("refused") or p == "Amanita",
       "a sub-line is never a label: it filters but does not name the option: %s" % c)

    pool = [x for x in (snap["argumentPools"].get("pick") or []) if x["selector"] == sel]
    ck(len(pool) == 4 and all(set(x) == {"selector", "value"} for x in pool) and
       {x["value"] for x in pool} == {"Amanita muscaria", "Amanita", "Suillus", "Pleurotus"},
       "the snapshot publishes each picker's option labels as an argument-set pool for pick, sub-lines stripped: %s" % pool)
    ck({x["value"] for x in (snap["argumentPools"].get("pick") or []) if x["selector"] != sel}
       == {"Boletus", "Butyriboletus"},
       "...and every picker gets its own entries, keyed by its own search box: %s"
       % [x for x in (snap["argumentPools"].get("pick") or []) if x["selector"] != sel])

    # ---- B2. a picker with nothing showing is still a picker (ADR-145) -------
    # The collection sheet REMOVES options that do not match instead of hiding
    # them, so a filter that matches nothing leaves the picker with no .opt in
    # the DOM at all. The guard asked for one BEFORE typing, so a single
    # refused pick made the picker unusable for the rest of the session: every
    # later pick answered "not a picker", including the one that would have
    # cleared the filter. It was found by a task entering a page's own stand
    # list, which narrows the host picker to the trees you actually named.
    strict = next((c["selector"] for c in plug.observe()["controls"]
                   if c["kind"] == "pick_search" and c.get("host") == "genEntry2"), None)
    ck(strict is not None,
       "the strict picker's search box is named by its own mount (#genEntry2), which is how a "
       "task reaches one picker of several")
    try:
        plug.execute("pick", {"selector": strict, "value": "Quercus"})
        ck(False, "a value no option matches was picked anyway")
    except HarnessError as e:
        ck("no option matches" in e.message and "not a picker" not in e.message,
           "a value nothing matches is refused as NO OPTION MATCHES -- what the caller got wrong "
           "is the value, not the control: %s" % e.message[:70])
    ck(pg.evaluate("() => document.querySelectorAll('#genEntry2 .opt').length") == 0,
       "and the page has removed every option, which is the state the old guard could not tell "
       "from 'this is not a picker'")
    try:
        ok, _, out = plug.execute("pick", {"selector": strict, "value": "Boletus"})
    except HarnessError as e:
        ok, out = False, e.message
    ck(ok and pg.evaluate("() => window.picked2") == "Boletus",
       "...so the NEXT pick still works: a control does not stop being a picker because of what "
       "someone typed into it, and without this a refused pick was unrecoverable: %s" % out)
    # ...and a control that is NOT a picker still says so
    plain = next((c["selector"] for c in plug.observe()["controls"] if c.get("id") == "cName"), None)
    try:
        plug.execute("pick", {"selector": plain, "value": "Boletus"})
        ck(False, "a pick on a plain text input was accepted")
    except HarnessError as e:
        ck("not a picker" in e.message,
           "a pick aimed at something that is not a picker at all is still refused as NOT A "
           "PICKER -- the structural test is what that message is for: %s" % e.message[:60])

    # ---- B3. assigning a value is not typing (ADR-150) ----------------------
    # set-text writes through the value setter, which is what a SCRIPT does. A
    # person presses keys. For most controls the two are the same, and for
    # <input type=number> they are not: assign "3e" and the value is "" with
    # validity.badInput FALSE; type it and the value is "" with badInput TRUE.
    # A page that tells the two apart -- and the experiment guide does, because
    # a blank seed means 42 and a typed-but-rejected seed does not -- had a
    # branch no task in this kit could reach.
    num = next((c["selector"] for c in plug.observe()["controls"]
                if c.get("label") == "area searched"), None)
    ck(num, "the fixture has a number control to type into: %r" % num)
    _ok, _m, r = plug.execute("set-text", {"selector": num, "value": "3e"})
    bad = pg.evaluate("(sel) => { const e = document.querySelector('[data-h=\"' + sel + '\"]');"
                      "  return {value: String(e.value),"
                      "          badInput: !!(e.validity && e.validity.badInput)}; }", num)
    ck(bad["value"] == "" and bad["badInput"] is False,
       "ASSIGNING an unparseable value to a number control empties it and leaves badInput FALSE "
       "-- which is exactly what a deliberately blank box looks like: %s" % bad)
    _ok, _m, r2 = plug.execute("type-text", {"selector": num, "value": "3e"})
    ck(r2.get("value") == "" and r2.get("badInput") is True,
       "...and TYPING the same characters empties it and leaves badInput TRUE, which is the only "
       "way a page can tell a rejected entry from a blank one: %s" % r2)
    _ok, _m, r3 = plug.execute("type-text", {"selector": num, "value": "42"})
    ck(r3.get("value") == "42" and r3.get("badInput") is False,
       "typing a value the control accepts leaves it in the box, badInput false: %s" % r3)
    txtc = next((c["selector"] for c in plug.observe()["controls"] if c.get("id") == "cName"), None)
    ck(txtc, "the fixture's named text control is findable, so the next checks ask something -- "
             "and it keeps its id: %r"
             % txtc)
    _ok, _m, r4 = plug.execute("type-text", {"selector": txtc or num, "value": "Boletus edulis"})
    ck(r4.get("value") == "Boletus edulis",
       "and on a plain text control typing is just typing: %s" % r4)
    _ok, _m, r5 = plug.execute("type-text", {"selector": txtc or num, "value": ""})
    ck(r5.get("value") == "",
       "typing an empty value CLEARS the control, rather than leaving what was there -- a task "
       "that empties a box is saying something, and it must not quietly do nothing: %s" % r5)
    # A CONTROL THAT CANNOT TAKE FOCUS IS A FACT ABOUT THE PAGE, not something
    # to wait on. The first draft CLICKED the control to put the caret in it,
    # and the robot drives every tool at every control -- including ones a
    # layout covers, where a click waits thirty seconds for a hit test that
    # never comes and the walk records a FAILURE against the page. Typing needs
    # the focus, not the pointer.
    pg.evaluate("(sel) => { document.querySelector('[data-h=\"' + sel + '\"]')"
                "  .style.visibility = 'hidden'; }", txtc)
    t0 = time.time()
    try:
        plug.execute("type-text", {"selector": txtc, "value": "x"})
        ck(False, "type-text into a control that cannot take focus was accepted")
    except HarnessError as e:
        ck("focus" in e.message or "hidden" in e.message.lower(),
           "typing into a control that cannot take focus is REFUSED, naming the reason: %s"
           % e.message[:80])
    ck(time.time() - t0 < 10,
       "...and refused at once rather than waited on: a pointer would have spent its whole "
       "actionability timeout on it, and the robot would have filed the wait as the page failing "
       "(%.1fs)" % (time.time() - t0))
    pg.evaluate("(sel) => { document.querySelector('[data-h=\"' + sel + '\"]')"
                "  .style.visibility = ''; }", txtc)
    try:
        btn = next(c["selector"] for c in plug.observe()["controls"]
                   if c["selector"].startswith("action_btn:"))
        plug.execute("type-text", {"selector": btn, "value": "x"})
        ck(False, "type-text into a button was accepted")
    except HarnessError as e:
        ck(e.code == "invalid_argument" and "not a text control" in e.message,
           "typing into a button is the CALLER's mistake, refused the same way set-text refuses "
           "it: %s" % e.message[:60])

    # ---- C. naming -----------------------------------------------------------
    snap = plug.observe(sensitive=True)
    byl = {}
    for c in snap["controls"]:
        byl.setdefault((c.get("host"), c["label"]), []).append(c)
    ck(all("id" in c and "host" in c for c in snap["controls"]), "every control carries id and host")
    ck(("rCov", "4") in byl and ("rCov", "+") in byl, "a dial option is labelled by its <span>, not by its text run together: %s"
       % sorted(l for h, l in byl if h == "rCov"))
    ck(("stateGrid", "forage") in byl, "a behaviour key is labelled by its .nm child: %s" % sorted(l for h, l in byl if h == "stateGrid"))
    ck(any(c["id"] == "cName" for c in snap["controls"]), "a plain input keeps its id")
    ck(("genEntry", "genus filter") in byl, "a picker's search carries its aria-label and its mount host: %s" % sorted(l for h, l in byl if h == "genEntry"))
    ck(any(c["label"] == "area searched" and c["kind"] == "step_val" for c in snap["controls"]),
       "a stepper's value input carries the stepper's label")

    # ---- ADR-140: the charts ------------------------------------------
    plug.execute("show-pane", {"pane": "p-an"})     # the chart lives behind the second tab
    ok, msg, r = plug.execute("read-report", {})
    ch = r["charts"]
    ck(ok and sorted(ch) == ["theBars", "theChart", "theTrend"],
       "a visible <svg> is a chart, keyed by its own id; one that is not shown is not read: %s" % sorted(ch))
    c = ch.get("theChart", {})
    ck(c.get("viewBox") == "0 0 200 100" and c.get("n") == 12,
       "the chart carries the space it was drawn in and how many texts it holds: %s %s"
       % (c.get("viewBox"), c.get("n")))
    ck(c.get("marks") == {"circle": 3, "rect": 1, "path": 1, "line": 2, "polyline": 1},
       "every mark is counted by what it is -- a chart that plots the wrong number of points "
       "looks exactly like one that plots the right number: %s" % c.get("marks"))
    ck(c.get("longest") == 6 and ch.get("theTrend", {}).get("longest") == 7,
       "and the longest drawn series is how many points it carries -- the path here, the polyline "
       "in the chart beside it: %s, %s" % (c.get("longest"), ch.get("theTrend", {}).get("longest")))
    ck(c.get("aligned", {}).get("row") == ["2021", "2022", "2023"],
       "the LOWEST row of text that lines up is the one taken -- the legend three rows above it is "
       "just as aligned and is not the x tick sequence: %s" % c.get("aligned", {}).get("row"))
    ck(c.get("aligned", {}).get("col") == ["10", "5", "0"],
       "and the leftmost column top to bottom: %s" % c.get("aligned", {}).get("col"))
    ck(c.get("points") == {"alpha": [60, 50], "beta": [100, 40], "gamma": [140, 20]},
       "a text beside a mark names it, and the pair says WHERE the page put it, in the svg's own "
       "units rather than in rendered pixels: %s" % c.get("points"))
    ck(c.get("at")[:4] == [[60, 50], [100, 40], [140, 20], [170, 60]],
       "...and every mark centre is there whether or not anything labelled it, a rect by its middle: %s"
       % c.get("at")[:4])
    ck([170, 60] in c.get("at", []) and [170, 60] not in c.get("points", {}).values(),
       "a mark with no text near it is placed but not named -- the pairing is the page's, and where "
       "the page put nothing beside a mark the reader invents no label")
    ck([t for t in c.get("texts", []) if t["t"] == "gamma"] == [{"t": "gamma", "x": 142, "y": 16}],
       "each text carries the position the page gave it")
    # ---- ADR-182: a path is placed by its box ----------------------------
    # A bar drawn as a rounded path (the lab's M V Q H Q V Z) has no cx and no
    # x/width, so `at` could not place it: a bar chart read as a row of
    # hit-rects all at one y, and its heights were nowhere in the report.
    bars = ch.get("theBars", {})
    ck(bars.get("spans") == [[10, 10, 30, 50], [40, 26, 60, 50], [70, 20, 90, 40]],
       "each path's box -- the smallest [x0, y0, x1, y1] holding every point a command ends at -- "
       "is reported in the svg's own units, the curve's control points left out: %s" % bars.get("spans"))
    ck(bars.get("spans", [[]])[1:2] == [[40, 26, 60, 50]],
       "a path drawn with relative commands is placed where it ends up, not where its numbers say: %s"
       % bars.get("spans", [[]])[1:2])
    ck(bars.get("spans", [[], [], []])[2:3] == [[70, 20, 90, 40]] and bars.get("longest") == 11,
       "a step line drawn with H and V is followed, and every command that ends somewhere is a point "
       "of the series -- the step line here is eleven, not one: %s, %s" % (bars.get("spans", [])[2:3], bars.get("longest")))
    ck(bars.get("at") == [[90, 20], [0.3, 6.5]],
       "an unplaced mark (a hover dot with no cx yet) is nowhere, not at [null, null], and a rect's "
       "centre is rounded like every other number here (0.1 + 0.2 is not 0.3 in a float): %s" % bars.get("at"))
    ck(bars.get("marks") == {"path": 3, "rect": 1, "circle": 2},
       "...while the unplaced mark is still COUNTED, because it is drawn: %s" % bars.get("marks"))

    # ---- F. what an activation would touch (ADR-141) --------------------
    # `activate` is how every button on these pages is pressed, and it was
    # DESTRUCTIVE for all of them because one of them is "Clear trial". Four
    # blind operators found what that cost: a session holding SENSITIVE_READ,
    # DRAFT and MUTATE could fill a whole collection sheet and record nothing.
    plug.execute("show-pane", {"pane": "p-rec"})
    snap = plug.observe(sensitive=True)
    by_id = dict((c["id"], c["selector"]) for c in snap["controls"] if c.get("id"))
    def risk(sel):
        return plug.risk_for("activate", {"selector": sel})
    ck(risk(by_id["bAdd"]) is None and risk(by_id["bSave"]) is None,
       "a button that adds or records stays at the declared MUTATE floor: %s / %s"
       % (risk(by_id["bAdd"]), risk(by_id["bSave"])))
    ck(risk(by_id["bNuclear"]) is None,
       "and a word that merely CONTAINS one of them is not one of them -- on these "
       "pages 'Nuclear count' stays at the declared MUTATE floor, which is what the "
       "word boundaries in the vocabulary are for: %s" % (risk(by_id["bNuclear"]),))
    for name, word in (("bClear", "clear"), ("bWipe", "clear"), ("bUndo", "undo"),
                       ("bForget", "forget")):
        got = risk(by_id[name])
        ck(got and got[0] == "DESTRUCTIVE" and word in got[1],
           "a button NAMED for removing work is raised to DESTRUCTIVE, and the reason "
           "quotes the label rather than asserting it: %s -> %s" % (name, got))
    for name in ("bX", "bChip"):
        got = risk(by_id[name])
        ck(got and got[0] == "DESTRUCTIVE" and "mark" in got[1],
           "the row-removing mark is caught, alone or glued to the row it removes -- 39 of "
           "the kit's buttons are named nothing but that and 11 more carry it before the "
           "chip's name: %s -> %s" % (name, got))
    # ...and the two glyphs a scientist writes for something else entirely
    ck(risk(by_id["bTimes"]) is None and risk(by_id["bMatrix"]) is None
       and risk(by_id["bCross"]) is None,
       "a MULTIPLICATION sign is not a delete: the kit writes '2\u00d7' on a playback speed "
       "and 'Copy host \u00d7 taxon matrix' on an export, and a mark in the MIDDLE of a label "
       "is punctuation between words -- a cross, on these pages, quite literally: %s / %s / %s"
       % (risk(by_id["bTimes"]), risk(by_id["bMatrix"]), risk(by_id["bCross"])))
    got = risk(by_id["bClose"])
    ck(got and got[0] == "DESTRUCTIVE" and "close mark" in got[1],
       "...while that same glyph ALONE is a close button and is raised: %s" % (got,))
    blank = next(c["selector"] for c in snap["controls"]
                 if c["kind"] == "action_btn" and not c["label"] and not c.get("id"))
    got = risk(blank)
    ck(got and got[0] == "DESTRUCTIVE" and "no label" in got[1],
       "a control with no label, id or title is raised too: what it would do cannot be "
       "read, and unreadable is not the same as harmless: %s" % (got,))
    got = risk("action_btn:9999")
    ck(got and got[0] == "DESTRUCTIVE" and "no control" in got[1] and "numbered 0-" in got[1],
       "a selector that resolves to NOTHING is raised, and the reason says how many "
       "selectors of that kind the page has now -- the blind trial watched a stale index "
       "of exactly this shape delete a tallied stem and answer ok:true: %s" % (got,))
    ck(risk(by_id["bClear"]) is not None and plug.risk_for("set-text", {"selector": by_id["bClear"]}) is None,
       "and only activate is classified: an action that names what it does needs no guess")
    pool = snap["argumentPools"]
    dest = set(pool.get("activate.destructive") or [])
    ck(dest == set(by_id[k] for k in ("bClear", "bWipe", "bUndo", "bX", "bForget",
                                      "bClose", "bChip")),
       "the snapshot NAMES them, before a call is spent: %s"
       % sorted(k for k in by_id if by_id[k] in dest))
    ck(dest < set(pool["activate.selector"]) and by_id["bAdd"] in pool["activate.selector"],
       "published beside the selectors, not instead of them: a caller is told which "
       "buttons remove work, not left to discover the rung by being refused")

    # ...and the refusal a stale selector gets from execute says the same thing
    try:
        plug.execute("activate", {"selector": "action_btn:9999"})
        ck(False, "a selector that names nothing was activated")
    except HarnessError as e:
        ck(e.code == "not_found" and "numbered 0-" in e.message and "observe again" in e.message,
           "and a selector that names nothing is refused by COUNT: these selectors are the "
           "moment's, and 'no control action_btn:9999' alone reads as a typo: %s" % e.message)

    # ---- G. read-control names the control it read (ADR-141) ------------
    ok, _, one = plug.execute("read-control", {"selector": by_id["bClear"]})
    ck(ok and one["id"] == "bClear" and one["label"] == "Clear trial" and one["host"] == "actBar",
       "read-control answers with the page's own names for the control -- id, label, host "
       "-- not with the selector the caller already had: %s"
       % {k: one.get(k) for k in ("id", "label", "host", "pane")})
    ck(one["pane"] == "p-rec",
       "and the pane it sits in, which is what a caller needs to reach it: %s" % one["pane"])
    lab = dict((c["selector"], c["label"]) for c in snap["controls"])
    ck(all(plug.execute("read-control", {"selector": s2})[2]["label"] == lab[s2]
           for s2 in sorted(lab)[:12]),
       "and it is the SAME label the snapshot published -- one definition, three readers")

    ctx.close()
    b.close()


# ---- D. on a real page -------------------------------------------------------
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=H.VIEWPORT)
    ctx.set_offline(True)
    ctx.add_init_script(H.STUBS)
    pg = ctx.new_page()
    # under mutation the tools directory is a copy with no docs beside it;
    # the runner names the real kit
    docs = os.environ.get("CSRBT_DOCS_DIR") or os.path.join(_kit.ROOT, "docs")
    pg.goto("file://" + os.path.join(docs, "collection-sheet.html").replace(os.sep, "/"), wait_until="domcontentloaded")
    pg.wait_for_timeout(300)
    try:
        from swarm import SWARM_KINDS
    except Exception:
        SWARM_KINDS = None
    plug = PP.PagePlugin(pg, "collection-sheet.html", kinds=SWARM_KINDS)
    snap = plug.observe(sensitive=True)
    gen = next(c["selector"] for c in snap["controls"] if c["kind"] == "pick_search" and c["host"] == "genEntry")
    ok, _, out = plug.execute("pick", {"selector": gen, "value": "Amanita"})
    tell = pg.inner_text("#cGenTell").lower()
    ck(ok and out["chose"].startswith("Amanita") and "volva" in tell and "ectomycorrhizal" in tell,
       "on the collection sheet a genus picked through the gateway is the genus the sheet records -- its tell "
       "and guild badge render from the picker's onchange: %s / %s" % (out, tell[:60]))
    ok, _, r = plug.execute("read-report", {})
    ck("anBox" in r["boxes"] and "anBox" not in r["shown"] and r["rows"].get("#cList", 0) == 0,
       "the analysis box is read behind its closed tab, and the collection list counts zero rows before an entry")
    pg.goto("file://" + os.path.join(docs, "experiment-guide.html").replace(os.sep, "/"), wait_until="domcontentloaded")
    pg.wait_for_timeout(300)
    plug = PP.PagePlugin(pg, "experiment-guide.html", kinds=SWARM_KINDS)
    plug.observe(sensitive=True)
    ok, _, out = plug.execute("show-pane", {"pane": "pane-designer"})
    ck(ok and "pane-designer" in out["open"],
       "on the experiment guide, whose tabs name their pane by aria-controls rather than data-pane, show-pane opens it: %s" % out)
    # ---- E. the environment as an argument (ADR-134) ----------------------
    from mulberry32 import Mulberry32
    ctx2 = b.new_context(viewport=H.VIEWPORT)
    ctx2.add_init_script(H.STUBS)
    ctx2.add_init_script(H.DETERMINISM)
    pg2 = ctx2.new_page()
    pg2.goto("file://" + fx.replace(os.sep, "/"), wait_until="domcontentloaded")
    env = PP.PagePlugin(pg2, "fixture.html", kinds=SWARM_KINDS)

    # untouched, the page has the real world. A shim that changed behaviour
    # before anyone asked would be a shim nobody could leave installed.
    ck(env.observe(sensitive=True)["environment"] == {"clock": None, "seed": None, "draws": 0,
                                                      "confirm": True, "dialogs": 0},
       "with nothing set the environment is empty and the page has the real clock and the real dice")
    ck(pg2.evaluate("() => { const a = Date.now(); let s = 0; for (let i = 0; i < 200000; i++) s += i; "
                    "return Date.now() >= a && s > 0; }"),
       "and the real clock still moves")
    # THE FIRST draws on this page, before anything else has touched Math.random.
    # "three different numbers" is not enough: a shim that ran the seeded
    # generator from an unset state would also give three different numbers, and
    # would have replaced the page's chance without anyone asking. The tell is
    # that the unset page must not be drawing the seeded stream at all.
    first3 = pg2.evaluate("() => [Math.random(), Math.random(), Math.random()]")
    ck(len(set(first3)) == 3, "and the real dice still differ")
    ck(first3 != Mulberry32(0).take(3),
       "and they are the REAL dice, not the seeded generator running from an unset state")

    ok, msg, out = env.execute("set-clock", {"at": "2026-03-01T09:00:00Z"})
    ck(ok and out["epochMs"] == 1772355600000 and out["reloadForLoadTime"] is True,
       "set-clock answers the epoch it froze, and says a reload is needed for code that reads the clock at "
       "load: %s" % out)
    ck(pg2.evaluate("() => [Date.now(), new Date().toISOString()]") == [1772355600000, "2026-03-01T09:00:00.000Z"],
       "Date.now() and new Date() answer the frozen instant")
    ck(pg2.evaluate("() => [new Date(0).getTime(), new Date(2020, 0, 2).getFullYear(), new Date() instanceof Date]")
       == [0, 2020, True],
       "and every OTHER Date form is untouched -- a date the page names itself is not 'now'")

    ok, _, out = env.execute("set-seed", {"seed": 42})
    ck(ok and out["seed"] == 42, "set-seed answers the seed it set")
    js = pg2.evaluate("() => [Math.random(), Math.random(), Math.random(), Math.random(), Math.random()]")
    ck(js == Mulberry32(42).take(5),
       "Math.random IS mulberry32, agreeing with tools/mulberry32.py bit for bit -- the port is what lets an "
       "oracle say what a page must print without asking the page: %s" % js[:2])
    ck(env.observe(sensitive=True)["environment"]["draws"] == 5,
       "and the snapshot counts the draws, so a figure that came out of chance can be reproduced")

    ok, _, out = env.execute("set-dialog", {"confirm": False, "prompt": "no thanks"})
    ck(ok and pg2.evaluate("() => [confirm('really?'), prompt('name?')]") == [False, "no thanks"],
       "a dialog is answered by policy: the branch a reader takes when they say NO is drivable")
    ok, _, out = env.execute("read-dialogs", {})
    ck(ok and out["count"] == 2 and out["dialogs"][0] == {"kind": "confirm", "text": "really?"},
       "and every dialog is recorded by kind and text, in order: %s" % out["dialogs"])

    env.execute("reload", {})
    ck(pg2.evaluate("() => [Date.now(), Math.random() === %r, window.__D.confirm]" % Mulberry32(42).random())
       == [1772355600000, True, False],
       "the whole environment survives a reload -- an init script, because a page that reads the clock at load "
       "has already read it by the time an action can run")

    ok, _, out = env.execute("set-clock", {})
    ck(ok and out["clock"] is None and pg2.evaluate("() => window.__D.epoch") is None,
       "set-clock with no argument hands the page its real clock back")
    ok, _, out = env.execute("set-seed", {})
    ck(ok and out["seed"] is None, "and set-seed with no argument hands back the real generator")
    try:
        env.execute("set-clock", {"at": "the day before yesterday"})
        ck(False, "a clock that is not an instant was accepted")
    except HarnessError as e:
        ck(e.code == "invalid_argument", "a clock that is not an ISO instant is refused: %s" % e.message[:60])
    try:
        env.execute("set-dialog", {})
        ck(False, "set-dialog with nothing to set was accepted")
    except HarnessError as e:
        ck(e.code == "invalid_argument", "set-dialog with neither answer is refused: %s" % e.message[:60])
    ctx2.close()

    ctx.close()
    b.close()

# ---- E. what leaves the page, for a caller who is not the robot (ADR-152) ----
#
# `collect-output` is published by the page plugin. What it reads -- window.__S
# -- was installed by tools/swarm.py, on the context the ROBOT builds, so every
# other caller got a page with no capture at all and the action answered
# "0 payload(s)": the same answer a page that emitted nothing gives. This
# fixture is driven by a plugin built the way a task's runner builds one.
OUT_FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>outputs</title></head><body>
<h1>outputs</h1>
<div id="toast" class="toast"></div>
<button id="copy" type="button">Copy the sheet</button>
<button id="dl" type="button">Download the sheet</button>
<button id="pr" type="button">Print</button>
<pre id="anSheet">kind,id\nrecorder,AM-014</pre>
<script>
  var $ = function(i){ return document.getElementById(i); };
  $("copy").addEventListener("click", function(){
    /* the hidden-textarea pattern: what every Copy button in this kit does */
    var a = document.createElement("textarea"); a.value = $("anSheet").textContent;
    a.style.position="fixed"; a.style.opacity="0";
    document.body.appendChild(a); a.select();
    try { document.execCommand("copy"); } catch(e){}
    document.body.removeChild(a);
    $("toast").classList.add("on");
  });
  $("dl").addEventListener("click", function(){
    var blob = new Blob([$("anSheet").textContent], {type:"text/csv"});
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "sheet.csv";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  });
  $("pr").addEventListener("click", function(){ window.print(); });
</script></body></html>
"""
ofx = os.path.join(tmp, "outputs.html")
io.open(ofx, "w", encoding="utf-8").write(OUT_FIXTURE)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=H.VIEWPORT)
    ctx.set_offline(True)
    ctx.add_init_script(H.STUBS)          # the environment stubs, and NOT the capture
    pg = ctx.new_page()
    pg.goto("file://" + ofx.replace(os.sep, "/"), wait_until="domcontentloaded")
    pg.wait_for_timeout(120)
    ck(pg.evaluate("() => !!window.__S") is False,
       "the page starts with no capture on it: this fixture is loaded the way a task's page is, "
       "not the way the robot's is")

    plug = PP.PagePlugin(pg, "outputs.html")
    ck(pg.evaluate("() => !!window.__S") is True,
       "constructing the plugin installs the capture INTO THE PAGE THAT IS ALREADY OPEN -- an init "
       "script added now would not run until the next navigation, and the ordinary case is a plugin "
       "built around a page somebody has just opened")

    snap = plug.observe(sensitive=True)
    sel = dict((c["label"], c["selector"]) for c in snap["controls"])

    plug.execute("activate", {"selector": sel["Copy the sheet"]})
    ok, msg, out = plug.execute("collect-output", {})
    pay = out["payloads"]
    ck(ok and len(pay) == 1 and pay[0]["k"] == "copy",
       "a Copy button is read by collect-output for a caller that is not the robot -- until ADR-152 "
       "this answered 0 payload(s), which is what a page that copied nothing answers: %s" % pay)
    ck(pay and "recorder,AM-014" in pay[0]["text"],
       "...and the payload is what the page put on the clipboard, not the name of the button: %s"
       % (pay[0]["text"][:60] if pay else None))

    ok, _, out = plug.execute("collect-output", {})
    ck(out["payloads"] == [],
       "collect-output TAKES the payloads: reading them twice does not report them twice")

    plug.execute("activate", {"selector": sel["Download the sheet"]})
    ok, _, out = plug.execute("collect-output", {})
    ck(out["payloads"] and out["payloads"][0]["k"] == "download"
       and out["payloads"][0]["name"] == "sheet.csv"
       and "recorder,AM-014" in out["payloads"][0]["text"],
       "a Blob download is captured with its filename and its bytes, and not followed -- the run "
       "stays on the page: %s" % out["payloads"])
    ck(pg.url.endswith("outputs.html"), "...which is why the page is still the page: %s" % pg.url[-30:])

    plug.execute("activate", {"selector": sel["Print"]})
    ok, _, out = plug.execute("collect-output", {})
    ck(out["payloads"] and out["payloads"][0]["k"] == "print",
       "and a print is an output too: %s" % out["payloads"])

    # ONE CAPTURE PER WINDOW. It is installed both as an init script and by
    # evaluation, and a second plugin over the same page must install neither
    # again -- a re-install throws away the payloads nobody has collected yet
    # and wraps every wrapper around itself.
    plug.execute("activate", {"selector": sel["Copy the sheet"]})   # left uncollected
    before = pg.evaluate("() => window.__S.toasts")
    plug2 = PP.PagePlugin(pg, "outputs.html")
    ck(pg.evaluate("() => window.__S.toasts") == before,
       "a second plugin over the same page does not install the capture twice: a re-install starts "
       "a fresh __S, so the count of what has already happened would go backwards (%s -> %s)"
       % (before, pg.evaluate("() => window.__S.toasts")))
    ok, _, out = plug2.execute("collect-output", {})
    ck(len(out["payloads"]) == 1,
       "...and a payload nobody had collected yet is still there to collect: %s" % out["payloads"])
    plug2.execute("activate", {"selector": sel["Copy the sheet"]})
    after = pg.evaluate("() => window.__S.toasts")
    ck(after - before == 1,
       "...and one press still raises one toast, not two: a wrapper wrapped around its own wrapper "
       "counts everything twice and nothing says so (%d -> %d)" % (before, after))
    ok, _, out = plug2.execute("collect-output", {})
    ck(len(out["payloads"]) == 1,
       "...and makes one payload: %s" % out["payloads"])

    # AND IT SURVIVES A NAVIGATION, which is what the init script is for.
    plug.execute("reload", {})
    pg.wait_for_timeout(120)
    ck(pg.evaluate("() => !!window.__S") is True,
       "the capture is on the page after a reload as well: a session that navigates must not lose "
       "the one tool that reads what leaves the page")
    plug.observe(sensitive=True)
    plug.execute("activate", {"selector": sel["Copy the sheet"]})
    ok, _, out = plug.execute("collect-output", {})
    ck(out["payloads"] and out["payloads"][0]["k"] == "copy",
       "...and it still reads a copy after the reload: %s" % out["payloads"])
    ctx.close()
    b.close()

# ---- F. addresses (ADR-188) --------------------------------------------------
#
# The third blind trial (ADR-187) put four operators on four science pages and
# all four reported the same thing: `action_btn:N` indexes the whole page and
# renumbers on every structural change, stable ids are published in the
# snapshot, and no tool accepted one. So every selector argument now takes an
# ADDRESS. The claims worth holding are that a published address resolves back
# to the control that published it, that the door answers a name exactly as the
# runner's find_control does -- two implementations of ADR-128's grammar, held
# to each other rather than left to drift -- and that the stamp refuses instead
# of resolving to whatever moved into an index.
import harness_tasks as _T

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=H.VIEWPORT)
    ctx.set_offline(True)
    ctx.add_init_script(H.STUBS)
    pg = ctx.new_page()
    docs = os.environ.get("CSRBT_DOCS_DIR") or os.path.join(_kit.ROOT, "docs")
    try:
        from swarm import SWARM_KINDS
    except Exception:
        SWARM_KINDS = None

    def _form(a):
        """an address, split the way the door splits it"""
        if a.startswith("#"):
            return "#", a[1:], None
        if a.startswith("@"):
            return "@", a[1:], None
        sel, _, ver = a.partition("@")
        return ":", sel, ver

    stale_msg = named_no_raise = None
    for page in ("collection-sheet.html", "stand-sheet.html", "pheno-tracker.html"):
        pg.goto("file://" + os.path.join(docs, page).replace(os.sep, "/"), wait_until="domcontentloaded")
        pg.wait_for_timeout(300)
        plug = PP.PagePlugin(pg, page, kinds=SWARM_KINDS)
        snap = plug.observe(sensitive=True)
        rows = snap["controls"]

        # 1. every published address resolves back to the control that published it
        bad = []
        for c in rows:
            r = pg.evaluate(PP.RESOLVE, list(_form(c["address"])))
            if not r.get("ok") or r["selector"] != c["selector"]:
                bad.append((c["address"], c["selector"], r.get("why")))
        ck(rows and not bad,
           "%s: every one of its %d controls publishes an address that resolves back to itself -- a name that "
           "did not work would be worse than no name at all: %s" % (page, len(rows), bad[:3]))

        # 2. the door's answer IS the runner's answer, name for name
        kd, dis, names = {"x": {"snapshot": snap}}, [], 0
        sibs = {}
        for c in rows:
            if c["host"] and c["label"]:
                sibs.setdefault((c["host"], c["label"]), []).append(c["selector"])
        for c in rows:
            scoped = (c["host"] + "/" + c["label"]) if c["host"] and c["label"] else None
            # the nth-match form too: a label shared by every dial in a row is
            # the case ADR-128 built "#n" for, and it is the case a mutation
            # that drops the suffix would sail through if nobody asked for one
            nth = ("%s#%d" % (scoped, sibs[(c["host"], c["label"])].index(c["selector"]))) if scoped else None
            for nm in (c["id"], c["label"], scoped, nth):
                if not nm:
                    continue
                try:
                    want = _T.find_control(nm, kd, "f")
                except Exception:
                    continue
                names += 1
                got = pg.evaluate(PP.RESOLVE, ["@", nm, None])
                if not got.get("ok") or got["selector"] != want:
                    dis.append((nm, want, got.get("selector")))
        ck(names > 40 and not dis,
           "%s: the door resolves all %d of its names exactly as the runner's find_control does -- one grammar, two "
           "implementations, held to each other: %s" % (page, names, dis[:3]))

        # 3. the stamp
        first = rows[0]
        live = pg.evaluate(PP.RESOLVE, [":", first["selector"], snap["version"]])
        dead = pg.evaluate(PP.RESOLVE, [":", first["selector"], "vnotnow"])
        ck(live.get("ok") and live["selector"] == first["selector"]
           and not dead.get("ok") and dead.get("why") == "stale"
           and (dead.get("at") or {}).get("address") == first["address"],
           "%s: a selector stamped with the snapshot it came from resolves, and one stamped with any other is "
           "refused as stale and told what is at that index now: %s / %s" % (page, live, dead))

        if page == "collection-sheet.html":
            # 4. #id is the id and nothing else
            lab = next((c for c in rows if c["label"] and not c["id"]
                        and not any(x["id"] == c["label"] for x in rows)), None)
            ck(lab is not None
               and pg.evaluate(PP.RESOLVE, ["@", lab["label"], None]).get("ok")
               and not pg.evaluate(PP.RESOLVE, ["#", lab["label"], None]).get("ok"),
               "a name that is a label and no control's id answers to @ and not to # -- the two forms are not "
               "synonyms, or an id would be whatever happened to be written on some other button: %r" % (lab or {}).get("label"))

            # 5. the version moves exactly when the numbering could mean something else
            v0 = plug.observe(sensitive=True)["version"]
            plug.execute("set-text", {"selector": "#cName", "value": "Amanita muscaria"})
            v1 = plug.observe(sensitive=True)["version"]
            gen = next(c for c in rows if c["kind"] == "pick_search" and c["host"] == "genEntry")
            plug.execute("set-text", {"selector": gen["address"], "value": "Amanit"})
            v2 = plug.observe(sensitive=True)["version"]
            ck(v0 == v1 and v1 != v2,
               "typing a value leaves the numbering alone and filtering a picker -- which takes options out of the "
               "document -- moves it: %s -> %s -> %s" % (v0, v1, v2))

            # ...and the version is not "something changed", it is a stated
            # digest over every selector AND id in document order. Ported here
            # rather than observed, because a version that watched only the
            # COUNT would pass every before/after check ever written and still
            # let an index mean a different control.
            def _digest(cs):
                h, txt = 5381, ",".join(c["selector"] + "|" + (c["id"] or "") for c in cs)
                for ch in txt:
                    h = ((h * 33) & 0xFFFFFFFF) ^ ord(ch)
                    h &= 0xFFFFFFFF
                d, out = h, ""
                while True:
                    out = "0123456789abcdefghijklmnopqrstuvwxyz"[d % 36] + out
                    d //= 36
                    if not d:
                        break
                return "v" + out
            fresh = plug.observe(sensitive=True)
            ck(fresh["version"] == _digest(fresh["controls"]),
               "and the version IS that digest, port for port: %s vs %s"
               % (fresh["version"], _digest(fresh["controls"])))

            # 6. a name that resolves to nothing is a typo, not a hazard
            named_no_raise = (plug.risk_for("activate", {"selector": "@no such control here"}),
                              plug.risk_for("activate", {"selector": "action_btn:999"}))
            try:
                plug.execute("activate", {"selector": "@no such control here"})
                stale_msg = "not refused"
            except HarnessError as e:
                stale_msg = str(e)
            ck(named_no_raise[0] is None and (named_no_raise[1] or [None])[0] == "DESTRUCTIVE"
               and "no control answers to" in stale_msg,
               "a NAME that names nothing is refused as not-found and is not raised, while an unresolvable "
               "POSITIONAL selector is still held at DESTRUCTIVE (ADR-141) -- an index is the moment's and a name "
               "is not: %s / %s" % (named_no_raise, stale_msg[:60]))

            # 7. the manifest, and the pools
            spec = next(a for a in plug.descriptor().actions if a.name == "set-text")
            arg = next(x for x in spec.arguments if x.name == "selector")
            good = ["text_in:3", "text_in:3@v1x7k", "#cName", "@working name", "@rCov/4", "@kind=drop_zone"]
            bad2 = ["", "@", "#", "text_in", "text_in:3@v", "text_in:3@x1", "@bad\nname"]
            import re as _re
            rx = _re.compile(arg.pattern)
            ck(all(rx.match(g) for g in good) and not any(rx.match(x) for x in bad2)
               and all(rx.match(e) for e in arg.examples),
               "the manifest's selector pattern takes every address form and nothing else, and its own examples "
               "satisfy it: %s" % [g for g in good if not rx.match(g)])
            live_n = [c for c in rows if c.get("commandable") and (c.get("visible") or c.get("pane"))]
            ck(len(snap["argumentPools"].get("address") or []) == len(live_n) and live_n,
               "the pools publish an address for every control they publish a selector for -- a pool that named "
               "only indexes is what taught four operators to count buttons: %d of %d"
               % (len(snap["argumentPools"].get("address") or []), len(live_n)))

        if page == "stand-sheet.html":
            # 8. a destructive control is destructive by either name
            dest = (snap["argumentPools"].get("activate.destructive") or [])[:2]
            same = [(plug.risk_for("activate", {"selector": d}),
                     plug.risk_for("activate", {"selector": next(c["address"] for c in rows if c["selector"] == d)}))
                    for d in dest]
            ck(dest and all(a == b and a and a[0] == "DESTRUCTIVE" for a, b in same),
               "a control named for removing something is held at DESTRUCTIVE through its address exactly as "
               "through its index -- the raise reads the control, not the spelling: %s" % same[:1])
            # 9. the runner's own spelling is accepted verbatim
            byid = next(c for c in rows if c["id"])
            try:
                ok9, _, out9 = plug.execute("read-control", {"selector": "@control:" + byid["id"]})
            except HarnessError as e:                      # a refusal is an answer, not a crash (ADR-180)
                ok9, out9 = False, {"selector": str(e)[:80]}
            ck(ok9 and out9["selector"] == byid["selector"],
               "the door answers to the runner's own spelling, '@control:<name>', so a task's argument can be "
               "pasted into a call by hand: %s" % out9.get("selector"))
    # ---- the three cases no real page of this kit offers ---------------------
    # An id that another control wears as a LABEL, a label repeated under one
    # host, and a control with no name at all. The kit's own pages name
    # everything, which is why these are built rather than found: an address
    # scheme is only as good as what it does when the page will not help.
    odd = os.path.join(tempfile.mkdtemp(), "odd.html")
    io.open(odd, "w", encoding="utf-8").write(
        u"""<!doctype html><html><head><meta charset="utf-8"><title>odd</title></head><body>
        <button id="zzTarget">first</button>
        <button>zzTarget</button>
        <div id="zzHost"><button>dup</button><button>dup</button></div>
        <button></button>
        </body></html>""")
    pg.goto("file://" + odd.replace(os.sep, "/"), wait_until="domcontentloaded")
    pg.wait_for_timeout(150)
    plug = PP.PagePlugin(pg, "odd.html", kinds=SWARM_KINDS)
    snap = plug.observe(sensitive=True)
    rows = snap["controls"]
    by_label = dict((c["label"], c) for c in rows)
    ck(pg.evaluate(PP.RESOLVE, ["@", "zzTarget", None]).get("selector") == by_label["first"]["selector"],
       "a name that is one control's id and another's label is the ID's -- the order is id, then label, then host, "
       "and a page that writes an id on a second button must not be able to steal a name: %s"
       % pg.evaluate(PP.RESOLVE, ["@", "zzTarget", None]))
    dups = [c for c in rows if c["label"] == "dup"]
    ck(len(dups) == 2
       and pg.evaluate(PP.RESOLVE, ["@", "zzHost/dup#1", None]).get("selector") == dups[1]["selector"]
       and dups[1]["address"] == "@zzHost/dup#1",
       "a label repeated under one host is reached by its number, and the second one publishes that as its address: %s"
       % [c["address"] for c in dups])
    blank = [c for c in rows if not c["id"] and not c["label"]]
    ck(len(blank) == 1 and blank[0]["address"] == blank[0]["selector"] + "@" + snap["version"]
       and pg.evaluate(PP.RESOLVE, list(_form(blank[0]["address"]))).get("selector") == blank[0]["selector"],
       "and a control the page gives no name at all publishes its INDEX, stamped with this snapshot -- an address "
       "that cannot be a name says so instead of being empty: %s" % [c["address"] for c in blank])
    # ---- G. settling (ADR-189) -----------------------------------------------
    #
    # Three of the four blind operators (ADR-187) opened with a `pick` or an
    # `activate` and were told the page had no control of that kind at all,
    # because the kit builds controls in script at load and nothing had stamped
    # them yet. The door settles now. The check that matters most is not that
    # the act works -- it is that the RISK READ of that first act sees the same
    # page the act will, because the gateway asks for the risk first and a
    # plugin that settled only in `execute` would wave a destructive button
    # through on the first call of every session.
    fresh = ctx.new_page()
    fresh.goto("file://" + os.path.join(docs, "stand-sheet.html").replace(os.sep, "/"),
               wait_until="domcontentloaded")
    fp = PP.PagePlugin(fresh, "stand-sheet.html", kinds=SWARM_KINDS)
    ck(fresh.evaluate("() => window.__H_SETTLED || null") is None,
       "a page that has only been navigated to is not settled yet")
    risk0 = fp.risk_for("activate", {"selector": "@↩ Undo"})
    ck(risk0 and risk0[0] == "DESTRUCTIVE" and "undo" in risk0[1],
       "the FIRST call of a session, by name, on a page nothing has looked at, still reads as DESTRUCTIVE -- the "
       "risk read settles the page itself, or it would answer for an empty one and the act would press what the "
       "name turned out to mean: %s" % (risk0,))
    # a SECOND untouched page, because the risk read above has already settled
    # the first one: each claim gets a document nothing has looked at, or the
    # check is measuring the check before it.
    fresh2 = ctx.new_page()
    fresh2.goto("file://" + os.path.join(docs, "stand-sheet.html").replace(os.sep, "/"),
                wait_until="domcontentloaded")
    fp2 = PP.PagePlugin(fresh2, "stand-sheet.html", kinds=SWARM_KINDS)
    try:
        ok_g, _, out_g = fp2.execute("read-control", {"selector": "#kReset"})
    except HarnessError as e:
        ok_g, out_g = False, {"selector": str(e)[:70]}
    ck(ok_g and str(out_g.get("selector", "")).startswith("action_btn:"),
       "and an act can be the first thing a session does -- no leading observe, no snapshot, a name: %s"
       % out_g.get("selector"))
    fresh2.close()
    v_g = fresh.evaluate("() => window.__H_SETTLED || null")
    ck(v_g and v_g == fp.observe(sensitive=True)["version"],
       "the settle marks the document with the version it settled at, and that is the version the snapshot "
       "then reports: %s" % v_g)
    # per document: a reload takes the marker with it, and the answer says so
    okr, _, outr = fp.execute("reload", {})
    ck(okr and outr.get("version") and fresh.evaluate("() => window.__H_SETTLED || null") == outr["version"],
       "a reload settles the document it arrives in and answers with its version -- the marker lives on the "
       "window, so it leaves with the old document and nothing in the plugin has to remember: %s" % outr)
    ok2, _, out2 = fp.execute("read-control", {"selector": "#kReset"})
    ck(ok2, "...and the first call after a reload needs no observe either")
    # ONCE PER DOCUMENT, not once per session. A plugin that remembered "I have
    # settled" would be right about the first page and wrong about every page
    # after it, and a session that navigates is the normal case.
    fresh.goto("file://" + os.path.join(docs, "collection-sheet.html").replace(os.sep, "/"),
               wait_until="domcontentloaded")
    fp.name = "collection-sheet.html"
    try:
        ok3, _, out3 = fp.execute("read-control", {"selector": "#cName"})
    except HarnessError as e:
        ok3, out3 = False, {"selector": str(e)[:70]}
    ck(ok3 and str(out3.get("selector", "")).startswith("text_in:"),
       "a session that navigates settles the page it lands on, not only the one it started on -- the marker is the "
       "document's, and the document is new: %s" % out3.get("selector"))
    # the stale refusal carries the new code
    snap_g = fp.observe(sensitive=True)
    try:
        fp.execute("read-control", {"selector": snap_g["controls"][0]["selector"] + "@vgone"})
        code_g = "not refused"
    except HarnessError as e:
        code_g = e.code
    ck(code_g == "stale",
       "a selector stamped with a snapshot the page has moved past is refused `stale`, not `not_found` and not "
       "`invalid_argument`: the argument was well formed and the control is there -- what expired is the "
       "caller's name for it, and only its own code says read again: %r" % code_g)
    # a control that is not there when the page finishes loading. The loop
    # waits for two readings that AGREE, so a control that appears while it is
    # looking is caught; one reading, or a fixed sleep shorter than the page,
    # would miss it. It is a bounded wait, not a promise: a page that adds a
    # control after the loop has given up is a page the door cannot settle,
    # and that is the honest limit of doing this without a session.
    slow = os.path.join(tempfile.mkdtemp(), "slow.html")
    io.open(slow, "w", encoding="utf-8").write(
        u"""<!doctype html><html><head><meta charset="utf-8"><title>slow</title></head><body>
        <button id="early">early</button>
        <script>setTimeout(function () {
          var b = document.createElement("button");
          b.id = "late"; b.textContent = "late"; document.body.appendChild(b);
        }, 40);</script></body></html>""")
    fresh.goto("file://" + slow.replace(os.sep, "/"), wait_until="domcontentloaded")
    sp = PP.PagePlugin(fresh, "slow.html", kinds=SWARM_KINDS)
    try:
        ok_s, _, out_s = sp.execute("read-control", {"selector": "#late"})
    except HarnessError as e:
        ok_s, out_s = False, {"selector": str(e)[:60]}
    ck(ok_s and out_s.get("selector"),
       "a control the page adds AFTER it finishes loading is there for the first call too -- the loop waits for "
       "two readings of the numbering that agree, so it waits out a page that is still building: %s"
       % out_s.get("selector"))
    fresh.close()

    # ---- H. the manual (ADR-190) ---------------------------------------------
    #
    # Three of ADR-187's remaining findings, and they are all the same
    # complaint: the door published a figure and withheld what a reader needed
    # to act on it. A pool that offers six of sixty-six teaches a client that
    # the pool is not the answer; a control read one at a time that does not
    # say what to call it sends the reader back to the snapshot; a box that is
    # one run of text is unreadable ("bean, common20you plan to keep20"); and a
    # page that prints its own scoring rule while the door publishes only the
    # score makes an operator recover the rule by experiment.
    man = ctx.new_page()
    man.goto("file://" + os.path.join(docs, "collection-sheet.html").replace(os.sep, "/"),
             wait_until="domcontentloaded")
    mp = PP.PagePlugin(man, "collection-sheet.html", kinds=SWARM_KINDS)
    msnap = mp.observe(sensitive=True)
    pk = [p for p in msnap.get("pickers") or [] if p["kind"] == "pick"]
    live = [p for p in pk if p["of"]]
    pool = msnap["argumentPools"]["pick"]
    ck(live and all(p["shown"] == p["of"] for p in live) and max(p["of"] for p in live) > 6
       and sum(p["shown"] for p in live) == len(pool),
       "a picker's pool is every option it offers, not six of them, and the snapshot says shown-of-how-many per "
       "picker: %s" % [(p["selector"], p["shown"], p["of"]) for p in pk])
    far = [c["value"] for c in pool if c["selector"] == live[0]["selector"]][20]
    okp, _, outp = mp.execute("pick", {"selector": live[0]["selector"], "value": far})
    ck(okp and outp["chose"].startswith(far[:12]),
       "...and an option past where the old pool stopped is one the picker actually takes: %r -> %s"
       % (far, outp.get("chose")))

    # a list longer than the cap says so rather than looking complete
    big = os.path.join(tempfile.mkdtemp(), "big.html")
    io.open(big, "w", encoding="utf-8").write(
        u"""<!doctype html><html><head><meta charset="utf-8"><title>big</title></head><body>
        <div id="bigHost"><div class="fek-pick"><input class="search" aria-label="many">
        <div class="opts">""" + u"".join(
            u'<button class="opt" type="button">opt%03d</button>' % i for i in range(PP.PICK_CAP + 25))
        + u"""</div></div></div></body></html>""")
    man.goto("file://" + big.replace(os.sep, "/"), wait_until="domcontentloaded")
    bp = PP.PagePlugin(man, "big.html", kinds=SWARM_KINDS)
    bsnap = bp.observe(sensitive=True)
    bpk = [p for p in bsnap.get("pickers") or [] if p["kind"] == "pick"]
    ck(bpk and bpk[0]["shown"] == PP.PICK_CAP and bpk[0]["of"] == PP.PICK_CAP + 25,
       "and a list longer than the cap publishes the cap and SAYS how many there were -- a pool that quietly "
       "stopped is what taught an operator to distrust pools: %s" % bpk[:1])

    # read-control says what to call it
    man.goto("file://" + os.path.join(docs, "stand-sheet.html").replace(os.sep, "/"),
             wait_until="domcontentloaded")
    rp = PP.PagePlugin(man, "stand-sheet.html", kinds=SWARM_KINDS)
    rsnap = rp.observe(sensitive=True)
    bad_addr = []
    for c in rsnap["controls"][:60]:
        _ok, _m, one = rp.execute("read-control", {"selector": c["selector"]})
        if one.get("address") != c["address"]:
            bad_addr.append((c["selector"], c["address"], one.get("address")))
    ck(not bad_addr,
       "every control read one at a time answers with the same address the snapshot publishes for it -- a reader "
       "identifying a control gets the name to call it by, in the same answer: %s" % bad_addr[:2])
    _ok, _m, byname = rp.execute("read-control", {"selector": rsnap["controls"][0]["address"]})
    ck(byname.get("address") == rsnap["controls"][0]["address"],
       "...and that address is one read-control itself takes, so the two ends of the loop meet")

    # a box's text, split, beside the run of text every task holds
    man.goto("file://" + os.path.join(docs, "breeding-bench.html").replace(os.sep, "/"),
             wait_until="domcontentloaded")
    lp = PP.PagePlugin(man, "breeding-bench.html", kinds=SWARM_KINDS)
    lp.observe(sensitive=True)
    _ok, _m, rep = lp.execute("read-report", {})
    multi = [k for k, v in (rep.get("lines") or {}).items() if len(v) > 2]
    ck(multi and set(rep["lines"]) == set(rep["boxes"]),
       "every box is published split as well as whole, and the two name the same boxes: %d of %d split into more "
       "than two lines" % (len(multi), len(rep["boxes"])))
    invented, compared = [], 0
    for k0, ls in rep["lines"].items():
        # a box whose whole text hit read-report's 4000-character cut cannot be
        # the thing the lines are compared against: the line past the cut is
        # the box's, and the truncated run of text is what is missing it
        if len(rep["boxes"][k0]) >= 4000:
            continue
        compared += 1
        flat = rep["boxes"][k0].replace(" ", "")
        for l in ls:
            if not l or l != l.strip() or l.replace(" ", "") not in flat:
                invented.append((k0, l[:40]))
    ck(compared > 10 and not invented,
       "...and every line of every box is that box's own text, trimmed, with nothing invented and nothing "
       "reworded: %s" % invented[:3])
    # AND NOTHING TWICE. Leaf blocks partition a box; every block would not --
    # a section's own line would repeat each of its children's. Counted in
    # characters, because two sibling tiles may legitimately read "10" and
    # "10.0%" and neither contains the other in any sense that matters.
    doubled = []
    for k0, ls in rep["lines"].items():
        if len(rep["boxes"][k0]) >= 4000 or not ls:
            continue
        if sum(len(l.replace(" ", "")) for l in ls) > len(rep["boxes"][k0].replace(" ", "")):
            doubled.append((k0, len(ls)))
    ck(not doubled,
       "...and no box's lines say more than the box does -- a split that took every block rather than the leaves "
       "would hand a section's text back once for the section and again for each thing in it: %s" % doubled[:3])

    # what the page says about its own arithmetic
    man.goto("file://" + os.path.join(docs, "pheno-tracker.html").replace(os.sep, "/"),
             wait_until="domcontentloaded")
    pp = PP.PagePlugin(man, "pheno-tracker.html", kinds=SWARM_KINDS)
    pp.observe(sensitive=True)
    _ok, _m, prep = pp.execute("read-report", {})
    rules = prep.get("rules") or []
    text = " ".join(r["t"] for r in rules)
    ck(len(rules) > 4 and all(r["t"] and len(r["t"]) <= 400 for r in rules)
       and any(r.get("host") for r in rules),
       "the page's own prose about itself is handed over, each piece with the identified thing it sits in: "
       "%d piece(s)" % len(rules))
    ck("dropped" in text and "weighted" in text,
       "and on the pheno tracker it carries the scoring rule a blind operator had to recover by experiment -- an "
       "unscored trait DROPPED from the weighted total rather than counted as a 1 -- quoted, not interpreted: %s"
       % [r["t"][:80] for r in rules if "dropped" in r["t"]][:1])
    # prose inside prose, on a page built for it: the kit nests these rarely
    # enough that a mutant taking every .hint and .fine rather than the
    # innermost would sail through the real pages
    nest = os.path.join(tempfile.mkdtemp(), "nest.html")
    io.open(nest, "w", encoding="utf-8").write(
        u"""<!doctype html><html><head><meta charset="utf-8"><title>nest</title></head><body>
        <div id="nHost"><div class="hint">the outer note
          <p class="fine">the inner rule is the one that says how</p></div></div>
        </body></html>""")
    man.goto("file://" + nest.replace(os.sep, "/"), wait_until="domcontentloaded")
    np_ = PP.PagePlugin(man, "nest.html", kinds=SWARM_KINDS)
    np_.observe(sensitive=True)
    _ok, _m, nrep = np_.execute("read-report", {})
    nr = nrep.get("rules") or []
    ck(len(nr) == 1 and nr[0]["t"] == "the inner rule is the one that says how" and nr[0]["host"] == "nHost",
       "prose that contains prose is handed over once, as the innermost piece -- a note wrapping a rule is not the "
       "rule, and handing back both would say the same thing twice: %s" % [(x["t"][:40], x["host"]) for x in nr])
    man.close()
    ctx.close()
    b.close()


# ---- I. the session, on a page that rebuilds (ADR-191) -----------------------
#
# The page plugin's part of ADR-191 is one sentence: a control is its ADDRESS.
# Everything below follows from it, and none of it is true of a diff that
# compared the controls list position by position -- which is what a diff
# written without ADR-188 would have had to do, and why these two slices are
# in this order.
#
# The measure is the one the third blind trial asked for: how much does a
# client have to read to find out what its own call did.

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=H.VIEWPORT)
    ctx.set_offline(True)
    ctx.add_init_script(H.STUBS)
    pg = ctx.new_page()
    docs = os.environ.get("CSRBT_DOCS_DIR") or os.path.join(_kit.ROOT, "docs")
    try:
        from swarm import SWARM_KINDS
    except Exception:
        SWARM_KINDS = None
    pg.goto("file://" + os.path.join(docs, "collection-sheet.html").replace(os.sep, "/"),
            wait_until="domcontentloaded")
    plug = PP.PagePlugin(pg, "collection-sheet.html", kinds=SWARM_KINDS)
    TK = "i" * 30
    g = C.Gateway(C.Registry([plug]),
                  C.Policy(token=TK, allow={"SENSITIVE_READ": True, "DRAFT": True,
                                            "MUTATE": True}, enabled=True))
    PID = plug.descriptor().id

    snap = g.observe(TK, PID)
    nsnap = len(json.dumps(snap))
    ck(snap.get("stamp") and snap.get("version"),
       "a page snapshot carries BOTH stamps: `version` is the numbering's (ADR-188, what a "
       "stamped selector is held to) and `stamp` is the observation's (what `since` is asked "
       "with). They answer different questions and a page that published one of them would "
       "leave the other unaskable: %r / %r" % (snap.get("stamp"), snap.get("version")))
    # Something distinctive in a field first, so what follows is about a value
    # the page is actually holding rather than about a row of empty strings.
    typed = [c for c in g.observe(TK, PID)["controls"]
             if c["kind"] == "text_in" and c.get("commandable") and c.get("visible")][0]
    MIXED = "ZqxMiXeD191"
    plug.execute("set-text", {"selector": typed["address"] or typed["selector"], "value": MIXED})
    snap = g.observe(TK, PID)
    nsnap = len(json.dumps(snap))
    mine = [c for c in snap["controls"]
            if (c.get("address") or c["selector"]) == (typed["address"] or typed["selector"])][0]
    ck(mine.get("value") == MIXED,
       "the snapshot hands the field's value over AS THE FIELD HOLDS IT -- a reading of its "
       "own (trimmed, folded, rounded) would be the door editing the page's data on the way "
       "out, and a client comparing what it typed against what came back would be told it "
       "had failed: %r" % mine.get("value"))

    vals = [c for c in snap["controls"] if c.get("value") is not None]
    ck(vals and all(c.get("commandable") for c in vals),
       "under SENSITIVE_READ a control carries WHAT IS IN IT, so a client holding that rung "
       "reads the page's entered state in the snapshot it was already taking rather than "
       "one read-control per control: %d of %d controls" % (len(vals), len(snap["controls"])))
    _ok1, _m1, one = plug.execute("read-control", {"selector": mine["address"] or mine["selector"]})
    ck(str(one.get("value")) == mine["value"],
       "and it is the same value read-control answers with -- two readers of one field, "
       "held to each other: %r vs %r" % (one.get("value"), mine["value"]))
    # By a HANDLE to the element, not by its selector: making it read-only
    # reclassifies it, every text control after it renumbers, and a restore by
    # the old selector would un-lock whichever control had moved into that
    # index -- which is the ADR-188 mistake, made by this suite.
    hand = pg.evaluate_handle("(sel) => document.querySelector('[data-h=\"' + sel + '\"]')",
                              mine["selector"])
    pg.evaluate("(e) => { e.readOnly = true; }", hand)
    locked = plug.observe(sensitive=True)
    leaked = [c for c in locked["controls"]
              if not c.get("commandable") and c.get("value") is not None]
    ck(not leaked,
       "and a control this session may not command hands over nothing: `commandable` is what "
       "excludes a password field, so a value published past it would publish one: %s"
       % [(c["selector"], c["kind"]) for c in leaked[:3]])
    pg.evaluate("(e) => { e.readOnly = false; }", hand)
    shy = plug.observe(sensitive=False)
    ck(all(c.get("value") is None for c in shy["controls"]) and shy.get("redacted"),
       "and a session WITHOUT that rung gets none of them: the redaction line says entered "
       "values are omitted, and it has to be true of the snapshot and not only of "
       "read-control: %d carried a value"
       % len([c for c in shy["controls"] if c.get("value") is not None]))

    quiet = g.observe(TK, PID, since=snap["stamp"])
    ck(quiet.get("changed") is False and len(json.dumps(quiet)) * 100 < nsnap,
       "a page nobody has touched answers `nothing changed` in a line: %d bytes against a "
       "%d-byte snapshot" % (len(json.dumps(quiet)), nsnap))

    # a pick filters the picker: options leave the document, one becomes selected
    pool = snap["argumentPools"]["pick"]
    chosen = pool[0]
    r = g.execute(TK, PID, {"request_id": "i-1", "action": "pick", "arguments": chosen})
    d = r["diff"]
    nd = len(json.dumps(d))
    ck(r["ok"] and d["changed"] is True and d["since"] == snap["stamp"],
       "and an act answers with what it did, against the snapshot the client planned it "
       "from: %s" % {k: d.get(k) for k in ("since", "changed")})
    ck(nd * 10 < nsnap,
       "THE MEASURE: what a client must read to learn what its own call did, %d bytes "
       "against the %d-byte snapshot every ADR-187 operator re-read after every act"
       % (nd, nsnap))
    ck(d["fields"].get("version") and d["fields"]["version"][0] != d["fields"]["version"][1],
       "the numbering moved, and the diff says so in one line rather than leaving a client "
       "to compare two snapshots for it: %s" % d["fields"].get("version"))
    alt = d["altered"].get("controls") or {}
    ck(chosen["value"] in [k.lstrip("@") for k in alt] or ("@" + chosen["value"]) in alt,
       "the option that was picked is named by its ADDRESS among the controls that changed, "
       "not by an index: %s" % list(alt)[:4])
    sel_moved = [k for k, v in alt.items() if "selector" in v and list(v) == ["selector"]]
    ck(sel_moved,
       "and a control whose only change is that it RENUMBERED is reported as that one field "
       "moving -- keyed positionally it would have read as a control vanishing and a "
       "different one appearing, which is the mistake the whole address grammar exists to "
       "stop: %s" % [(k, alt[k]) for k in sel_moved[:2]])
    ck(not d["appeared"].get("controls"),
       "nothing APPEARED: a filter takes options out of the document, and a diff that said "
       "three hundred controls arrived would be describing the rebuild rather than the act: "
       "%s" % list((d["appeared"].get("controls") or [])[:2]))
    ck(d["counts"].get("pickChoices") and d["counts"]["pickChoices"][1] < d["counts"]["pickChoices"][0],
       "the pools are counted rather than listed -- every one of them is derived from "
       "`controls`, so naming each arrival would say the same thing twice and cost for it: "
       "%s" % d["counts"].get("pickChoices"))
    ck(any(c["where"].startswith("controls.") for c in d["capped"]) or
       len(d["vanished"].get("controls") or []) < C.DIFF_CAP,
       "and where the diff stopped naming, it says so: %s" % d["capped"])

    # a structural act: the pane, and the two tabs that swapped
    tabs = [t for t in snap["tabs"] if not t["open"]]
    r2 = g.execute(TK, PID, {"request_id": "i-2", "action": "show-pane",
                             "arguments": {"pane": tabs[0]["pane"]}})
    d2 = r2["diff"]
    ck(d2["fields"].get("route") and d2["fields"]["route"][1] == tabs[0]["pane"],
       "a pane change moves `route`, and the diff names the pane that is now open: %s"
       % d2["fields"].get("route"))
    at = d2["altered"].get("tabs") or {}
    ck(at.get(tabs[0]["pane"], {}).get("open") == [False, True]
       and any(v.get("open") == [True, False] for k, v in at.items() if k != tabs[0]["pane"]),
       "and BOTH tabs -- the one that opened and the one that closed -- keyed by the pane "
       "each drives: %s" % at)

    # the stamp is the observation's, and it moves for a value the version cannot see
    s3 = g.observe(TK, PID)
    texts = [c for c in s3["controls"]
             if c["kind"] == "text_in" and c.get("commandable") and c.get("visible")]
    if texts:
        who = texts[0]["address"] or texts[0]["selector"]
        r3 = g.execute(TK, PID, {"request_id": "i-3", "action": "set-text",
                                 "arguments": {"selector": who, "value": "Zqx-191"}})
        d3 = r3["diff"]
        ck(d3["changed"] is True and "version" not in d3["fields"],
           "typing into a field changes the OBSERVATION and not the numbering: the stamp "
           "moves, `version` does not, and a door that had only `version` could not tell a "
           "client its own text had landed: %s" % {k: d3["fields"].get(k) for k in ("version",)})

    # and the two ends agree: the stamp an act hands back is what `since` calls current
    q = g.observe(TK, PID, since=r2["stamp"] if not texts else r3["stamp"])
    ck(q.get("changed") is False,
       "the stamp an act hands back is the one the next `since` calls current, so a client "
       "that reads every response never has to guess where the session is")

    pg.close()
    ctx.close()
    b.close()

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
