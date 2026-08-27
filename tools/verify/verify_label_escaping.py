# -*- coding: utf-8 -*-
"""Guards the one input that reaches an UNESCAPED path on old published pages.

WHY THIS EXISTS, AND WHY IT IS NOT AN ESCAPING AUDIT

The kit already has two escaping instruments: audit_escaping types markup into
every text field and watches what comes back, and each page's own suite drives
its render paths. Both test the CURRENT code. Neither can say anything about the
copies of this kit that are already published.

Twenty-six published pages are of unknown vintage and eleven are measurably
behind. Spot-checking one -- Breeding Bench -- found it serving Field Entry Kit
v1.1.1, whose dial builds an option as

    '<span>' + op.label + '</span>'

with no escaping. That is the exact defect ADR-031 fixed in v1.2.0, and it is
live on an unknown number of URLs that people have been given.

WHAT WAS ACTUALLY MEASURED

Before spending several million tokens republishing every page, the question
worth asking is whether that defect can FIRE. My first answer -- reached by
grepping for angle brackets and stopping -- was that it cannot. That answer was
wrong, and this file is what overturned it: cp-bench maps user-typed plant names
and cross parents straight into picker labels, and its published copy was on
v1.1.1.

The sentence that stood here for four ADRs -- "every option list in this kit is
built from a page constant, never from typed input" -- was also wrong, and it
was wrong about FIVE pages. ADR-069 found them: selection-log pushes a typed
trait name and unit into an ALL-CAPS table, collection-sheet replaces its whole
genus table from a file the user loads, survey-design puts typed event names in
a sub-label. The convention was never a guarantee, and a docstring is not a
check. The detector in tools/reach.py is, and section 2 below asserts its
answer.

ADR-031's original injection was `Sarracenia <hybrid>`: a TAXON NAME carrying
angle brackets, sitting in a constant table. Not user input at all.

WHAT THIS FILE DOES AND DOES NOT COVER

Sections 1 to 4 are properties of the SOURCE and are byte-insensitive, so a
mutation sweep can use them as witnesses. The requirement that a reachable
page be published CURRENT is a property of the published copy, and lives in
verify_publish_reach.py -- see section 5 for why that separation is not
tidiness.

Run:  python3 tools/verify/verify_label_escaping.py
"""
import glob, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS = os.path.join(ROOT, "docs")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


# The detector and its tracer live in tools/reach.py, imported here and by
# verify_publish_reach.py -- one tracer, two readers, and no second copy to
# drift. A drifted tracer fails OPEN: it calls typed input a constant.
sys.path.insert(0, os.path.join(ROOT, "tools"))
import reach as _reach
LABEL, ANGLE, DYNAMIC = _reach.LABEL, _reach.ANGLE, _reach.DYNAMIC
roots_in_constant, grows_at_runtime = _reach.roots_in_constant, _reach.grows_at_runtime

pages = sorted(glob.glob(os.path.join(DOCS, "*.html")))
ck("there are pages to check", len(pages) > 20, len(pages))

# --- 1. labels that CONTAIN angle brackets -------------------------------
angled = _reach.angled_pages(pages)
ck("the pages carrying angle-bracket labels are known and listed",
   set(angled) <= {"releve.html"}, angled)
ck("and there is at least one, so this check is not vacuous", bool(angled), angled)

# --- 2. option lists built from RUNTIME data -----------------------------
runtime = _reach.runtime_pages(pages)
ck("some pages build option lists at runtime, so this check is not vacuous",
   any(DYNAMIC.search(io.open(q, encoding="utf-8").read()) for q in pages), "")
# The tracer gets its own fixtures, because a tracer that silently resolves
# the wrong binding fails OPEN -- it calls typed input a constant.
_sb = io.open(os.path.join(DOCS, "soil-bench.html"), encoding="utf-8").read()
_at = _sb.index("options:n.a")
ck("the tracer resolves a local bound to a constant table (soil-bench's n=TEX[node])",
   roots_in_constant("n", _sb, _at), "")
ck("and it does NOT resolve a local bound to anything else",
   not roots_in_constant("n", "var n = userTyped.trim();\nuse(n)", 40), "")
# The binding that actually governs is the nearest PRECEDING one. Both of these
# exist in soil-bench; picking either by file order rather than by position is
# how the first version got it wrong in both directions.
_fix = "var n=typedByUser;\n/*...*/\nvar n=TEX[node];\noptions:n.a"
ck("the tracer takes the nearest preceding binding, not the first in the file",
   roots_in_constant("n", _fix, _fix.index("options:n.a")), "")
_fix2 = "var n=TEX[node];\n/*...*/\nvar n=typedByUser;\noptions:n.a"
ck("and it is not fooled when the constant binding is the one that got shadowed",
   not roots_in_constant("n", _fix2, _fix2.index("options:n.a")), "")
# Five, not one. The first version of this check required `.map(` at the
# options site itself and treated any ALL-CAPS name as a constant, and both
# assumptions were wrong on real pages in this kit:
#
#   selection-log   `options:opts`, opts = traitOptions(), which maps TRAITS --
#                   and the "add trait" button PUSHES a typed name and unit
#                   into TRAITS. ALL-CAPS, and not a constant.
#   collection-sheet  PACK starts as GENERA.slice() and is REPLACED wholesale
#                   from a genus pack the user loads from a file. A label out
#                   of a file that came from anywhere.
#   pheno-tracker, survey-design  plants, crosses, events -- typed, then mapped
#                   straight into picker labels and subs.
#
# Every one was checked by opening the page, not by trusting the tracer. Each
# is safe on FEK v1.3.0, which escapes option labels; each is a page whose
# STALE published copy would render typed text as markup, which is what
# section 5 turns into a requirement.
_expect = {"collection-sheet.html": ["opts"], "cp-bench.html": ["crosses", "plants"],
           "pheno-tracker.html": ["opts"], "selection-log.html": ["opts"],
           "survey-design.html": ["opts"]}
ck("the pages feeding runtime data into option labels are known and listed",
   {k: sorted(set(v)) for k, v in runtime.items()} == _expect,
   {k: sorted(set(v)) for k, v in runtime.items()})

# Fixtures for the two capabilities added above. Both fail OPEN if wrong --
# they would call typed input a constant -- so neither goes in without a
# canary of its own.
_hop = ("var T=[1];\nfunction f(){ return T.map(g); }\nvar opts=f();\noptions:opts")
ck("the tracer follows one hop through a helper that returns a constant table",
   roots_in_constant("opts", _hop, _hop.index("options:opts")), "")
_hop2 = ("function f(){ return typed.map(g); }\nvar opts=f();\noptions:opts")
ck("and not through one that returns something else",
   not roots_in_constant("opts", _hop2, _hop2.index("options:opts")), "")
_grow = "var T=[1];\nT.push(x);\noptions:T"
ck("an ALL-CAPS table that is pushed to is not a constant",
   not roots_in_constant("T", _grow, _grow.index("options:T")), "")
_grow2 = "var T=[1];\nvar y=T.slice();\noptions:T"
ck("and one that is only read from still is",
   roots_in_constant("T", _grow2, _grow2.index("options:T")), "")
_grow3 = "var T=[1];\nif(T==x){}\noptions:T"
ck("a comparison is not a write",
   roots_in_constant("T", _grow3, _grow3.index("options:T")), "")

# --- 3. the component escapes both halves --------------------------------
fek = io.open(os.path.join(ROOT, "tools", "fek.py"), encoding="utf-8").read()
# COUNTED, not `in`. The dial and the picker each escape both halves, so an
# `in` test still passes after one of the four is removed -- which is exactly
# what a seeded mutation did: it dropped one escv(op.sub) and this check stayed
# green. Every interpolation of a caller-supplied option string is counted.
n_label = fek.count("escv(op.label)")
n_sub = fek.count("escv(op.sub)")
# Three, not two: the dial, the chips and the picker each render a label.
# Writing 2 here would have been a number I assumed rather than counted, and it
# would have failed on working code the moment anyone looked.
ck("every dial, chip and picker option LABEL is escaped (%d sites)" % n_label,
   n_label == 3, n_label)
ck("every dial and picker option SUB is escaped (%d sites)" % n_sub,
   n_sub == 2, n_sub)
ck("no option string is interpolated raw anywhere in the module",
   not re.search(r"\+\s*op\.(label|sub)\b", fek),
   [l.strip()[:60] for l in fek.split("\n") if re.search(r"\+\s*op\.(label|sub)\b", l)][:3])
ck("the unescaped v1.1.1 form is gone from the module",
   "'<span>'+op.label+'</span>'" not in fek, "")

# --- 3b. and no CALLER escapes a label the component already escapes ------
# The other direction, and the one that actually bit. FEK escapes an option
# label deliberately, "rather than at each call site, because a component whose
# safety depends on every caller remembering is a component that will bite
# somebody" -- its own comment. Two call sites escaped anyway, and the entity
# reached the screen: selection-log's trait chip read `girth (&quot;)` while the
# trait list two inches below it read `girth"`. The same unit, two spellings,
# one page. Nobody saw it for months because both are "escaped" and the eye
# reads &quot; as a quote.
#
# A component's OWN label is different -- it is authored markup, and
# pheno-tracker's dial passes `FEK.esc(t.n)+'<span class="u">…'` on purpose.
# So this matches only an OPTION literal: a line carrying `value:` alongside a
# `label:`/`sub:` that calls an escaper. That shape is what found both, and it
# is narrow enough that the dial's authored label cannot match it.
# The shape is an OPTION LITERAL: a brace-bounded object carrying `value:`
# alongside a `label:` or `sub:` that calls an escaper. Brace-bounded and
# comment-stripped, both learned the hard way:
#
#   The first version was one line, anchored with re.M. Fixing selection-log
#   split the return across three lines with an explanatory comment, and the
#   rule went blind to the very line it was written for -- re-seeding the
#   defect afterwards passed 22/22. A canary that cannot fail is not a canary.
#
#   Stripping comments matters for the same edit: the comment I added SAYS
#   "NOT esc()", so a rule that reads comments flags the fix as the defect.
#
# `[^{}]*` keeps it inside one literal and cannot run away across a file; it
# also means a CONTROL's own options -- `FEK.dial({label:..., options:[{...}]})`
# -- never match, because that object has nested braces. Measured across all
# thirty-nine pages: zero hits clean, one hit with the defect re-seeded.
OPT_LITERAL = re.compile(r"\{[^{}]*\}", re.S)
HAS_VALUE = re.compile(r"\bvalue\s*:")
ESCAPED_LABEL = re.compile(r"\b(?:label|sub)\s*:[^,}]*?\b(?:FEK\.)?esc\w*\(", re.S)
_BLOCK_C = re.compile(r"/\*.*?\*/", re.S)
_LINE_C = re.compile(r"(^|[^:])//[^\n]*")


def decomment(t):
    return _LINE_C.sub(lambda m: m.group(1), _BLOCK_C.sub(" ", t))


def pre_escaped(src):
    """Option literals that escape a label the component escapes for them."""
    out = []
    for m in OPT_LITERAL.finditer(src):
        t = decomment(m.group(0))
        if HAS_VALUE.search(t) and ESCAPED_LABEL.search(t):
            out.append(re.sub(r"\s+", " ", t).strip()[:80])
    return out


pre_escaped_pages = {}
for p_ in pages:
    hits = pre_escaped(io.open(p_, encoding="utf-8").read())
    if hits:
        pre_escaped_pages[os.path.basename(p_)] = hits
ck("no page escapes an option label that FEK escapes for it",
   not pre_escaped_pages, pre_escaped_pages)
# A rule nothing can trip is not a rule, and this one could not trip for an
# hour. The fixture is the line as it stood, in the shape it is in now.
_was = ('return {value:t.id,\n'
        '        /* NOT esc(): FEK escapes an OPTION label itself. */\n'
        '        label:t.name+(t.unit?" ("+esc(t.unit)+")":"")}; });')
ck("and the rule fires on the line that motivated it, split across lines",
   bool(pre_escaped(_was)), _was)
ck("it is not fooled by a comment that merely mentions esc()",
   not pre_escaped('return {value:t.id, /* not esc(label) here */ label:t.name};'), "")
ck("but not on a component's own authored label",
   not pre_escaped("FEK.dial({label:FEK.esc(t.n)+'<span>x</span>', value:v, "
                   "options:[{value:'1',label:'1'}]})"), "")

# --- 4. and no page in docs/ still carries the old form -------------------
stale = [os.path.basename(p) for p in pages
         if "'<span>'+op.label+'</span>'" in io.open(p, encoding="utf-8").read()]
ck("no page in docs/ still carries the unescaped dial", not stale, stale)

# --- 5. it used to live here, and it cost the four sections above --------
# "Every page where the injection is reachable is published current" is now
# tools/verify/verify_publish_reach.py. It compares each page against a digest,
# so it fails on ANY edit -- and a mutation sweep edits pages by construction,
# so ADR-070's guard threw this WHOLE suite out on all five reachable pages as
# "measuring bytes, not behaviour". It was right to. The cost was that sections
# 1 to 4, which are byte-insensitive and are the actual escaping rules, could
# not kill a single mutant on the pages that most need them.
#
# The reachable set both files work from is tools/reach.py, imported by each, so
# they cannot come to different conclusions about which pages those are
# (ADR-039). The fixtures for the tracer stay HERE: they are checks about
# whether the detector is right, and verify_publish_reach only consumes its
# answer.

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
