# -*- coding: utf-8 -*-
"""What does a page show when it is PRINTED that it never shows on screen?

NOT tools/audit_print.py, which already existed and asks the opposite question:
that one measures what print LOSES (content hidden when the page is printed).
This one measures what print ADDS. I wrote this file over that one, and only
verify_print_slice -- which reads a PROBE block out of it -- noticed. Checking
whether the name was taken would have cost one `ls`; see ADR-092 section 5.

ADR-091 defined what "on screen" means -- innerText, SVG <text>, and every
tooltip a chart yields -- and named the one channel outside that definition:
a print stylesheet. This measures it.

Seventeen of the kit's thirty-nine pages put text on paper that a reader never
sees in the browser: the field sheets build a whole tab-separated report under
`@media print`, and it carries numbers. No suite had ever rendered any of it.

    python3 tools/audit_print.py

Method: render each page, take the screen observation, switch the emulated
media to print, take it again, and report the lines that only the second one
has. Same-page comparison, so nothing here depends on knowing which selector
does the hiding.

This is a finder, not a gate. It says a channel exists and how much is in it;
it does not claim any particular line is wrong.
"""
import glob, io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "verify"))
import _kit

OBSERVE = """() => {
  const parts = [document.body.innerText];
  parts.push([...document.querySelectorAll('svg text')].map(t => t.textContent).join('\\n'));
  return parts.join('\\n');
}"""
DIGIT = re.compile(r"\d")


def lines(pg):
    return set(l.strip() for l in pg.evaluate(OBSERVE).splitlines() if l.strip())


def sweep(pw, names=None):
    """{page: (only_print_lines, how_many_carry_digits)} for every page given."""
    names = names or sorted(os.path.basename(p)
                            for p in glob.glob(os.path.join(_kit.DOCS_DIR, "*.html")))
    out = {}
    b = pw.chromium.launch()
    for name in names:
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        _kit.offline(pg)
        pg.goto(_kit.url(name), wait_until="load")
        pg.wait_for_timeout(900)
        screen = lines(pg)
        pg.emulate_media(media="print")
        pg.wait_for_timeout(350)
        only = lines(pg) - screen
        out[name] = (len(only), sum(1 for l in only if DIGIT.search(l)))
        pg.close()
    b.close()
    return out


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        res = sweep(pw)
    hot = {k: v for k, v in res.items() if v[0]}
    print("%-32s %-14s %s" % ("page", "print-only", "of those, carrying digits"))
    print("-" * 78)
    for k, (n, d) in sorted(hot.items(), key=lambda kv: -kv[1][0]):
        print("%-32s %-14d %d" % (k, n, d))
    print("-" * 78)
    print("%d of %d pages put text on paper that no screen shows it: %d lines, "
          "%d of them carrying digits"
          % (len(hot), len(res), sum(v[0] for v in hot.values()),
             sum(v[1] for v in hot.values())))
    print("(a finder, not a gate -- no line here is claimed to be wrong)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
