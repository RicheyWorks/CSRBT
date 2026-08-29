# -*- coding: utf-8 -*-
"""Locks the claims triage: the corrections, and the finder's exemptions.

The worklist sat at 71 for four slices. Working it down produced two kinds of
change, and both need holding in place.

Corrections, where the kit asserted more than it could support:
  * the drying temperature, where the practitioner rule and the controlled
    experiment disagree and the page had only the rule;
  * the Venus flytrap's range, which is a LANDWARD radius -- half that circle is
    ocean -- and whose legal status now carries a date and a penalty;
  * Roridula's nitrogen share, where the mechanism is citable and the number is
    not, so the number is marked approximate rather than asserted.

Exemptions, where the finder was reporting things that were never faults. Each
is asserted here against a seeded example, because an exemption is a hole in a
tool and holes should be shown to be the shape you meant.
"""

# Declared for tools/mutate.py. This suite writes ONE synthetic fixture file --
# and every other assertion in it is about the real pages in docs/. It is a
# subject, not a fixture-builder, and saying so is not optional: two different
# text predicates in mutate.py used to answer this question, they disagreed
# about this exact file, and the disagreement cost a real kill.
MUTATE_ROLE = "subject"
import io, os, re, sys, tempfile

import _kit
from playwright.sync_api import sync_playwright

P = F = 0
def ck(c, m):
    global P, F
    if c: P += 1
    else: F += 1; print("FAIL:", m)

def text(f):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", io.open(_kit.DOCS_DIR + f, encoding="utf-8").read()))


# text() strips tags with <[^>]+>, which is fine for prose and WRONG for script
# content: a page's JS contains bare < and > (comparisons, arrows), so the regex
# pairs them off and swallows whole spans. Every claim this kit renders from a
# widget's `help:` option lives in a script string, and an assertion about one
# written against text() does not fail -- it silently looks somewhere else. Read
# the raw source for those. ADR-098 found this by writing two such assertions
# and having them fail for a reason that had nothing to do with the page.
def raw(f):
    return re.sub(r"\s+", " ", io.open(_kit.DOCS_DIR + f, encoding="utf-8").read())

# ---- 1. the drying temperature carries both sides -------------------------
for f in ("collection-sheet.html", "fungal-characters.html"):
    t = text(f)
    ck("Fungal Diversity Survey" in t, "%s names the guide the 43-50 C window comes from" % f)
    ck("Wang" in t and "2017" in t, "%s names the experiment that disagrees" % f)
    ck("93" in t, "%s gives the range that experiment actually tested" % f)
    ck("stay below that" not in t, "%s no longer states the 50 C rule as a fact about DNA" % f)
cs = text("collection-sheet.html")
cs_raw = raw("collection-sheet.html")
ck("headroom" in cs, "collection-sheet says what the disagreement means for the reader")
ck("Record the temperature you actually used" in cs,
   "collection-sheet asks for the number that makes a failed extraction interpretable")

# ADR-098: the dryer help sent the reader to the Method tab for the 50 C
# discussion. That discussion is on the Voucher tab, in the note directly under
# the same log -- the pointer named the one tab that does not carry it.
ck("The note under this log" in cs_raw, "collection-sheet points at the note that is actually there")
ck("see the Method tab" not in cs_raw,
   "and no longer sends the reader to a tab that does not carry the 50 C discussion")
ck("Silica beats any drying temperature" not in cs_raw,
   "the unsourced comparative about silica is gone -- no number, so no run of the finder saw it")
ck("conventional choice for a DNA subsample" in cs_raw,
   "and what replaced it says what kind of claim it is")
ck("conventional working compromise" in cs,
   "40-45 C is labelled a convention, which is what the note below it argues")
ck("rule of thumb rather than a measured floor" in cs,
   "and the 35 C floor says which kind of number it is")

# ---- 2. the flytrap range, corrected and cited ---------------------------
cpc = text("cp-characters.html")
ck("landward" in cpc, "cp-characters says landward -- half the circle is ocean")
ck("Center for Plant Conservation" in cpc, "cp-characters cites the range")
ck("1 December 2014" in cpc, "the felony claim carries the date it became true")
ck("25 months" in cpc, "and the penalty, rather than just the word felony")
ck("each plant taken counts as a separate offence" in cpc, "and how the offence is counted")
ck("extirpated" in cpc, "and what has been lost since")

# ---- 3. a number that could not be sourced is marked, not asserted -------
ck("Ellis" in cpc and "1996" in cpc, "Roridula's mechanism is cited")
ck("approximate" in cpc, "and the share that could not be sourced says so")
ck("taking ~70% of its nitrogen from prey" not in cpc,
   "the bare assertion of 70% is gone")

# ---- 4. the finder's exemptions are the shape they were meant to be ------
CANARY = """<!doctype html><html><head><meta charset="utf-8"><title>c</title></head><body>
<section><p>Hold the pile above 55 C for at least 12 days before you turn it, then let it fall to 40 C.</p></section>
<section><p>By convention the reading is taken at 30 s, so two people read it at the same moment.</p></section>
<section><p>Hold at 55 C for 3 days (40 CFR 503 Appendix B), which names the clause you can go and read.</p></section>
<section><p>A count of N carries CV = 1/&#8730;N, so 100 cells is &#177;10% and 400 cells is &#177;5%.</p></section>
<section><p class="lab-for">For: ecology students &#183; setting: a lawn &#183; ~90 min incl. fieldwork</p></section>
<section><p>Water TDS best below 160 ppm. Gate 1 &#8212; cited.</p></section>
</body></html>"""
d = tempfile.mkdtemp()
io.open(os.path.join(d, "c.html"), "w", encoding="utf-8").write(CANARY)
probe = _kit.tool("audit_claims").PROBE
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1100, "height": 900})
    ctx.set_offline(True)
    pg = ctx.new_page()
    pg.goto("file://" + os.path.join(d, "c.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(300)
    hits = pg.evaluate(probe)
    ck(len(hits) == 1, "canary: exactly one of six claims is reported (%d)" % len(hits))
    ck(hits and "Hold the pile above 55 C for at least 12 days" in hits[0],
       "canary: and it is the unlabelled, uncited one")
    for phrase, why in (("By convention", "a labelled convention"),
                        ("40 CFR", "a named regulation"),
                        ("CV = 1", "a derivation shown inline"),
                        ("For: ecology students", "lesson metadata"),
                        ("Gate 1", "the kit's own gate verdict")):
        ck(not any(phrase in h for h in hits), "canary: %s is exempt" % why)
    ctx.close()
    b.close()

# ---- 5a. the derivation exemption is arithmetic, not provenance ----------
# ADR-098. Two sibling claims, neither carrying a provenance token and neither
# sitting near one. They differ in exactly one way: whether the arithmetic can
# be written down. The finder exempts the one that can.
#
# That is the derivation rule behaving as designed, and it has a consequence
# worth asserting rather than remembering: a claim whose CONTENT is that a
# quantity cannot be computed can never take that exit, however well sourced it
# is. micro-bench's "above 300" bullet is the kit's live example, and section 5b
# holds its provenance in place so the flag stays a known-good one.
ARITH = """<!doctype html><html><head><meta charset="utf-8"><title>a</title></head><body>
<ul>
<li>Below 30 the count is imprecise: CV = 1/&#8730;N, so 30 colonies gives 1/&#8730;30 &#8776; 18%.</li>
<li>Above 300 colonies merge and crowd, so you undercount by a growing and unknowable amount.</li>
</ul>
</body></html>"""
d2 = tempfile.mkdtemp()
io.open(os.path.join(d2, "a.html"), "w", encoding="utf-8").write(ARITH)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1100, "height": 900})
    ctx.set_offline(True)
    pg = ctx.new_page()
    pg.goto("file://" + os.path.join(d2, "a.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(300)
    hits = pg.evaluate(probe)
    ck(len(hits) == 1, "arithmetic canary: one of the two siblings is reported (%d)" % len(hits))
    ck(hits and "Above 300" in hits[0],
       "arithmetic canary: and it is the one that cannot show its working")
    ck(not any("Below 30" in h for h in hits),
       "arithmetic canary: the one that can show its working is exempt")

    # and the same pair on the real page, so the finder's last open item is the
    # one this ADR triaged. A change here is not a failure to fix quietly: read
    # ADR-098 first.
    pg2 = ctx.new_page()
    pg2.goto("file://" + os.path.join(_kit.DOCS_DIR, "micro-bench.html"),
             wait_until="domcontentloaded")
    pg2.wait_for_timeout(400)
    mb_hits = pg2.evaluate(probe)
    ck(any("Above 300" in h for h in mb_hits),
       "micro-bench's above-300 bullet is still the reported one (ADR-098 triaged it sound)")
    ck(not any("Below 30" in h for h in mb_hits),
       "and its sibling, which shows the Poisson arithmetic, is not")
    ctx.close()
    b.close()

# ---- 5b. and it is reported despite being sourced, not because it is not --
mb_src = io.open(_kit.DOCS_DIR + "micro-bench.html", encoding="utf-8").read()
mb = text("micro-bench.html")
ck("APHA Standard Methods 9215" in mb,
   "micro-bench names the standard the 30-300 window comes from")
ck("a convention rather" in mb, "and calls the window a convention rather than a constant")
ck("Breed and Dotterrer" in mb and "1916" in mb,
   "and cites the measurement the ranges disagree about")
bullet = mb_src.split("<li><b>Above 300</b>")[1].split("</li>")[0]
ck(not any(c in bullet for c in "=\u00f7\u221a"),
   "the above-300 bullet carries no arithmetic -- which is why it cannot take the derivation exit")
ck("unknowable" in bullet,
   "because its claim is that the quantity is unknowable, not that nobody did the sum")

# ---- 5. the record of provenance is not asked for provenance -------------
src = io.open(os.path.join(_kit.TOOLS_DIR, "audit_claims.py"), encoding="utf-8").read()
ck('nm == "adr-031.html"' in src, "ADR-031 is exempt: it is the record OF provenance")
ck("category error" in src, "and the exemption says why, where a reader will find it")
ck("finder" in src.lower() and "not a gate" in src.lower(),
   "the tool still calls itself a finder rather than a gate")
ck("PAGES THAT FAILED TO LOAD" in src,
   "a run where nothing loaded can no longer report zero claims")

print("---"); print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
