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
    # ADR-136: a control the page mounts AFTER the last stamp
    pg2 = b.new_page(viewport={"width": 390, "height": 900})
    pg2.goto("file://" + fx.replace(os.sep, "/"), wait_until="domcontentloaded")
    LATE = ("() => { const e = document.createElement('button'); e.id = 'late'; e.textContent = 'late'; "
            "document.body.appendChild(e); return true; }")
    seen2, mounted = [], []
    for state, _r in S.each_state(pg2, "fixture.html", lambda: pg2.evaluate(BOXED)):
        seen2.append(state)
        if state == "entered/state:more" and not mounted:
            pg2.evaluate(LATE)                      # the page builds a control after the walk's last stamp
            mounted.append(1)
    ck(mounted and seen2[-1] == "settled" and seen2[:-1] == names,
       "a page that grows a control after the last state settles into one more state, and only then: %s" % seen2[-2:])
    cov2 = S.coverage(pg2)
    ck(cov2["exist"] == 16 and cov2["exposed"] == 15 and len(cov2["never"]) == 1 and "#never" in cov2["never"][0],
       "the late control is stamped and MEASURED, not counted as a control no state exposed -- the only one "
       "never exposed is still the one that never had a box: exist=%s exposed=%s never=%s"
       % (cov2["exist"], cov2["exposed"], cov2["never"]))
    ck(not any(x is None for x in pg2.evaluate(S.UNSTAMPED_JS, S.CONTROLS)),
       "and no control is left carrying no stamp -- a fault that names nothing is the worst kind")
    # ADR-140: a control whose box arrives a moment after the last state's probe
    # ADR-140: a control the page reveals from its own animation frame. Settling
    # on getAnimations() cannot see it -- nothing is animating, the browser has
    # simply not produced a frame yet -- and a walk that measures before the
    # frame lands records a control that has a box as having none.
    pgF = b.new_page(viewport={"width": 390, "height": 900})
    pgF.goto("file://" + fx.replace(os.sep, "/"), wait_until="domcontentloaded")
    pgF.evaluate("""() => {
        const b = document.createElement('button');
        b.id = 'raf'; b.textContent = 'raf'; b.style.display = 'none';
        document.body.appendChild(b);
        document.querySelector('#more').addEventListener('click', () => {
            requestAnimationFrame(() => { b.style.display = ''; });
        });
    }""")
    for _s, _r in S.each_state(pgF, "fixture.html", lambda: pgF.evaluate(BOXED), entered=False):
        pass
    covF = S.coverage(pgF)
    ck(not any("#raf" in x for x in covF["never"]),
       "a control the page reveals asynchronously, after the click handler returns, is still "
       "measured: %s" % covF["never"])
    pgF.close()

    pg3 = b.new_page(viewport={"width": 390, "height": 900})
    pg3.goto("file://" + fx.replace(os.sep, "/"), wait_until="domcontentloaded")
    LATE_BOX = ("() => { const e = document.createElement('button'); e.id = 'slow'; "
                "e.textContent = 'slow'; e.style.display = 'none'; document.body.appendChild(e); "
                "return true; }")
    SHOW = "() => { document.getElementById('slow').style.display = ''; return true; }"
    pg3.evaluate(LATE_BOX)
    for state, _r in S.each_state(pg3, "fixture.html", lambda: pg3.evaluate(BOXED)):
        pass
    cov3 = S.coverage(pg3)
    ck(any("#slow" in x for x in cov3["never"]),
       "a control that never had a box in any state, and still has none, is named: %s" % cov3["never"])
    pg3.evaluate(SHOW)                       # ...and now it has one, a moment late
    cov4 = S.coverage(pg3)
    ck(not any("#slow" in x for x in cov4["never"]) and cov4["exposed"] == cov3["exposed"] + 1,
       "a control whose box arrived after the last state's probe is counted as exposed -- coverage "
       "settles and measures once more, because the end of the walk is still the last state: %s"
       % cov4["never"])
    # ADR-143: the look repeats, and says which look found what. A control
    # revealed BETWEEN two looks of one coverage() call is the contention case
    # that survived ADR-140 -- one extra look is itself a probe, and a probe can
    # be early.
    # The reveal is triggered by the MEASUREMENT, not by a timer: a timer long
    # enough to beat _settle would make the suite slow and a short one is
    # exactly the race this fixture must not depend on. The control's own
    # getBoundingClientRect answers "no box" the first time it is asked and
    # reveals the element as it does so -- which is what a browser that has not
    # laid the state out yet looks like from where the probe stands.
    LATE2 = ("() => { const e = document.createElement('button'); e.id = 'slower'; "
             "e.textContent = 'slower'; e.style.display = 'none'; document.body.appendChild(e); "
             "let asked = 0; const real = e.getBoundingClientRect.bind(e); "
             "e.getBoundingClientRect = () => { if (asked++ === 0) { e.style.display = ''; "
             "  return {width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0}; } "
             "  return real(); }; return true; }")
    pg3.evaluate(LATE2)
    cov5 = S.coverage(pg3)
    ck(not any("#slower" in x for x in cov5["never"]),
       "a control revealed BETWEEN two looks of one coverage() call is still counted: %s" % cov5["never"])
    ck(len(cov5["lateLooks"]) >= 2 and sum(cov5["lateLooks"][1:]) >= 1,
       "...and the run SAYS a later look found it, rather than absorbing the race silently: %s"
       % cov5["lateLooks"])
    cov6 = S.coverage(pg3)
    ck(len(cov6["lateLooks"]) == 2 and cov6["lateLooks"][0] > 0 and cov6["lateLooks"][1] == 0,
       "on a settled page the second look finds nothing and the looking stops there: %s"
       % cov6["lateLooks"])
    ck(S.coverage(pg3, looks=1)["lateLooks"] == cov6["lateLooks"][:1],
       "looks is a bound a caller can set, and looks=1 is exactly the old behaviour")
    # ADR-144: a control that mounts AFTER the last stamp has no data-audit at
    # all, and came back from UNSTAMPED_JS as null -- counted as a control no
    # state exposed and named "None", which is what audit_targets' never-exposed
    # fault turned out to be. Stamping immediately before enumerating closes the
    # gap; anything still unstamped is reported as what it is.
    # The control has to arrive DURING the enumeration, which is a window of
    # microseconds -- so, as with the late-look fixture, the measurement itself
    # is the trigger: an existing control's getBoundingClientRect appends a new
    # button the second time coverage() asks about it, which is inside the last
    # look's stamping pass and therefore after the snapshot that pass took.
    LATE3 = ("() => { const b = document.getElementById('b1'); let n = 0; "
             "const real = b.getBoundingClientRect.bind(b); "
             "b.getBoundingClientRect = () => { n++; "
             "  if (n === 2 && !document.getElementById('fresh')) { "
             "    const e = document.createElement('button'); e.id = 'fresh'; "
             "    e.textContent = 'fresh'; document.body.appendChild(e); } "
             "  return real(); }; return true; }")
    pg3.evaluate(LATE3)
    cov7 = S.coverage(pg3)
    ck(cov7.get("unstamped") == 0
       and not any(m is None or str(m) == "None" for m in cov7["never"]),
       "a control that arrived DURING the enumeration is stamped and measured, not counted as a "
       "control no state exposed and named by an id that does not exist -- which is what "
       "audit_targets' never-exposed fault turned out to be: unstamped=%s never=%s"
       % (cov7.get("unstamped"), cov7["never"]))
    ck(not any("#fresh" in str(m) for m in cov7["never"]),
       "...and it counts as exposed, because by the time anything asks it has a box: %s"
       % cov7["never"])
    pg3.close()
    pg2.close()

    # ADR-145: an unnamed control's index is counted WITHIN ITS HOST. Adding a
    # row above it renumbered it before, so a control measured before the row
    # existed was a different control after -- the collection sheet's stand-age
    # dial read as never-entered by a task that had just clicked it.
    grew = pg.evaluate("""() => {
      const before = document.querySelector('#p2 #rows');
      const b = document.createElement('button'); b.textContent = 'x';
      document.body.insertBefore(b, document.body.firstChild);
      return true; }""")
    pg.evaluate(S.MARK_JS, S.CONTROLS)
    after_growth = pg.evaluate("() => [...document.querySelectorAll('.rowDrop')].map(e => e.getAttribute('data-audit'))")
    ck(after_growth == ["button.rowDrop[submit]@rows|1"],
       "and a control with no id keeps its stamp when the page GROWS somewhere else: its index is "
       "counted inside its own host, not across the document: %s" % after_growth)
    # ...and the other half of that rule: a control WITH an id is keyed by the id
    # ALONE. Scoping a named control to its host too would re-key it the moment
    # the page moved it -- which is the very failure the host scoping exists to
    # prevent -- and an id is already unique document-wide, so the host adds
    # nothing but a way to lose the measurement.
    named_before = pg.evaluate("() => document.getElementById('typed').getAttribute('data-audit')")
    pg.evaluate("""() => { document.getElementById('rows').appendChild(document.getElementById('typed')); return true; }""")
    pg.evaluate(S.MARK_JS, S.CONTROLS)
    named_moved = pg.evaluate("() => document.getElementById('typed').getAttribute('data-audit')")
    pg.evaluate("""() => { document.getElementById('p2').appendChild(document.getElementById('typed')); return true; }""")
    pg.evaluate(S.MARK_JS, S.CONTROLS)
    ck("@" not in named_before and named_before == "input#typed[text]|1",
       "a control with an id is keyed by the id alone -- no host in the stamp, because an id is "
       "already unique document-wide: %s" % named_before)
    ck(named_moved == named_before,
       "...so MOVING it into a different identified ancestor keeps its stamp and every measurement "
       "taken under it: %s then %s" % (named_before, named_moved))

    stamps = pg.evaluate("() => [...document.querySelectorAll('[data-audit]')].map(e => e.getAttribute('data-audit'))")
    ck(len(stamps) == 16 and len(set(stamps)) == 16,
       "every control carries one stable stamp, the ones the entry built and the one this check "
       "grew included: %d stamps, %d distinct"
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
    ck(rebuilt == [None] and again == ["button.rowDrop[submit]@rows|1"],
       "a region rebuilt with innerHTML comes back under the SAME stamp -- a counter would have forgotten every "
       "state that measured it: %s then %s" % (rebuilt, again))

    # ---- C. the click is programmatic ---------------------------------------
    inv = pg.evaluate(AF.PROBE)["invisible"]
    ck(inv == [], "after the walk the focus audit's own probe sees a ring on every control: the states were pressed "
                  "by JS, not by a pointer (a pointer click hides rings on programmatic focus): %s" % inv)
    # A CONTROL THE ENTRY LEFT FOCUSED (ADR-148). The lab's chip adder returns
    # focus to its count box after Add, and that one control then read as "no
    # visible focus" on a page whose ring is fine -- because the probe's
    # "unfocused" reading was taken while it was focused. Nothing else on the
    # page was wrong; the instrument could not ask the question.
    # Focused and probed IN THE SAME EVALUATE. Across two calls the headless
    # page can lose the focus between them, and the check would then be asking
    # nothing while looking like it asked.
    # THE FIRST focusable control in document order, and visible. The probe walks
    # the page focusing and blurring as it goes, so every control except the
    # first is blurred by the time the loop reaches it -- only the first can
    # still be focused when its resting state is read, which is exactly the case
    # the lab hit and the only one a fixture can pose.
    FIRST = ("const e = [...document.querySelectorAll("
             "  'a[href],button,input,select,textarea')].find(x => {"
             "  const b = x.getBoundingClientRect();"
             "  return (b.width > 0 || b.height > 0) && !x.disabled; });")
    focused = pg.evaluate("(src) => { " + FIRST +
                          " if (!e) return null; e.id = e.id || 'left-focused'; e.focus();"
                          " return document.activeElement === e ? e.id : null; }", "")
    ck(focused, "the fixture really does leave a VISIBLE control focused, so the next check is "
                "asking something: %r" % focused)
    inv2 = pg.evaluate(
        "(src) => { const probe = eval('(' + src + ')'); " + FIRST +
        "  e.focus();"
        "  if (document.activeElement !== e) return [['NOT FOCUSED', 1]];"
        "  return probe().invisible; }", AF.PROBE)
    ck(inv2 == [],
       "a control the ENTRY LEFT FOCUSED is still measured: a probe that reads its unfocused "
       "state while it is focused finds no difference and reports a ring that is there: %s" % inv2)
    still = pg.evaluate("() => (document.activeElement || {}).id || ''")
    ck(still == focused,
       "...and the probe puts focus back where the page had it, because the audits run one after "
       "another on the same tab and a probe that leaves focus moved changes what the next one "
       "measures: %r" % still)
    pg.evaluate("() => document.activeElement && document.activeElement.blur()")
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
