# -*- coding: utf-8 -*-
"""Kit-wide keyboard and focus audit.

The touch-target audit covers the finger. This covers the hand that never
leaves the keyboard, and the screen reader that announces whatever it lands on.
Four faults, in the order they hurt:

  INVISIBLE  a control takes focus but nothing on screen changes, so a keyboard
             user cannot tell where they are. Almost always `outline:none` with
             no replacement.
  UNREACHABLE a control responds to a click but cannot be tabbed to at all.
             Custom controls built from div/span, or tabindex="-1" on something
             the user is meant to operate.
  UNNAMED    a control takes focus but has no accessible name, so it is
             announced as "button" and nothing else.
  TABINDEX   a positive tabindex. It yanks the element out of document order and
             breaks the tab sequence for every other control on the page.

Run:  python3 tools/audit_focus.py
Exits non-zero if any fault is found, so it fails a build.
"""
import glob, os, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_states as S

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
DOCS = os.path.normpath(DOCS) + os.sep
DOCS = (os.environ.get("CSRBT_DOCS_DIR") or DOCS).rstrip(os.sep) + os.sep   # verify_audit_states's fixture hook

PROBE = r"""
() => {
  const out = {invisible:[], unreachable:[], unnamed:[], tabindex:[]};
  const key = e => {
    const c = e.getAttribute('class');
    return e.tagName.toLowerCase() + (c ? '.' + String(c).trim().split(/\s+/)[0] : '');
  };
  const visible = e => {
    const b = e.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) return false;
    const s = getComputedStyle(e);
    return s.visibility !== 'hidden' && s.display !== 'none';
  };
  const name = e => {
    const al = e.getAttribute('aria-label');
    if (al && al.trim()) return true;
    if (e.getAttribute('aria-labelledby')) return true;
    if (e.title && e.title.trim()) return true;
    if ((e.textContent || '').trim()) return true;
    if (e.tagName === 'INPUT' || e.tagName === 'SELECT' || e.tagName === 'TEXTAREA') {
      if (e.id && document.querySelector('label[for="' + CSS.escape(e.id) + '"]')) return true;
      if (e.closest('label')) return true;
      if (e.placeholder && e.placeholder.trim()) return true;
      if (e.type === 'submit' || e.type === 'button') return !!(e.value || '').trim();
    }
    if (e.querySelector('svg title, img[alt]')) return true;
    return false;
  };
  const bump = (bucket, e) => {
    const k = key(e);
    const hit = bucket.find(x => x[0] === k);
    if (hit) hit[1]++; else bucket.push([k, 1]);
  };

  // ---- positive tabindex ----
  document.querySelectorAll('[tabindex]').forEach(e => {
    if (parseInt(e.getAttribute('tabindex'), 10) > 0) bump(out.tabindex, e);
  });

  // ---- unreachable: acts clickable, cannot be tabbed to ----
  document.querySelectorAll('[role=button],[onclick],[role=tab],[role=link]').forEach(e => {
    if (!visible(e)) return;
    const nat = /^(BUTTON|A|INPUT|SELECT|TEXTAREA)$/.test(e.tagName) &&
                !(e.tagName === 'A' && !e.hasAttribute('href'));
    const ti = e.getAttribute('tabindex');
    if (nat && ti === null) return;
    if (ti !== null && parseInt(ti, 10) >= 0) return;
    bump(out.unreachable, e);
  });

  // ---- focusable controls: name + visible focus ----
  const sel = 'a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])';
  const snap = e => {
    const s = getComputedStyle(e);
    return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.outlineOffset,
            s.boxShadow, s.backgroundColor, s.borderColor, s.borderWidth,
            s.color, s.filter, s.textDecorationLine].join('|');
  };
  document.querySelectorAll(sel).forEach(e => {
    if (!visible(e)) return;
    if (e.disabled) return;
    if (!name(e)) bump(out.unnamed, e);
    const before = snap(e);
    try { e.focus({preventScroll:true}); } catch (_) { return; }
    if (document.activeElement !== e) return;
    const after = snap(e);
    e.blur();
    if (before === after) bump(out.invisible, e);
  });
  return out;
}
"""

FAULTS = [("invisible", "no visible focus"),
          ("unreachable", "not keyboard reachable"),
          ("unnamed", "no accessible name"),
          ("tabindex", "positive tabindex"),
          ("never", "never exposed, so never measured"),
          ("entry_not_reached", "the entered state was never reached")]


def main():
    pages = sorted(glob.glob(DOCS + "*.html"))
    if not pages:
        print("no pages found under", DOCS); return 1
    totals = {k: 0 for k, _ in FAULTS}
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 900})
        pg.set_default_timeout(20000)
        pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
        pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
        for path in pages:
            nm = os.path.basename(path)
            try:
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(600)
                # ADR-130: every state of the page, findings merged by selector
                res, nstates = {}, 0
                # THE BROWSER'S MOOD IS THIS AUDIT'S PRECONDITION (ADR-131).
                #
                # Chromium decides whether to paint a focus ring on
                # programmatic focus from how the page was last interacted
                # with: after a pointer, it does not. audit_states presses its
                # states with el.click() to stay in the keyboard mood, but the
                # ENTERED state is reached by driving the page the way a finger
                # does -- that is what entering data means -- and the mood flips.
                # Rather than depend on what the last caller did, this audit
                # asserts its own precondition: one keypress before every probe,
                # so "is focus visible" is always asked of a keyboard user.
                def probe():
                    try:
                        pg.keyboard.press("Tab")
                        pg.wait_for_timeout(40)
                        # ...and then let go of it. The probe reads each
                        # control's style BEFORE focusing it and again after; an
                        # element the keypress left focused shows no change and
                        # would be reported as having no ring -- the mood is
                        # what this press is for, not the focus.
                        pg.evaluate("() => { const a = document.activeElement; if (a && a.blur) a.blur(); }")
                    except Exception:
                        pass
                    return pg.evaluate(PROBE)

                for state, r in S.each_state(pg, nm, probe):
                    nstates += 1
                    for k in r:
                        have = dict(res.get(k, []))
                        for sel, c in r[k]:
                            have[sel] = max(have.get(sel, 0), c)
                        res[k] = sorted(have.items())
                res["states"] = nstates
                # ADR-130: a control no state exposed had its focus checked in
                # no state; that is a fault of the audit's reach, counted here
                # so it cannot print as a pass
                cov = S.coverage(pg)
                # ADR-143: a look that found what an earlier look had missed is
                # contention, and it is printed rather than absorbed.
                if sum((cov.get("lateLooks") or [])[1:]):
                    print("%-30s LATE  %d control(s) only a later look saw"
                          % (name, sum(cov["lateLooks"][1:])))
                res["never"] = [(nm_, 1) for nm_ in cov["never"]]
                res["coverage"] = cov
                res["entry"] = getattr(pg, "_audit_entered", None)
                ef = S.entry_fault(res["entry"])
                res["entry_not_reached"] = [(ef, 1)] if ef else []
            except Exception as exc:
                rows.append((nm, None, str(exc)[:70])); continue
            n = 0
            for k, _ in FAULTS:
                c = sum(x[1] for x in res.get(k, []))
                totals[k] += c
                n += c
            rows.append((nm, n, res))
        b.close()

    print("%-30s %s" % ("PAGE", "FAULTS"))
    print("-" * 74)
    for nm, n, res in rows:
        if n is None:
            print("%-30s LOAD FAIL  %s" % (nm, res)); continue
        if n == 0:
            cov = res.get("coverage", {})
            ent = res.get("entry")
            print("%-30s ok   %d states, %d/%d controls measured%s"
                  % (nm, res.get("states", 1), cov.get("exposed", 0), cov.get("exist", 0),
                     "" if not ent else "   entry %s %d/%d driven" % (ent["task"], ent["driven"], ent["steps"]))); continue
        print("%-30s %d" % (nm, n))
        for k, label in FAULTS:
            for sel, c in res.get(k, []):
                print("%-30s     %-22s %s x%d" % ("", label, sel, c))
    print("-" * 74)
    # the same, and for the same reason (ADR-144)
    for nm, n, res in rows:
        if not isinstance(res, dict):
            continue
        for nme in ((res.get("coverage") or {}).get("never") or []):
            print("%-26s %-30s %s" % ("never exposed:", nm, nme))
    grand = sum(totals.values())
    for k, label in FAULTS:
        print("%-24s %d" % (label + ":", totals[k]))
    print("%-24s %d" % ("total:", grand))
    return grand


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
