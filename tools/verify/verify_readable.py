# -*- coding: utf-8 -*-
"""The figures a page publishes that no task can read -- checked (ADR-146).

`tools/audit_readable.py` says 26 written elements across the kit are outside
`read-report`'s reach. That number is a worklist and a ratchet, so it has to be
right about four things a fixture can pin exactly:

  A. WHAT COUNTS AS WRITTEN. An element whose rendered text differs from what
     the FILE says -- so a figure painted at boot counts, not only one a task
     brings into being -- at the DEEPEST id in each chain, because a parent's
     text changes whenever a child's does. Controls are not reports.
  B. WHAT COUNTS AS READABLE. All three of read-report's channels: boxes by
     name, tables by their host, charts by the svg's host. An audit that knew
     only about boxes would disagree with the reader it exists to measure.
  C. AN ENTRY HOST IS NOT A REPORT. A div the Field Entry Kit mounts controls
     into changes its text and is not a figure; entry_reach accounts for what
     is inside it. Structural -- it holds a control -- not by name.
  D. THE RATCHET AND THE FURNITURE. The ceiling falls on request and never
     rises silently; declaring furniture needs a reason that goes into the
     ledger.

Run:  python3 tools/verify/verify_readable.py
"""
MUTATE_ROLE = "subject"
import io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import audit_states as S
import audit_readable as R

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>readable fixture</title>
<style>.pane{display:none}.pane.on{display:block}
 button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>readable fixture</h1>
<button class="tab" data-pane="p1">One</button><button class="tab" data-pane="p2">Two</button>
<section class="pane on" id="p1">
  <!-- written at BOOT, and named the kit's way: readable -->
  <div id="anBoot"></div>
  <!-- written at BOOT, named outside the convention: the case this audit exists for -->
  <div id="heatload"></div>
  <!-- written only once the ENTRY runs, outside the convention -->
  <div id="tally"></div>
  <!-- a card AROUND an unreadable figure: only the deepest id is the owner -->
  <div id="wrapper"><div id="inner"></div></div>
  <!-- a table: read-report reads it through the tables channel -->
  <div id="tableHost"></div>
  <!-- an svg: read-report reads it through the charts channel (ADR-140) -->
  <div id="plotHost"></div>
  <!-- the page never writes this one -->
  <div id="prose">A paragraph the page never touches.</div>
  <!-- a control's own value is not a report -->
  <input id="typed" aria-label="typed">
  <button id="go" type="button">Go</button>
  <!-- an <option>: not a control the swarm discovers, and still not a report -->
  <select id="pick" aria-label="pick"><option id="opt1">a</option></select>
</section>
<section class="pane" id="p2">
  <!-- behind a tab, written at boot, outside the convention -->
  <div id="behind"></div>
  <!-- an entry host: the kit mounts controls into it and its text changes -->
  <div id="hostEntry"></div>
</section>
<script>
  function $(i){ return document.getElementById(i); }
  document.querySelectorAll('.tab').forEach(function(t){ t.addEventListener('click', function(){
    document.querySelectorAll('.pane').forEach(function(x){ x.classList.remove('on'); });
    $(t.getAttribute('data-pane')).classList.add('on');
    // written only once its tab is pressed: a figure behind a tab
    if (t.getAttribute('data-pane') === 'p2') $('behind').textContent = 'behind a tab: 7'; }); });
  // BOOT
  $('anBoot').textContent = 'boot analysis: 3 of 4';
  $('heatload').textContent = 'Folded aspect 0 deg (cool)';
  $('inner').textContent = 'the inner figure: 42';
  $('tableHost').innerHTML = '<table><tr><th>k</th><th>v</th></tr><tr><td>a</td><td>1</td></tr></table>';
  $('plotHost').innerHTML = '<svg viewBox="0 0 10 10"><text x="1" y="2">9</text>'
    + '<rect x="0" y="0" width="3" height="3"></rect></svg>';
  $('hostEntry').innerHTML = '<label>picked</label><input aria-label="picked">'
    + '<button type="button">+</button>';
  // ONLY ONCE THE ENTRY RUNS
  $('opt1').textContent = 'b';
  $('go').addEventListener('click', function(){
    $('tally').textContent = 'stems: 4';
    $('go').textContent = 'Done';        // a control's own label is not a report
  });
</script></body></html>
"""

TASKS = {
    "page-fixture-science": {
        "id": "page-fixture-science", "target": "page", "page": "fixture.html",
        "goal": "press the one button that brings a figure into being",
        "steps": [
            {"id": "obs", "action": "observe"},
            {"id": "go", "action": "activate", "arguments": {"selector": "@control:go"}},
        ],
    },
}

# A page with NO TASK. Nothing replays here, so nothing discovers the controls
# unless the audit stamps them itself -- and an audit that leans on the entry to
# do its stamping reports every entry host on such a page as a figure.
FIXTURE2 = u"""<!doctype html><html><head><meta charset="utf-8"><title>no task</title></head><body>
<h1>no task here</h1>
<div id="lonely"></div>
<div id="mountEntry"></div>
<script>
  document.getElementById('lonely').textContent = 'a figure nobody reads: 5';
  document.getElementById('mountEntry').innerHTML =
    '<label>picked</label><input aria-label="picked"><button type="button">+</button>';
</script></body></html>
"""

tmp = tempfile.mkdtemp(prefix="readable_")
docs = os.path.join(tmp, "docs")
os.mkdir(docs)
io.open(os.path.join(docs, "fixture.html"), "w", encoding="utf-8").write(FIXTURE)
io.open(os.path.join(docs, "fixture2.html"), "w", encoding="utf-8").write(FIXTURE2)
tasks_dir = os.path.join(tmp, "tasks")
os.mkdir(tasks_dir)
for tid, t in TASKS.items():
    io.open(os.path.join(tasks_dir, tid + ".json"), "w", encoding="utf-8").write(json.dumps(t, indent=1))
S.TASKS_DIR = tasks_dir
os.environ["CSRBT_DOCS_DIR"] = docs
R.LEDGER = os.path.join(tmp, "readable_ledger.json")

got = R.walk("fixture.html", tasks_dir)
r = got["fixture.html"]
written, readable = r["written"], set(r["readable"])
bad = R.unreadable(r, {})

# ---- A. what counts as written ----------------------------------------------
ck(r.get("task") == "page-fixture-science",
   "the page's own task is what is replayed, the same entry entry_reach and the three audits "
   "replay: %s" % r.get("task"))
ck("heatload" in written,
   "an element written AT BOOT counts: the baseline is what the FILE says, rendered by nothing, "
   "not what the page has already made of itself -- against a post-load baseline the stand "
   "sheet's plot area and expansion factor read as never written: %s" % written)
ck("tally" in written,
   "...and so does one that only exists once the entry has run: a figure that appears when a "
   "stem is tallied is exactly the figure a reader most wants held: %s" % written)
ck("behind" in written,
   "a figure behind a tab is a figure -- the page is walked through every state before it is "
   "measured: %s" % written)
ck("inner" in written and "wrapper" not in written,
   "only the DEEPEST id in a chain owns the change: a parent's text changes whenever a child's "
   "does, and reporting the card around a figure as a second figure would triple this number "
   "on every page in the kit: %s" % written)
ck("prose" not in written,
   "an element the page never writes is not a written element, however much text it holds: %s"
   % written)
ck("go" not in written,
   "a control is not a report, even when its own label changes: a stepper's readout moving is "
   "the control, and entry_reach is the file that accounts for those: %s" % written)
ck("opt1" not in written and "typed" not in written and "pick" not in written,
   "and neither is an <option>, an input or a select -- a value is not a figure, whether or not "
   "the swarm happens to have stamped it as a control: %s" % written)

# ---- B. what counts as readable ---------------------------------------------
ck("anBoot" in readable and "anBoot" not in bad,
   "an element named the kit's way -- an analysis, an *Out, a *Box, *Stats, *Card -- is read as "
   "a box and is not on the worklist: %s" % sorted(readable))
ck("tableHost" in readable and "tableHost" not in bad,
   "read-report has THREE channels, and a table is read through the second one, keyed by its "
   "host: an audit that knew only about boxes would disagree with the reader it measures: %s"
   % sorted(readable))
ck("plotHost" in readable and "plotHost" not in bad,
   "...and an svg through the third, the chart reader ADR-140 added: %s" % sorted(readable))
ck("heatload" in bad and "tally" in bad and "behind" in bad and "inner" in bad,
   "and everything else the page writes is on the worklist, NAMED -- a task cannot fail to hold "
   "a figure it cannot see: %s" % bad)
ck(len(bad) == 4, "four unreadable figures on this fixture, no more and no fewer: %s" % bad)

# ---- C. an entry host is not a report ---------------------------------------
ck("hostEntry" not in written and "hostEntry" not in bad,
   "a div the entry kit mounts CONTROLS into is not a figure: its text changes because controls "
   "arrived in it, and counting it made 41 pages' worth of *Entry hosts read as figures the "
   "harness cannot see -- true of the string, false of the thing: %s" % written)

got2 = R.walk("fixture2.html", tasks_dir)
r2 = got2["fixture2.html"]
ck(r2.get("task") is None,
   "a page with no task replays nothing -- and is still measured: %s" % r2.get("task"))
ck("mountEntry" not in r2["written"],
   "...so the entry host on it is skipped because the AUDIT stamped the controls, not because "
   "somebody else's entry happened to: an audit that leans on the entry for that reports every "
   "mount on every task-less page as a figure: %s" % r2["written"])
ck(R.unreadable(r2, {}) == ["lonely"],
   "and the one figure it really does publish blind is the one on the worklist: %s"
   % R.unreadable(r2, {}))

# ---- D. the ratchet and the furniture ---------------------------------------
rc = R.main([])
led = json.load(io.open(R.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["unreadable"] == bad and "ceiling" not in led,
   "a first reading records what it found and no ceiling: nothing to compare against is not a "
   "failure: %s" % led)
rc = R.main(["--raise-floors"])
led = json.load(io.open(R.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led.get("ceiling") == 4,
   "the ceiling is set on request, at today's reading: %s" % led)

state = R.load()
state["pages"]["fixture.html"]["ceiling"] = 3
R.save(state)
rc = R.main([])
ck(rc != 0,
   "a page carrying MORE unreadable figures than its ceiling fails, with no flag: run_all runs "
   "an audit with no arguments, and a ceiling that only bit under --check would be a ceiling "
   "nothing ever checked")
rc = R.main(["--check"])
ck(rc != 0, "--check is accepted for symmetry with the kit's other ratchets, and refuses too")

state = R.load()
state["pages"]["fixture.html"]["ceiling"] = 4
R.save(state)
ck(R.main([]) == 0, "back at its ceiling, the page passes")

rc = R.main(["--furniture", "fixture.html:heatload"])
ck(rc != 0,
   "declaring furniture WITHOUT a reason is refused: a list of things this audit is choosing "
   "not to care about is only useful if every line says why")
rc = R.main(["--furniture", "fixture.html:heatload", "--reason", "a rehearsal, not a reading"])
led = json.load(io.open(R.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["furniture"]["heatload"] == "a rehearsal, not a reading",
   "...and with one, the reason is what is stored: %s" % led.get("furniture"))
got2 = R.walk("fixture.html", tasks_dir)
bad2 = R.unreadable(got2["fixture.html"], R.furniture_of(R.load(), "fixture.html"))
ck(len(bad2) == 3 and "heatload" not in bad2,
   "declared furniture leaves the worklist -- and only that element: %s" % bad2)
ck(R.main([]) == 0, "the ratchet runs downward: fewer than the ceiling is never a failure")
rc = R.main(["--raise-floors"])
led = json.load(io.open(R.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("ceiling") == 3,
   "...and --raise-floors LOWERS it, because this ceiling only ever comes down: %s" % led)

# ---- E. the audit does not disagree with the reader --------------------------
ck(set(bad).isdisjoint(readable),
   "nothing is both readable and on the worklist: the two sets come from the reader itself, "
   "not from a second copy of its naming rule")

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
