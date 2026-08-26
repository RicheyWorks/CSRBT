# -*- coding: utf-8 -*-
"""Does the kit contradict itself about a number it has already researched?

Every other suite in this kit is PAGE-SCOPED. Each one drives its own page and
asserts that page is right. Nothing has ever asked whether page A and page B
agree, and there is one place where they do not:

  ecology-glossary, under "Trophic transfer efficiency (Lindeman 1942)", says
  the 10% figure is a TEACHING CONVENTION, gives Lindeman's own reported spread
  of 0.1%-37.5%, and warns in as many words:

      "If you are using it to argue that a chain cannot be longer than n levels,
       the argument is only as strong as the efficiency you assumed."

  ecology-lab-manual told a student: "Use the ~10% energy-transfer figure to
  estimate how much of the producers' energy reaches your top predator."
  food-web said: "energy loss (~90% per level) usually caps chains at 4-5" --
  which is precisely the argument the glossary names as unsafe, made by the tool
  the glossary is the reference for.

The gate in ADR-031 was applied on one page and not carried to the two that use
the number. That is not a stale publish (ADR-050) and not an unreachable defect
(ADR-049): it is the kit disagreeing with itself in the repo, today.

HOW THE FIRST VERSION FAILED

I first matched hedged SENTENCES to bare sentences by shared vocabulary. It
returned one candidate and missed BOTH defects above -- a detector that cannot
tell the two apart is not a weaker detector, it is measuring something else
(ADR-039). Two reasons:

  * the glossary's hedge sentence and the lab manual's instruction share almost
    no words; they are about the same TERM, not the same phrasing;
  * food-web says 90%, not 10%. For an efficiency, "10% transfers" and "90% is
    lost" are one claim. No vocabulary overlap can see that.

So the anchor is the glossary ENTRY -- its term, its citation, its figures and
their complements -- not any sentence in it. That also means the check grows
with the glossary instead of with a hand-kept list.

Run:  python3 tools/verify/verify_kit_consistency.py
"""
import glob, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS = os.path.join(ROOT, "docs")
GLOSSARY = "ecology-glossary.html"

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

ENTRY = re.compile(r'<div class="entry"><dt>(.*?)</dt><dd>(.*?)</dd>', re.S)
TAG = re.compile(r"<[^>]+>")
PCT = re.compile(r"(?<![\w#.-])(\d+(?:\.\d+)?)\s*%")

# Language that marks a figure as one the kit does NOT stand behind as a constant.
HEDGE = re.compile(r"teaching convention|hobby convention|a convention\b|not a constant|"
                   r"never been a law|treat it as|rather than a constant|not a standard|"
                   r"customary|not measured optima|not a requirement|useful number to think with|"
                   r"working assumption|as an assumption|which figure you assumed|not a law",
                   re.I)
# Language that USES a figure to compute or to bound something -- the thing the
# glossary warns against. A page may mention a convention figure freely; what it
# may not do is reason from it as if it were a constant.
INFER = re.compile(r"\buse the\b|\busing the\b|\bestimate\b|\bcaps?\b|\bmeans that\b|"
                   r"\bso the\b|\bmultiply\b|\bcannot be longer\b|\btherefore\b|\bworks out\b", re.I)


def plain(html):
    h = re.sub(r"<style\b.*?</style>", " ", html, flags=re.S | re.I)
    h = TAG.sub(" ", h)
    for a, b in (("&mdash;", "-"), ("&ndash;", "-"), ("&nbsp;", " "), ("&amp;", "&"),
                 ("&lt;", "<"), ("&gt;", ">"), ("&deg;", " deg"), ("&asymp;", "~")):
        h = h.replace(a, b)
    h = re.sub(r"&[a-zA-Z#0-9]+;", " ", h)
    return " ".join(h.split())


BLOCK = re.compile(r"</?(?:li|p|div|td|dd|section|h[1-6]|tr|ul|ol)\b[^>]*>", re.I)

def sentences(html):
    """Yields (kind, sentence, block) -- and the BLOCK is what carries the hedge.

    Hedging was first tested on the sentence alone. That is not how a reader
    reads: the lab manual's exercise says "take 10% as a working assumption"
    and explains two sentences later, in the same list item, that it is a
    teaching convention and asks the student to redo it at 1% and 40%. Scoped
    to the sentence, that reads as an unhedged instruction; scoped to the block
    a reader actually takes in, it is exactly the hedge the glossary asks for.

    Scoping to the whole PAGE would be the other error -- one disclaimer at the
    top would then excuse every bare claim below it.

    Script strings are read too: food-web's most confident sentence lives in a
    template concatenation inside stats(), and a checker that only reads prose
    cannot see it. There the block is the whole literal.
    """
    body = re.sub(r"<style\b.*?</style>", " ", html, flags=re.S | re.I)
    out = []
    prose = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    for blk in BLOCK.split(prose):
        btxt = plain(blk)
        if not btxt:
            continue
        for chunk in re.split(r"(?<=[.!?])\s+", btxt):
            if chunk.strip():
                out.append(("prose", " ".join(chunk.split()), btxt))
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script>", body, re.S | re.I):
        for lit in re.findall(r"'((?:[^'\\]|\\.){12,})'|\"((?:[^\"\\]|\\.){12,})\"", m.group(1)):
            t = plain(lit[0] or lit[1])
            if t:
                out.append(("script", t, t))
    return out


def convention_figures(body):
    """Every figure the hedged entry carries.

    An earlier version took only the figures stated BEFORE the hedge -- the
    convention (10%) but not the spread offered against it (0.1%, 1%, 37.5%,
    40%). The reasoning was that the defect is treating THE CONVENTION as a
    constant.

    A mutation sweep widened it back and no fixture noticed, so I went looking
    for the fixture that would justify the narrowing and could not write an
    honest one: "use the 40% transfer efficiency to estimate the energy
    reaching the top predator" is the same error as using 10%. The spread is
    the range of what has been measured, not a set of better constants. The
    narrowing was a precision tweak dressed as a semantic one, and the wider
    rule is both simpler and more correct.

    It costs nothing here because the locality test, not the figure set, is
    what holds the false-positive rate down.
    """
    return set(PCT.findall(body))


def complements(figs):
    """For a percentage, x% and (100-x)% are the same claim stated from either
    end. food-web says 90% where the glossary says 10%, and without this the
    two never meet."""
    out = set(figs)
    for f in figs:
        try:
            v = float(f)
        except ValueError:
            continue
        if 0 < v < 100:
            c = 100 - v
            out.add(("%g" % c))
    return out


def entries():
    src = io.open(os.path.join(DOCS, GLOSSARY), encoding="utf-8").read()
    got = []
    for dt, dd in ENTRY.findall(src):
        term = plain(dt)
        body = plain(dd)
        # The citation, when there is one, sits in a <span class="who">.
        cite = re.search(r'<span class="who">(.*?)</span>', dt)
        got.append({"term": re.sub(r"\s+", " ", TAG.sub(" ", dt)).strip(),
                    "head": plain(re.sub(r'<span class="who">.*?</span>', " ", dt)),
                    "cite": plain(cite.group(1)) if cite else "",
                    "body": body,
                    "hedged": bool(HEDGE.search(body)),
                    "pcts": convention_figures(body)})
    return got


ALL = entries()
ck("the glossary parses into entries", len(ALL) > 15, len(ALL))
HEDGED = [e for e in ALL if e["hedged"] and e["pcts"]]
ck("at least one entry hedges a percentage -- otherwise this check is vacuous",
   bool(HEDGED), [e["head"] for e in ALL if e["hedged"]])

# The topic of an entry is its own term's distinctive words, not its phrasing.
STOP = set("the a an and or of to in is it as that this for with by from on at".split())
# Split on hyphens as well as spaces. "energy-transfer" is one token to a naive
# \w regex, so the entry's topic word "transfer" never matched the lab manual's
# instruction and the direct-prose fixture failed while the harder
# complement-inside-a-script fixture passed -- the tokenizer, not the idea.
WORD = re.compile(r"[A-Za-z]{4,}")

def subject(e):
    """What the entry's figure is a rate OF -- taken from the entry's DEFINITION
    sentence, and tested against the figure's own neighbourhood.

    Four attempts at document-level word overlap all failed in opposite
    directions, and the failures are worth recording because each looked
    reasonable:

      head words only      -- too narrow: food-web says "energy loss per level"
                              and never says "transfer".
      head + whole body    -- too wide: the body says "the source of the
                              figure", so "use the 10% slope figure to estimate
                              runoff" became topical.
      document frequency   -- cannot separate discourse words from subject
                              words. Across 111 entries "figure" appears in
                              five, which any sane cap calls distinctive.
      one hop in the term  -- linked entries on "rather", "than", "never" and
      graph                  "cannot", pulled in 27 entries including one about
                              a selection gradient, and handed the slope
                              fixture the word "slope".

    The claim is not document-level. "10%" is a defect only where it is a rate
    of the thing the entry defines, and that shows up within a few words of the
    figure: "energy-transfer", "per level", "energy lost per step". So the test
    is local, and the vocabulary comes from the entry's first sentence -- a
    glossary definition, the most reliable description of a subject there is --
    rather than from its commentary.
    """
    first = re.split(r"(?<=[.!?])\s", e["body"])[0]
    return ({w.lower() for w in WORD.findall(e["head"])}
            | {w.lower() for w in WORD.findall(first)}) - STOP


WINDOW = 60

def about(sentence, subj):
    """Is any figure in this sentence a rate of the entry's subject?"""
    for m in PCT.finditer(sentence):
        lo, hi = max(0, m.start() - WINDOW), m.end() + WINDOW
        near = {w.lower() for w in WORD.findall(sentence[lo:hi])}
        if near & subj:
            return True
    return False


def violations(html, e):
    """THE rule, in one place.

    It was written twice: once in the loop over the real pages and once inside
    the fixture runner. A mutation sweep then killed five operators with no
    fixture noticing, because every fixture went through the copy and every
    mutation landed in the original. That is the connectance defect from
    ADR-039 exactly -- one formula, three implementations, and a canary that
    changes one leaves the others reporting the old answer.
    """
    want, subj = complements(e["pcts"]), subject(e)
    out = []
    for kind, sent, blk in sentences(html):
        if HEDGE.search(blk):
            continue
        got = {m.group(1) for m in PCT.finditer(sent)}
        if not (got & want):
            continue
        if not INFER.search(sent):
            continue
        if not about(sent, subj):
            continue
        out.append((kind, sorted(got & want), sent))
    return out


pages = {os.path.basename(p): io.open(p, encoding="utf-8").read()
         for p in sorted(glob.glob(os.path.join(DOCS, "*.html")))
         if not os.path.basename(p).startswith("adr-")}

findings = []
for e in HEDGED:
    for name, html in pages.items():
        if name == GLOSSARY:
            continue
        for kind, figs, sent in violations(html, e):
            findings.append((e["head"], name, kind, figs, sent))

ck("no page reasons from a figure the glossary calls a convention",
   not findings, [(f[1], f[3], f[4][:90]) for f in findings])

# ---- and the detector is not vacuous -------------------------------------
# Two fixtures, both drawn from the real defect, because a detector that returns
# nothing on a clean kit and nothing on a broken one has told you nothing.
def scan(fixture_html, entry_head="Trophic transfer efficiency"):
    e = [x for x in HEDGED if x["head"].startswith(entry_head)]
    if not e:
        return "NO SUCH ENTRY"
    return [v[2] for v in violations(fixture_html, e[0])]


DIRECT = ("<p>Use the ~10% energy-transfer figure to estimate how much of the "
          "producers' energy reaches your top predator.</p>")
ck("it catches the figure used directly, in prose", scan(DIRECT), scan(DIRECT))

# food-web's actual wording, which never says "transfer". The first version of
# this fixture wrote "energy transfer loss", handing the checker a head word the
# real page did not contain -- and a mutant that reduced the subject vocabulary
# to the entry's head alone then survived, because the fixture no longer needed
# the definition sentence the real defect needs.
COMPLEMENT = ("<script>var t=' A chain of 5 levels is long for nature - energy loss "
              "(~90% per level) usually caps chains at 4-5.';</script>")
ck("it catches the SAME claim stated as the complement, inside a script string",
   scan(COMPLEMENT), scan(COMPLEMENT))

# The spread figures are the range of what has been MEASURED, not a menu of
# better constants. Reasoning from the top of the range as though it were one
# is the same defect as reasoning from the convention.
UPPER = ("<p>Use the 40% transfer efficiency to estimate how much of the "
         "producers' energy reaches the top predator.</p>")
ck("reasoning from the measured upper end is the same error, and is caught",
   scan(UPPER), scan(UPPER))

ck("a page that merely mentions the figure without reasoning from it is left alone",
   not scan("<p>The transfer efficiency is often quoted as 10% in textbooks.</p>"),
   scan("<p>The transfer efficiency is often quoted as 10% in textbooks.</p>"))
ck("and one that hedges it is left alone",
   not scan("<p>Use the 10% transfer efficiency, treat it as a teaching convention.</p>"),
   scan("<p>Use the 10% transfer efficiency, treat it as a teaching convention.</p>"))
ck("an unrelated percentage is not swept up",
   not scan("<p>Use the 10% slope figure to estimate runoff.</p>"),
   scan("<p>Use the 10% slope figure to estimate runoff.</p>"))

ck("the complement rule is what makes 90% reachable from a 10% entry",
   "90" in complements({"10"}) and "10" in complements({"90"}), complements({"10"}))
ck("and it does not invent a complement for an out-of-range figure",
   complements({"150"}) == {"150"}, complements({"150"}))

ck("script string literals reach the scanner at all",
   any(t[0] == "script" for t in sentences(COMPLEMENT)), "")
ck("and page code that is not a string does not",
   not any("getElementById" in t[1] for t in
           sentences("<script>var x=document.getElementById('a');</script>")), "")

# The block is the unit, and the page is not. A hedge in the SAME list item
# excuses the sentence; a hedge in a different block does not.
SAME_BLOCK = ("<li>Take 10% transfer per level and estimate the energy reaching the top "
              "predator. It is a teaching convention, not a constant.</li>")
ck("a hedge elsewhere in the same block excuses the sentence",
   not scan(SAME_BLOCK), scan(SAME_BLOCK))
OTHER_BLOCK = ("<p>Efficiency is a teaching convention, not a constant.</p>"
               "<li>Take 10% transfer per level and estimate the energy reaching the top predator.</li>")
ck("a hedge in a DIFFERENT block does not", scan(OTHER_BLOCK), scan(OTHER_BLOCK))

# =========================================================================
# RULE 2 -- a figure that carries a citation somewhere must not appear
# uncited elsewhere.
#
# Rule 1 above anchors on the glossary. That anchor was too narrow, and the
# kit proved it: `stand-sheet` states
#
#     Stand Density Index (Reineke 1933)   SDI = N (QMD/25)^1.605
#     Metric form, 25 cm reference. Derived for even-aged single-species
#     stands -- treat it as indicative in mixed uneven-aged forest.
#
# while `ecology-field-card` shipped the same formula with no citation and
# added a threshold stand-sheet never claims: ">55% of max means
# competition-driven mortality has begun", stated as a universal fact. The
# literature puts the onset of imminent competition mortality at 0.55 of
# maximum for lodgepole pine and 0.45 for white spruce -- species-specific --
# with ~35% the lower limit of full site occupancy and ~60% the lower limit
# of self-thinning (Long & Daniel 1990).
#
# Same defect class as rule 1, and rule 1 could not see it, because the
# researched position lived on a bench page rather than in the glossary.
# Only 18 of the kit's 31 citations are in the glossary.
#
# WHAT COUNTS AS A FIGURE HERE
#
# A first attempt matched any figure of three or more significant digits and
# returned 49 hits, of which one was real: 100, 180, 225 and 0.05 are slider
# maxima, compass bearings, CSS widths and p-value cutoffs, and they are
# everywhere. Distinctiveness is not magnitude -- it is that nobody writes the
# number by accident. A fingerprint is a decimal carrying three or more
# decimal places, or two that do not end in 0 or 5. On this kit exactly one
# figure qualifies, which is honest about the rule's reach: it is narrow, and
# it caught the one thing in range.
# Two alternatives, not three. The kit writes citations three ways --
# "(Reineke 1933)", "<span class=\"who\">Lindeman 1942</span>", and a bare
# "after Reineke 1933" in running prose -- but the bare pattern already matches
# the author-year inside the parentheses, so a separate parenthesised
# alternative was pure decoration: a mutation sweep deleted it and nothing
# noticed, because every test string still matched through the bare form.
#
# The span form is NOT redundant, and a fixture below says why: one glossary
# entry cites a year with no author at all, which the bare form -- which
# requires a capitalised author immediately before the year, so that a date
# like "the 2026-08-09 audits" is not mistaken for a citation -- cannot see.
CITE = re.compile(
    r"<span class=\"who\">([^<]*(?:19|20)\d{2}[^<]*)</span>"
    r"|\b([A-Z][A-Za-z.\-]{2,}(?:\s+(?:et\s+al\.|and|&amp;|&)\s+[A-Z][A-Za-z.\-]+)?"
    r"\s+(?:19|20)\d{2})\b")
DECIMAL = re.compile(r"(?<![\w.-])(\d+\.\d{2,})(?![\w])")
NEAR = 180


def fingerprint(v):
    frac = v.split(".")[1]
    return len(frac) >= 3 or frac[-1] not in "05"


def bare(text):
    return re.sub(r"<style\b.*?</style>", " ", text, flags=re.S | re.I)


def cited_figures(page_map):
    """figure -> {(page, citation)} for every fingerprint near a citation."""
    out = {}
    for name, html in page_map.items():
        t = bare(html)
        for m in CITE.finditer(t):
            window = TAG.sub(" ", t[max(0, m.start() - NEAR):m.end() + NEAR])
            for f in DECIMAL.finditer(window):
                if fingerprint(f.group(1)):
                    out.setdefault(f.group(1), set()).add(
                        (name, (m.group(1) or m.group(2)).strip()))
    return out


def uncited_uses(page_map, figure, homes):
    out = []
    for name, html in page_map.items():
        if name in homes:
            continue
        t = TAG.sub(" ", bare(html))
        for f in re.finditer(r"(?<![\w.-])%s(?![\w])" % re.escape(figure), t):
            if CITE.search(t[max(0, f.start() - NEAR):f.end() + NEAR]):
                continue
            out.append((name, " ".join(t[max(0, f.start() - 90):f.end() + 60].split())))
            break
    return out


CITED = cited_figures(pages)
ck("the kit has at least one cited fingerprint figure -- else rule 2 is vacuous",
   bool(CITED), sorted(CITED))

loose = []
for fig, where in sorted(CITED.items()):
    loose += [(fig, n, c) for n, c in uncited_uses(pages, fig, {p for p, _ in where})]
ck("no cited figure appears uncited on another page", not loose,
   [(f, n, c[:70]) for f, n, c in loose])

# Fixtures for rule 2, in both directions.
FIX = {"a.html": '<p>The exponent (Reineke 1933) is 1.605 in the metric form.</p>',
       "b.html": '<p>Use N(QMD/25)^1.605 to get stocking.</p>'}
ck("rule 2 catches a fingerprint used without its citation",
   uncited_uses(FIX, "1.605", {"a.html"}), "")
FIX_OK = dict(FIX, **{"b.html": '<p>N(QMD/25)^1.605, after Reineke 1933.</p>'})
ck("and leaves it alone once the citation travels with it",
   not uncited_uses(FIX_OK, "1.605", {"a.html"}), uncited_uses(FIX_OK, "1.605", {"a.html"}))
ck("a round two-decimal number is not a fingerprint",
   not fingerprint("0.05") and not fingerprint("1.10"), "")
ck("but three decimals is, and so is a two-decimal odd ending",
   fingerprint("1.605") and fingerprint("11.28"), "")
ck("every citation form the kit uses is read",
   bool(CITE.search("(Reineke 1933)"))
   and bool(CITE.search('<span class="who">Lindeman 1942</span>'))
   and bool(CITE.search("after Reineke 1933,")), "")
ck("the span form earns its place: a year with no author is still a citation",
   bool(CITE.search('<span class="who">1908</span>'))
   and not re.search(r"\b[A-Z][A-Za-z.\-]{2,}\s+(?:19|20)\d{2}\b", "<span>1908</span>"), "")
ck("and a bare date is not mistaken for a citation",
   not CITE.search("the 2026-08-09 audits") and not CITE.search("window: 2000 operations"), "")

# =========================================================================
# RULE 3 -- ADR-031's own category-2 list, enforced (ADR-057)
# =========================================================================
# ADR-031 sorts every displayed number into three gates, and gate 2 reads:
#
#     Ship it labelled a convention -- widely used, useful, but arbitrary or
#     contested. Examples: ... the 30-300 plate window; 20-50 cells per
#     haemocytometer square; 40-45 deg C for drying fungal vouchers. The word
#     conventional must appear beside it.
#
# Nothing checked it. Micro Bench spends a paragraph on whose window 30-300
# actually is ("There is no single countable range"), and the glossary, the
# field card and the landing page each state the same figure as "the 30-300
# rule" -- flat, unqualified, and read by more people than the paragraph is.
# That is ADR-051's defect (the kit contradicting itself) in a shape rule 1
# cannot see, because rule 1 anchors on a hedged PERCENTAGE and this is a
# hedged RANGE.
#
# THE ANCHOR IS THE POLICY, NOT A LIST I WROTE
#
# The figures are read out of ADR-031's own category-2 paragraph. A list
# retyped here would be a second copy of the policy, free to drift from it,
# and ADR-039 is about exactly that. Add a figure to the ADR and this rule
# starts enforcing it with no edit here.
#
# WHY NOT THE LITERAL WORD "conventional"
#
# The ADR asks for a word; what it wants is a reader able to tell a convention
# from a constant. fungal-characters says 40-45 deg C is "a starting point to
# adapt, not a standard", which does that job and never says "convention".
# Enforcing the token would have forced an edit that made honest prose worse,
# so this accepts the same vocabulary rule 1 uses, plus the word itself. The
# ADR's wording is the narrow thing here, and ADR-057 says so rather than
# having this file quietly disagree with it.
LABEL = re.compile(HEDGE.pattern + r"|convention|usual working compromise|"
                   r"starting point to adapt|rules? of thumb|no single\b", re.I)

DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
RANGE = re.compile(r"(?<![\w.-])(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)(?![\w.-])")
CAT2 = re.compile(r"Ship it labelled a convention</strong>(.*?)<p>3\.", re.S)
# Block-level tags only. A first version split on EVERY tag, so "<b>20-50</b>
# cells per square" became a block holding just the figure, cut off from the
# sentence that labels it -- and eight of ten reported violations were that
# artefact. Inline markup stays inside its block and plain() removes it.
# <td> is deliberately absent. A field-card row is "metric | what it reads",
# and a reader reads the row; splitting the cells would put the figure in one
# block and the sentence describing it in the next, so the only way to satisfy
# the rule would be to cram the label into the narrow nowrap metric cell. The
# row is the unit, exactly as <dt>+<dd> is.
BLOCKTAG = re.compile(r"<(/?)((?:li|p|div|dd|dt|section|tr|ul|ol|h[1-6]))\b[^>]*>", re.I)
HEADING = re.compile(r"h[1-6]$|^dt$", re.I)
POLICY = "adr-031.html"


def dashed(text):
    """Every dash a reader sees as a range dash, written the one way.

    The kit uses &ndash;, a literal en dash and a hyphen interchangeably. A
    first version normalised only the entity, read ADR-031's own example list
    as containing NO ranges, and reported a clean kit -- passing on nothing,
    which is the failure mode ADR-039 names."""
    return plain(text).translate(DASHES)


def convention_windows():
    """The ranges ADR-031 itself files under 'ship it labelled a convention'."""
    src = io.open(os.path.join(DOCS, POLICY), encoding="utf-8").read()
    m = CAT2.search(src)
    if not m:
        return []
    return [(a, b) for a, b in RANGE.findall(dashed(m.group(1))) if float(b) > float(a)]


def blocks(html):
    """The smallest unit a reader takes in at once, with headings attached.

    A heading is not a claim and not a block: <h3>The 30-300 window</h3> names
    the prose under it, and a glossary <dt> names its <dd>. So a heading's text
    PREFIXES the next block rather than standing alone -- which is also what
    makes the glossary catchable, since the entry titled "30-300 rule" has the
    figure in its <dt> and the words in its <dd>.

    A <div class="card"> holding five paragraphs is NOT one unit. ADR-051 chose
    block scope over page scope so a disclaimer at the top could not excuse
    everything below; a disclaimer three paragraphs BELOW excuses nothing above
    it for the same reason."""
    src = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    raw, tag, pos = [], "", 0
    for m in BLOCKTAG.finditer(src):
        raw.append((tag, dashed(src[pos:m.start()])))
        tag, pos = ("" if m.group(1) else m.group(2).lower()), m.end()
    raw.append((tag, dashed(src[pos:])))

    out, carry = [], ""
    for t, text in raw:
        if not text:
            continue
        if HEADING.match(t or ""):
            carry = (carry + " " + text).strip()
            continue
        out.append((carry + " " + text).strip() if carry else text)
        carry = ""
    if carry:                     # a heading with nothing under it still counts
        out.append(carry)
    return out


def states(text, fig):
    a, b = fig
    return re.search(r"(?<![\w.-])%s\s*-\s*%s(?![\w.-])" % (re.escape(a), re.escape(b)), text)


def unlabelled(pages, figs):
    """(page, figure, text) wherever a category-2 figure is stated with no label."""
    out = []
    for name, html in sorted(pages.items()):
        if name == POLICY:          # the policy names them all; that is its job
            continue
        for text in blocks(html):
            for fig in figs:
                if states(text, fig) and not LABEL.search(text):
                    out.append((name, "%s-%s" % fig, text))
    return out


WINDOWS = convention_windows()
ck("ADR-031's category-2 list parses into figures",
   len(WINDOWS) >= 3, WINDOWS)
ck("and 30-300, the window this rule was written for, is one of them",
   ("30", "300") in WINDOWS, WINDOWS)

# The detector, against pages built to fail and to pass. Fixtures first: a
# rule proved only against the kit passes the moment the kit is fixed, and
# then goes on passing whatever anyone writes next.
BARE_PAGE = {"x.html": "<p>Plates are counted under the 30-300 rule.</p>"}
LBL_PAGE = {"x.html": "<p>The 30-300 window is a convention, not a constant.</p>"}
FAR_PAGE = {"x.html": "<p>It is a convention.</p><p>Count under the 30-300 rule.</p>"}
HEAD_PAGE = {"x.html": "<h3>The 30-300 window</h3><p>No single range exists.</p>"}
HEAD_BARE = {"x.html": "<h3>The 30-300 window</h3><p>Plates outside it are excluded.</p>"}
DT_BARE = {"x.html": "<dt>30-300 rule</dt><dd>Only plates in that window count.</dd>"}
INLINE = {"x.html": "<p><b>30-300</b> is the teaching convention here.</p>"}
ck("a bare category-2 figure is caught", len(unlabelled(BARE_PAGE, WINDOWS)) == 1,
   unlabelled(BARE_PAGE, WINDOWS))
ck("a labelled one is not", not unlabelled(LBL_PAGE, WINDOWS),
   unlabelled(LBL_PAGE, WINDOWS))
ck("a label in a DIFFERENT block does not excuse it -- that is page scope",
   len(unlabelled(FAR_PAGE, WINDOWS)) == 1, unlabelled(FAR_PAGE, WINDOWS))
ck("a heading reads with the prose under it, so its label counts",
   not unlabelled(HEAD_PAGE, WINDOWS), unlabelled(HEAD_PAGE, WINDOWS))
ck("and a heading over UNLABELLED prose is still caught",
   len(unlabelled(HEAD_BARE, WINDOWS)) == 1, unlabelled(HEAD_BARE, WINDOWS))
ck("a glossary term states the figure and its definition must label it",
   len(unlabelled(DT_BARE, WINDOWS)) == 1, unlabelled(DT_BARE, WINDOWS))
ck("inline markup does not orphan a figure from its own sentence",
   not unlabelled(INLINE, WINDOWS), unlabelled(INLINE, WINDOWS))
ROW_OK = {"x.html": "<tr><td>30-300 rule</td><td>a convention, not a constant</td></tr>"}
ROW_BARE = {"x.html": "<tr><td>30-300 rule</td><td>plates outside it are excluded</td></tr>"}
ck("a table row is one unit: a label in the description cell counts",
   not unlabelled(ROW_OK, WINDOWS), unlabelled(ROW_OK, WINDOWS))
ck("and a row with no label anywhere in it is caught",
   len(unlabelled(ROW_BARE, WINDOWS)) == 1, unlabelled(ROW_BARE, WINDOWS))
ck("a figure ADR-031 does not list is not policed",
   not unlabelled({"x.html": "<p>Count under the 77-999 rule.</p>"}, WINDOWS), "")
ck("the policy page itself is exempt -- listing them is what it is for",
   not unlabelled({POLICY: "<p>the 30-300 plate window</p>"}, WINDOWS), "")
# Dash forms, all three, because the kit writes all three and a normaliser
# that handles one is a checker that reads a third of the kit.
for label, page in (("entity", "<p>the 30&ndash;300 rule</p>"),
                    ("literal en dash", "<p>the 30–300 rule</p>"),
                    ("hyphen", "<p>the 30-300 rule</p>")):
    ck("a bare figure written with a %s is caught" % label,
       len(unlabelled({"x.html": page}, WINDOWS)) == 1, page)

BARE_KIT = unlabelled(pages, WINDOWS)
ck("no page states an ADR-031 category-2 figure without labelling it",
   not BARE_KIT, [(n, f, t[:70]) for n, f, t in BARE_KIT])


print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
