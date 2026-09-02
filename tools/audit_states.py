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

import json, os

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
  // stamp every control with a stable id for the accounting, remember which
  // ones have a box in this state
  let n = 0, exposed = [];
  document.querySelectorAll(css).forEach(e => {
    if (!e.hasAttribute("data-audit")) e.setAttribute("data-audit", "a" + (n));
    n++;
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


def each_state(pg, name, probe):
    """Yield (state, probe()) for every state of the page. Keeps the exposure
    accounting on the page itself (data-audit stamps) for coverage()."""
    pg.evaluate(OPEN_DETAILS_JS)
    pg.wait_for_timeout(100)
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


def coverage(pg):
    """After each_state: how many controls exist, how many had a box in some
    state, and the names of those no state exposed."""
    exposed = getattr(pg, "_audit_exposed", set())
    all_ids = pg.evaluate("(css) => [...document.querySelectorAll(css)].map(e => e.getAttribute('data-audit'))", CONTROLS)
    never = [i for i in all_ids if i not in exposed]
    return {"exist": len(all_ids), "exposed": len(all_ids) - len(never),
            "never": pg.evaluate(NAME_JS, never)}


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
