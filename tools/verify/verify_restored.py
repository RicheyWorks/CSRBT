# -*- coding: utf-8 -*-
"""What the page says when it comes back -- checked (ADR-210).

`tools/audit_restored.py` says 0 of 552 things the seventeen keeping pages say
before the tab closes go missing when it comes back. It said 125 on the day it
was written. That number is a worklist and a ratchet, and it is wrong in both
directions unless five things are right, so a fixture pins each:

  A. THE PAGE IS ENTERED, FLUSHED AND RELOADED, and the reading is two calls to
     read-report either side of that -- what the page publishes, not a list of
     what each page ought to bring back.
  B. A LOSS IS A KEY THAT WENT OR A VALUE THAT CHANGED. Both, because a sheet
     that comes back with a smaller coordinate uncertainty than the one typed
     has lost nothing a key-count could see.
  C. WHAT IS SUPPOSED TO COME BACK DIFFERENT IS NAMED. The autosave strip, the
     outbox strip and the toast say what just happened, and a reload is a thing
     that just happened; a pane is a container and changes when anything inside
     it does.
  D. A PAGE THAT DID NOT RESTORE SAYS SO, because a reading taken from a page
     that never came back is about the instrument.
  E. THE RATCHET AND THE EXEMPTION. The ceiling falls on request and never
     rises silently; an exemption needs a reason and the reason is stored.

Run:  python3 tools/verify/verify_restored.py
"""
MUTATE_ROLE = "fixture-builder"     # the temp dir here holds fixture pages
import contextlib, importlib.util, io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import audit_states as S
import audit_restored as A

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


def fixture(keeps_rows, keeps_note, restores_stat):
    """A page that keeps SOME of what it holds and repaints SOME of it.

    `keeps_rows`   the records go in the snapshot
    `keeps_note`   the typed note goes in the snapshot
    `restores_stat` the analysis is repainted after a restore
    """
    return u"""<!doctype html><html><head><meta charset="utf-8"><title>restored fixture</title>
<style>%s
 button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>restored fixture</h1><div id="toast" class="toast"></div>
<div id="keepBox"></div>
<section class="pane on" id="p-out">
  <label>Note <input id="f-note" type="text" aria-label="Note"></label>
  <button id="add" type="button">Add a row</button>
  <div class="rowlist" id="rList"></div>
  <div id="anStat"></div>
  <div id="anNote"></div>
</section>
<script>
%s
</script>
<script>
  var $=function(i){return document.getElementById(i);};
  var recs=[], KEPT;
  function paintRows(){
    $("rList").innerHTML = recs.map(function(r){
      return '<div class="row2"><span>'+r.plot+'</span></div>'; }).join("");
  }
  function paintStat(){
    /* a labelled figure as well as prose, so the `by` half of the reading has
       something in it: read-report keys these as by/anStat/<label> */
    $("anStat").innerHTML = recs.length
      ? '<div class="tile"><div class="v">'+recs.length+'</div><div class="l">rows on this sheet</div></div>'
      : 'Nothing yet.';
  }
  function paintNote(){
    $("anNote").innerHTML = $("f-note").value
      ? 'Note reads: ' + $("f-note").value : 'No note.';
  }
  function paintAll(){ paintRows(); paintStat(); paintNote(); }
  $("add").addEventListener("click", function(){
    recs.push({plot: "p" + (recs.length + 1)});
    paintAll(); $("toast").textContent = "added";
    if (KEPT) KEPT.touch(); });
  $("f-note").addEventListener("input", function(){ paintAll(); if (KEPT) KEPT.touch(); });
  /* THE BOOT PAINT RUNS BEFORE THE AUTOSAVE IS WIRED, as it does on every page
     of this kit -- a restore that fires and then has the whole page repainted
     over it by a boot line further down would hide exactly the defect this
     fixture exists to show. */
  paintAll();
  KEPT = KEEP.wire({ key: "csrbtRestoredFixture", format: 1, mount: "keepBox",
    noun: "this fixture",
    snapshot: function(){
      var f = KEEP.formSnapshot(), k, any = recs.length;
      if (!any) for (k in f) if (f.hasOwnProperty(k) && String(f[k]).trim() !== "") any = true;
      if (!any) return null;
      %s
      return { fields: %s, state: { recs: %s } }; },
    restore: function(b){
      if(!b||!b.state) return false;
      KEEP.formRestore(b.fields);
      recs = b.state.recs || [];
      paintRows(); %s
      return true; } });
</script></body></html>
""" % (keep.CSS, keep.JS,
       "" if keeps_note else "f = {};",
       "f", "recs" if keeps_rows else "[]",
       "paintStat(); paintNote();" if restores_stat else "")


TASK = {
    "id": "page-fixture-science", "target": "page", "page": "fixture.html",
    "goal": "put a note and three rows on the fixture, so that what comes back can be compared "
            "with what was there",
    "steps": [
        {"id": "obs", "action": "observe"},
        {"id": "note", "action": "set-text",
         "arguments": {"selector": "@control:f-note", "value": "north slope"}},
        {"id": "a1", "action": "activate", "arguments": {"selector": "@control:add"}},
        {"id": "a2", "action": "activate", "arguments": {"selector": "@control:add"}},
        {"id": "a3", "action": "activate", "arguments": {"selector": "@control:add"}},
        {"id": "look", "action": "read-report"},
    ],
}

tmp = tempfile.mkdtemp(prefix="restored_")
docs = os.path.join(tmp, "docs")
os.mkdir(docs)
tasks_dir = os.path.join(tmp, "tasks")
os.mkdir(tasks_dir)


def write(name, html, page_task=True):
    io.open(os.path.join(docs, name), "w", encoding="utf-8").write(html)
    if page_task:
        t = dict(TASK)
        t["id"] = "page-%s-science" % name.replace(".html", "")
        t["page"] = name
        io.open(os.path.join(tasks_dir, t["id"] + ".json"), "w", encoding="utf-8").write(
            json.dumps(t, indent=1))


write("whole.html", fixture(True, True, True))
write("norows.html", fixture(False, True, True))
write("nonote.html", fixture(True, False, True))
write("nopaint.html", fixture(True, True, False))
S.TASKS_DIR = tasks_dir
os.environ["CSRBT_DOCS_DIR"] = docs
A.LEDGER = os.path.join(tmp, "restored_ledger.json")
A.KEEPERS = ["whole.html", "norows.html", "nonote.html", "nopaint.html"]

got = A.walk(tasks_dir=tasks_dir)


def lost(name):
    return sorted(got[name].get("lost", []))


# ---- A. entered, flushed, reloaded ------------------------------------------
ck(all(not r.get("error") for r in got.values()),
   "every fixture was entered, flushed and reloaded: %s"
   % [(k, v.get("error")) for k, v in got.items() if v.get("error")])
ck(all(r.get("restored") for r in got.values()),
   "...and every one of them came back from its own autosave: %s"
   % [(k, v.get("restored")) for k, v in got.items()])
ck(got["whole.html"]["before"] > 0,
   "the reading is what the page PUBLISHES -- read-report's figures and blocks -- rather than a "
   "list here of what each page ought to bring back: %d key(s)" % got["whole.html"]["before"])

# ---- B. a loss is a key that went OR a value that changed -------------------
ck(lost("whole.html") == [],
   "A PAGE THAT KEEPS WHAT IT HOLDS AND REPAINTS IT COMES BACK WHOLE: %s" % lost("whole.html"))
ck("by/anStat/rows on this sheet" in lost("norows.html"),
   "BOTH HALVES OF THE READING ARE COMPARED: the labelled figure as well as the prose around it. "
   "A page that came back with a smaller coordinate uncertainty than the one typed loses a "
   "FIGURE, and a rule that read only blocks would have called that page clean: %s"
   % lost("norows.html"))
ck("box/rList" in lost("norows.html") and "box/anStat" in lost("norows.html"),
   "a page whose snapshot leaves its records out comes back without them, and the analysis "
   "built from them goes too: %s" % lost("norows.html"))
ck("box/anNote" in lost("nonote.html"),
   "A VALUE THAT CHANGED IS A LOSS, not only a key that went: the note's block is still there "
   "and says something else, which is the shape a coordinate uncertainty that came back smaller "
   "than the one typed would have: %s" % lost("nonote.html"))
ck("box/rList" not in lost("nonote.html"),
   "...and the records it DID keep are not counted against it: %s" % lost("nonote.html"))
ck("box/anStat" in lost("nopaint.html") and "box/rList" not in lost("nopaint.html"),
   "A PAGE THAT KEEPS EVERYTHING AND REPAINTS HALF OF IT is caught too -- the records came back "
   "and the analysis over them did not, which is the experiment guide's measurement rows in "
   "ADR-207 and eleven pages' worth of the same thing here: %s" % lost("nopaint.html"))

# ---- C. what is supposed to come back different -----------------------------
ck(set(A.STATUS) == set(["keepBox", "sendBox", "toast"]),
   "three blocks are named as saying what just happened: %s" % sorted(A.STATUS))
ck(all(v.strip() for v in A.STATUS.values()),
   "...and each says why, in this file, where the next person reads it: %s"
   % [k for k, v in A.STATUS.items() if not v.strip()])
ck(not any(k.split("/")[1] in A.STATUS for k in lost("whole.html") + lost("norows.html")),
   "and none of them is ever a loss -- the autosave strip goes from 'saved a moment ago' to "
   "'restored', which is the whole point of it, and a rule that called that a loss would be "
   "switched off within a week")
ck("box/p-out" not in lost("norows.html"),
   "A PANE IS A CONTAINER, NOT A REPORT: it changes when anything inside it changes, and what is "
   "inside it is compared on its own -- counting the pane too is counting the same difference "
   "again under the name of whatever happens to hold it: %s" % lost("norows.html"))

# ---- D. a page that did not restore says so ---------------------------------
write("silent.html", fixture(True, True, True).replace(
    'KEEP.wire({ key: "csrbtRestoredFixture"', 'KEEP.wire({ key: "csrbtRestoredSilent"')
    .replace("if(!b||!b.state) return false;", "return false;"))
A.KEEPERS = ["silent.html"]
g2 = A.walk(tasks_dir=tasks_dir)["silent.html"]
ck(g2.get("restored") is False,
   "a page whose restore refuses the blob is reported as NOT RESTORED, because a reading taken "
   "from a page that never came back is about the instrument and not about the page: %s"
   % g2.get("restored"))

# ---- E. the ratchet and the exemption ---------------------------------------
A.KEEPERS = ["whole.html", "norows.html"]
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
ck(rc == 0 and led["norows.html"]["lost"] and "ceiling" not in led["norows.html"],
   "a first reading records what it found and no ceiling: %s" % led["norows.html"])
with contextlib.redirect_stdout(io.StringIO()):
    rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
n = len(led["norows.html"]["lost"])
ck(rc == 0 and led["norows.html"].get("ceiling") == n,
   "the ceiling is set on request, at today's reading: %s" % led["norows.html"])

state = A.load()
state["pages"]["norows.html"]["ceiling"] = 0
A.save(state)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
ck(rc != 0,
   "A PAGE THAT COMES BACK SAYING LESS THAN IT SAID FAILS, with no flag -- run_all runs an audit "
   "with no arguments, and a ratchet nothing runs is a comment")
ck(A.main(["--check"]) != 0, "--check is accepted for symmetry, and refuses too")
ck(any("norows.html" in l and "ceiling" in l for l in said.split("\n")),
   "...and it NAMES the page and what went: %s" % said.strip().split("\n")[-1][:80])

ck(A.main(["--declare", "norows.html:box/rList"]) != 0,
   "declaring a difference expected WITHOUT a reason is refused: a page that comes back saying "
   "something else is either broken or right, and only the reason says which")
rc = A.main(["--declare", "norows.html:box/rList", "--reason",
             "a demo of the rule, in this suite's own fixture directory"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["norows.html"]
ck(rc == 0 and led.get("declared", {}).get("box/rList")
   == "a demo of the rule, in this suite's own fixture directory",
   "...and with one, THE REASON IS WHAT IS STORED, word for word: %s" % led.get("declared"))
ck("box/rList" not in A.losses(got["norows.html"], A.declared_of(A.load(), "norows.html")),
   "a declared difference leaves the worklist: %s"
   % A.losses(got["norows.html"], A.declared_of(A.load(), "norows.html")))

# ---- THE EXEMPTION RECORDS WHAT IT TOOK OUT (ADR-224) ----------------------
# Filtering the finding out of the list and writing the filtered list to the
# ledger discarded the evidence at the moment the exemption was applied, and no
# reader in the kit could then tell a declaration covering a real finding from
# one naming a thing the page no longer has. The rule lives in tools/exempt.py
# and is asserted HERE, through this audit's own reading, so that a copy of it
# that filtered quietly would fail this suite and not only the reader's.
with contextlib.redirect_stdout(io.StringIO()):
    A.main([])
_row = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["norows.html"]
ck('box/rList' in (_row.get("raw") or []) and 'box/rList' not in (_row.get("lost") or []),
   "the row records what was flagged BEFORE the exemption under `raw`, beside the filtered "
   "list it always recorded -- the declared key is in one and not the other: raw %s, filtered %s"
   % (_row.get("raw"), _row.get("lost")))
ck(isinstance(_row.get("seen"), list) and set(_row.get("raw") or []) <= set(_row.get("seen") or [])
   and set(_row.get("lost") or []) <= set(_row.get("raw") or []),
   "...and everything the reading could have flagged under `seen`, with filtered within raw within "
   "seen -- without the universe, `this finding is covered` and `this thing is gone` are the same "
   "absence: seen %s" % _row.get("seen"))
_live, _e = ["k1"], {}
A.X.apply(_e, _live, {}, ["k1", "other"])
_live.append("added after the record was written")
ck(_e["raw"] == ["k1"] and _e["seen"] == ["k1", "other"],
   "the record is a COPY, not the audit's live list: a row holding the list the audit goes on "
   "using would be rewritten by whatever the audit did to it next: %s" % _e["raw"])

state = A.load()
state["pages"]["norows.html"]["ceiling"] = 9
A.save(state)
with contextlib.redirect_stdout(io.StringIO()):
    A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["norows.html"]
ck(led.get("ceiling") < 9,
   "--raise-floors LOWERS the ceiling, because this ratchet only ever comes down: %s" % led)
# AND IT DOES NOT RAISE IT -- from a page that is OVER its ceiling, because a
# ratchet asked to move the way it must not, from a reading that equals the
# ceiling, is a check with no violator (ADR-207, ADR-208, ADR-209).
state = A.load()
state["pages"]["norows.html"].pop("declared", None)
state["pages"]["norows.html"]["ceiling"] = 0
A.save(state)
with contextlib.redirect_stdout(io.StringIO()):
    rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["norows.html"]
ck(led.get("ceiling") == 0 and led.get("lost"),
   "...and with the declaration taken away and the page back over its ceiling, a --raise-floors "
   "run leaves the ceiling where it was rather than recording today's worse reading as the new "
   "normal: %s" % led)
ck(rc != 0,
   "...and that run still fails, because --raise-floors lowers what it can and reports what it "
   "cannot")

# ---- F. the list of pages is the emitter's -----------------------------------
_src = io.open(os.path.join(_kit.TOOLS_DIR, "audit_restored.py"), encoding="utf-8").read()
ck("_ke.CONSUMERS" in _src,
   "THE PAGES THIS AUDIT WALKS ARE THE EMITTER'S LIST, not a second one kept here -- a page "
   "wired to the autosave tomorrow is measured tomorrow, which is the rule ADR-204, ADR-205, "
   "ADR-207 and ADR-208 each found broken in turn")

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
