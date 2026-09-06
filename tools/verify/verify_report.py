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
import io, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import harness_plugin_page as PP
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
  <div id="mStats"><div class="stat"><span class="k">Nodes</span><span class="v">13</span></div></div>
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
    ck(r["order"][:3] == ["families", "Nodes", "collections"], "figures are in document order: %s" % r["order"][:3])
    boxes = r["boxes"]
    ck("anBox" in boxes and "lower bound" in boxes["anBox"] and "selOut" in boxes and "eco-out" in boxes and
       "triTable" in boxes and "kMatrix" in boxes and "lPlan" in boxes and "toast" in boxes and "packStat" in boxes
       and "cList" in boxes,
       "boxes follow the kit's naming -- an*, *Out, *Box, *Stat, *Matrix, *Plan, *Table, *List, hyphenated, toast: %s" % sorted(boxes))
    ck("kres" in boxes and "msg" in boxes and "spCheck" in boxes,
       "the keys' result, the visualizer's message and the proofs' check are boxes too (ADR-129): %s" % sorted(boxes))
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
    ck(ok and sorted(ch) == ["theChart", "theTrend"],
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

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
