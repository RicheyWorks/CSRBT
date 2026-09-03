# -*- coding: utf-8 -*-
"""Audits, everywhere (ADR-130).

The kit's audits -- 44 px targets, AA contrast, keyboard focus -- measured
each page as loaded. Half of an instrument sits behind a closed tab, an
unopened <details>, a "compare" toggle or a season not yet started, and an
element with no box was simply skipped: the rules had never been applied to
most of the controls a reader uses, and 35 real defects hid there. This
suite holds tools/audit_states.py, and the three audits that use it, to what
"everywhere" has to mean:

  A. the states: rest (every <details> opened), each .tab[data-pane] and each
     [aria-controls] button pressed in document order, each page-specific
     reveal (a button, or a <select> set to a value that grows a dependent
     field -- its owning tab pressed first, or the field has no box), and a
     revealed surface's own tabs after it
  B. the accounting: every control that exists is stamped once and its stamp
     survives every state; the controls no state exposed are named, by
     element, so "measured everywhere" is a count and not a hope; a hidden
     input and a file input are not controls
  C. the click is programmatic: after a pointer click the browser hides
     focus rings on programmatic focus, and a focus audit run after real
     clicks reported 1,461 faults that were the mouse's
  D. the audits: run on a fixture directory whose faults are known -- a 20 px
     button behind the second tab, faint text behind the third, a control no
     state reaches -- audit_targets, audit_focus and audit_contrast each
     exit non-zero, name the fault, and count the unreached control as one
  E. on real pages: the season starts for the audits (field-season), the
     guide's hot-phase fields are reached through their tab
     (experiment-guide), and the coverage on both is complete
  F. the entered state (ADR-131): the page's OWN science task is what is
     replayed -- never a reference task, never a canary, never another page's;
     the entry steps are driven and the reads are not; a control that exists
     only in a built row is exposed and measured; each tab is walked again
     from there; an entry that drove nothing is a fault, and a refusal on a
     step that was meant to refuse is not

Run:  python3 tools/verify/verify_audit_states.py
"""
# Declared for tools/mutate.py: this suite writes its own fixture pages and
# asserts about tools/audit_states.py -- a subject.
MUTATE_ROLE = "subject"
import io, json, os, re, subprocess, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import audit_states as S
import audit_focus as AF  # noqa: its PROBE is check C's witness

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


FIXTURE = u"""<!doctype html><html><head><meta charset="utf-8"><title>states fixture</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{margin:0;padding:8px;background:#fff;color:#222;font:16px/1.4 sans-serif}
  .pane{display:none}.pane.on{display:block}
  button,select,input{min-height:44px;min-width:44px;font-size:16px;border:1px solid #666;background:#fff;color:#222}
  #small{min-height:0;height:20px}
  #never{display:none}
  #extra{display:none}#extra.on{display:block}
  #hotInput{display:none}body.hot #hotInput{display:block}
  button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #0a58ca}
</style></head><body>
<h1>fixture</h1>
<button class="tab" data-pane="p1">One</button>
<button class="tab" data-pane="p2">Two</button>
<button id="t3" aria-controls="p3">Three</button>
<div id="p1" class="pane on"><button id="b1">B1</button></div>
<div id="p2" class="pane">
  <button id="small">tiny</button>
  <select id="kind" aria-label="kind"><option>cold</option><option>hot</option></select>
  <input id="hotInput" aria-label="hot set">
  <input id="typed" aria-label="typed">
  <button id="addRow">add</button>
  <div id="rows"></div>
</div>
<div id="p3" class="pane"><p id="faint" style="color:#c8c8c8">faint text behind the third tab</p><button id="b3">B3</button></div>
<details><summary>more about it</summary><button id="inDetails">D</button></details>
<button id="never">never</button>
<button id="more">more</button>
<div id="extra">
  <button class="tab" data-pane="p4">nested</button>
  <div id="p4" class="pane"><input id="extraIn" aria-label="extra"></div>
</div>
<input type="hidden" id="h"><label>file <input type="file" id="f"></label>
<script>
  function show(id){ document.querySelectorAll('.pane').forEach(function(p){ p.classList.toggle('on', p.id === id); }); }
  document.querySelectorAll('.tab[data-pane]').forEach(function(t){ t.addEventListener('click', function(){ show(t.getAttribute('data-pane')); }); });
  document.getElementById('t3').addEventListener('click', function(){ show('p3'); });
  // "more" replaces the third tab with the nested surface: B3 is then reachable
  // in the first pass over the tabs and never again, which is what makes the
  // accounting's accumulation across states a claim the suite can refute
  document.getElementById('more').addEventListener('click', function(){ document.getElementById('extra').classList.add('on'); document.getElementById('t3').remove(); });
  document.getElementById('kind').addEventListener('change', function(e){ document.body.classList.toggle('hot', e.target.value === 'hot'); });
  // a row exists only once something has been entered: its buttons have no box
  // in any state of the empty page, which is the whole point of "entered"
  document.getElementById('addRow').addEventListener('click', function(){
    var v = document.getElementById('typed').value;
    if (!v) return;
    document.getElementById('rows').insertAdjacentHTML('beforeend',
      '<div class="row"><span class="l">name</span><span class="v">' + v + '</span>' +
      '<button class="rowDrop" aria-label="remove ' + v + '">x</button></div>');
  });
</script></body></html>
"""

# A page with an entry: one task file whose steps build a row, so the entered
# state is a real state and not a hope. Written beside the fixture page so the
# suite owns both halves of what it asserts.
TASKS = {
    "page-fixture-science": {
        "id": "page-fixture-science", "target": "page", "page": "fixture.html",
        "goal": "build a row, then read what the page says about it",
        "steps": [
            {"id": "s0", "action": "observe"},
            {"id": "s1", "action": "show-pane", "arguments": {"pane": "p2"}},
            {"id": "s2", "action": "set-text", "arguments": {"selector": "@control:typed", "value": "kestrel"}},
            {"id": "s3", "action": "activate", "arguments": {"selector": "@control:addRow"}},
            {"id": "s4", "action": "read-report"},
        ],
    },
    "page-fixture-reference": {
        "id": "page-fixture-reference", "target": "page", "page": "fixture.html",
        "goal": "the outline", "steps": [{"id": "r0", "action": "read-report"}],
    },
    "page-fixture-canary": {
        "id": "page-fixture-canary", "target": "page", "page": "fixture.html", "must": "FAIL",
        "goal": "a canary: enter what the page must reject",
        "steps": [{"id": "c0", "action": "observe"},
                  {"id": "c1", "action": "activate", "arguments": {"selector": "@control:never"}}],
    },
    # three pages that isolate one selection rule each -- without them the
    # preference for "-science" masks the canary and reference filters, and
    # alphabetical order masks the preference
    "page-canaryonly-canary": {
        "id": "page-canaryonly-canary", "target": "page", "page": "canaryonly.html", "must": "FAIL",
        "goal": "a canary and nothing else",
        "steps": [{"id": "c0", "action": "activate", "arguments": {"selector": "#more"}}],
    },
    "page-refonly-reference": {
        "id": "page-refonly-reference", "target": "page", "page": "refonly.html",
        "goal": "reads and nothing else",
        "steps": [{"id": "r0", "action": "observe"}, {"id": "r1", "action": "read-report"}],
    },
    "page-aprefer-extra": {
        "id": "page-aprefer-extra", "target": "page", "page": "prefer.html",
        "goal": "sorts first, and is not the science task",
        "steps": [{"id": "a0", "action": "activate", "arguments": {"selector": "#more"}}],
    },
    "page-zprefer-science": {
        "id": "page-zprefer-science", "target": "page", "page": "prefer.html",
        "goal": "sorts last, and is the science task",
        "steps": [{"id": "z0", "action": "activate", "arguments": {"selector": "#more"}}],
    },
    "page-other-science": {
        "id": "page-other-science", "target": "page", "page": "other.html",
        "goal": "another page's task", "steps": [{"id": "o0", "action": "activate", "arguments": {"selector": "#more"}}],
    },
}

tmp = tempfile.mkdtemp(prefix="states_")
docs = os.path.join(tmp, "docs")
os.mkdir(docs)
fx = os.path.join(docs, "fixture.html")
io.open(fx, "w", encoding="utf-8").write(FIXTURE)
tasks_dir = os.path.join(tmp, "tasks")
os.mkdir(tasks_dir)
for tid, t in TASKS.items():
    io.open(os.path.join(tasks_dir, tid + ".json"), "w", encoding="utf-8").write(json.dumps(t, indent=1))
S.TASKS_DIR = tasks_dir

S.STATE_BUTTONS["fixture.html"] = [("select", "#kind", "hot"), "#more"]
# the controls with a box, plus "details:open" when the <details> is open --
# Chromium lays out a closed <details>' content (content-visibility: hidden
# keeps the boxes), so opening it is a matter of the state a reader sees, not
# of a box appearing, and the check has to look at the attribute
BOXED = ("() => [...document.querySelectorAll('button,select,input')].filter(e => { const b = e.getBoundingClientRect(); "
         "return b.width > 0 || b.height > 0; }).map(e => e.id || e.textContent.trim())"
         ".concat(document.querySelector('details').open ? ['details:open'] : [])")

from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.goto("file://" + fx.replace(os.sep, "/"), wait_until="domcontentloaded")

    # ---- A. the states ----------------------------------------------------
    seen = []
    for state, r in S.each_state(pg, "fixture.html", lambda: pg.evaluate(BOXED)):
        seen.append((state, set(r)))
    names = [s for s, _ in seen]
    want = ["rest", "pane:p1", "pane:p2", "pane:p4", "pane:p3", "state:kind=hot", "state:more",
            "state:more/pane:p1", "state:more/pane:p2", "state:more/pane:p4",
            "entered", "entered/pane:p1", "entered/pane:p2", "entered/pane:p4",
            "entered/state:kind=hot", "entered/state:more"]
    ck(names == want, "the states, in order: rest, each tab (data-pane then aria-controls), each reveal, "
                      "a revealed surface's tabs after it: %s" % names)
    by = dict(seen)
    ck("inDetails" in by.get("rest", set()) and "details:open" in by.get("rest", set()),
       "at rest every <details> is opened, so a reader's view of its content is the audited one: %s" % sorted(by.get("rest", set())))
    ck("small" not in by.get("rest", set()) and "small" in by.get("pane:p2", set()),
       "a control behind the second tab has a box only once that tab is pressed")
    ck("b3" in by.get("pane:p3", set()), "an [aria-controls] button opens its pane: %s" % sorted(by.get("pane:p3", set())))
    ck("hotInput" not in by.get("pane:p2", set()) and "hotInput" in by.get("state:kind=hot", set()),
       "a <select> reveal grows the dependent field, reached through its own tab after another tab closed it: %s"
       % sorted(by.get("state:kind=hot", set())))
    ck("extraIn" not in by.get("state:more", set()) and "extraIn" in by.get("state:more/pane:p4", set()),
       "a revealed surface's own tab is pressed after the reveal: %s" % sorted(by.get("state:more/pane:p4", set())))

    # ---- B. the accounting ------------------------------------------------
    cov = S.coverage(pg)
    ck(cov["exist"] == 15, "15 controls exist at the end (the row's button included; hidden and file inputs are not controls; the third tab is gone): %s" % cov["exist"])
    ck(cov["exposed"] == 14, "14 had a box in some state -- B3's box in the third pane, seen once, is remembered: %s" % cov["exposed"])
    ck(len(cov["never"]) == 1 and "#never" in cov["never"][0],
       "the one control no state exposed is named by element: %s" % cov["never"])
    stamps = pg.evaluate("() => [...document.querySelectorAll('[data-audit]')].map(e => e.getAttribute('data-audit'))")
    ck(len(stamps) == 15 and len(set(stamps)) == 15,
       "every control carries one stable stamp, the ones the entry built included: %d stamps, %d distinct"
       % (len(stamps), len(set(stamps))))
    first = pg.evaluate("() => document.querySelector('.tab[data-pane]').getAttribute('data-audit')")
    ck(first == "button.tab[submit]|1",
       "a stamp is what the element IS -- tag, id, non-state classes, input type -- plus its occurrence, so a "
       "region rebuilt from the same template keeps its stamps and its measurements: %s" % first)
    onoff = pg.evaluate("""() => { const t = document.querySelector('.tab[data-pane]');
      const before = t.getAttribute('data-audit'); t.classList.add('on'); return [before, t]; }""")
    pg.evaluate(S.MARK_JS, S.CONTROLS)
    after = pg.evaluate("() => { const t = document.querySelector('.tab[data-pane]'); const a = t.getAttribute('data-audit'); t.classList.remove('on'); return a; }")
    ck(after == "button.tab[submit]|1",
       "a state class (on/open/active/selected...) does not re-key a control: a chip you pick is the same chip: %s" % after)
    # a real re-render: the page rebuilds the region from its own template, so
    # the elements come back WITHOUT the stamp the audit put on them
    rebuilt = pg.evaluate("""() => { const box = document.getElementById('rows');
      const html = box.innerHTML.replace(/ data-audit="[^"]*"/g, '');
      box.innerHTML = ''; box.innerHTML = html;
      return [...document.querySelectorAll('.rowDrop')].map(e => e.getAttribute('data-audit')); }""")
    pg.evaluate(S.MARK_JS, S.CONTROLS)
    again = pg.evaluate("() => [...document.querySelectorAll('.rowDrop')].map(e => e.getAttribute('data-audit'))")
    ck(rebuilt == [None] and again == ["button.rowDrop[submit]|1"],
       "a region rebuilt with innerHTML comes back under the SAME stamp -- a counter would have forgotten every "
       "state that measured it: %s then %s" % (rebuilt, again))

    # ---- C. the click is programmatic ---------------------------------------
    inv = pg.evaluate(AF.PROBE)["invisible"]
    ck(inv == [], "after the walk the focus audit's own probe sees a ring on every control: the states were pressed "
                  "by JS, not by a pointer (a pointer click hides rings on programmatic focus): %s" % inv)
    ck(S._click(pg, "#nothing-here") is False, "pressing a selector that matches nothing is False, not an error")
    b.close()

# ---- D. the audits on a fixture directory whose faults are known ------------
env = dict(os.environ, CSRBT_DOCS_DIR=docs,
           CSRBT_AUDIT_STATES='{"fixture.html": [["select", "#kind", "hot"], "#more"]}')


def audit(name):
    p = subprocess.run([sys.executable, os.path.join(_kit.TOOLS_DIR, name + ".py")], capture_output=True, text=True,
                       timeout=300, env=env, cwd=_kit.TOOLS_DIR)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


rc, out = audit("audit_targets")
ck(rc == 1, "audit_targets exits 1 on the fixture (rc %s)" % rc)
ck("total under 44px or never measured across the kit: 2" in out,
   "targets: the 20 px button behind the second tab and the never-exposed control are two faults: %s" % out.strip().split("\n")[-1])
ck("NEVER EXPOSED in 10 states" in out and "#never" in out, "targets names the unreached control and the state count")
ck("10 states" in out, "targets reports the states it measured")

rc, out = audit("audit_focus")
ck(rc == 1, "audit_focus exits 1 on the fixture (rc %s)" % rc)
ck(re.search(r"^no visible focus:\s+0$", out, re.M) is not None,
   "focus: no false 'no visible focus' -- the clicks that opened the states were not pointer clicks: %s"
   % [l for l in out.split("\n") if "visible focus" in l])
ck(re.search(r"^never exposed, so never measured:\s+1$", out, re.M) is not None,
   "focus counts the unreached control as a fault: %s" % [l for l in out.split("\n") if "never" in l])
ck("#never" in out, "focus names the unreached control")

rc, out = audit("audit_contrast")
ck(rc == 1, "audit_contrast exits 1 on the fixture (rc %s)" % rc)
ck(re.search(r"^text below AA:\s+1$", out, re.M) is not None,
   "contrast: the faint text behind the third tab is found: %s" % [l for l in out.split("\n") if "below AA" in l])
ck(re.search(r"^never exposed, unmeasured:\s+1$", out, re.M) is not None
   and re.search(r"^total faults:\s+2$", out, re.M) is not None,
   "contrast counts the unreached control in its total: %s" % [l for l in out.split("\n") if "never" in l or "total" in l])
ck("10 states" in out or "faint" in out, "contrast reports per state")

# ---- E. real pages -------------------------------------------------------
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    for name, must in (("field-season.html", "state:startBtn"), ("experiment-guide.html", "state:p-kind=hot")):
        pg.goto(_kit.url(name), wait_until="domcontentloaded")
        pg.wait_for_timeout(700)
        states = [s for s, _ in S.each_state(pg, name, lambda: 0)]
        cov = S.coverage(pg)
        ck(must in states, "%s reaches %s: %s" % (name, must, states))
        ck(cov["exist"] > 0 and cov["never"] == [], "%s: every one of its %d controls was exposed in some state (never: %s)"
           % (name, cov["exist"], cov["never"][:5]))
    ck("#startBtn" in S.states_of("field-season.html") and "#cmpBtn" in S.states_of("tree-visualizer.html"),
       "the page-specific reveals are declared for the pages that need them")
    b.close()

# ---- F. the entered state (ADR-131) ---------------------------------------
t = S.task_for("fixture.html", tasks_dir)
ck(t is not None and t["id"] == "page-fixture-science",
   "the page's own SCIENCE task is what gets replayed -- not the reference task (all reads), "
   "not the canary (written to be refuted): %s" % (t and t["id"]))
ck(S.task_for("other.html", tasks_dir)["id"] == "page-other-science",
   "a task is matched by the page it names, never by another page's")
ck(S.task_for("nobody.html", tasks_dir) is None, "a page with no task has no entry")
ck(S.task_for("canaryonly.html", tasks_dir) is None,
   "a page whose only task is a canary has NO entry -- a task written to be refuted enters what the page must "
   "reject: %s" % (S.task_for("canaryonly.html", tasks_dir) or {}).get("id"))
ck(S.task_for("refonly.html", tasks_dir) is None,
   "a page whose only task is all reads has no entry -- replaying it would change nothing: %s"
   % (S.task_for("refonly.html", tasks_dir) or {}).get("id"))
ck(S.task_for("prefer.html", tasks_dir)["id"] == "page-zprefer-science",
   "with two tasks that both enter, the SCIENCE task wins even though the other sorts first: %s"
   % S.task_for("prefer.html", tasks_dir)["id"])

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.goto("file://" + fx.replace(os.sep, "/"), wait_until="domcontentloaded")
    seen = dict((state, set(r)) for state, r in S.each_state(pg, "fixture.html", lambda: pg.evaluate(BOXED)))
    names = list(seen)
    ck("entered" in names and names[-1].startswith("entered"),
       "the entered state comes after every state of the empty page: %s" % names[-5:])
    ck([n for n in names if n.startswith("entered/pane:")] ==
       ["entered/pane:p1", "entered/pane:p2", "entered/pane:p4"],
       "and each tab is walked again from there (the third tab is gone by then): %s"
       % [n for n in names if n.startswith("entered/")])
    ent = getattr(pg, "_audit_entered", None)
    ck(ent and ent["task"] == "page-fixture-science" and ent["driven"] == 3 and ent["steps"] == 3,
       "the entry drives the three entry steps and skips the two reads: %s" % ent)
    ck("x" in seen.get("entered/pane:p2", set()),
       "a control that exists only in a built row has a box in the entered state, and in no earlier one: %s"
       % sorted(seen.get("entered/pane:p2", set())))
    ck(all("x" not in v for k, v in seen.items() if not k.startswith("entered")),
       "...and in no state of the empty page")
    cov = S.coverage(pg)
    ck(cov["exist"] == 15 and len(cov["never"]) == 1 and "#never" in cov["never"][0],
       "the row's button is counted and measured; the one control no state exposes is still the only one unmeasured: "
       "%d controls, never %s" % (cov["exist"], cov["never"]))
    ck(S.entry_fault(ent) is None, "an entry that drove its steps is not a fault")
    b.close()

ck(S.entry_fault({"task": "t", "driven": 0, "refused": 2, "steps": 2}) is not None,
   "an entry that drove nothing IS a fault: the states after it are the empty page's")
ck(S.entry_fault({"task": "t", "driven": 0, "refused": 0, "steps": 0, "error": "no plugin"}) is not None,
   "an entry that could not run at all is a fault")
ck(S.entry_fault({"task": "t", "driven": 3, "refused": 1, "steps": 4}) is None,
   "a refusal on a step written to be refused is not: a science task drives refusal paths on purpose")
ck(S.entry_fault(None) is None, "a page with no task is not a fault -- it has nothing to enter")

# the three audits actually use the walker: an audit that does not loop over
# each_state and count coverage is the old audit under a new docstring
for name in ("audit_targets", "audit_focus", "audit_contrast"):
    src = io.open(os.path.join(_kit.TOOLS_DIR, name + ".py"), encoding="utf-8").read()
    ck("S.each_state(" in src and "S.coverage(" in src, "%s measures per state and keeps the accounting" % name)

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
