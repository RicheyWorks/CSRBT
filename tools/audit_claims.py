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

Four things are exempt, each for a stated reason: ADR-031 itself (it is the
record OF provenance -- its whole job is to quote numbers and say where they
stand), a number shown with its own
derivation (the reader can check it without going anywhere), a line carrying the
kit's own gate verdict, and lesson-plan durations in a lab header.

What counts as provenance in view: an author-year citation, a `.cite`/`.src`/
`.ref` element, the word convention/conventional/arbitrary/rule of thumb, or
sitting inside a `.refuse` panel where the kit declines to assert at all. A block marked
`data-claim="definitional"` or `data-claim="derived"` is also skipped: those say
the number follows from a definition or from arithmetic shown on the page, which
the reader can check without going anywhere.

That last branch is DEAD, and saying so is better than leaving it to be
rediscovered. `verify_claims_slice` forbids the attribute in docs/ outright --
it was a reverted attempt, and the suite checks the revert held. So the escape
this file documents cannot be used by any page, and a reader of this docstring
who reaches for it will be stopped by a suite two directories away. The branch
stays because removing it would make the two files disagree about history; the
paragraph stays because a documented mechanism nobody may use is exactly the
silent kind of wrong (ADR-061).

Deliberately not flagged: numbers inside controls (a stepper's min and max are
UI, not claims), unit-conversion arithmetic, and anything already inside a
refusal panel.

Two things this finder cannot see. They are named here because an undocumented
blind spot is the silent kind of wrong (ADR-061), and because a reader who
trusts a clean run should know what a clean run does not cover.

  * A CLAIM WITH NO NUMBER. The two tests are a number carrying a unit, and a
    comparison written with a digit. A comparative in words takes neither:
    "Silica beats any drying temperature for sequencing" was an unsourced
    instruction about a collector's only DNA subsample, and no run of this file
    would ever have reported it. It was found by reading, not by running this.

  * A CLAIM WHOSE CONTENT IS THAT A QUANTITY CANNOT BE COMPUTED. The derivation
    exemption below is a showable-arithmetic test, not a provenance test. Take
    the arithmetic out of micro-bench's "below 30 the Poisson error is large"
    bullet and it is reported exactly like its sibling, with its sourcing
    untouched -- the two differ in whether the sum can be written down, not in
    where they come from. The sibling, "above 300 you undercount by a growing
    and unknowable amount", can never take that exit: there is no arithmetic to
    show, and saying so IS the claim. Both shapes are seeded in
    verify_claims_triage so the asymmetry is asserted rather than remembered.

Run:  python3 tools/audit_claims.py
"""
import glob, os, re, sys
from playwright.sync_api import sync_playwright

# --full prints each claim whole. Triage needs the sentence, not its first
# 150 characters -- half these lines were cut mid-number.
FULL = "--full" in sys.argv
DOCS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")) + os.sep


# ONE VOCABULARY, TWO PROBES.
#
# These three regexes were written out twice -- once in each probe -- and the two
# copies had drifted. The section-level list named FDA BAM, AOAC, USP, APHA and
# Standard Methods; the block-level list did not. The strict test was therefore
# WEAKER than the loose one on the same tokens: a claim naming FDA BAM in its own
# sentence read BARE, while a claim three paragraphs away from one read `near`.
# That is not a strictness setting, it is a contradiction (ADR-051), and it is
# the reason micro-bench's plating volumes could be offered in ADR-094 as the
# worked example of a number no standard in the card covers -- FDA BAM Chapter 23
# fixes the spread volume at 0.1 mL in so many words.
#
# Written once and substituted into both, so widening is one visible edit rather
# than drift between two copies.
_VOCAB = r"""
  const PROV = /\b(?:convention|conventional|conventionally|arbitrary|rule of thumb|by definition|definitional|as defined|indicative|cf\.|et al\.?)/i;
  const STD  = /\b(?:\d+\s*CFR\s*\d+|USDA\s+NOP|NOP\s*§|CLSI|EUCAST|ISO\s*\d|ASTM\s*[A-Z]?\d|EN\s*\d{3,}|Mueller[- ]Hinton|McFarland|IUCN|CITES|Braun[- ]Blanquet|Lincoln[-–\s]Petersen|Chapman|Daubenmire|USFS|FIA|FDA\s+BAM|AOAC|USP|APHA|Standard\s+Methods)\b/i;
  const CITED = /(?:after\s+[A-Z][a-z]+|\(\s*[A-Z][A-Za-z’'\-]+(?:\s+(?:&|and)\s+[A-Z][A-Za-z’'\-]+)?,?\s*(?:19|20)\d\d\s*\))/;
"""

# How far away is the nearest provenance? A SECOND question, asked after the
# first has already been answered strictly.
#
# The worklist sat around thirty for several slices, and measuring showed why:
# 27 of 41 flagged claims have provenance somewhere in their own section --
# micro-bench states 30-300 in one paragraph and names FDA BAM, AOAC, USP and
# ASTM three paragraphs down, in the same card.
#
# It would be easy, and wrong, to widen the test to the section. One citation
# would then exempt every number under the same heading, including the ones it
# says nothing about: micro-bench's "0.1 mL spread, 1.0 mL pour" sits in that
# same card and comes from no standard named in it. A section-level pass is a
# silent exclusion with a plausible face (ADR-061).
#
# The constant below is deliberately NOT named with the four letters P-R-O-B-E
# followed by the raw-string opener. Two suites read this file by splitting it
# on that exact sequence, so any second occurrence -- a differently named probe,
# or a COMMENT quoting the sequence to warn about it -- hijacks the split and
# hands them the wrong body. The first draft of this file did it with a name;
# the comment written to explain that did it again, verbatim, which is ADR-077:
# a sentence about the rule can break the rule. This paragraph therefore
# describes the marker without containing it, and verify_claims_slice checks
# that every tool read this way carries exactly one.
#
# So the test does not move. The REPORT gains a column: `near` means provenance
# exists elsewhere in this claim's section, and the claim is therefore likely --
# not certainly -- covered. Triage reads it as an ordering hint. Fourteen claims
# have nothing anywhere near them, and those are the real front of the list.
SECTION_PROVENANCE = r"""
(claims) => {
__VOCAB__
  const has = t => PROV.test(t) || STD.test(t) || CITED.test(t);
  const BLOCK = 'p,li,td,th,dd,figcaption,blockquote,summary';
  return claims.map(c => {
    for (const el of document.querySelectorAll(BLOCK)) {
      const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
      if (!t.startsWith(c.slice(0, 45))) continue;
      const sec = el.closest('section, .card, article, .pane') || document.body;
      return has(sec.innerText || '');
    }
    return false;
  });
}
""".replace("__VOCAB__", _VOCAB)

PROBE = r"""
(FULL) => {
  const UNIT = /(?:^|[\s(])(?:[<>≤≥±~]\s*)?\d[\d.,]*\s*(?:°C|°F|\bK\b|mm|cm|\bm\b|km|µm|nm|\bg\b|kg|mg|ppm|ppb|mL|\bL\b|pH|%|days?|weeks?|hours?|hrs?|minutes?|min\b|seconds?|GDD|lux|kPa|bar|mS\/cm|dS\/m)(?![\w-])/i;
  const CMP  = /(?:^|\s)(?:at least|no more than|not below|not above|below|above|under|over|greater than|less than|between)\s+\d/i;
  // PROV, STD and CITED come from the one vocabulary above.
  // Case-insensitivity on PROV matters: the kit labels its own conventions
  // as "Rule of thumb:" at the head of a sentence, and a case-sensitive
  // test hid every one of them. Named standards and regulations are
  // provenance too -- arguably the strongest kind here, since the reader
  // can go and look the clause up.
__VOCAB__

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
    // NOT an exemption for "a legend that restates the reader's own entry".
    // One was written, with a class and a suite that drove each named control to
    // prove the text moved. Then the live copy of the only page that would have
    // used it turned out to have solved the same problem better: the duty legend
    // now prints "60 s of 600 s = 10.0% duty", so the derivation exemption above
    // already covers it and the reader gains the arithmetic. An escape with zero
    // members is the silent kind of wrong (ADR-094), so it was withdrawn rather
    // than kept for a case that no longer needs it. ADR-096 section 5.
    const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (t.length < 12 || t.length > 400) return;
    if (!UNIT.test(t) && !CMP.test(t)) return;
    // Three exemptions earned by working the list, not by wanting it shorter.
    //
    // 1. A number shown WITH its own derivation carries its provenance inline.
    //    DBH = C/pi, CV = 1/sqrt(N), 11.28 m = 400 m2, 100% = a 45-degree slope:
    //    the reader can check these without going anywhere, and asking for a
    //    citation would be asking where arithmetic comes from.
    if (/[=\u00f7\u221a\u00b1]|\bdivided by\b|\bper\b\s*\u221a/.test(t)
        && /\d/.test(t) && /[a-zA-Z]\s*[=]|=\s*\d|\d\s*[\u00f7=]/.test(t)) return;
    // 2. The kit's own provenance vocabulary. ADR-031 records each number's
    //    verdict as "Gate 1 -- cited", "Gate 2", "Gate 3 -- refused"; a record
    //    that states its gate has said where the number stands.
    if (/\bGate\s*[123]\b/.test(t)) return;
    // 3. Lesson metadata. "~90 min incl. fieldwork" in a lab header is how long
    //    to book the room, not a measurement of anything.
    if (el.classList.contains('lab-for') || el.closest('.lab-for')) return;

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
    // A floor under the strongest escape in this file. `.cite`/`.src`/`.ref`
    // exempted a block by EXISTING: an empty span silenced every number under
    // it and nothing checked. A provenance element has to name something.
    const sourced = root => [].slice.call(
        root.querySelectorAll('.cite, .src, .ref, cite, sup a'))
      .some(n => (n.textContent || '').trim().length >= 3 || n.querySelector('a[href]'));
    if (sourced(el)) return;
    if (par && par !== document.body && sourced(par)) return;

    out.push(FULL ? t : t.slice(0, 150));
  });
  return out;
}
""".replace("__VOCAB__", _VOCAB)


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
            # ADR-031 is the provenance record. Nearly every line in it quotes a
            # number in order to say where that number stands -- which gate it
            # passed, who it is cited to, why it was refused. Flagging the
            # document that exists to answer this question is a category error,
            # and ten of its lines were the largest single block on the list.
            if nm == "adr-031.html":
                rows.append((nm, [], None)); continue
            try:
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(600)
                hits = pg.evaluate(PROBE, FULL)
            except Exception as exc:
                rows.append((nm, None, str(exc)[:60])); continue
            seen, uniq = set(), []
            for h in hits:
                if h in seen: continue
                seen.add(h); uniq.append(h)
            total += len(uniq)
            try:
                near = pg.evaluate(SECTION_PROVENANCE, [re.sub(r"\s+", " ", h).strip()
                                                for h in uniq])
            except Exception:
                near = [False] * len(uniq)
            rows.append((nm, list(zip(uniq, near)), None))
        b.close()

    for nm, hits, err in rows:
        if err: print("%-30s LOAD FAIL %s" % (nm, err)); continue
        if not hits: continue
        print("%s  (%d)" % (nm, len(hits)))
        for h, near in hits:
            print("    %s %s" % ("near" if near else "BARE", h))
        print()
    print("-" * 78)
    broke = [nm for nm, h, e in rows if e]
    if broke:
        print("PAGES THAT FAILED TO LOAD: %d -- the count below is meaningless until they do"
              % len(broke))
        print("   " + ", ".join(broke[:6]))
    print("pages with unsourced-looking claims: %d of %d"
          % (sum(1 for _, h, e in rows if h), len(rows) - len(broke)))
    bare = sum(1 for _, h, e in rows if h for _, n in h if not n)
    print("claims to triage: %d -- %d BARE (no provenance anywhere in the claim's "
          "section) and %d near (some in the section, so likely covered)"
          % (total, bare, total - bare))
    print("`near` is an ordering hint, NOT an exemption: one citation must not "
          "cover every number under the same heading (ADR-094).")
    print("(this is a finder, not a gate -- every line above is a question, not a verdict)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
