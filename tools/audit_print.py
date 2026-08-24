# -*- coding: utf-8 -*-
"""Kit-wide print-fidelity audit.

Several pages in this kit are reference cards: the point of them is that you
print one, fold it, and carry it into a field where there is no phone signal.
Every page here already ships an `@media print` block, so the question is not
whether print was considered but whether what comes out of the printer is the
document. This measures the printed rendering, not the screen one.

Four faults, in the order they cost you:

  LOST      content that is display:none when printing. On screen a tab panel
            you have not opened is fine; on paper it is a page you will never
            see. Only flagged when the hidden block carries real text.
  CUT       an element wider than the printable column, so its right edge is
            sliced off by the printer. Measured at 720px -- US Letter portrait
            at 96dpi with half-inch margins, the narrower of the two common
            paper sizes.
  SPLIT     a repeating item (a card, a species row, a key couplet) with no
            break-inside:avoid, so it can be guillotined across two sheets.
  INK       dark fill that survives into print. A field card should not cost a
            cartridge; reported as a share of the printed column's area.

Run:  python3 tools/audit_print.py
Exits non-zero if any LOST or CUT fault is found -- those lose you the document.
SPLIT and INK are reported but do not fail the build; they are judgement calls
about paper, and the number is there to be judged.
"""
import glob, os, sys
from playwright.sync_api import sync_playwright

DOCS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")) + os.sep
PRINT_W = 720

PROBE = r"""
(W) => {
  const key = e => {
    const c = e.getAttribute('class');
    return e.tagName.toLowerCase() + (c ? '.' + String(c).trim().split(/\s+/)[0] : '');
  };
  const tally = arr => {
    const m = new Map();
    arr.forEach(k => m.set(k, (m.get(k) || 0) + 1));
    return [...m].sort((a, b) => b[1] - a[1]).slice(0, 6);
  };
  const lum = c => {
    const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[,\s\/]+/).filter(Boolean).map(Number);
    if (p.length > 3 && p[3] < 0.5) return null;
    const f = v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
    return 0.2126*f(p[0]) + 0.7152*f(p[1]) + 0.0722*f(p[2]);
  };

  // --- LOST: hidden in print, but carries real text --------------------
  const lost = [];
  let lostChars = 0;
  const NOTCONTENT = /^(SCRIPT|STYLE|TEMPLATE|LINK|META|NOSCRIPT|TITLE)$/;
  document.querySelectorAll('body *').forEach(e => {
    if (NOTCONTENT.test(e.tagName)) return;   // never rendered anywhere; not "lost"
    const s = getComputedStyle(e);
    if (s.display !== 'none') return;
    if (e.parentElement && getComputedStyle(e.parentElement).display === 'none') return; // count the outermost only
    const t = (e.innerText || e.textContent || '').trim();
    if (t.length < 200) return;
    // Navigation is chrome, not content: suppressing it in print is correct, and
    // flagging it would train the reader to ignore this tool. A block whose text
    // lives almost entirely inside links is navigation, whatever it is called.
    if (e.tagName === 'NAV' || e.closest('nav')) return;
    // An explicit marker is the author saying what this block is. Reading a
    // stated intent is not the same as guessing at one, so these are honoured:
    //   .noprint            chrome that has no meaning on paper
    //   data-print="mode"   one arm of a mutually exclusive set; whichever arm
    //                       you are actually on is the one that prints
    if (e.classList.contains('noprint') || e.closest('.noprint')) return;
    if (e.dataset.print === 'mode' || e.dataset.print === 'chrome') return;
    if (e.closest('[data-print="mode"],[data-print="chrome"]')) return;
    const links = e.querySelectorAll('a[href]');
    let linked = 0;
    links.forEach(a => { linked += (a.textContent || '').trim().length; });
    if (links.length >= 3 && linked / t.length > 0.5) return;   // a link list is navigation
    // Same principle for controls: a grid of buttons printed on paper is a grid
    // of dead buttons. Suppressing a control panel is a decision, not a loss.
    let ctl = 0;
    e.querySelectorAll('button,input,select,textarea,[role=button]').forEach(
      c => { ctl += (c.textContent || c.value || '').trim().length; });
    if (ctl / t.length > 0.6) return;
    lost.push(key(e)); lostChars += t.length;
  });

  // --- CUT: past the right edge of the printable column ----------------
  const cut = [];
  document.querySelectorAll('body *').forEach(e => {
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden') return;
    const b = e.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) return;
    if (b.right > W + 2) {
      // an ancestor that already clips is the real culprit, not this child
      let clipped = false;
      for (let n = e.parentElement; n; n = n.parentElement) {
        const os = getComputedStyle(n).overflowX;
        if (os === 'hidden' || os === 'auto' || os === 'scroll') { clipped = true; break; }
      }
      if (!clipped) cut.push(key(e));
    }
  });

  // --- SPLIT: repeating blocks with no break-inside guard --------------
  const split = [];
  const groups = new Map();
  document.querySelectorAll('body *').forEach(e => {
    const s = getComputedStyle(e);
    if (s.display === 'none') return;
    const b = e.getBoundingClientRect();
    if (b.height < 28) return;                       // too small to be worth a rule
    const k = key(e);
    if (!k.includes('.')) return;                    // only class-named repeats
    (groups.get(k) || groups.set(k, []).get(k)).push(s.breakInside || s.pageBreakInside);
  });
  groups.forEach((v, k) => {
    if (v.length < 3) return;                        // not a repeating series
    if (v.every(x => x === 'avoid')) return;
    split.push(k);
  });

  // --- INK: dark fill that survives into print -------------------------
  let dark = 0;
  const colW = Math.min(W, document.documentElement.scrollWidth);
  const total = colW * document.documentElement.scrollHeight;
  document.querySelectorAll('body *').forEach(e => {
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden') return;
    const l = lum(s.backgroundColor);
    if (l === null || l > 0.35) return;
    const b = e.getBoundingClientRect();
    dark += Math.max(0, Math.min(b.width, colW)) * Math.max(0, b.height);
  });

  return {lost: tally(lost), lostChars, cut: tally(cut), cutN: cut.length,
          split: split.slice(0, 6), splitN: split.length,
          ink: total ? Math.round(dark / total * 1000) / 10 : 0};
}
"""


def main():
    pages = sorted(glob.glob(DOCS + "*.html"))
    rows, hard = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": PRINT_W, "height": 1000})
        pg.set_default_timeout(25000)
        pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
        pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
        pg.emulate_media(media="print")
        for path in pages:
            nm = os.path.basename(path)
            try:
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(600)
                r = pg.evaluate(PROBE, PRINT_W)
            except Exception as exc:
                rows.append((nm, None, str(exc)[:70])); continue
            hard += len(r["lost"]) + r["cutN"]
            rows.append((nm, r, None))
        b.close()

    print("%-30s %5s %5s %5s %6s" % ("PAGE", "LOST", "CUT", "SPLIT", "INK%"))
    print("-" * 74)
    for nm, r, err in rows:
        if err: print("%-30s LOAD FAIL %s" % (nm, err)); continue
        print("%-30s %5s %5s %5s %5.1f%%"
              % (nm, len(r["lost"]) or "-", r["cutN"] or "-", r["splitN"] or "-", r["ink"]))
        for k, n in r["lost"]:
            print("%-32s   lost   %s x%d" % ("", k, n))
        for k, n in r["cut"]:
            print("%-32s   cut    %s x%d" % ("", k, n))
    print("-" * 74)
    worst = sorted(((r["ink"], nm) for nm, r, e in rows if r), reverse=True)[:3]
    print("heaviest ink: " + ", ".join("%s %.1f%%" % (n, i) for i, n in worst))
    print("pages losing content to display:none in print: %d"
          % sum(1 for nm, r, e in rows if r and r["lost"]))
    print("pages with content cut by the paper edge: %d"
          % sum(1 for nm, r, e in rows if r and r["cutN"]))
    print("hard faults (lost + cut):", hard)
    return hard


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
