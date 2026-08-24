# -*- coding: utf-8 -*-
"""Finds numeric claims in prose that carry no visible provenance.

ADR-031 says every number the kit prints must pass a three-way test: ship it if
it is definitional or citable; ship it labelled a convention; or refuse to ship
it and take the user's own value with provenance recorded. This looks for the
numbers that took none of those three routes.

It is a FINDER, not a gate. It cannot tell a sourced number from an unsourced
one -- only whether provenance is visible near the claim. Every hit is a
question for a human, and a clean run is not a certificate. It exits zero
always, and prints a count for triage rather than a verdict.

What counts as a claim: a number carrying a physical unit or a comparison, in
running prose. Growing degree days, incubation temperatures, pH breakpoints,
percentage thresholds -- the load-bearing kind in this domain.

What counts as provenance in view: an author-year citation, a `.cite`/`.src`/
`.ref` element, the word convention/conventional/arbitrary/rule of thumb, or
sitting inside a `.refuse` panel where the kit declines to assert at all. A block marked
`data-claim="definitional"` or `data-claim="derived"` is also skipped: those say
the number follows from a definition or from arithmetic shown on the page, which
the reader can check without going anywhere.

Deliberately not flagged: numbers inside controls (a stepper's min and max are
UI, not claims), unit-conversion arithmetic, and anything already inside a
refusal panel.

Run:  python3 tools/audit_claims.py
"""
import glob, os, re, sys
from playwright.sync_api import sync_playwright

DOCS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")) + os.sep

PROBE = r"""
() => {
  const UNIT = /(?:^|[\s(])(?:[<>≤≥±~]\s*)?\d[\d.,]*\s*(?:°C|°F|\bK\b|mm|cm|\bm\b|km|µm|nm|\bg\b|kg|mg|ppm|ppb|mL|\bL\b|pH|%|days?|weeks?|hours?|hrs?|minutes?|min\b|seconds?|GDD|lux|kPa|bar|mS\/cm|dS\/m)(?![\w-])/i;
  const CMP  = /(?:^|\s)(?:at least|no more than|not below|not above|below|above|under|over|greater than|less than|between)\s+\d/i;
  // Case-insensitive: the kit labels its own conventions as "Rule of thumb:" at
  // the head of a sentence, and a case-sensitive test hid every one of them.
  const PROV = /\b(?:convention|conventional|conventionally|arbitrary|rule of thumb|by definition|definitional|as defined|indicative|cf\.|et al\.?)/i;
  // Named standards and regulations are provenance too -- arguably the strongest
  // kind here, since the reader can go and look the clause up.
  const STD  = /\b(?:\d+\s*CFR\s*\d+|USDA\s+NOP|NOP\s*§|CLSI|EUCAST|ISO\s*\d|ASTM\s*[A-Z]?\d|EN\s*\d{3,}|Mueller[- ]Hinton|McFarland|IUCN|CITES|Braun[- ]Blanquet|Lincoln[-–\s]Petersen|Chapman|Daubenmire|USFS|FIA)\b/i;
  const CITED = /(?:after\s+[A-Z][a-z]+|\(\s*[A-Z][A-Za-z’'\-]+(?:\s+(?:&|and)\s+[A-Z][A-Za-z’'\-]+)?,?\s*(?:19|20)\d\d\s*\))/;

  const out = [];
  const BLOCK = 'p,li,td,th,dd,figcaption,blockquote,summary';
  document.querySelectorAll(BLOCK).forEach(el => {
    if (el.closest('.refuse, .refusal, [data-refuse]')) return;   // the kit already declined here
    // A number that follows from a definition or from arithmetic the reader can
    // redo needs no citation -- DBH = C/pi, a 45-degree slope being 100%, the
    // Poisson CV of 1/sqrt(N). Those are declared in the markup rather than
    // guessed at, on the same principle as the print audit: reading a stated
    // intent is not the same as inferring one.
    if (el.closest('[data-claim="definitional"], [data-claim="derived"]')) return;
    if (el.closest('button, label, select, .fek-step, .fek-slide, .fek-pick, .fek-tiles')) return;
    const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (t.length < 12 || t.length > 400) return;
    if (!UNIT.test(t) && !CMP.test(t)) return;

    // Provenance has to be in VIEW of the claim, not merely somewhere on the
    // page. An earlier version searched the nearest section, which on a page
    // with no section wrapper resolved to <body> -- so one citation anywhere
    // laundered every unsourced number on the page. Its own canary caught it.
    // The neighbourhood is now bounded: the block, its parent, and the nearest
    // card only while that card is still small enough to count as nearby.
    const own = (el.textContent || '').replace(/\s+/g, ' ');
    const near = [own];
    const par = el.parentElement;
    if (par && par !== document.body) {
      const pt = (par.textContent || '').replace(/\s+/g, ' ');
      if (pt.length < own.length * 4) near.push(pt);       // a parent, not the page
    }
    const card = el.closest('section, .card, .panel, details, article');
    if (card && card !== document.body) {
      const ct = (card.textContent || '').replace(/\s+/g, ' ');
      if (ct.length < own.length * 4) near.push(ct);       // still the same neighbourhood
    }
    if (near.some(t => PROV.test(t) || STD.test(t) || CITED.test(t))) return;
    if (el.querySelector('.cite, .src, .ref, cite')) return;
    if (par && par !== document.body && par.querySelector('.cite, .src, .ref, cite, sup a')) return;

    out.push(t.slice(0, 150));
  });
  return out;
}
"""


def main():
    pages = sorted(glob.glob(DOCS + "*.html"))
    rows, total = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 900})
        pg.set_default_timeout(25000)
        pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
        pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
        for path in pages:
            nm = os.path.basename(path)
            try:
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(600)
                hits = pg.evaluate(PROBE)
            except Exception as exc:
                rows.append((nm, None, str(exc)[:60])); continue
            seen, uniq = set(), []
            for h in hits:
                if h in seen: continue
                seen.add(h); uniq.append(h)
            total += len(uniq)
            rows.append((nm, uniq, None))
        b.close()

    for nm, hits, err in rows:
        if err: print("%-30s LOAD FAIL %s" % (nm, err)); continue
        if not hits: continue
        print("%s  (%d)" % (nm, len(hits)))
        for h in hits:
            print("    %s" % h)
        print()
    print("-" * 78)
    print("pages with unsourced-looking claims: %d of %d"
          % (sum(1 for _, h, e in rows if h), len(rows)))
    print("claims to triage: %d" % total)
    print("(this is a finder, not a gate -- every line above is a question, not a verdict)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
