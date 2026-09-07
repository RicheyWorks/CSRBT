# -*- coding: utf-8 -*-
"""The number box that shows text and reads as blank -- checked (ADR-151).

`tools/audit_badinput.py` says N live number boxes across the kit cannot tell a
keystroke buffer the browser rejected from an empty one. That number is a
worklist and a ratchet, and it is wrong in both directions if any of five
things is wrong, so a fixture pins each of them:

  A. THE SUBJECT. `<input type=number>` and nothing else -- a text box holding
     digits has no badInput, the page gets the characters, and there is nothing
     to be blind to -- and, within those, only the ones the browser actually
     rejects the token into: a readonly box keeps what it had and the
     experiment never ran on it.
  B. THE CONTROL. A box is only measured against blank once a GOOD value is
     shown to change what the page renders. Without that, every box read only
     on submit joins the worklist and the worklist means nothing.
  C. THE FINDING. Blank and typed-and-rejected render the same thing, while
     validity.badInput is TRUE -- which is what makes it a finding rather than
     a page with nothing to say.
  D. WHAT COUNTS AS TELLING THEM APART. A sentence, a mark, or a sentence in an
     element with no id: aria-invalid on the box is telling them apart as
     surely as a printed line is, and an id-keyed, text-only comparison would
     call both of those pages silent.
  E. THE WALK AND THE LADDER. Every state, not the last one -- a box the entry
     brings into being is asked -- and the ladder moves only UP: a box that
     tells them apart in ANY state leaves the worklist, and one that goes quiet
     in a later state does not.
  F. Ids that move on their own are dropped, or a clock makes every box on the
     page look like it is being told apart.
  G. THE RATCHET. The ceiling falls on request and never rises silently; an
     exemption needs a reason and it is the reason that is stored.

Run:  python3 tools/verify/verify_badinput.py
"""
MUTATE_ROLE = "subject"
import io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import audit_states as S
import audit_badinput as B

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>badinput fixture</title>
<style>.pane{display:none}.pane.on{display:block}
 button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>badinput fixture</h1>
<button class="tab" data-pane="p1">One</button><button class="tab" data-pane="p2">Two</button>
<section class="pane on" id="p1">
  <!-- the finding: blank and rejected render the same sentence -->
  <label>blind <input type="number" id="nBlind" aria-label="blind"></label>
  <div id="anBlind"></div>
  <!-- tells them apart with a sentence -->
  <label>tells <input type="number" id="nTells" aria-label="tells"></label>
  <div id="anTells"></div>
  <!-- tells them apart with a MARK and no sentence at all -->
  <label>marked <input type="number" id="nMark" aria-label="marked"></label>
  <div id="anMark"></div>
  <!-- read only when the button is pressed: inert, and not a finding -->
  <label>inert <input type="number" id="nInert" aria-label="inert"></label>
  <div id="anInert"></div>
  <button id="go" type="button">Go</button>
  <!-- tells them apart in an element that carries no id at all -->
  <label>noid <input type="number" id="nNoId" aria-label="noid"></label>
  <p class="noid-out">nothing yet</p>
  <!-- live and blind at rest, and INERT once the entry has run: the ladder must
       not let the quieter later reading overwrite the finding -->
  <label>flip <input type="number" id="nFlip" aria-label="flip"></label>
  <div id="anFlip"></div>
  <!-- the entry BRINGS THIS ONE INTO BEING: it is in no state of the page at
       rest, so no amount of revealing finds it -->
  <div id="made"></div>
  <!-- a READONLY number box: the token goes nowhere, so there is no subject -->
  <label>readonly <input type="number" id="nRead" aria-label="readonly" readonly></label>
  <div id="anRead"></div>
  <!-- a text box holding a number: no badInput, no subject -->
  <label>text <input type="text" id="tNum" aria-label="text number"></label>
  <div id="anText"></div>
  <!-- the entry presses this, and the late box starts telling them apart -->
  <button id="strict" type="button">Strict</button>
  <div id="clock">0</div>
</section>
<section class="pane" id="p2">
  <!-- behind a tab, and blind: found only because the states are walked -->
  <label>behind <input type="number" id="nBehind" aria-label="behind"></label>
  <div id="anBehind"></div>
  <!-- blind at rest, tells once the entry has run -->
  <label>late <input type="number" id="nLate" aria-label="late"></label>
  <div id="anLate"></div>
</section>
<script>
  function $(i){ return document.getElementById(i); }
  var strict = false;
  document.querySelectorAll('.tab').forEach(function(t){ t.addEventListener('click', function(){
    document.querySelectorAll('.pane').forEach(function(x){ x.classList.remove('on'); });
    $(t.getAttribute('data-pane')).classList.add('on'); }); });
  function blankish(e){ return e.value === '' ? 'no value' : 'value ' + e.value; }
  $('nBlind').addEventListener('input', function(){ $('anBlind').textContent = blankish($('nBlind')); });
  $('nTells').addEventListener('input', function(){
    var e = $('nTells');
    $('anTells').textContent = e.validity.badInput ? 'not a whole number' : blankish(e); });
  $('nMark').addEventListener('input', function(){
    var e = $('nMark');
    $('anMark').textContent = blankish(e);            // the SAME sentence either way
    e.setAttribute('aria-invalid', e.validity.badInput ? 'true' : 'false'); });
  $('nNoId').addEventListener('input', function(){
    var e = $('nNoId'), p = document.querySelector('.noid-out');
    p.textContent = e.validity.badInput ? 'not a whole number' : blankish(e); });
  $('nRead').addEventListener('input', function(){ $('anRead').textContent = blankish($('nRead')); });
  $('tNum').addEventListener('input', function(){ $('anText').textContent = blankish($('tNum')); });
  $('go').addEventListener('click', function(){ $('anInert').textContent = blankish($('nInert')); });
  $('nFlip').addEventListener('input', function(){
    if (strict) return;                      // stops being read at all
    $('anFlip').textContent = blankish($('nFlip')); });
  $('strict').addEventListener('click', function(){
    strict = true;
    if (!document.getElementById('nMade')) {
      var l = document.createElement('label'); l.textContent = 'made ';
      var i = document.createElement('input');
      i.type = 'number'; i.id = 'nMade'; i.setAttribute('aria-label', 'made');
      var o = document.createElement('div'); o.id = 'anMade';
      i.addEventListener('input', function(){ o.textContent = blankish(i); });
      l.appendChild(i); $('made').appendChild(l); $('made').appendChild(o);
    } });
  $('nBehind').addEventListener('input', function(){ $('anBehind').textContent = blankish($('nBehind')); });
  $('nLate').addEventListener('input', function(){
    var e = $('nLate');
    $('anLate').textContent = (strict && e.validity.badInput) ? 'not a whole number' : blankish(e); });
  // moves on its own: a clock is not an answer
  var n = 0; setInterval(function(){ $('clock').textContent = String(++n); }, 60);
</script></body></html>
"""

TASKS = {
    "page-fixture-science": {
        "id": "page-fixture-science", "target": "page", "page": "fixture.html",
        "goal": "press the button that makes the late box strict",
        "steps": [
            {"id": "obs", "action": "observe"},
            {"id": "strict", "action": "activate", "arguments": {"selector": "@control:strict"}},
        ],
    },
}

tmp = tempfile.mkdtemp(prefix="badinput_")
docs = os.path.join(tmp, "docs")
os.mkdir(docs)
io.open(os.path.join(docs, "fixture.html"), "w", encoding="utf-8").write(FIXTURE)
tasks_dir = os.path.join(tmp, "tasks")
os.mkdir(tasks_dir)
for tid, t in TASKS.items():
    io.open(os.path.join(tasks_dir, tid + ".json"), "w", encoding="utf-8").write(
        json.dumps(t, indent=1))
S.TASKS_DIR = tasks_dir
os.environ["CSRBT_DOCS_DIR"] = docs
B.LEDGER = os.path.join(tmp, "badinput_ledger.json")

got = B.walk("fixture.html", tasks_dir)
r = got["fixture.html"]
by = dict((f["key"], f) for f in r["fields"])
bad = B.blind(r, {})


def verdict(k):
    return (by.get(k) or {}).get("verdict", "MISSING")


# ---- A. the subject ---------------------------------------------------------
ck("tNum" not in by,
   "a text box holding digits is not a subject: it has no badInput, the page is handed the "
   "characters the user typed, and there is nothing here to be blind to: %s" % sorted(by))
ck("nBlind" in by and "nInert" in by and "nBehind" in by,
   "every <input type=number> the swarm stamped is one, wherever it sits: %s" % sorted(by))

ck(verdict("nRead") == "no-bad-input" and "nRead" not in bad,
   "a box the browser will not put the token INTO has no subject and the experiment did not "
   "run: a readonly box takes the focus, takes the keystrokes and keeps what it had, so its "
   "value reads the same as a blank one for a reason that has nothing to do with the page -- "
   "there is nothing there to be blind to: %s" % verdict("nRead"))

# ---- B. the control ---------------------------------------------------------
ck(verdict("nInert") == "inert",
   "a box no figure on the page reads until a button is pressed is INERT, not blind: without "
   "that control every box read only on submit joins the worklist and the worklist means "
   "nothing: %s" % verdict("nInert"))
ck("nInert" not in bad, "...and an inert box is not on the worklist: %s" % bad)

# ---- C. the finding ---------------------------------------------------------
ck(verdict("nBlind") == "cannot-tell",
   "a box whose page renders the SAME thing for a blank value and for a keystroke buffer the "
   "browser rejected is the finding this audit exists for: %s" % verdict("nBlind"))
ck("nBlind" in bad, "...and it is on the worklist, named: %s" % bad)
ck(verdict("nTells") == "tells" and "nTells" not in bad,
   "a box whose page checks validity.badInput and says a different thing is not: %s"
   % verdict("nTells"))

ck(verdict("nNoId") == "tells" and "nNoId" not in bad,
   "a page that answers in an element carrying no id has still answered: an id is how the rest "
   "of this kit names a figure, and an id-keyed comparison alone would put a page on the "
   "worklist for the kit's own naming convention rather than for anything the reader would "
   "see: %s" % verdict("nNoId"))

# ---- D. a mark is telling them apart ----------------------------------------
ck(verdict("nMark") == "tells" and "nMark" not in bad,
   "marking the box aria-invalid is telling them apart as surely as printing a sentence is -- "
   "this box's TEXT is identical in both states, and a text-only comparison would put a page "
   "that marks its bad fields red on the worklist: %s" % verdict("nMark"))

# ---- E. every state, and the ladder -----------------------------------------
ck(verdict("nBehind") == "cannot-tell" and "nBehind" in bad,
   "a box behind a tab is a box: %s" % verdict("nBehind"))
ck(verdict("nMade") == "cannot-tell" and "nMade" in bad,
   "and so is a box the entry BRINGS INTO BEING -- it is in no state of the page at rest, so "
   "no amount of revealing finds it, and a page measured where the load left it would report "
   "a box it never asked as a box with nothing wrong: %s" % verdict("nMade"))
ck(verdict("nFlip") == "cannot-tell" and "nFlip" in bad,
   "a box that could not tell them apart, and then goes INERT in a later state, KEEPS the "
   "finding: letting a later, quieter reading overwrite an earlier one would take a blind box "
   "off the worklist because a pane closed behind it: %s" % verdict("nFlip"))
ck(verdict("nLate") == "tells" and "nLate" not in bad,
   "a box that CANNOT tell them apart at rest and tells them apart once the entry has run is "
   "not on the worklist: the verdict only moves up the ladder, because the finding is 'in no "
   "state did the page say a different thing': %s" % verdict("nLate"))
ck((by.get("nLate") or {}).get("tries", 0) > 1,
   "...which means it really was asked more than once: %s" % (by.get("nLate") or {}).get("tries"))
ck(r.get("states", 0) >= 3,
   "the page was put in more than one state to get there: %s" % r.get("states"))
ck(r.get("task") == "page-fixture-science",
   "and the state that matters is the page's own entry, the same replay the other audits make: "
   "%s" % r.get("task"))

# ---- F. what moves on its own is not an answer ------------------------------
ck(r.get("unstable", 0) >= 1,
   "the clock is found by reading the page twice at rest and dropped: left in, it differs "
   "between every pair of readings and every box on the page reads as told apart: %s"
   % r.get("unstable"))
ck(bad, "...and dropping it does not drop the finding with it: %s" % bad)

# ---- the count --------------------------------------------------------------
ck(sorted(bad) == ["nBehind", "nBlind", "nFlip", "nMade"],
   "four blind boxes on this fixture, no more and no fewer: %s" % sorted(bad))

# ---- G. the ratchet and the exemption ---------------------------------------
rc = B.main([])
led = json.load(io.open(B.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["blind"] == sorted(bad) and "ceiling" not in led,
   "a first reading records what it found and no ceiling: nothing to compare against is not a "
   "failure: %s" % led)
rc = B.main(["--raise-floors"])
led = json.load(io.open(B.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led.get("ceiling") == 4, "the ceiling is set on request, at today's reading: %s" % led)

state = B.load()
state["pages"]["fixture.html"]["ceiling"] = 3
B.save(state)
ck(B.main([]) != 0,
   "a page carrying MORE blind boxes than its ceiling fails, with no flag: run_all runs an "
   "audit with no arguments, and a ceiling that only bit under --check would be a ceiling "
   "nothing ever checked")
ck(B.main(["--check"]) != 0,
   "--check is accepted for symmetry with the kit's other ratchets, and refuses too")
state = B.load()
state["pages"]["fixture.html"]["ceiling"] = 4
B.save(state)
ck(B.main([]) == 0, "back at its ceiling, the page passes")

ck(B.main(["--declare", "fixture.html:nBlind"]) != 0,
   "declaring a box exempt WITHOUT a reason is refused: a list of boxes this audit is choosing "
   "not to care about is only useful if every line says why")
rc = B.main(["--declare", "fixture.html:nBlind", "--reason", "a rehearsal, not a reading"])
led = json.load(io.open(B.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["declared"]["nBlind"] == "a rehearsal, not a reading",
   "...and with one, the reason is what is stored: %s" % led.get("declared"))
bad2 = B.blind(r, B.declared_of(B.load(), "fixture.html"))
ck(bad2 == ["nBehind", "nFlip", "nMade"],
   "a declared box leaves the worklist -- and only that box: %s" % bad2)
rc = B.main(["--raise-floors"])
led = json.load(io.open(B.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("ceiling") == 3,
   "...and --raise-floors LOWERS the ceiling, because this ratchet only ever comes down: %s" % led)

# ---- the good value comes from the box, not from a constant -----------------
ck(B.good_value({"min": "0", "max": "1", "step": None}) == "0.5",
   "the GOOD value is picked from the box's own bounds: a 7 in a box that accepts 0..1 would "
   "be read as out of range and the control reading would be about the range: %s"
   % B.good_value({"min": "0", "max": "1", "step": None}))
ck(B.good_value({"min": "2", "max": "1000000", "step": "1"}) not in ("", None)
   and float(B.good_value({"min": "2", "max": "1000000", "step": "1"})) >= 2,
   "...and it respects an integer step and stays inside the range: %s"
   % B.good_value({"min": "2", "max": "1000000", "step": "1"}))
ck(B.good_value({"min": None, "max": None, "step": None}) == "7",
   "a box that declares no bounds gets a plain 7: %s" % B.good_value({}))

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
