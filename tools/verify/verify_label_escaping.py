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
v1.1.1. The general shape below still holds for the rest of the kit:

  * Every dial and picker option list in this kit is built from a page CONSTANT
    -- CROPS, GENERA, PHENO, TARGETS, CAMS, FEED -- never from typed input.
  * No option label in any page constant contains an angle bracket.

ADR-031's original injection was `Sarracenia <hybrid>`: a TAXON NAME carrying
angle brackets, sitting in a constant table. Not user input at all.

Where the fuse IS lit -- cp-bench, and releve's "<2 m" stratum labels -- this
check names it, and section 5 then requires those pages to be published current
rather than merely correct in the repo. It fails the moment a page constant
gains an angle bracket in a label, or a page starts feeding typed text into an
option list, or such a page falls behind its published copy.

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


# A label or sub-label written into a component option, anywhere in a page.
LABEL = re.compile(r'\b(?:label|sub)\s*:\s*"((?:[^"\\]|\\.)*)"')
ANGLE = re.compile(r"[<>]")

# An option list built by mapping over something at runtime.
DYNAMIC = re.compile(r'options\s*:\s*([A-Za-z_$][\w$.]*)\s*\.map\s*\(')

pages = sorted(glob.glob(os.path.join(DOCS, "*.html")))
ck("there are pages to check", len(pages) > 20, len(pages))

# --- 1. labels that CONTAIN angle brackets -------------------------------
# Banning them would be wrong: "<2 m" is a legitimate stratum height and
# "> 10 m" is its pair. What matters is that the component escapes them, and
# that a page carrying them is known to be one where a stale published copy
# renders visibly wrong.
angled = {}
for p in pages:
    src = io.open(p, encoding="utf-8").read()
    hits = sorted({m.group(1) for m in LABEL.finditer(src) if ANGLE.search(m.group(1))})
    if hits:
        angled[os.path.basename(p)] = hits[:6]
ck("the pages carrying angle-bracket labels are known and listed",
   set(angled) <= {"releve.html"}, angled)
ck("and there is at least one, so this check is not vacuous", bool(angled), angled)

# --- 2. option lists built from RUNTIME data -----------------------------
# This is the case that turns a display bug into an injection: typed text
# becoming a component label. The kit's convention is that an option list maps
# over an ALL-CAPS constant table; anything else is data whose contents no
# static check can vouch for.
#
# One assignment hop is followed before calling something runtime data.
# soil-bench maps `n.a`, and `n` is lower-case -- but two lines above sits
# `var n=TEX[node]`, so `n` IS the constant table, reached through a local.
# The first version of this check called soil-bench runtime data and then
# exempted it by NAME in a later section, with a hand-written detector that a
# canary walked straight past. Tracing the assignment is the same exemption
# made out of evidence, in the section that draws the conclusion, and it
# generalises to the next page that does this.
ASSIGN = r"\b(?:var|let|const)\s+%s\s*=\s*([A-Za-z_$][\w$.\[\]]*)"

def roots_in_constant(head, src, pos):
    """True if `head` at offset `pos` is an ALL-CAPS table, or reaches one.

    Scoped to the NEAREST PRECEDING binding, which is what a reader does. The
    first version searched the whole file for `var n=` and found
    `var n=parseFloat(x)` inside the FEK module -- a different `n`, hundreds of
    lines away, in another scope -- and concluded soil-bench was runtime data.
    A finder that matches the wrong binding is not a weaker check, it is a
    check of something else.
    """
    seen = set()
    while head and head not in seen:
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", head):
            return True
        seen.add(head)
        before = [m for m in re.finditer(ASSIGN % re.escape(head), src) if m.start() < pos]
        if not before:
            return False
        m = before[-1]                       # nearest preceding, not first in file
        pos = m.start()
        head = m.group(1).split(".")[0].split("[")[0]
    return False

runtime = {}
for p_ in pages:
    src = io.open(p_, encoding="utf-8").read()
    for m in DYNAMIC.finditer(src):
        head = m.group(1).split(".")[0]
        if not roots_in_constant(head, src, m.start()):
            runtime.setdefault(os.path.basename(p_), []).append(m.group(1))
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
ck("the pages feeding runtime data into option labels are known and listed",
   {k: sorted(set(v)) for k, v in runtime.items()}
   == {"cp-bench.html": ["crosses", "plants"]},
   {k: sorted(set(v)) for k, v in runtime.items()})

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

# --- 4. and no page in docs/ still carries the old form -------------------
stale = [os.path.basename(p) for p in pages
         if "'<span>'+op.label+'</span>'" in io.open(p, encoding="utf-8").read()]
ck("no page in docs/ still carries the unescaped dial", not stale, stale)

# --- 5. every page where the defect is REACHABLE is published current ------
# The earlier version of this check ended by asserting a "republish priority"
# built from sections 1 and 2 alone. That was wrong in a way worth recording:
# reachability is a property of the SOURCE, and staleness is a property of the
# PUBLISHED COPY, and nothing here had looked at a published copy. It named
# releve.html as priority; releve's live artifact was already serving FEK
# v1.3.0 with the escaping in place. The check was not measuring what its own
# sentence claimed.
#
# What it should assert is the crossing of the two: for every page where a
# stale copy would render typed text or an angle-bracket label as markup, the
# published copy must be STAMPED CURRENT. publish_state.py is the only thing
# in this repo that knows that, so this reads its state rather than restating
# section 1.
#
import json, hashlib, importlib.util

reach = set(angled) | set(runtime)

ck("the reachable set is not empty -- this check would be vacuous otherwise",
   bool(reach), sorted(reach))

# The publish bytes are recomputed IN MEMORY, through publish.py's own strip()
# and wire(), rather than by shelling out to it. Shelling out would have this
# suite write into build/publish/ as a side effect of being run -- a test that
# mutates the tree it is testing, which is exactly the mistake the mutation
# sweep made and had to be rebuilt to avoid. Recomputed, never a pinned digest:
# a legitimate edit to a page must not fail this check, only an UNSTAMPED one.
_spec = importlib.util.spec_from_file_location("_pub", os.path.join(ROOT, "tools", "publish.py"))
_pub = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_pub)
_base, _pages = _pub.load()

def publish_bytes(name):
    src = io.open(os.path.join(DOCS, name), encoding="utf-8").read()
    return _pub.wire(_pub.strip(src), _base, _pages).encode("utf-8")

# There is no reimplementation here to drift: strip() and wire() ARE
# publish.py's, imported. What can go wrong is importing something else --
# a stub, a stale copy, a module that silently lacks them -- and then hashing
# bytes no publisher would ever produce. So the check is on the provenance of
# the functions, not on a file that may simply be an unrebuilt build dir.
#
# The first version of this check compared against build/publish/cp-bench.html
# and called that "reproduces publish.py's output byte for byte". It did not:
# it measured whether the build directory was fresh, and fired on a canary that
# only edited a page. Naming a check for something it does not measure is the
# same error section 5 was rewritten to fix, two checks apart.
ck("strip and wire are publish.py's own, not a local reimplementation",
   getattr(_pub.strip, "__module__", "") == "_pub"
   and getattr(_pub.wire, "__module__", "") == "_pub"
   and os.path.samefile(_pub.__file__, os.path.join(ROOT, "tools", "publish.py")),
   getattr(_pub, "__file__", None))
ck("and the publish transform is not a no-op on these pages",
   publish_bytes("cp-bench.html")
   != io.open(os.path.join(DOCS, "cp-bench.html"), "rb").read(), "")

stamps = json.load(io.open(os.path.join(ROOT, "tools", "published.json"), encoding="utf-8"))["pages"]
not_current = []
for n in sorted(reach):
    digest = hashlib.sha256(publish_bytes(n)).hexdigest()
    if n not in stamps:        not_current.append((n, "never stamped"))
    elif stamps[n] != digest:  not_current.append((n, "behind"))
ck("every page where the injection is reachable is published current",
   not not_current, not_current)

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
