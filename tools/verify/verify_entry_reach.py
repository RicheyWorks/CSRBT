# -*- coding: utf-8 -*-
"""How much of a page's data a task enters -- the measurement, checked (ADR-144).

`tools/entry_reach.py` says the kit's tasks fill 183 of 516 fields. That number
becomes a worklist and a ratchet, so it has to be right about three things a
fixture can pin exactly:

  A. WHAT COUNTS AS A FIELD. A control that carries a value counts; Add, Save
     and Clear do not. A stepper's minus, value and plus are ONE field, not
     three. A group of mutually exclusive chips is one field, not four.
  B. WHAT COUNTS AS ENTERED. The control the entry acted on -- resolved BEFORE
     the step runs, because a key removes the option it has just answered and a
     region rebuilt on change takes its stamps with it.
  C. THE RATCHET. Floors rise on request, a reading below one is named and
     --check refuses, and lowering needs a reason that goes into the ledger.

Run:  python3 tools/verify/verify_entry_reach.py
"""
MUTATE_ROLE = "subject"
import io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import audit_states as S
import entry_reach as E

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>entry fixture</title>
<style>.pane{display:none}.pane.on{display:block}
 button,input,select{min-height:44px;font-size:16px}</style></head><body>
<h1>entry fixture</h1>
<button class="tab" data-pane="p1">One</button><button class="tab" data-pane="p2">Two</button>
<section class="pane on" id="p1">
  <div class="fek-row"><label class="fek-lab">stems</label><div class="fek-step">
    <button type="button">&minus;</button><input class="val" type="number" aria-label="stems" value="0"><button type="button">+</button></div></div>
  <div class="fek-row"><label class="fek-lab">girth</label><div class="fek-step">
    <button type="button">&minus;</button><input class="val" type="number" aria-label="girth" value="0"><button type="button">+</button></div></div>
  <div id="shapes"><div class="fek-chips">
    <button class="fek-chip" type="button">circle</button>
    <button class="fek-chip" type="button">square</button>
    <button class="fek-chip" type="button">belt</button></div></div>
  <div id="soils"><div class="fek-chips">
    <button class="fek-chip" type="button">sand</button>
    <button class="fek-chip" type="button">clay</button></div></div>
  <input id="site" aria-label="site">
  <input id="notes" aria-label="notes">
  <input id="tally" aria-label="tally" value="12" readonly>
  <button id="addRow" type="button">Add row</button>
  <button id="clearAll" type="button">Clear all</button>
</section>
<section class="pane" id="p2">
  <input id="behind" aria-label="behind a tab">
  <div id="kbox">
    <button class="kopt" id="k1" type="button">answer one</button>
    <button class="kopt" id="k2" type="button">answer two</button>
  </div>
  <div id="kbox2"></div>
</section>
<script>
  document.querySelectorAll('.tab').forEach(function(t){ t.addEventListener('click', function(){
    document.querySelectorAll('.pane').forEach(function(x){ x.classList.remove('on'); });
    document.getElementById(t.getAttribute('data-pane')).classList.add('on'); }); });
  // a key that REMOVES the option it has answered, the way the character keys do
  document.querySelectorAll('#kbox .kopt').forEach(function(o){
    o.addEventListener('click', function(){
      o.remove();
      // ...and the answer that only EXISTS once an earlier one is given: a
      // control the state walk never saw and the page does not keep
      if (o.textContent === 'answer one' && !document.querySelector('#kbox2 .kopt')) {
        ['k3', 'k4'].forEach(function(id){
          var n = document.createElement('button');
          n.type = 'button'; n.className = 'kopt'; n.id = id;
          n.textContent = id === 'k3' ? 'answer three' : 'answer four';
          n.addEventListener('click', function(){ n.remove(); });
          document.getElementById('kbox2').appendChild(n);
        });
      }
    }); });
</script></body></html>
"""

TASKS = {
    "page-fixture-science": {
        "id": "page-fixture-science", "target": "page", "page": "fixture.html",
        "goal": "enter some of it, and leave the rest alone, so the measurement has both to find",
        "steps": [
            {"id": "obs", "action": "observe"},
            {"id": "s0", "action": "set-text",
             "arguments": {"selector": "@control:site", "value": "north ridge"}},
            {"id": "s1", "action": "set-text",
             "arguments": {"selector": "@control:stems", "value": "4"}},
            {"id": "s2", "action": "activate", "arguments": {"selector": "@control:shapes/circle"}},
            {"id": "s3", "action": "activate", "arguments": {"selector": "@control:kbox/answer one"}},
            {"id": "s5", "action": "activate", "arguments": {"selector": "@control:kbox2/answer three"}},
            {"id": "s7", "action": "activate", "arguments": {"selector": "@control:kbox2/answer four"}},
            {"id": "s4", "action": "activate", "arguments": {"selector": "@control:addRow"}},
            # a step that is REFUSED: a slider action on a text box. The entry
            # reports it as refused, and a refused step must not count as having
            # entered the field it was pointed at.
            {"id": "s6", "action": "set-slider",
             "arguments": {"selector": "@control:notes", "value": 3}},
        ],
    },
}

tmp = tempfile.mkdtemp(prefix="entryreach_")
docs = os.path.join(tmp, "docs")
os.mkdir(docs)
io.open(os.path.join(docs, "fixture.html"), "w", encoding="utf-8").write(FIXTURE)
tasks_dir = os.path.join(tmp, "tasks")
os.mkdir(tasks_dir)
for tid, t in TASKS.items():
    io.open(os.path.join(tasks_dir, tid + ".json"), "w", encoding="utf-8").write(json.dumps(t, indent=1))
S.TASKS_DIR = tasks_dir
os.environ["CSRBT_DOCS_DIR"] = docs
E.LEDGER = os.path.join(tmp, "entry_ledger.json")

from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport=H.VIEWPORT)
    ctx.set_offline(True)
    ctx.add_init_script(H.STUBS)
    pg = ctx.new_page()
    pg.goto("file://" + os.path.join(docs, "fixture.html").replace(os.sep, "/"),
            wait_until="domcontentloaded")
    pg.wait_for_timeout(200)
    r = E.measure(pg, "fixture.html", tasks_dir)
    ctx.close()
    b.close()

# ---- A. what counts as a field ----------------------------------------------
ck(r["task"] == "page-fixture-science", "the page's own task is what is replayed: %s" % r["task"])
ck(r["controls"] == 18,
   "eighteen controls carry a value here: two steppers of three, two chip groups of three and "
   "two, four key options (two of which the page built as answers to another) and three inputs, "
   "one behind a tab -- and Add row, Clear all and the readonly tally are NOT among them: %d"
   % r["controls"])
ck(r["fields"] == 10,
   "...and they are TEN fields: two steppers (one each, not three), two chip groups (one each, "
   "not five, and not one -- they are different groups), the key (one, not two), the two answers "
   "the key built (their own, since the page kept no host for them), and three inputs: %d"
   % r["fields"])

# ---- B. what counts as entered ----------------------------------------------
ck(r["entered"] == 6,
   "six were entered: the site input, the stems stepper through its value, the shapes chip group "
   "through one chip, the key through the option it answered, and both answers that option "
   "built: %d" % r["entered"])
missed = " | ".join(r["missed"])
ck("notes" in missed and "behind" in missed,
   "the two inputs nothing filled are NAMED, the one behind a tab included -- the worklist is "
   "the point: %s" % missed)
ck(any("sand" in m or "clay" in m or "soils" in m for m in r["missed"]),
   "the chip group the task never touched is one missed field, not two: %s" % " | ".join(r["missed"]))
ck(any("girth" in m for m in r["missed"]),
   "and so is the stepper the task never touched -- named by the member that says most, "
   "because 'button(-)' tells a reader nothing about which field was never filled: %s" % missed)
ck("addRow" not in missed and "clearAll" not in missed and "Add row" not in missed,
   "a button that carries no value is neither entered nor missed -- it is not a field: %s" % missed)
ck("tally" not in missed,
   "and neither is a READONLY box: the swarm's own name for it is readonly_out, 'a display, "
   "not a control', and a display nobody filled is not a field nobody filled: %s" % missed)
ck(r["entered"] <= r["fields"] <= r["controls"],
   "entered <= fields <= controls, always: %d <= %d <= %d"
   % (r["entered"], r["fields"], r["controls"]))
ck(r["driven"] == 7 and r["steps"] == 8,
   "the entry drove seven of the eight steps it was given, and the eighth was refused -- a "
   "slider action on a text box: %d of %d" % (r["driven"], r["steps"]))
ck(any("notes" in m for m in r["missed"]),
   "and the field that REFUSED step was pointed at is not entered: a step that did not happen "
   "did not enter anything: %s" % " | ".join(r["missed"]))

# The key case, stated on its own: the answered option is GONE by the end.
ck(not any("answer one" in m for m in r["missed"]),
   "a control the entry answered and the page then REMOVED still counts as entered -- a "
   "character key deletes the option it has answered, and counting only what survives said "
   "'0 entered' about a task that answered the whole key: %s" % missed)
ck(not any("answer three" in m for m in r["missed"]),
   "...and one that the page CREATED as an answer to an earlier one, which no state walk ever "
   "saw and which the page did not keep, is counted too -- it is a field, it was entered, and "
   "the only record of it is what the entry touched: %s" % missed)

# ---- C. the ratchet ---------------------------------------------------------
rc = E.main([])
led = json.load(io.open(E.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["entered"] == 6 and led.get("floor", 0) == 0,
   "a plain run records the reading and sets no floor: %s" % led)
rc = E.main(["--raise-floors"])
led = json.load(io.open(E.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led["floor"] == 6, "--raise-floors records today's reading as the floor: %s" % led)

state = E.load()
state["pages"]["fixture.html"]["floor"] = 9        # a floor no reading can meet
E.save(state)
rc = E.main([])
ck(rc == 1,
   "a page that entered fewer fields than its floor makes the run REFUSE, with no flag needed: "
   "run_all runs an audit with no arguments, so a floor that only bit under --check would be a "
   "floor nothing ever checked: rc=%d" % rc)
ck(E.main(["--check"]) == 1, "...and --check is accepted and means the same thing")
state = E.load()
state["pages"]["fixture.html"]["floor"] = 0
E.save(state)
E.main(["--raise-floors"])            # back to a floor the reading meets
ck(E.main([]) == 0 and E.main(["--check"]) == 0,
   "...and it passes when no page is below its floor: a gate that refuses whatever the reading "
   "is not a gate")
state = E.load()
state["pages"]["fixture.html"]["floor"] = 9
E.save(state)
ck(E.main(["--lower", "fixture.html"]) == 2,
   "lowering a floor with no reason is refused")
ck(E.main(["--lower", "nosuch.html", "--reason", "x"]) == 2,
   "and a page with no floor cannot be lowered")
ck(E.main(["--lower", "fixture.html", "--reason", "the task was split in two"]) == 0,
   "lowering with a reason is allowed")
led = json.load(io.open(E.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led["floor"] == 0 and led["lowered"] and led["lowered"][-1]["reason"] == "the task was split in two"
   and led["lowered"][-1]["from"] == 9,
   "and the reason, and what it was lowered FROM, go into the ledger where a reader will find "
   "them: %s" % led.get("lowered"))

# ---- D. the kinds are a partition, not a guess -------------------------------
import harness as H2
kinds = set(k for k, _sel in getattr(H2, "KINDS", []))
if kinds:
    ck(set(E.ENTERABLE) | set(E.NOT_ENTERABLE) >= kinds - {"tab"},
       "every kind the swarm discovers is on one side of the line or the other: %s"
       % sorted(kinds - (set(E.ENTERABLE) | set(E.NOT_ENTERABLE))))
    ck(not (set(E.ENTERABLE) & set(E.NOT_ENTERABLE)), "and no kind is on both sides")
else:
    ck(True, "harness.KINDS is not a list of pairs here; the partition is checked by the fixture")
ck(set(E.CHOICE_KINDS) <= set(E.ENTERABLE),
   "a choice kind is an enterable kind: %s" % sorted(set(E.CHOICE_KINDS) - set(E.ENTERABLE)))

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
