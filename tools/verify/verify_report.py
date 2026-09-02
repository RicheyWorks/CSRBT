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
     named; every table's cells; every .row2 list's count; nothing outside
     the conventions
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
  <div id="ignored-plain">not a box</div>
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
</section>
<script>
  document.querySelectorAll('.tab').forEach(function(t){ t.addEventListener('click', function(){
    document.querySelectorAll('.tab').forEach(function(x){ x.classList.remove('on'); });
    document.querySelectorAll('.pane').forEach(function(x){ x.classList.remove('on'); });
    t.classList.add('on'); document.getElementById(t.getAttribute('data-pane')).classList.add('on'); }); });
  window.picked = null;
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
    ck(r["figures"].get("families") == "23" and r["figures"].get("families #2") == "2",
       "flat figures: the first label wins and a second carries #2: %s" % r["figures"])
    ck(r["by"].get("packStat", {}).get("families") == "23" and r["by"].get("anBox", {}).get("families") == "2",
       "and by the box: a label is a fact of its box: %s" % r["by"])
    ck(r["by"]["anBox"].get("doubling time") == "1.000 h" and r["by"]["anBox"].get("doubling time #2") == "60.0 min",
       "the same label twice in one box keeps both: %s" % r["by"]["anBox"])
    ck(r["by"]["anBox"].get("DLI") == "38.9 mol/m²/d", "a <small> unit inside the value is spaced off: %r" % r["by"]["anBox"].get("DLI"))
    ck(r["order"][:2] == ["families", "collections"], "figures are in document order: %s" % r["order"][:3])
    boxes = r["boxes"]
    ck("anBox" in boxes and "lower bound" in boxes["anBox"] and "selOut" in boxes and "eco-out" in boxes and
       "triTable" in boxes and "kMatrix" in boxes and "lPlan" in boxes and "toast" in boxes and "packStat" in boxes
       and "cList" in boxes,
       "boxes follow the kit's naming -- an*, *Out, *Box, *Stat, *Matrix, *Plan, *Table, *List, hyphenated, toast: %s" % sorted(boxes))
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

    pool = snap["argumentPools"].get("pick") or []
    ck(len(pool) == 4 and all(set(x) == {"selector", "value"} and x["selector"] == sel for x in pool) and
       {x["value"] for x in pool} == {"Amanita muscaria", "Amanita", "Suillus", "Pleurotus"},
       "the snapshot publishes each picker's option labels as an argument-set pool for pick, sub-lines stripped: %s" % pool)

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
    ctx.close()
    b.close()

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
