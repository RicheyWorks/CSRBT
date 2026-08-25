# -*- coding: utf-8 -*-
"""Does anything you type come back as markup?

Several pages in this kit build list rows, labels and exports by concatenating
HTML strings around values the user typed -- a species name, a site, a note.
Seventeen pages carry an esc() helper for exactly that, in nine slightly
different versions, and the question this answers is not whether the helper
exists but whether it is reached on every path.

Grep cannot answer that: it finds the concatenations, not the ones that run.
So this types a probe into every text field, commits it the way a user would,
and then asks the DOM a question with only one right answer.

The probe carries two attacks in one string:

    <x-probe>p</x-probe>" data-x-probe="1

  ELEMENT    an <x-probe> element exists afterwards -> the value was interpolated
             into markup unescaped. `x-probe` is a custom element name that
             cannot appear any other way, so a hit is never a coincidence.
  ATTRIBUTE  any element carries data-x-probe -> the value broke out of an
             attribute. Escaping < and > but not " leaves this open, and four of
             the nine esc() variants in this kit do exactly that.

A page that is doing it right shows the probe back as visible text, quotes and
angle brackets and all, and neither node ever exists.

Run:  python3 tools/audit_escaping.py
Exits non-zero on any hit.
"""
import glob, os, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs") + os.sep
PROBE = '<x-probe>p</x-probe>" data-x-probe="1'

FILL = """
(probe) => {
  const out = [];
  const sel = 'input[type=text],input:not([type]),textarea,input[type=search]';
  document.querySelectorAll(sel).forEach(e => {
    if (e.disabled || e.readOnly) return;
    const b = e.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) return;
    e.value = probe;
    e.dispatchEvent(new Event('input', {bubbles:true}));
    e.dispatchEvent(new Event('change', {bubbles:true}));
    out.push(e.id || e.className || e.tagName);
  });
  // Most "add" buttons refuse an incomplete row, so a text-only probe never gets
  // committed and the page reads as clean without ever having been tested.
  // Give every number on the form something valid to be.
  document.querySelectorAll('.fek-step .val, input[type=number]').forEach(e => {
    if (e.disabled || e.readOnly) return;
    if (e.value !== '') return;                       // leave what the page chose
    const lo = parseFloat(e.min), hi = parseFloat(e.max);
    let v = 1;
    if (!isNaN(lo) && lo > v) v = lo;
    if (!isNaN(hi) && hi < v) v = hi;
    e.value = String(v);
    e.dispatchEvent(new Event('input', {bubbles:true}));
    e.dispatchEvent(new Event('change', {bubbles:true}));
  });
  return out;
}
"""

# Whatever the page calls "put that in the list". Clicking these is what turns a
# typed value into rendered HTML, which is where the escaping either happens or
# does not.
COMMIT = """
() => {
  let n = 0;
  const want = /^(add|\\+|save|record|log|append|enter|new|make|build|create)\\b|^\\+ /i;
  document.querySelectorAll('button,[role=button]').forEach(b => {
    const t = (b.textContent || '').trim();
    if (!t || t.length > 34) return;
    if (!want.test(t)) return;
    const r = b.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    try { b.click(); n++; } catch (_) {}
  });
  return n;
}
"""

CHECK = """
() => ({
  // A page with no hits has either escaped correctly or never rendered the probe
  // at all, and those are not the same result. If the probe is nowhere in the
  // visible text, this page was not exercised and "clean" would be a lie.
  echoed: (document.body.innerText || '').split('<x-probe>').length - 1,
  element: document.querySelectorAll('x-probe').length,
  attribute: document.querySelectorAll('[data-x-probe]').length,
  // where it landed, to make a hit actionable rather than just true
  where: [...document.querySelectorAll('x-probe')].slice(0,3).map(e => {
    const p = e.parentElement;
    return p ? (p.tagName.toLowerCase() + (p.className ? '.' + String(p.className).split(' ')[0] : '')) : '(detached)';
  }),
  attrWhere: [...document.querySelectorAll('[data-x-probe]')].slice(0,3).map(e =>
    e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : '')),
})
"""


def main():
    pages = sorted(glob.glob(DOCS + "*.html"))
    rows, total = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        for path in pages:
            nm = os.path.basename(path)
            ctx = b.new_context(viewport={"width": 1100, "height": 900})
            ctx.set_offline(True)                 # no webfont wait; see audit_offline.py
            pg = ctx.new_page()
            pg.set_default_timeout(20000)
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            try:
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(700)
                # every pane, not just the open one -- a list that renders on a
                # tab you have not clicked is still a list that renders
                panes = pg.evaluate(
                    "()=>{const p=[...document.querySelectorAll('.pane')];"
                    " p.forEach(x=>x.classList.add('on')); return p.length;}")
                onlyfilter = pg.evaluate(
                    "()=>{const t=[...document.querySelectorAll('input[type=text],input:not([type]),textarea')]"
                    ".filter(e=>!e.disabled&&!e.readOnly&&(e.getBoundingClientRect().width>0));"
                    " return t.length>0 && t.every(e=>e.closest('.fek-pick'));}")
                filled = pg.evaluate(FILL, PROBE)
                pg.wait_for_timeout(200)
                clicked = pg.evaluate(COMMIT)
                pg.wait_for_timeout(600)
                # some pages only render on a second pass
                pg.evaluate(FILL, PROBE)
                pg.evaluate(COMMIT)
                pg.wait_for_timeout(600)
                r = pg.evaluate(CHECK)
            except Exception as exc:
                rows.append((nm, None, str(exc)[:60])); ctx.close(); continue
            ctx.close()
            n = r["element"] + r["attribute"]
            total += n
            rows.append((nm, dict(r, fields=len(filled), buttons=clicked, panes=panes,
                                  onlyfilter=onlyfilter), None))
        b.close()

    print("%-30s %7s %7s %6s %6s %6s" % ("PAGE", "FIELDS", "CLICKS", "ECHO", "ELEM", "ATTR"))
    print("-" * 74)
    for nm, r, err in rows:
        if err:
            print("%-30s LOAD FAIL %s" % (nm, err)); continue
        quiet = not r["echoed"] and not r["element"] and not r["attribute"]
        state = ("" if not quiet else
                 "nothing to record - every field is a picker filter" if r["onlyfilter"]
                 else "no text fields" if r["fields"] == 0
                 else "NOT EXERCISED - probe never rendered")
        print("%-30s %7d %7d %6s %6s %6s  %s"
              % (nm, r["fields"], r["buttons"], r["echoed"] or "-",
                 r["element"] or "-", r["attribute"] or "-", state))
        for w in r["where"]:
            print("%-32s   markup injected inside  %s" % ("", w))
        for w in r["attrWhere"]:
            print("%-32s   attribute broken out of %s" % ("", w))
    print("-" * 74)
    print("pages where typed markup became markup: %d"
          % sum(1 for _, r, e in rows if r and (r["element"] or r["attribute"])))
    print("total injections: %d" % total)
    quiet = [(nm, r) for nm, r, e in rows
             if r and not r["echoed"] and not r["element"] and not r["attribute"]]
    untested = [nm for nm, r in quiet if r["fields"] and not r["onlyfilter"]]
    print("pages exercised and clean:            %d"
          % sum(1 for _, r, e in rows if r and r["echoed"] and not r["element"] and not r["attribute"]))
    print("pages with nothing to type into:      %d" % sum(1 for _, r in quiet if not r["fields"]))
    print("pages whose only fields are filters:  %d" % sum(1 for _, r in quiet if r["onlyfilter"]))
    print("pages NOT exercised (a real gap):     %d%s"
          % (len(untested), ("   " + ", ".join(untested)) if untested else ""))
    return total


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
