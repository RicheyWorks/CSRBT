# -*- coding: utf-8 -*-
"""Every state of a page, for the audits (ADR-130).

The kit's audits measured each page AS LOADED: whatever had a bounding box
after domcontentloaded. Half of every instrument's surface sits behind a
closed tab, an unopened <details>, a "compare" toggle or a season that has
not started, and an element with no box was skipped -- so the 44 px rule,
the contrast rule and the focus rule had never been applied to most of the
controls a reader actually uses. The experiment guide's import card
spilling 30 px sideways on a phone (ADR-128) had been invisible to every
audit for that reason: the guide's tabs name their pane by aria-controls,
and nothing ever opened one.

This module walks a page through its STATES so an audit can measure each:

  rest        the page as loaded, every <details> opened
  pane:<id>   each tab -- .tab[data-pane], or any [aria-controls] button --
              pressed, in document order
  state:<id>  each page-specific button that reveals a surface no tab does
              (a season started, a comparison opened, a height card toggled)

  entered     the page after its science task's own entry steps have been
              replayed -- a row built, a species picked, a season filed -- and
              then each tab again (entered/pane:<id>). Half of an instrument's
              report does not exist until something has been entered: the
              greenhouse's runOut table, the sheet's analysis with figures in
              it, the season's recap. Auditing the empty page measures the
              form and never the report (ADR-131).

and keeps the ACCOUNTING that makes "audited everywhere" a claim rather
than a hope: the set of controls that had a box in at least one state,
against the set that exist. A control no state ever exposed is reported by
name; the audits count it as a fault, because "I never measured it" must
not print as "it is fine".

    import audit_states as S
    for state, result in S.each_state(pg, name, lambda: pg.evaluate(PROBE)):
        ...
    cov = S.coverage(pg)          # after the loop: {"exist", "exposed", "never": [...]}
"""

import io, json, os, re, sys

# Buttons that reveal a surface no tab reaches. A CSS selector each; pressed
# in order, cumulatively (the season's report needs the season started).
# An entry is a CSS selector to press, or ("select", css, value) to choose an
# option that reveals a dependent field (the guide's hot-set inputs exist
# only for a hot phase).
STATE_BUTTONS = {
    "field-season.html": ["#startBtn", "#aMark", "#aRecap", "#fileBtn", "#gradeBtn"],
    "tree-visualizer.html": ["#cmpBtn"],
    "experiment-guide.html": [("select", "#p-kind", "hot"), ("select", "#p-kind", "churn"),
                              ("select", "#x-metric", "q-survivorship"), "#track-eng"],
    "stand-sheet.html": ["#htToggle", "#packToggle"],
    "releve.html": ["#packToggle"],
    "pheno-tracker.html": ["#plantGrid button"],
}

# What counts as a control for the accounting: what the audits look at. A
# file input is not: it is display:none behind its label by design (the
# label is the target), and the OS chooser is what a finger hits.
CONTROLS = "button, input:not([type=hidden]):not([type=file]), select, textarea, [role=button], .tab"

TABS_JS = r"""
() => {
  const out = [];
  document.querySelectorAll(".tab[data-pane]").forEach((t, i) => out.push({sel: ".tab[data-pane]", i, id: t.getAttribute("data-pane")}));
  document.querySelectorAll("[aria-controls]").forEach((t, i) => {
    if (t.matches(".tab[data-pane]")) return;
    out.push({sel: "[aria-controls]", i, id: t.getAttribute("aria-controls")});
  });
  return out;
}
"""

OPEN_DETAILS_JS = r"""() => { let n = 0; document.querySelectorAll("details:not([open])").forEach(d => { d.open = true; n++; }); return n; }"""

MARK_JS = r"""
(css) => {
  // Stamp every control with a STABLE identity and remember which ones have a
  // box in this state.
  //
  // The identity cannot be a counter. A per-pass index (a0, a1, ...) hands a
  // control the entry built part-way down the document a number an earlier
  // element already carries -- two controls under one stamp, and the second
  // silently stops being measured. A monotonic counter fixes that and breaks
  // something worse: these pages rebuild whole regions with innerHTML, so the
  // SAME control comes back as a new element, takes a new number, and every
  // state that measured it is forgotten. pheno-tracker went from 106/106
  // measured to 27/106 on that alone.
  //
  // So the stamp is what the element IS -- tag, id, classes, input type -- plus
  // its occurrence among identical siblings. A region rebuilt from the same
  // template keeps its stamps; a control that did not exist before gets a new
  // one. Deliberately not the label: a value that changes as data is entered
  // would re-key a control that never moved -- and for the same reason the
  // kit's STATE classes are stripped. A chip that gains "on" when you pick it
  // is the same chip; keying on the class it wears while selected loses every
  // measurement taken before the click.
  const STATE = /^(on|open|active|sel|selected|current|good|bad|warn|hot|cold|found|absent)$/;
  const seen = {}, exposed = [];
  document.querySelectorAll(css).forEach(e => {
    const cls = (e.getAttribute("class") || "").trim().split(/\s+/)
                 .filter(c => c && !STATE.test(c)).sort().join(".");
    const key = e.tagName.toLowerCase() + (e.id ? "#" + e.id : "") + (cls ? "." + cls : "")
              + (e.type ? "[" + e.type + "]" : "");
    const n = seen[key] = (seen[key] || 0) + 1;
    e.setAttribute("data-audit", key + "|" + n);
    const b = e.getBoundingClientRect();
    if (b.width > 0 || b.height > 0) exposed.push(e.getAttribute("data-audit"));
  });
  return exposed;
}
"""

NAME_JS = r"""
(ids) => ids.map(id => {
  const e = document.querySelector('[data-audit="' + id + '"]');
  if (!e) return id;
  const label = (e.getAttribute("aria-label") || e.id || e.textContent || e.placeholder || "").replace(/\s+/g, " ").trim().slice(0, 30);
  return e.tagName.toLowerCase() + (e.id ? "#" + e.id : "") + (e.className ? "." + String(e.className).split(/\s+/)[0] : "") + (label ? "(" + label + ")" : "");
})
"""


SETTLE_JS = r"""
() => {
  // still animating? a pane that fades in is mid-transform when the click
  // returns, and a child's border box is then a sub-pixel short of what the
  // stylesheet says: pheno-tracker's 44 px keys measured 43.99997 under a
  // pane sliding 0.17 px, and the 44 px rule reported three faults that were
  // the transition's. Ask the browser whether anything is still running.
  try { return document.getAnimations().some(a => a.playState === "running"); }
  catch (e) { return false; }
}
"""


def _settle(pg, tries=40):
    """Wait until nothing on the page is still animating (bounded, 2s).

    Two seconds, not one: under the kit's own parallel run a second browser is
    competing for the CPU and a 300 ms transition can take past a second to
    finish. audit_focus reported one fault under -j 2 that it did not report
    alone, which is the instrument's flakiness and not the page's -- and an
    audit whose answer depends on what else is running is not an audit.
    """
    for _ in range(tries):
        try:
            if not pg.evaluate(SETTLE_JS):
                return
        except Exception:
            return
        pg.wait_for_timeout(50)
    _frames(pg)


FRAMES_JS = r"""
() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(true))))
"""


def _frames(pg):
    """Two animation frames, and then measure.

    Settling on document.getAnimations() answers "is anything still moving?"
    and cannot answer "has the browser laid this state out yet?". A page that
    reveals a control from its own requestAnimationFrame -- or simply a browser
    competing for the CPU with the other half of `run_all -j 2` -- has run the
    click handler and not yet produced a frame, and a control measured then has
    no box. That is how audit_focus and audit_contrast each reported exactly one
    "never exposed" fault under the parallel run and none of it alone, twice.
    Waiting for two frames is the browser's own answer to the question: the
    first schedules, the second is delivered only after the first has been
    painted."""
    try:
        pg.evaluate(FRAMES_JS)
    except Exception:
        pass


def _click(pg, sel, i=0):
    """A programmatic click, not a pointer: after a real mouse click the
    browser's :focus-visible heuristic hides focus rings on programmatic
    focus, and the focus audit then reported 1,461 'no visible focus'
    faults that were the mouse's, not the pages'."""
    els = pg.query_selector_all(sel)
    if i >= len(els):
        return False
    try:
        pg.evaluate("(el) => el.click()", els[i])
        pg.wait_for_timeout(150)
        _settle(pg)
        return True
    except Exception:
        return False


REVEAL_JS = r"""
(css) => {
  // press the tab that owns the element's pane, so a dependent field that
  // appears has a box to measure
  const e = document.querySelector(css); if (!e) return false;
  let n = e.parentElement;
  while (n) {
    if (n.id) {
      const tab = document.querySelector('.tab[data-pane="' + n.id + '"], [aria-controls="' + n.id + '"]');
      if (tab) { tab.click(); return n.id; }
    }
    n = n.parentElement;
  }
  return false;
}
"""


def _reveal(pg, css):
    try:
        r = pg.evaluate(REVEAL_JS, css)
        if r:
            pg.wait_for_timeout(120)
    except Exception:
        pass


def each_state(pg, name, probe, entered=True):
    """Yield (state, probe()) for every state of the page. Keeps the exposure
    accounting on the page itself (data-audit stamps) for coverage().

    entered=False leaves the page's own data out of it -- for a caller that has
    already entered, or one measuring the empty form on purpose."""
    # one page object walks the whole kit, so last page's entry must not be
    # read as this one's: a reference page with no task was printing the
    # previous page's task id on its row
    pg._audit_entered = None
    pg.evaluate(OPEN_DETAILS_JS)
    pg.wait_for_timeout(100)
    _settle(pg)
    exposed = set(pg.evaluate(MARK_JS, CONTROLS))
    pg._audit_exposed = exposed
    yield "rest", probe()
    for t in pg.evaluate(TABS_JS):
        if _click(pg, t["sel"], t["i"]):
            pg.evaluate(OPEN_DETAILS_JS)
            exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
            yield "pane:%s" % t["id"], probe()
    for sel in states_of(name):
        if isinstance(sel, tuple):
            _, css, value = sel
            _reveal(pg, css)
            try:
                pg.select_option(css, value, timeout=3000)
                pg.wait_for_timeout(150)
                _settle(pg)
            except Exception:
                continue
            exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
            yield "state:%s=%s" % (css.lstrip("#"), value), probe()
            continue
        _reveal(pg, sel)
        if _click(pg, sel):
            pg.evaluate(OPEN_DETAILS_JS)
            exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
            yield "state:%s" % sel.lstrip("#"), probe()
            # a revealed surface may carry its own tabs
            for t in pg.evaluate(TABS_JS):
                if _click(pg, t["sel"], t["i"]):
                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
                    yield "state:%s/pane:%s" % (sel.lstrip("#"), t["id"]), probe()
    # ADR-131: and the page with its own data in it
    if entered:
        ent = enter(pg, name)
        if ent:
            pg._audit_entered = ent
            pg.evaluate(OPEN_DETAILS_JS)
            _settle(pg)
            exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
            yield "entered", probe()
            for t in pg.evaluate(TABS_JS):
                if _click(pg, t["sel"], t["i"]):
                    pg.evaluate(OPEN_DETAILS_JS)
                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
                    yield "entered/pane:%s" % t["id"], probe()
            # and the page's own reveals again: a reveal pressed BEFORE the
            # entry can be undone by it. The experiment guide's engineering
            # track is opened by #track-eng and closed again when the designer
            # re-renders, so the six measurement inputs the entry builds inside
            # it had a box in no state at all -- reported, correctly, as never
            # measured, by an audit that had simply not looked again.
            for sel in states_of(name):
                if isinstance(sel, tuple):
                    _, css, value = sel
                    _reveal(pg, css)
                    try:
                        pg.select_option(css, value, timeout=3000)
                        pg.wait_for_timeout(150)
                        _settle(pg)
                    except Exception:
                        continue
                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
                    yield "entered/state:%s=%s" % (css.lstrip("#"), value), probe()
                    continue
                _reveal(pg, sel)
                if _click(pg, sel):
                    pg.evaluate(OPEN_DETAILS_JS)
                    exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
                    yield "entered/state:%s" % sel.lstrip("#"), probe()
    # THE PAGE MAY STILL BE BUILDING (ADR-136).
    #
    # Every state stamps before it probes, and coverage() counts after the walk
    # -- so a control the page mounts AFTER the last stamp (a region rendered on
    # a timer, a chart that builds its own buttons) carries no stamp at all, and
    # coverage reports it, correctly by its own rule and falsely in fact, as a
    # control no state exposed. deployment-log produced exactly that fault on
    # one run and not the next two: a phantom, and the worst kind, because it
    # names nothing (the stamp it would be named by is the stamp it never got).
    # So the walk settles once more at the end and, if the page did grow a
    # control since the last stamp, MEASURES it in a final state rather than
    # counting it as never measured.
    _settle(pg)
    if None in pg.evaluate(UNSTAMPED_JS, CONTROLS):
        pg.evaluate(OPEN_DETAILS_JS)
        exposed |= set(pg.evaluate(MARK_JS, CONTROLS))
        yield "settled", probe()


UNSTAMPED_JS = "(css) => [...document.querySelectorAll(css)].map(e => e.getAttribute('data-audit'))"


def coverage(pg, looks=3):
    """After each_state: how many controls exist, how many had a box in some
    state, and the names of those no state exposed.

    ONE LAST LOOK, AND WHY (ADR-140). Every state stamps and measures exposure
    at the moment it probes. Under load a probe can run before the browser has
    finished laying the state out, so a control that DOES have a box a moment
    later is recorded as having had none -- and, if that was the last state to
    show it, coverage reports it as a control no state exposed. audit_focus
    produced exactly that fault under `run_all -j 2` and produced none of it in
    three solo runs, twice now (ADR-134 widened _settle for the same reason).
    The end of the walk is still the last state, so settling once more and
    measuring exposure again is not a new state and not a second chance: it is
    finishing the measurement that state's probe began.

    ONE LOOK WAS NOT ENOUGH EITHER (ADR-143). audit_targets still lost exactly
    one control to "never exposed" in one of six full runs after ADR-140, and
    passed every solo run -- the same shape, one layer down: the single extra
    look is itself a probe, and under contention a probe can be early. So the
    look REPEATS, up to `looks` times, and stops as soon as a look finds nothing
    the previous ones had not. That is bounded (three settles at worst, and the
    second one usually ends it), it cannot invent exposure -- every id still has
    to have a box when it is measured -- and it makes the race visible instead
    of silent: `lateLooks` says how many controls each look was the first to
    see, so a run that needed the third look SAYS it needed the third look."""
    late, gained = set(), []
    for i in range(max(1, int(looks))):
        _settle(pg)
        seen = set(pg.evaluate(MARK_JS, CONTROLS))
        new = seen - late
        late |= seen
        gained.append(len(new))
        if i and not new:
            break
    if hasattr(pg, "_audit_exposed"):
        pg._audit_exposed |= late
    exposed = getattr(pg, "_audit_exposed", late)
    all_ids = pg.evaluate(UNSTAMPED_JS, CONTROLS)
    never = [i for i in all_ids if i not in exposed]
    return {"exist": len(all_ids), "exposed": len(all_ids) - len(never),
            "never": pg.evaluate(NAME_JS, never),
            # how many controls each look was the first to see. [n, 0] is a
            # settled page; anything after the first zero means a look that
            # found something a previous look had missed, which is contention
            # reported rather than absorbed.
            "lateLooks": gained}


# ---- the entered state (ADR-131) -----------------------------------------
#
# The entry is the page's OWN science task, replayed in the audit's browser --
# not a second script that would drift from it. The task runner drives the page
# through the gateway with its own child process and its own browser; here the
# same steps go straight to the page plugin, in process, on the page the audit
# already has open. The task file is the single source of what "entered" means
# for a page, so a task that grows a field grows the audited state with it.
#
# What is replayed and what is not: the entry actions only. A read (read-report,
# read-page) changes nothing and costs a round of JSON; a task's expectations are
# the task runner's business and are ignored here -- an audit does not grade the
# page, it measures it. A step that refuses is not fatal either: the audit wants
# the state the page reached, and reports how far the entry got.
ENTRY_SKIP = ("read-report", "read-page", "observe", "open", "reload")
TASKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")


def task_for(name, tasks_dir=None):
    """The science task whose page this is, or None.

    A reference task is not one: its steps are all reads, and replaying it would
    change nothing. Nor is a CANARY -- a task written to be refuted (must: FAIL)
    enters what the page should reject, and the collection sheet's canary was
    the first thing this picked up. The science task wins; anything else with
    entry steps is the fallback."""
    # resolved at call time, not bound as a default: a suite that points this
    # at its own fixture directory sets TASKS_DIR, and a default argument
    # captured at import would have ignored it
    tasks_dir = tasks_dir or TASKS_DIR
    if not os.path.isdir(tasks_dir):
        return None
    hits = []
    for f in sorted(os.listdir(tasks_dir)):
        if not f.endswith(".json"):
            continue
        try:
            t = json.load(io.open(os.path.join(tasks_dir, f), encoding="utf-8"))
        except ValueError:
            continue
        if t.get("target") != "page" or t.get("page") != name:
            continue
        if t.get("must", "PASS") != "PASS":
            continue
        if any(s.get("action") not in ENTRY_SKIP for s in t.get("steps") or []):
            hits.append(t)
    if not hits:
        return None
    return next((t for t in hits if str(t.get("id", "")).endswith("-science")), hits[0])


def enter(pg, name, task=None, tasks_dir=None):
    """Replay the page's task entry steps on this page. Returns
    {"task", "driven", "refused", "steps"} or None when the page has no task.

    Never raises: a page whose entry cannot be replayed is a page audited at
    rest, reported as such -- an audit that dies because a task moved is worse
    than one that says how far it got."""
    task = task or task_for(name, tasks_dir)
    if not task:
        return None
    tools = os.path.dirname(os.path.abspath(__file__))
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        import harness_plugin_page as PP
        import harness_tasks as HT
        try:
            from swarm import SWARM_KINDS
        except Exception:
            SWARM_KINDS = None
        plug = PP.PagePlugin(pg, name, kinds=SWARM_KINDS)
    except Exception as exc:
        return {"task": task["id"], "driven": 0, "refused": 0, "steps": 0,
                "error": "the page plugin would not load: %s" % exc}
    done, driven, refused, ran = {}, 0, 0, 0
    # the snapshot @control: names are resolved against -- the same one the task
    # runner's first "observe" step gets
    done["_snap"] = {"ok": True, "snapshot": plug.observe(sensitive=True), "output": {}}
    for st in task.get("steps") or []:
        action = st.get("action")
        if action in ENTRY_SKIP:
            continue
        ran += 1
        try:
            args = HT.resolve(st.get("arguments") or {}, done, "audit/%s" % name)
            ok, msg, out = plug.execute(action, args)
        except Exception as exc:
            refused += 1
            done[st["id"]] = {"ok": False, "snapshot": {}, "output": {}, "message": str(exc)[:120]}
            continue
        driven += 1 if ok else 0
        refused += 0 if ok else 1
        done[st["id"]] = {"ok": bool(ok), "output": out or {}, "message": msg,
                          "snapshot": plug.observe(sensitive=True)}
    # THE POINTER, AGAIN (ADR-130's lesson, one layer up).
    #
    # audit_states presses its own states with el.click() precisely so the
    # browser's :focus-visible heuristic stays in its keyboard mood. The ENTRY
    # does not get that choice: it goes through the page plugin, which types and
    # clicks the way a finger does, because that is the point of it. So the
    # heuristic flips, and the focus audit run afterwards reported 1,384 "no
    # visible focus" faults that were the entry's pointer, not the pages'.
    # One keypress puts the browser back in the mood a keyboard user is in --
    # which is the only mood in which "is focus visible" is a real question.
    try:
        pg.keyboard.press("Tab")
        pg.wait_for_timeout(60)
    except Exception:
        pass
    return {"task": task["id"], "driven": driven, "refused": refused, "steps": ran}


def entry_fault(ent):
    """Why the entered state was not reached, or None.

    Not every refusal is a fault: a science task drives refusal paths on purpose
    (the guide refusing a JPEG, a key with no match), and an audit that called
    those faults would be reading the task's intent wrong. What IS a fault is an
    entry that never happened -- the plugin would not load, or every step was
    refused -- because the states after it were then the empty page's wearing
    the label "entered"."""
    if not ent:
        return None
    if ent.get("error"):
        return "the entry could not run: %s" % ent["error"]
    if ent.get("steps") and not ent.get("driven"):
        return "the entry drove nothing: %d step(s), all refused" % ent["steps"]
    return None


def states_of(name):
    """The reveals for a page: the table above, plus -- for a fixture page a
    suite wrote into a temporary docs directory -- whatever CSRBT_AUDIT_STATES
    declares as JSON ({"fixture.html": ["#more", ["select", "#kind", "hot"]]}).
    Nothing but verify_audit_states sets it."""
    extra = {}
    raw = os.environ.get("CSRBT_AUDIT_STATES")
    if raw:
        try:
            extra = json.loads(raw)
        except ValueError:
            extra = {}
    out = list(STATE_BUTTONS.get(name, []))
    for e in extra.get(name, []):
        out.append(tuple(e) if isinstance(e, list) else e)
    return out
