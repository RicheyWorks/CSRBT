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
import contextlib, io, json, os, sys, tempfile

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
  <!-- AND FIVE MORE THAT ARE NOT BUTTONS EITHER (ADR-208), every one of them a
       kind this kit composes, every label naming a handover, and not one of
       them spelt with the two characters the rule used to look for -->
  <div class="fek-step"><button type="button">-</button><span class="val" id="sv"
    role="spinbutton" aria-label="Plants you plan to save seed from">3</span><button
    type="button">+</button></div>
  <div class="fek-slide"><input id="sl" type="range" min="0" max="10" value="4"
    aria-label="How many rows to export"></div>
  <label>Copy which sheet <select id="pick" aria-label="Copy which sheet"><option>one</option>
    <option>two</option></select></label>
  <label>Print the labels <input id="pl" type="checkbox" aria-label="Print the labels"></label>
  <div id="drop" data-h-drop aria-label="Drop a photo to save it here">drop here</div>
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

# ---- THE EXEMPTION RECORDS WHAT IT TOOK OUT (ADR-224) ----------------------
# Filtering the finding out of the list and writing the filtered list to the
# ledger discarded the evidence at the moment the exemption was applied, and no
# reader in the kit could then tell a declaration covering a real finding from
# one naming a thing the page no longer has. The rule lives in tools/exempt.py
# and is asserted HERE, through this audit's own reading, so that a copy of it
# that filtered quietly would fail this suite and not only the reader's.
with contextlib.redirect_stdout(io.StringIO()):
    A.main([])
_row = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck('pr' in (_row.get("raw") or []) and 'pr' not in (_row.get("unread") or []),
   "the row records what was flagged BEFORE the exemption under `raw`, beside the filtered "
   "list it always recorded -- the declared key is in one and not the other: raw %s, filtered %s"
   % (_row.get("raw"), _row.get("unread")))
ck(isinstance(_row.get("seen"), list) and set(_row.get("raw") or []) <= set(_row.get("seen") or [])
   and set(_row.get("unread") or []) <= set(_row.get("raw") or []),
   "...and everything the reading could have flagged under `seen`, with filtered within raw within "
   "seen -- without the universe, `this finding is covered` and `this thing is gone` are the same "
   "absence: seen %s" % _row.get("seen"))
_live, _e = ["k1"], {}
A.X.apply(_e, _live, {}, ["k1", "other"])
_live.append("added after the record was written")
ck(_e["raw"] == ["k1"] and _e["seen"] == ["k1", "other"],
   "the record is a COPY, not the audit's live list: a row holding the list the audit goes on "
   "using would be rewritten by whatever the audit did to it next: %s" % _e["raw"])
ck(isinstance(_row.get("mute_raw"), list) and isinstance(_row.get("mute_seen"), list)
   and _row.get("mute_raw") is not _row.get("raw"),
   "A PAGE WITH TWO RATCHETS KEEPS TWO RAW LISTS, under two keys: mute_raw %s" % _row.get("mute_raw"))
ck(_row.get("trap") is False,
   "and the row carries the audit's own VERDICT on the page (trap), so a whole-page declaration "
   "can be held to it: %s" % _row.get("trap"))
rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("ceiling") == 3,
   "...and --raise-floors LOWERS the ceiling, because this ratchet only ever comes down: %s" % led)

# ---- F. THE PAGE SHAPE THIS AUDIT COULD NOT SEE (ADR-205) -------------------
#
# A page with no output button used to be skipped by a single `continue`, so
# the ONE shape this audit exists to catch -- data in, nothing out -- produced
# no row, no ledger entry and no number. Two pages of this kit sat that way for
# months. Two fixtures here: a trap, and a page that is right to hand nothing
# over, because a rule that named both would be turned off within a week.
TRAP = u"""<!doctype html><html><head><meta charset="utf-8"><title>trap fixture</title>
<style>button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>trap fixture</h1><div id="toast" class="toast"></div>
<label>Plot <input id="a" type="text" aria-label="Plot"></label>
<label>Date <input id="b" type="date" aria-label="Date"></label>
<label>Count <input id="c" type="number" aria-label="Count"></label>
<label>Observer <input id="d" type="text" aria-label="Observer"></label>
<label>Notes <textarea id="e" aria-label="Notes"></textarea></label>
<button id="add" type="button">Add a row</button>
<pre id="sheet"># nothing yet</pre>
<script>
  var rows=[];
  document.getElementById("add").addEventListener("click",function(){
    rows.push("row"); document.getElementById("sheet").textContent="# "+rows.length+" row(s)"; });
</script></body></html>
"""
QUIET = u"""<!doctype html><html><head><meta charset="utf-8"><title>quiet fixture</title>
<style>button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>quiet fixture</h1><div id="toast" class="toast"></div>
<label>Search <input id="q" type="text" aria-label="Search the glossary"></label>
<p>A reference page. Nothing is entered here that anybody would want back.</p>
</body></html>
"""
io.open(os.path.join(docs, "trap.html"), "w", encoding="utf-8").write(TRAP)
io.open(os.path.join(docs, "quiet.html"), "w", encoding="utf-8").write(QUIET)

tr = A.walk("trap.html", tasks_dir)["trap.html"]
qt = A.walk("quiet.html", tasks_dir)["quiet.html"]
ck(not tr.get("buttons") and not qt.get("buttons"),
   "neither fixture hands anything over, which is the shape under test: %s / %s"
   % (len(tr.get("buttons") or []), len(qt.get("buttons") or [])))
ck(tr.get("entry", 0) >= A.TRAP_ENTRY,
   "THE AUDIT NOW MEASURES WHAT A PAGE TAKES IN, so that handing nothing over can be judged "
   "rather than skipped. A page with no export used to hit a bare `continue` -- no row, no "
   "ledger entry, no number -- which is why two benches accepting nineteen and twenty-nine "
   "typed values sat unreported under an audit built to ask exactly this: %s" % tr.get("entry"))
ck(qt.get("entry", 0) < A.TRAP_ENTRY,
   "and a reference page with a search box is UNDER the bar. A rule that called every page "
   "without an export a data trap would be switched off within a week, and then the real ones "
   "would be invisible again: %s" % qt.get("entry"))
ck(A.ENTRY_KINDS >= frozenset(H.TYPED),
   "what counts as taking something in is read from harness.TYPED rather than restated here, so "
   "a kind added tomorrow counts tomorrow -- the ADR-141 rule this whole slice is an instance "
   "of: %s" % sorted(A.ENTRY_KINDS))

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
print(said)
ck(rc != 0, "A PAGE THAT TAKES RECORDS AND HANDS NOTHING OVER FAILS THE AUDIT. It is a data "
            "trap: the work exists on one screen and there is no way to get it off, and the "
            "absence of a row is the loudest thing a ledger can say")
_named = [l for l in said.split("\n") if "entry control(s), 0 outputs" in l]
ck(any("trap.html" in l for l in _named),
   "...and the audit NAMES it, on the worklist, rather than only failing: %s" % _named)
ck(not any("quiet.html" in l for l in _named),
   "AND IT DOES NOT NAME THE PAGE THAT IS RIGHT TO HAND NOTHING OVER. A rule that called every "
   "page without an export a data trap would be switched off within a week, and then the real "
   "ones would be invisible again: %s" % _named)
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
ck("trap.html" in led and led["trap.html"]["buttons"] == 0,
   "...and it is IN THE LEDGER at zero outputs, rather than missing from it: %s"
   % sorted(led))
ck("quiet.html" in led and led["quiet.html"]["buttons"] == 0,
   "so is the page that is right to hand nothing over -- a row that says zero is evidence, and "
   "no row at all is not: %s" % sorted(led))

ck(A.main(["--declare-page", "trap.html"]) != 0,
   "declaring a page exempt without a reason is refused")
rc = A.main(["--declare-page", "trap.html", "--reason",
             "a demo of the rule, in this suite's own fixture directory"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
ck(rc == 0 and led["trap.html"].get("no_outputs")
   == "a demo of the rule, in this suite's own fixture directory",
   "...and with one, THE REASON IS WHAT IS STORED, word for word, where the judgement can be "
   "read. A ledger that recorded only that a page was exempt would be a list of silences: %s"
   % led["trap.html"].get("no_outputs"))
ck(A.main([]) == 0,
   "a declared page passes. The exemption is a written judgement, not a silence")
_trow = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["trap.html"]
ck(_trow.get("trap") is True and _trow.get("buttons") == 0,
   "...and its row says it IS a trap (the verdict), beside the declaration that excuses it -- "
   "ADR-224 reads both: %s" % {k: _trow.get(k) for k in ("trap", "buttons", "no_outputs")})

# ---- G. A SILENT BUTTON IS NOT AN OUTPUT (ADR-208) -------------------------
#
# Two halves of one defect. `HANDS_OVER` reads a LABEL, and every control on
# every page has one -- so the rule that keeps a text box out of the candidate
# list is doing the whole job of deciding what a button IS. It was written
# `kind.endswith("_in")`: a check about how a kind is SPELT. It catches
# `text_in`, `field_in` and `file_in`, and lets `step_val`, `slider`, `select`,
# `checkbox` and `drop_zone` straight through -- which is most of what this kit
# composes. Section A above pinned that rule with an `<input>`, the one kind
# whose spelling happens to match, and it read green for fifty-five ADRs.
#
# What made it unobservable is the other half: a control pressed by mistake
# hands nothing over and is filed `silent`, and `silent` was a number in a
# column. Nothing named it, no ratchet held it, and the audit exited zero. So
# an export that quietly stopped working, a control that should never have been
# pressed, and a page that never had an export all read the same.
import harness_plugin_page as PP


def snap_of(name):
    """The fixture's own snapshot, so that what is NOT a candidate can be
    checked against what the page actually offers. A check that only asserts an
    absence passes just as well when the control was never there."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=H.VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(H.STUBS)
        pg = ctx.new_page()
        pg.goto("file://" + os.path.join(docs, name).replace(os.sep, "/"),
                wait_until="domcontentloaded")
        pg.wait_for_timeout(250)
        pg.evaluate(S.OPEN_DETAILS_JS)
        out = PP.PagePlugin(pg, name).observe(sensitive=True)
        ctx.close()
        b.close()
        return out


sn = snap_of("fixture.html")
named = [c for c in sn.get("controls", []) if A.HANDS_OVER.search(c.get("label") or "")]
named_kinds = sorted(set(c.get("kind") for c in named))
NOT_BUTTONS = ("step_val", "slider", "select", "checkbox", "drop_zone")
ck(set(NOT_BUTTONS) <= set(named_kinds),
   "the fixture really does offer a step control, a slider, a select, a tick box and a drop "
   "zone whose labels every one of them say they hand something over -- a check that only "
   "asserts an absence passes just as well when the control was never there: %s" % named_kinds)

cand_kinds = sorted(set(c.get("kind") for c in A.candidates(sn)))
ck(all(k in A.PRESSED for k in cand_kinds),
   "and NOT ONE OF THEM IS A CANDIDATE: a control the door does not press cannot be a button "
   "that hands something over: %s" % cand_kinds)
ck(not (set(NOT_BUTTONS) & set(cand_kinds)),
   "...named one kind at a time, because this is the list that was wrong: %s"
   % sorted(set(NOT_BUTTONS) & set(cand_kinds)))
ck(not any(k.endswith("_in") or k == "pick_search" for k in NOT_BUTTONS),
   "AND THE RULE THIS REPLACED WOULD HAVE LET EVERY ONE OF THEM THROUGH. It read "
   "kind.endswith('_in') -- about how a kind is spelt, not about what it does -- and section A "
   "above pinned it with an <input>, the one kind whose spelling happens to match: %s"
   % list(NOT_BUTTONS))
ck(A.PRESSED == frozenset(PP.POOL_KINDS["activate"]),
   "what a button IS, is read from the door's own activate pool rather than restated here, so a "
   "kind added to that pool tomorrow counts tomorrow -- ADR-141's rule, for the fifth time: %s"
   % sorted(A.PRESSED))
ck("action_btn" in A.PRESSED and "chip" in A.PRESSED,
   "...and that pool is not empty of the things this kit exports with: %s" % sorted(A.PRESSED))

# the fixture's own silent button, now named rather than counted
ck(A.mute(r, {}) == ["notes"],
   "a button named for handing something over that hands NOTHING over is named: 'silent' used to "
   "be a number in a column, and a number nothing can point at is not a finding: %s"
   % A.mute(r, {}))
ck("notes" not in A.blind(r, {}),
   "...and it is still not on the UNREAD worklist. The two claims are separate: unread is about "
   "an output nobody looks at, mute is about a button that produces no output at all: %s"
   % A.blind(r, {}))

led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("mute") == ["notes"],
   "and the ledger carries the NAME, where a worklist can be read off it: %s" % led.get("mute"))
ck(led.get("mute_ceiling") == 1,
   "--raise-floors sets a mute ceiling the same way it sets the unread one: %s" % led)

state = A.load()
state["pages"]["fixture.html"]["mute_ceiling"] = 0
A.save(state)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
ck(rc != 0,
   "A PAGE THAT GREW A BUTTON HANDING NOTHING OVER FAILS, with no flag -- run_all runs an audit "
   "with no arguments, and a ratchet nothing runs is a comment")
_loud = [l for l in said.split("\n") if "silent, ceiling" in l]
ck(any("fixture.html" in l and "notes" in l for l in _loud),
   "...and it NAMES the page and the button, rather than only failing: %s" % _loud)

ck(A.main(["--declare-mute", "fixture.html:notes"]) != 0,
   "declaring a silent button exempt WITHOUT a reason is refused: a button that hands nothing "
   "over is either broken or right, and only the reason says which")
rc = A.main(["--declare-mute", "fixture.html:notes", "--reason",
             "the notes pane is empty until a reviewer writes in it"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(rc == 0 and led.get("mute_declared", {}).get("notes")
   == "the notes pane is empty until a reviewer writes in it",
   "...and with one, THE REASON IS WHAT IS STORED, word for word: %s" % led.get("mute_declared"))
ck(A.mute(r, A.muted_of(A.load(), "fixture.html")) == [],
   "a declared silent button leaves the mute worklist: %s"
   % A.mute(r, A.muted_of(A.load(), "fixture.html")))
ck(A.main([]) == 0,
   "...and the page passes at a mute ceiling of zero, because the exemption is a written "
   "judgement rather than a silence")
ck(sorted(A.blind(r, {})) == ["behind", "dl", "late", "pr"],
   "and declaring it changed NOTHING about the unread worklist -- two ratchets, two claims, and "
   "a page can fail either one alone: %s" % sorted(A.blind(r, {})))
state = A.load()
state["pages"]["fixture.html"]["mute_ceiling"] = 3
A.save(state)
rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("mute_ceiling") == 0,
   "--raise-floors LOWERS the mute ceiling, because this ratchet also only ever comes down: %s"
   % led)
# AND IT DOES NOT RAISE IT. Written with a page that is OVER its ceiling, because a
# ratchet asked to move in the direction it must not move, from a reading that
# equals the ceiling, is a check with no violator -- ADR-207's finding, and the
# first draft of this one read green under a mutant that inverted the comparison.
state = A.load()
state["pages"]["fixture.html"].pop("mute_declared", None)
state["pages"]["fixture.html"]["mute_ceiling"] = 0
A.save(state)
rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["fixture.html"]
ck(led.get("mute_ceiling") == 0 and led.get("mute") == ["notes"],
   "...and with the declaration taken away and the silent button back on the worklist, a "
   "--raise-floors run leaves the ceiling where it was rather than recording today's worse "
   "reading as the new normal: %s" % led)
ck(rc != 0,
   "...and that run still fails, because --raise-floors lowers what it can and reports what it "
   "cannot: a flag that forgave the page it could not ratchet would be a way to turn the rule "
   "off one page at a time")

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
