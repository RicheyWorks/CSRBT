# -*- coding: utf-8 -*-
"""What each page produces, and whether its task reads it -- checked (ADR-153).

`tools/audit_outputs.py` says 44 outputs across the kit leave a page with
nothing reading them. That number is a worklist and a ratchet, and it is wrong
in both directions unless five things are right, so a fixture pins each:

  A. WHAT COUNTS AS A BUTTON THAT HANDS SOMETHING OVER -- its NAME, before it
     is pressed, because a button is a candidate or there is no experiment.
     Not a text box that happens to say "save", and not something the gateway's
     own risk rule calls DESTRUCTIVE.
  B. "FORGET THIS DEVICE'S COPY" IS NOT PRESSED. It matches `copy` and a naive
     verb list would press it; the answer would be a lost autosave.
  C. A PAGE WITH A TASK IS MEASURED WITH ITS OWN DATA IN IT. An export pressed
     at rest hands over the page's empty-state placeholder, which is a payload
     -- so the button would be recorded as emitting the wrong bytes and never
     asked again.
  D. HELD MEANS THE TASK PRESSES IT AND THEN ASKS WHAT CAME OUT. Pressing it is
     not reading it.
  E. THE RATCHET AND THE EXEMPTION. The ceiling falls on request and never
     rises silently; an exemption needs a reason and the reason is stored.

Run:  python3 tools/verify/verify_outputs.py
"""
MUTATE_ROLE = "subject"
import io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness as H
import audit_states as S
import audit_outputs as A

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>outputs fixture</title>
<style>.pane{display:none}.pane.on{display:block}
 button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>outputs fixture</h1>
<div id="toast" class="toast"></div>
<button class="tab" data-pane="p1">One</button><button class="tab" data-pane="p2">Two</button>
<section class="pane on" id="p1">
  <!-- FIRST on the page on purpose: if this were ever pressed, every export
       after it would hand over the empty-state line instead of the rows -->
  <button id="forget" type="button">Forget this device's copy</button>
  <pre id="anSheet"># nothing recorded yet</pre>
  <!-- emits as soon as it is pressed -->
  <button id="always" type="button">Copy the sheet</button>
  <!-- refuses while the page is empty, and hands over rows once the entry has run -->
  <button id="late" type="button">Copy the rows CSV</button>
  <!-- a download, and a print -->
  <button id="dl" type="button">Download the sheet</button>
  <button id="pr" type="button">Print / save PDF</button>
  <!-- named for handing something over and never hands anything over -->
  <button id="notes" type="button">Copy the notes</button>
  <!-- the verb is INSIDE a word: not a control that hands anything over -->
  <button id="preprint" type="button">Preprint checklist</button>
  <!-- not an export at all -->
  <button id="add" type="button">Add a row</button>
  <!-- a text box whose LABEL says save: not a control that hands anything over -->
  <label>Plants you plan to save <input id="plans" aria-label="Plants you plan to save"></label>
</section>
<section class="pane" id="p2">
  <!-- behind a tab: found only because the states are walked -->
  <button id="behind" type="button">Export the matrix</button>
</section>
<script>
  var $ = function(i){ return document.getElementById(i); };
  window.__forgotten = false;
  var rows = [];
  function copy(text){
    var a = document.createElement("textarea"); a.value = text;
    a.style.position="fixed"; a.style.opacity="0";
    document.body.appendChild(a); a.select();
    try { document.execCommand("copy"); } catch(e){}
    document.body.removeChild(a);
  }
  $("add").addEventListener("click", function(){
    rows.push("row " + (rows.length + 1));
    $("anSheet").textContent = "# " + rows.length + " row(s)\\n" + rows.join("\\n"); });
  $("always").addEventListener("click", function(){ copy($("anSheet").textContent); });
  $("late").addEventListener("click", function(){
    if(!rows.length){ $("toast").classList.add("on"); return; }   /* nothing to hand over */
    copy("n,label\\n" + rows.map(function(r,i){ return (i+1)+","+r; }).join("\\n")); });
  $("dl").addEventListener("click", function(){
    var b = new Blob([$("anSheet").textContent], {type:"text/plain"});
    var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "sheet.txt";
    document.body.appendChild(a); a.click(); document.body.removeChild(a); });
  $("pr").addEventListener("click", function(){ window.print(); });
  $("notes").addEventListener("click", function(){ $("toast").classList.add("on"); });
  $("preprint").addEventListener("click", function(){ $("toast").classList.add("on"); });
  $("forget").addEventListener("click", function(){
    window.__forgotten = true; rows.length = 0;
    $("anSheet").textContent = "# nothing recorded yet"; });
  $("behind").addEventListener("click", function(){ copy("m,1,2"); });
  document.querySelectorAll(".tab").forEach(function(t){ t.addEventListener("click", function(){
    document.querySelectorAll(".pane").forEach(function(x){ x.classList.remove("on"); });
    $(t.getAttribute("data-pane")).classList.add("on"); }); });
</script></body></html>
"""

TASKS = {
    "page-fixture-science": {
        "id": "page-fixture-science", "target": "page", "page": "fixture.html",
        "goal": "add a row, then copy the sheet and read what came out",
        "steps": [
            {"id": "obs", "action": "observe"},
            {"id": "add", "action": "activate", "arguments": {"selector": "@control:add"}},
            # pressed AND read -> held
            {"id": "press", "action": "activate", "arguments": {"selector": "@control:always"}},
            {"id": "read", "action": "collect-output"},
            # pressed and never read -> not held
            {"id": "dl", "action": "activate", "arguments": {"selector": "@control:dl"}},
            # a step AFTER the last press and before any further read: a
            # collect-output credits the presses that have already happened,
            # and a rule that credits every step would credit this one with the
            # download nobody asked about
            {"id": "look", "action": "observe"},
        ],
    },
}

tmp = tempfile.mkdtemp(prefix="outputs_")
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
A.LEDGER = os.path.join(tmp, "outputs_ledger.json")

got = A.walk("fixture.html", tasks_dir)
r = got["fixture.html"]
by = dict((b["key"], b) for b in r["buttons"])
bad = A.blind(r, {})


def verdict(k):
    return (by.get(k) or {}).get("verdict", "MISSING")


# ---- A. what counts as a candidate ------------------------------------------
ck(r.get("task") == "page-fixture-science",
   "the page's own task is replayed, the same entry the other audits make: %s" % r.get("task"))
ck("always" in by and "dl" in by and "pr" in by and "late" in by,
   "a control whose NAME says it hands something over is a candidate -- copy, download, print, "
   "export, save -- and it is one BEFORE it is pressed, or there is no experiment: %s"
   % sorted(by))
ck("preprint" not in by,
   "a verb INSIDE a word is not a verb: 'Preprint checklist' is not a control that hands "
   "anything over, and matching inside a word is where a naive rule starts pressing things: "
   "%s" % sorted(by))
ck(verdict("notes") == "silent" and "notes" not in bad,
   "a button named for handing something over that hands over NOTHING is silent, and silent is "
   "not on the worklist: a page with nothing to export is right to export nothing, and the only "
   "claim here is about what does leave: %s" % verdict("notes"))
ck("add" not in by,
   "a button that is not named for handing anything over is not a candidate, whatever it does: "
   "%s" % sorted(by))
ck("plans" not in by and not any("Plants" in k for k in by),
   "and neither is a TEXT BOX whose label happens to say save -- 'Plants you plan to save' is "
   "where a naive verb list starts pressing things: %s" % sorted(by))

# ---- B. the destructive one is not pressed ----------------------------------
ck("forget" not in by,
   "'Forget this device's copy' matches `copy` and is NOT a candidate: the rule is not written "
   "twice, it is harness_plugin_page.destroys, the same rule the gateway's risk ladder raises "
   "DESTRUCTIVE on: %s" % sorted(by))
ck((by.get("always") or {}).get("head", "").startswith("# 1 row"),
   "...and it was not pressed, which is the claim that matters: it sits first on the page and "
   "clears the rows, so every export after it would have handed over the empty-state line. What "
   "they handed over is the sheet the entry built: %s" % (by.get("always") or {}).get("head"))

# ---- C. measured with the page's own data in it -----------------------------
ck(verdict("late") == "emits",
   "a button that refuses while the page is empty and hands over rows once the entry has run is "
   "measured AFTER the entry: at rest it would read as silent, which is a fact about the moment "
   "and not about the page: %s" % verdict("late"))
ck((by.get("late") or {}).get("bytes", 0) > 0 and "n,label" in (by.get("late") or {}).get("head", ""),
   "...and what it hands over is the rows, not the empty-state placeholder: %s"
   % (by.get("late") or {}).get("head"))
ck("# nothing recorded yet" not in (by.get("always") or {}).get("head", ""),
   "and the same is true of one that always emits: pressed at rest it would hand over the page's "
   "empty-state line, be recorded as emitting, and never be asked again: %s"
   % (by.get("always") or {}).get("head"))
ck(verdict("behind") == "emits",
   "a button behind a tab is a button: the page is walked through every state: %s"
   % verdict("behind"))

# ---- D. held means pressed AND read -----------------------------------------
ck((by.get("always") or {}).get("held") is True,
   "an output the task presses and then asks about is HELD: %s" % by.get("always"))
ck((by.get("dl") or {}).get("held") is False and "dl" in bad,
   "an output the task presses and never asks about is NOT held -- pressing it is not reading "
   "it, and this is the whole distinction the audit exists to make: %s" % by.get("dl"))
ck(sorted(bad) == ["behind", "dl", "late", "pr"],
   "four unread outputs on this fixture, no more and no fewer: %s" % sorted(bad))
ck((by.get("pr") or {}).get("kinds") == ["print"],
   "a print is an output too, and it is read through the same channel: %s" % by.get("pr"))
ck((by.get("dl") or {}).get("kinds") == ["download"],
   "...and a Blob download comes back as one: %s" % by.get("dl"))

# ---- E. the ratchet and the exemption ---------------------------------------
rc = A.main([])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["unread"] == sorted(bad) and "ceiling" not in led,
   "a first reading records what it found and no ceiling: %s" % led)
rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led.get("ceiling") == 4, "the ceiling is set on request, at today's reading: %s" % led)

state = A.load()
state["pages"]["fixture.html"]["ceiling"] = 3
A.save(state)
ck(A.main([]) != 0,
   "a page carrying MORE unread outputs than its ceiling fails, with no flag: run_all runs an "
   "audit with no arguments")
ck(A.main(["--check"]) != 0, "--check is accepted for symmetry, and refuses too")
state = A.load()
state["pages"]["fixture.html"]["ceiling"] = 4
A.save(state)
ck(A.main([]) == 0, "back at its ceiling, the page passes")

ck(A.main(["--declare", "fixture.html:pr"]) != 0,
   "declaring an output exempt WITHOUT a reason is refused: a list of outputs this audit is "
   "choosing not to care about is only useful if every line says why")
rc = A.main(["--declare", "fixture.html:pr", "--reason", "a print is the browser's, not the page's"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led["declared"]["pr"] == "a print is the browser's, not the page's",
   "...and with one, the reason is what is stored: %s" % led.get("declared"))
bad2 = A.blind(r, A.declared_of(A.load(), "fixture.html"))
ck(bad2 == ["behind", "dl", "late"],
   "a declared output leaves the worklist -- and only that one: %s" % bad2)
rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("ceiling") == 3,
   "...and --raise-floors LOWERS the ceiling, because this ratchet only ever comes down: %s" % led)

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
