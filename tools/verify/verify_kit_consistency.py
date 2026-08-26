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

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
