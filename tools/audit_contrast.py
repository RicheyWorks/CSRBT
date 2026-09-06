# -*- coding: utf-8 -*-
"""Kit-wide WCAG AA colour-contrast audit.

The kit is meant to be read on a phone, in a field, in daylight. Contrast is not
a nicety there; it is whether the number can be read at all. This measures what
the browser actually computes -- not what the token file says it should be --
for every element that paints its own text.

Thresholds (WCAG 2.1 AA):
  4.5:1  normal text
  3.0:1  large text (>=24px, or >=18.66px when bold)
  3.0:1  1.4.11 non-text: the visible boundary of an input, select or textarea
         against the surface behind it, since that boundary is the only thing
         telling you where to write.

What it deliberately does not flag:
  - placeholder text (browser-dimmed by design, and it is never the only label
    here -- audit_focus.py enforces that separately)
  - :disabled controls, which WCAG exempts
  - text over a background-image, where a static ratio is meaningless. These are
    counted and reported separately rather than silently dropped, so a page that
    hides failures behind gradients still shows up.

ADR-130: measured in every state of the page (tools/audit_states.py), not
only as loaded -- text behind a closed tab had no box and was never measured.

Run:  python3 tools/audit_contrast.py
Exits non-zero if any fault is found, so it fails a build.
"""
import glob, os, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_states as S

DOCS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")) + os.sep
DOCS = (os.environ.get("CSRBT_DOCS_DIR") or DOCS).rstrip(os.sep) + os.sep   # verify_audit_states's fixture hook

PROBE = r"""
() => {
  // --- colour plumbing -------------------------------------------------
  const parse = c => {
    const m = String(c).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[,\s\/]+/).filter(Boolean).map(Number);
    return {r:p[0], g:p[1], b:p[2], a:(p.length > 3 ? p[3] : 1)};
  };
  const over = (fg, bg) => ({            // composite fg (with alpha) onto bg
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
    return 0.2126*f(c.r) + 0.7152*f(c.g) + 0.0722*f(c.b);
  };
  const ratio = (a, b) => {
    const la = lum(a), lb = lum(b);
    return (Math.max(la,lb) + 0.05) / (Math.min(la,lb) + 0.05);
  };
  const r2 = v => Math.round(v * 100) / 100;

  // Walk ancestors accumulating any translucent layers until something opaque.
  // Returns null when an image/gradient is in the stack -- a static ratio would
  // be a guess, and a guess that passes is worse than an honest unknown.
  const backdrop = el => {
    const stack = [];
    for (let n = el; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.backgroundImage && s.backgroundImage !== 'none') return null;
      const c = parse(s.backgroundColor);
      if (c && c.a > 0) { if (c.a >= 1) { let out = c; for (let i = stack.length-1; i >= 0; i--) out = over(stack[i], out); return out; } stack.push(c); }
    }
    let out = {r:255,g:255,b:255,a:1};
    for (let i = stack.length-1; i >= 0; i--) out = over(stack[i], out);
    return out;
  };
  const paintsText = el => {
    for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) return true;
    return false;
  };
  const shown = el => {
    const b = el.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05;
  };
  const key = el => {
    const c = el.getAttribute('class');
    return el.tagName.toLowerCase() + (c ? '.' + String(c).trim().split(/\s+/)[0] : '');
  };

  const text = [], nontext = [], unknown = [];
  const seen = new Map();
  const record = (bucket, el, got, need, extra) => {
    const k = key(el) + '|' + got + '|' + need + (extra || '');
    const hit = seen.get(k);
    if (hit) { hit[1]++; return; }
    const row = [key(el), 1, got, need, (el.textContent || '').trim().slice(0, 34), extra || ''];
    seen.set(k, row); bucket.push(row);
  };

  // --- 1.4.3 text ------------------------------------------------------
  document.querySelectorAll('body *').forEach(el => {
    if (!paintsText(el) || !shown(el)) return;
    if (el.disabled) return;
    const s = getComputedStyle(el);
    const bg = backdrop(el);
    if (!bg) { unknown.push(key(el)); return; }
    const fgRaw = parse(s.color); if (!fgRaw) return;
    const fg = over(fgRaw, bg);
    const px = parseFloat(s.fontSize);
    const w  = parseInt(s.fontWeight, 10) || 400;
    const big = px >= 24 || (px >= 18.66 && w >= 700);
    const need = big ? 3 : 4.5;
    const got = ratio(fg, bg);
    if (got + 0.005 < need) record(text, el, r2(got), need, ' ' + Math.round(px) + 'px');
  });

  // --- 1.4.11 the edge of a field you are meant to write in ------------
  document.querySelectorAll('input,select,textarea').forEach(el => {
    if (!shown(el) || el.disabled) return;
    if (/^(checkbox|radio|hidden|range|color)$/.test(el.type || '')) return;
    const s = getComputedStyle(el);
    if (parseFloat(s.borderTopWidth) === 0) return;
    if (s.borderTopStyle === 'none') return;
    const bc = parse(s.borderTopColor); if (!bc) return;
    const outside = backdrop(el.parentElement); if (!outside) return;
    const got = ratio(over(bc, outside), outside);
    if (got + 0.005 < 3) record(nontext, el, r2(got), 3, ' border');
  });

  return {text, nontext, unknown};
}
"""


def main():
    pages = sorted(glob.glob(DOCS + "*.html"))
    if not pages:
        print("no pages found under", DOCS); return 1
    rows, tot_t, tot_n, tot_u, tot_never = [], 0, 0, 0, 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 390, "height": 900})
        pg.set_default_timeout(25000)
        pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
        pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
        for path in pages:
            nm = os.path.basename(path)
            try:
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(600)
                # ADR-130: every state of the page, the findings merged by their
                # key (an element found under two tabs is one finding)
                res = {"text": [], "nontext": [], "unknown": [], "states": 0}
                keys = set()
                for state, r in S.each_state(pg, nm, lambda: pg.evaluate(PROBE)):
                    res["states"] += 1
                    for bucket in ("text", "nontext"):
                        for row in r[bucket]:
                            k = (bucket, row[0], row[2], row[3], row[5])
                            if k not in keys:
                                keys.add(k); res[bucket].append(row)
                    for u in r["unknown"]:
                        if u not in res["unknown"]:
                            res["unknown"].append(u)
                res["coverage"] = S.coverage(pg)
                # ADR-143: a look that found what an earlier look had missed is
                # contention, and it is printed rather than absorbed.
                if sum((res["coverage"].get("lateLooks") or [])[1:]):
                    print("%-30s LATE  %d control(s) only a later look saw"
                          % (nm, sum(res["coverage"]["lateLooks"][1:])))
                res["entry"] = getattr(pg, "_audit_entered", None)
            except Exception as exc:
                rows.append((nm, None, str(exc)[:70])); continue
            t = sum(r[1] for r in res["text"])
            n = sum(r[1] for r in res["nontext"])
            # ADR-130: a control no state exposed was measured in no state
            never = len(res["coverage"]["never"]) + (1 if S.entry_fault(res.get("entry")) else 0)
            tot_t += t; tot_n += n; tot_u += len(res["unknown"]); tot_never += never
            rows.append((nm, t + n + never, res))
        b.close()

    print("%-30s %s" % ("PAGE", "AA FAILURES"))
    print("-" * 78)
    for nm, n, res in rows:
        if n is None:
            print("%-30s LOAD FAIL  %s" % (nm, res)); continue
        cov = res.get("coverage", {"exposed": 0, "exist": 0, "never": []})
        if n == 0:
            ent = res.get("entry")
            print("%-30s ok   %d states, %d/%d controls measured%s%s" % (nm, res.get("states", 1), cov["exposed"], cov["exist"],
                                              "   (%d over imagery, unmeasured)" % len(res["unknown"]) if res["unknown"] else "",
                                              "" if not ent else "   entry %s %d/%d driven" % (ent["task"], ent["driven"], ent["steps"])))
            continue
        print("%-30s %d" % (nm, n))
        for name in cov["never"]:
            print("%-32s %-9s %s" % ("", "never", "never exposed in %d states: %s" % (res.get("states", 1), name)))
        for label, bucket in (("text", res["text"]), ("non-text", res["nontext"])):
            for sel, c, got, need, sample, extra in bucket:
                print("%-32s %-9s %-22s %5.2f:1 need %.1f x%d  %r"
                      % ("", label, sel + extra, got, need, c, sample))
    print("-" * 78)
    print("%-26s %d" % ("text below AA:", tot_t))
    print("%-26s %d" % ("field borders below 3:1:", tot_n))
    print("%-26s %d" % ("unmeasured (over imagery):", tot_u))
    print("%-26s %d" % ("never exposed, unmeasured:", tot_never))
    # ADR-143: and WHICH ones, here at the end. The per-page line that names
    # them can be two hundred lines above this summary, and run_all prints only
    # a failing job's tail -- so under `run_all -j 2` the kit's own report of
    # this fault has been "never exposed, unmeasured: 1" with the name cut off,
    # three times now. A count with no name costs a whole re-run to read.
    for nm, _n, res in rows:
        for name in (res.get("coverage") or {}).get("never", []):
            print("%-26s %s   %s" % ("", nm, name))
    print("%-26s %d" % ("total faults:", tot_t + tot_n + tot_never))
    return tot_t + tot_n + tot_never


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
