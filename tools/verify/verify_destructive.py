# -*- coding: utf-8 -*-
"""What one tap can destroy, and whether the page asks -- checked (ADR-209).

`tools/audit_destructive.py` says 0 of 95 destructive controls across this kit
take two or more records on one tap and ask nothing. It said 15 on the day it
was written. That number is a worklist and a ratchet, and it is wrong in both
directions unless six things are right, so a fixture pins each:

  A. WHAT COUNTS AS A DESTRUCTIVE CONTROL is the gateway's own rule -- the same
     `destroys` the risk ladder raises on and the outputs audit refuses to
     press -- and only a control the door would press (ADR-208).
  B. THE LOSS IS READ FROM THE PAGE'S OWN AUTOSAVE, not from rows on the
     screen. A record shown in a list AND in a results table is one record; the
     first draft of this audit counted it twice and called a row remover a bulk
     delete.
  C. ...AND THE SCREEN IS THE FALLBACK, for a page with no autosave, reported
     as such.
  D. ASKING BEATS LOSING. The harness stub answers confirm() with true, so the
     act still happens and the loss is still measured -- a rule that stopped at
     "it asked" would not know whether asking stopped anything.
  E. ONE RECORD IS NOT A BULK DELETE. Every list in this kit that can lose a row
     has an Undo beside it, and a rule that fired on a crossed-off chip would be
     turned off within a week -- after which the sheet-clearing ones would be
     invisible again.
  F. THE RATCHET AND THE EXEMPTION. The ceiling falls on request and never
     rises silently; an exemption needs a reason and the reason is stored.

Run:  python3 tools/verify/verify_destructive.py
"""
MUTATE_ROLE = "fixture-builder"     # the temp dir here holds fixture pages
import contextlib, importlib.util, io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import audit_states as S
import harness_plugin_page as PP
import audit_destructive as A

_kspec = importlib.util.spec_from_file_location(
    "keep", os.path.join(_kit.TOOLS_DIR, "keep.py"))
keep = importlib.util.module_from_spec(_kspec)
_kspec.loader.exec_module(keep)

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# A page with an autosave: rows live in `recs`, and the results table shows the
# same rows a second time. That second showing is the whole point of B.
FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>destructive fixture</title>
<style>%s
 button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>destructive fixture</h1><div id="toast" class="toast"></div>
<div id="keepBox"></div>
<label>Plot <input id="f-plot" type="text" aria-label="Plot"></label>
<label>Observer <input id="f-obs" type="text" aria-label="Observer"></label>
<button id="add" type="button">Add a row</button>
<div class="rowlist" id="rList"></div>
<div id="anOut"></div>
<!-- the bulk removers -->
<button id="clearBare" type="button">Clear every row</button>
<button id="clearAsks" type="button">Reset the sheet</button>
<!-- one record, which is what an undo is for -->
<button id="dropOne" type="button">Delete the last row</button>
<!-- takes only what is TYPED IN BOXES, and asks: two records, no array in sight -->
<button id="wipeText" type="button">Erase the header</button>
<!-- a destructive name over something that holds nothing -->
<button id="clearEmpty" type="button">Clear the filter</button>
<!-- NOT a destructive control: the multiplication sign in the middle of a name -->
<button id="matrix" type="button">Copy host &#215; taxon matrix</button>
<!-- NOT a control the door presses: a box whose LABEL says clear (ADR-208) -->
<label>Clear the notes <input id="notes" type="text" aria-label="Clear the notes"></label>
<script>
%s
</script>
<script>
  var $=function(i){return document.getElementById(i);};
  var recs=[], KEPT;
  function render(){
    $("rList").innerHTML = recs.map(function(r,i){
      return '<div class="row2"><span>'+r.plot+'</span><button type="button" data-i="'+i+
             '">\\u2715</button></div>'; }).join("");
    /* THE SAME ROWS A SECOND TIME. A results table built from the records is
       what every bench in this kit does, and it is why counting rows on the
       screen reads one record as two. */
    $("anOut").innerHTML = recs.length
      ? '<table><tr><th>n</th><th>plot</th></tr>' + recs.map(function(r,i){
          return '<tr><td>'+(i+1)+'</td><td>'+r.plot+'</td></tr>'; }).join('') + '</table>'
      : '';
    Array.prototype.forEach.call($("rList").querySelectorAll("button[data-i]"), function(b){
      b.addEventListener("click", function(){
        recs.splice(+b.getAttribute("data-i"), 1); render(); }); });
    if (KEPT) KEPT.touch();
  }
  $("add").addEventListener("click", function(){
    recs.push({plot: "p" + (recs.length + 1)}); render(); });
  $("clearBare").addEventListener("click", function(){ recs = []; render(); });
  $("clearAsks").addEventListener("click", function(){
    if (recs.length && !confirm("Reset the sheet? " + recs.length + " row(s) go.")) return;
    recs = []; render(); });
  $("dropOne").addEventListener("click", function(){ recs.pop(); render(); });
  $("wipeText").addEventListener("click", function(){
    var n = 0;
    ["f-plot","f-obs"].forEach(function(id){ if($(id).value.trim()) n++; });
    if (n && !confirm("Erase the header? " + n + " typed field(s) go.")) return;
    $("f-plot").value = ""; $("f-obs").value = ""; if (KEPT) KEPT.touch(); });
  $("clearEmpty").addEventListener("click", function(){ $("notes").value = ""; });
  $("matrix").addEventListener("click", function(){ $("toast").textContent = "copied"; });
  KEPT = KEEP.wire({ key: "csrbtDestructiveFixture", format: 1, mount: "keepBox",
    noun: "this fixture",
    snapshot: function(){
      var f = KEEP.formSnapshot(), k, any = recs.length;
      if (!any) for (k in f) if (f.hasOwnProperty(k) && String(f[k]).trim() !== "") any = true;
      return any ? { fields: f, state: { recs: recs } } : null; },
    restore: function(b){ if(!b||!b.state) return false;
      KEEP.formRestore(b.fields); recs = b.state.recs || []; render(); return true; } });
  render();
</script></body></html>
""" % (keep.CSS, keep.JS)

# A page with NO autosave at all, so the screen is the only reading there is.
BARE = u"""<!doctype html><html><head><meta charset="utf-8"><title>bare fixture</title>
<style>button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>bare fixture</h1><div id="toast" class="toast"></div>
<div class="rowlist" id="rList"></div>
<button id="add" type="button">Add a row</button>
<button id="wipe" type="button">Erase the list</button>
<script>
  var $=function(i){return document.getElementById(i);};
  var recs=[];
  function render(){ $("rList").innerHTML = recs.map(function(r){
      return '<div class="row2"><span>'+r+'</span></div>'; }).join(""); }
  $("add").addEventListener("click", function(){ recs.push("r"+(recs.length+1)); render(); });
  $("wipe").addEventListener("click", function(){ recs = []; render(); });
  render();
</script></body></html>
"""

# A page that ASKS and destroys anyway. No page in this kit does this -- which is
# exactly why it is written here: a rule with no violator cannot show that it
# fires (ADR-207), and the confirmations ADR-209 put between a person and their
# morning are now the only thing standing there.
DEFIANT = u"""<!doctype html><html><head><meta charset="utf-8"><title>defiant fixture</title>
<style>button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>defiant fixture</h1><div id="toast" class="toast"></div>
<div class="rowlist" id="rList"></div>
<button id="add" type="button">Add a row</button>
<!-- asks, and then does it whatever the answer -->
<button id="clearAnyway" type="button">Clear every row</button>
<!-- asks, and honours the answer -->
<button id="clearHonest" type="button">Erase the list</button>
<script>
  var $=function(i){return document.getElementById(i);};
  var recs=[];
  function render(){ $("rList").innerHTML = recs.map(function(r){
      return '<div class="row2"><span>'+r+'</span></div>'; }).join(""); }
  $("add").addEventListener("click", function(){ recs.push("r"+(recs.length+1)); render(); });
  $("clearAnyway").addEventListener("click", function(){
    /* the shape under test: the answer is asked for and thrown away */
    confirm("Clear every row? " + recs.length + " go.");
    recs = []; render(); });
  $("clearHonest").addEventListener("click", function(){
    if (recs.length && !confirm("Erase the list? " + recs.length + " go.")) return;
    recs = []; render(); });
  render();
</script></body></html>
"""

TASKS = {
    "page-fixture-science": {
        "id": "page-fixture-science", "target": "page", "page": "fixture.html",
        "goal": "put three rows and a plot name on the fixture, so that what a tap takes is "
                "measured with the page's own data in it",
        "steps": [
            {"id": "obs", "action": "observe"},
            {"id": "plot", "action": "set-text",
             "arguments": {"selector": "@control:f-plot", "value": "north slope"}},
            {"id": "obs2", "action": "set-text",
             "arguments": {"selector": "@control:f-obs", "value": "RJ"}},
            {"id": "a1", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "a2", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "a3", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "look", "action": "read-report"},
        ],
    },
    "page-defiant-science": {
        "id": "page-defiant-science", "target": "page", "page": "defiant.html",
        "goal": "put three rows on the fixture that asks and ignores the answer, so the refusal "
                "path is watched on a page with data in it",
        "steps": [
            {"id": "obs", "action": "observe"},
            {"id": "a1", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "a2", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "a3", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "look", "action": "read-report"},
        ],
    },
    "page-bare-science": {
        "id": "page-bare-science", "target": "page", "page": "bare.html",
        "goal": "put three rows on the fixture that keeps nothing, so the screen reading is "
                "exercised on a page with data in it",
        "steps": [
            {"id": "obs", "action": "observe"},
            {"id": "a1", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "a2", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "a3", "action": "activate", "arguments": {"selector": "@control:add"}},
            {"id": "look", "action": "read-report"},
        ],
    },
}

tmp = tempfile.mkdtemp(prefix="destructive_")
docs = os.path.join(tmp, "docs")
os.mkdir(docs)
io.open(os.path.join(docs, "fixture.html"), "w", encoding="utf-8").write(FIXTURE)
io.open(os.path.join(docs, "bare.html"), "w", encoding="utf-8").write(BARE)
io.open(os.path.join(docs, "defiant.html"), "w", encoding="utf-8").write(DEFIANT)
tasks_dir = os.path.join(tmp, "tasks")
os.mkdir(tasks_dir)
for tid, t in TASKS.items():
    io.open(os.path.join(tasks_dir, tid + ".json"), "w", encoding="utf-8").write(
        json.dumps(t, indent=1))
S.TASKS_DIR = tasks_dir
os.environ["CSRBT_DOCS_DIR"] = docs
A.LEDGER = os.path.join(tmp, "destructive_ledger.json")

got = A.walk("fixture.html", tasks_dir)
r = got["fixture.html"]
by = dict((c["key"], c) for c in r["controls"])
bad = A.bare(r, {})


def v(k):
    return (by.get(k) or {}).get("verdict", "MISSING")


def loss(k):
    return (by.get(k) or {}).get("loss", "MISSING")


# ---- A. what counts as a destructive control --------------------------------
ck(r.get("controls"), "the fixture offers destructive controls at all: %s" % sorted(by))
ck(set(["clearBare", "clearAsks", "dropOne", "clearEmpty"]) <= set(by),
   "a control whose NAME says it removes something is measured -- clear, reset, delete, erase: "
   "%s" % sorted(by))
ck("matrix" not in by,
   "and the MULTIPLICATION SIGN in the middle of a name is not a remover: 'Copy host x taxon "
   "matrix' is an export, and raising it would be the classifier crying wolf on its first day: "
   "%s" % sorted(by))
ck("notes" not in by and not any("Clear the notes" in k for k in by),
   "...and neither is a TEXT BOX whose label says clear. What a control IS comes from the door's "
   "own activate pool, not from the words on it (ADR-208): %s" % sorted(by))
ck(A.PRESSED == frozenset(PP.POOL_KINDS["activate"]),
   "which is read from that pool rather than restated here: %s" % sorted(A.PRESSED))
ck(all(PP.destroys(c.get("label") or "", c.get("title") or "") for c in r["controls"]),
   "every control measured is one the GATEWAY'S OWN RULE calls destructive -- the same "
   "`destroys` the risk ladder raises on and the outputs audit refuses to press, not a second "
   "list kept here: %s" % [c["key"] for c in r["controls"]])
ck(all(c.get("why") for c in r["controls"]),
   "...and each carries the reason that rule gave, so a row can be read: %s"
   % [(c["key"], (c.get("why") or "")[:30]) for c in r["controls"]][:2])

# ---- B. the loss is read from the autosave ----------------------------------
ck(all(c.get("read") == "autosave" for c in r["controls"] if c.get("read")),
   "a page with an autosave is read through it: %s"
   % sorted(set(c.get("read") for c in r["controls"])))
ck(loss("clearBare") == 3,
   "THREE RECORDS, NOT SIX. The fixture shows every row twice -- once in its list and once in "
   "the results table built from it, which is what every bench in this kit does -- and counting "
   "rows on the screen made a row remover read as a bulk delete: %s" % loss("clearBare"))
ck(loss("dropOne") == 1,
   "...and one row is one record, for the same reason: %s" % loss("dropOne"))
ck(loss("wipeText") == 2 and v("wipeText") == "asks",
   "A TYPED FIELD IS A RECORD. The kappa pane of the ethogram keeps two observers' "
   "sequences in two textareas and no array at all; a rule that counted only arrays would "
   "score clearing both as nothing at all: %s / %s" % (loss("wipeText"), v("wipeText")))
ck(loss("rList/✕") == 1,
   "including the row's own mark, which is a control this kit writes as a bare glyph: %s"
   % loss("rList/✕"))

# ---- C. ...and the screen is the fallback -----------------------------------
gb = A.walk("bare.html", tasks_dir)["bare.html"]
byb = dict((c["key"], c) for c in gb["controls"])
ck("wipe" in byb and byb["wipe"].get("read") == "screen",
   "A PAGE WITH NO AUTOSAVE IS READ OFF THE SCREEN, and says which reading it is -- a rule that "
   "silently measured nothing on such a page would report every one of them clean: %s"
   % [(k, byb[k].get("read")) for k in byb])
ck(byb.get("wipe", {}).get("loss", 0) >= 2 and byb["wipe"]["verdict"] == "bulk",
   "...and the bulk remover on it is still caught: %s" % byb.get("wipe"))

# ---- D. asking beats losing -------------------------------------------------
ck(v("clearAsks") == "asks",
   "a control that ASKS before it takes anything is not on the worklist: %s" % v("clearAsks"))
ck(by.get("clearAsks", {}).get("asked") is True and by.get("clearAsks", {}).get("loss") == 3,
   "AND THE LOSS IS STILL MEASURED. The harness stub answers confirm with true, so the act "
   "happens -- a rule that stopped at 'it asked' would not know whether asking stopped anything, "
   "and a page could ask a question and then take the sheet whatever the answer: %s"
   % by.get("clearAsks"))
ck(all(c["before"] - c["after"] == c["loss"] for c in r["controls"] if "loss" in c),
   "AND THE ROW SAYS WHERE THE NUMBER CAME FROM. before, after and loss are what a person reads "
   "off the ledger to decide whether a finding is real; a row whose loss does not follow from its "
   "own two readings is a number with nothing behind it: %s"
   % [(c["key"], c.get("before"), c.get("after"), c.get("loss")) for c in r["controls"]][:3])
ck(by.get("clearBare", {}).get("asked") is False,
   "...and the one that asks nothing says so: %s" % by.get("clearBare"))

# ---- E. one record is not a bulk delete -------------------------------------
ck(v("dropOne") == "one" and "dropOne" not in bad,
   "a control that takes ONE record is not on the worklist: every list in this kit that can lose "
   "a row has an Undo beside it, and a rule that fired on a crossed-off chip would be turned off "
   "within a week -- after which the sheet-clearing ones would be invisible again: %s"
   % v("dropOne"))
ck(v("clearEmpty") == "nothing" and "clearEmpty" not in bad,
   "and one that takes NOTHING is not either -- a filter named clear is named honestly: %s"
   % v("clearEmpty"))
ck(v("clearBare") == "bulk" and bad == ["clearBare"],
   "ONE BARE REMOVER ON THIS FIXTURE, no more and no fewer: %s" % bad)
ck(A.BULK == 2,
   "the bar is two records, written down rather than tuned: %s" % A.BULK)

# ---- F. the ratchet and the exemption ---------------------------------------
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["bare"] == ["clearBare"] and "ceiling" not in led,
   "a first reading records what it found and no ceiling: %s" % led)
rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led.get("ceiling") == 1,
   "the ceiling is set on request, at today's reading: %s" % led)

state = A.load()
state["pages"]["fixture.html"]["ceiling"] = 0
A.save(state)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
ck(rc != 0,
   "A PAGE THAT GREW A CONTROL TAKING A SHEET WITHOUT ASKING FAILS, with no flag -- run_all runs "
   "an audit with no arguments, and a ratchet nothing runs is a comment")
ck(A.main(["--check"]) != 0, "--check is accepted for symmetry, and refuses too")
_named = [l for l in said.split("\n") if "ceiling" in l and "clearBare" in l]
ck(_named, "...and it NAMES the page and the control: %s" % said.strip().split("\n")[-1][:70])

ck(A.main(["--declare", "fixture.html:clearBare"]) != 0,
   "declaring a bulk remover exempt WITHOUT a reason is refused: a control that takes a sheet "
   "without asking is either a defect or a judgement, and only the reason says which")
rc = A.main(["--declare", "fixture.html:clearBare", "--reason",
             "a demo of the rule, in this suite's own fixture directory"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led.get("declared", {}).get("clearBare")
   == "a demo of the rule, in this suite's own fixture directory",
   "...and with one, THE REASON IS WHAT IS STORED, word for word: %s" % led.get("declared"))
ck(A.bare(r, A.declared_of(A.load(), "fixture.html")) == [],
   "a declared control leaves the worklist: %s"
   % A.bare(r, A.declared_of(A.load(), "fixture.html")))
ck(A.main([]) == 0,
   "...and the page passes at a ceiling of zero, because the exemption is a written judgement "
   "rather than a silence")

state = A.load()
state["pages"]["fixture.html"]["ceiling"] = 3
A.save(state)
A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("ceiling") == 0,
   "--raise-floors LOWERS the ceiling, because this ratchet only ever comes down: %s" % led)
# AND IT DOES NOT RAISE IT -- written from a page that is OVER its ceiling,
# because a ratchet asked to move the way it must not, from a reading that
# equals the ceiling, is a check with no violator (ADR-207, ADR-208).
state = A.load()
state["pages"]["fixture.html"].pop("declared", None)
state["pages"]["fixture.html"]["ceiling"] = 0
A.save(state)
rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("ceiling") == 0 and led.get("bare") == ["clearBare"],
   "...and with the declaration taken away and the control back on the worklist, a --raise-floors "
   "run leaves the ceiling where it was rather than recording today's worse reading as the new "
   "normal: %s" % led)
ck(rc != 0,
   "...and that run still fails, because --raise-floors lowers what it can and reports what it "
   "cannot")

# ---- G. A QUESTION WHOSE ANSWER CHANGES NOTHING IS NOT A QUESTION (ADR-210) --
#
# The stub answers confirm() with TRUE, which is what makes the loss measurable
# -- the act happens and the records that went can be counted. It also means the
# rule above only ever watched the YES path, and a page that asks, ignores the
# answer and destroys anyway would read as ASKS: safer than the one that never
# asked, on a measurement that never looked. It is worse. A question the page
# does not mean teaches the person that every question on it is noise.
#
# NO PAGE IN THIS KIT DOES THIS -- all twenty that ask honour the answer -- so
# the rule has no violator anywhere and would read green if it had never been
# written. ADR-127's point about a refusal nobody has watched, and ADR-207's
# about a rule with nothing left to catch, arriving together on the
# confirmations the previous half of this slice added.
gd = A.walk("defiant.html", tasks_dir)["defiant.html"]
byd = dict((c["key"], c) for c in gd["controls"])
ck("clearAnyway" in byd and "clearHonest" in byd,
   "the defiant fixture offers both shapes: one that asks and obeys, one that asks and does not: "
   "%s" % sorted(byd))
ck(byd.get("clearAnyway", {}).get("asked") is True
   and byd.get("clearHonest", {}).get("asked") is True,
   "BOTH OF THEM ASK, so the difference between them cannot be read off whether a question "
   "appeared: %s" % [(k, byd[k].get("asked")) for k in sorted(byd)])
ck(byd.get("clearAnyway", {}).get("loss") == 3
   and byd.get("clearHonest", {}).get("loss") == 3,
   "...and on the YES path both take the same three records, which is the reading ADR-209 made "
   "and the reason it could not tell them apart: %s"
   % [(k, byd[k].get("loss")) for k in sorted(byd)])
ck((byd.get("clearAnyway", {}).get("said") or {}).get("lost") == 3,
   "ANSWERING NO TO THE DEFIANT ONE CHANGES NOTHING: three records go anyway, which is the whole "
   "finding: %s" % (byd.get("clearAnyway", {}).get("said")))
ck((byd.get("clearHonest", {}).get("said") or {}).get("lost") == 0,
   "...and answering no to the honest one stops it dead: %s"
   % (byd.get("clearHonest", {}).get("said")))
ck(byd.get("clearAnyway", {}).get("verdict") == "ignores",
   "so the defiant one is IGNORES, not ASKS -- a verdict of its own, because 'it asked' was the "
   "thing that made it invisible: %s" % byd.get("clearAnyway", {}).get("verdict"))
ck(byd.get("clearHonest", {}).get("verdict") == "asks",
   "...and the honest one is still ASKS: %s" % byd.get("clearHonest", {}).get("verdict"))
ck(A.bare(gd, {}) == ["clearAnyway"],
   "IT IS ON THE WORKLIST, beside the controls that never asked at all -- a page that asks and "
   "does it anyway is not in a better state than one that is silent about it: %s"
   % A.bare(gd, {}))
_no = [c for c in r["controls"] if c.get("asked") and isinstance(c.get("said"), dict)]
ck(_no and all(c["said"]["lost"] == 0 for c in _no),
   "and on the fixture that keeps its state, the control that asks honours the answer: %s"
   % [(c["key"], c["said"]) for c in _no])
ck(all(c.get("said") is None for c in r["controls"] if not c.get("asked")),
   "a control that never asked is not asked a second time -- there is no answer to give it, and "
   "a second press would be a second measurement of the same thing: %s"
   % [(c["key"], c.get("said")) for c in r["controls"] if not c.get("asked")])

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
