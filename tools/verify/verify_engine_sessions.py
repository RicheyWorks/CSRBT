# -*- coding: utf-8 -*-
"""Do the flagship page's numbers actually come from the engine?

CSRBT is a Java ordered-set engine. `docs/ecology-lab.html` is the page that
shows what it does, and its headline sentence reads

    "80% of keys survive a generation, but only 57% of the physical nodes --
     the gap is the price of path copying"

Those two figures are not written in the prose. The page interpolates them from
a recorded session inlined at `const SESSION = {...}`, which is a copy of
`docs/ecology-lab-session.json`, which is supposed to be the output of
`EcologyFieldDay.run().json()` in csrbt-experimental.

Three links, and until this file **nothing checked any of them**:

    engine  ->  docs/ecology-lab-session.json  ->  inline copy  ->  rendered prose

EcologyFieldDayTest asserts the JSON is byte-deterministic across two runs and
that its braces balance. Both true of a JSON the engine has never seen. The
shipped artifact could have been hand-edited, or the engine could have moved
underneath it, and every suite in the kit would still be green -- which is the
FEK emitter problem (a generated value inlined in a page, with no check binding
the two) one layer further down, at the boundary between the docs and the
system they describe.

Measured, not assumed: the engine's output is byte-identical to the shipped file
today. That is a fact with a date on it, and this file is what keeps it true.

WHAT UNVERIFIED MEANS HERE

Link A needs a compiled engine. Where it cannot run, this suite says so and
reports a SHORT score -- run_all cross-checks the score against the total and
marks a shortfall, so "could not check" surfaces instead of passing quietly. A
fresh clone needs one `./gradlew classes` before this link can be verified.

Run:  python3 tools/verify/verify_engine_sessions.py
"""
# Declared for tools/mutate.py: the temp dir here holds two fixture .java files used only to digest a rename, not fixture pages (ADR-139)
MUTATE_ROLE = "subject"

import decimal, glob, io, json, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kit

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS = os.path.join(ROOT, "docs")
PAGE = os.path.join(DOCS, "ecology-lab.html")
SHIPPED = os.path.join(DOCS, "ecology-lab-session.json")

ok = bad = 0
unverified = []
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


def inline_session(page_src):
    """The JSON the page actually ships, pulled out by brace matching.

    A regex would be wrong: the blob contains braces in string values, and the
    point of this check is that the page's copy is REAL JSON that parses to the
    same object -- not that some bytes look similar.
    """
    i = page_src.index("const SESSION = ")
    start = page_src.index("{", i)
    depth = 0
    in_str = False
    esc = False
    for k in range(start, len(page_src)):
        c = page_src[k]
        # String-aware. A plain brace counter stops at the first "}" inside a
        # string value; the fixture below is what found that, before shipping.
        # Today's session happens to carry no brace in any string, so link B
        # passed and would have gone on passing until one did.
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return page_src[start:k + 1]
    raise ValueError("unterminated SESSION object")


# ADR-139: ONE implementation of "run the engine", in tools/engine_attest.py,
# because there are now two consumers -- this suite, and the attestation the
# suite falls back to. Two copies of a classpath hunt is how the two disagree.
sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import engine_attest as EA
classpath = EA.classpath


def engine_json():
    return EA.engine_output("docs/ecology-lab-session.json")


page = io.open(PAGE, encoding="utf-8").read()
shipped_txt = io.open(SHIPPED, encoding="utf-8").read()
shipped = json.loads(shipped_txt)

# ---- link B: shipped file -> the copy the page ships ---------------------
raw = inline_session(page)
ck("the page's inlined SESSION is valid JSON on its own",
   isinstance(json.loads(raw), dict), raw[:60])
ck("and it is the same object as docs/ecology-lab-session.json",
   json.loads(raw) == shipped,
   sorted(set(json.loads(raw)) ^ set(shipped)) or "same keys, different values")

# ---- link A: engine -> shipped file --------------------------------------
txt, why = engine_json()
if why:
    # THE LIVE PATH IS PREFERRED AND IT IS NOT AVAILABLE HERE. What is left is
    # the attestation (ADR-139): a dated record, written only by a machine that
    # RAN the engine, saying what it emitted and digesting the engine's sources
    # as they stood. It is evidence exactly while those sources have not moved,
    # and it says which of the two it is rather than passing quietly as the
    # stronger one.
    kind, awhy = EA.check("docs/ecology-lab-session.json", shipped_txt)
    if kind == "attested":
        ck("the shipped session is what the engine emitted -- ATTESTED, not run here (%s; %s)"
           % (awhy, why), True)
    elif kind == "differs":
        ck("the shipped session is what the engine emitted (attested)", False, awhy)
    else:
        unverified.append("engine -> docs/ecology-lab-session.json (%s; and %s)" % (why, awhy))
        print("UNVERIFIED  the shipped session is the engine's output   (%s)" % why)
else:
    ck("the shipped session is byte-for-byte what the engine emits today",
       txt == shipped_txt,
       "parsed-equal but bytes differ" if json.loads(txt) == shipped else "content differs")
    # the attestation is only ever written by a run of the engine, so a live run
    # that agrees with it is also the check that the record is honest
    _kind, _awhy = EA.check("docs/ecology-lab-session.json", txt)
    ck("...and the attestation on record says the same thing this live run just did (%s)" % _awhy,
       _kind in ("attested", "absent", "stale"), (_kind, _awhy))
    ck("and the headline figures are the engine's, not the page's",
       json.loads(txt)["fossils"]["meanContent"] == shipped["fossils"]["meanContent"]
       and json.loads(txt)["fossils"]["meanStructural"] == shipped["fossils"]["meanStructural"],
       json.loads(txt)["fossils"])

# ---- link C: prose must DERIVE the figures, never restate them -----------
# The two headline numbers are interpolated: ${fmt(f.meanContent*100,0)}%. A
# hand-written "80%" beside them would read identically and would then be free
# to drift from the session it claims to describe.
def scalars(o, out):
    if isinstance(o, dict):
        for v in o.values(): scalars(v, out)
    elif isinstance(o, list):
        for v in o: scalars(v, out)
    elif isinstance(o, float) and 0 < o <= 1:
        out.add(round(o * 100))
    return out

pcts = scalars(shipped, set())
ck("the session carries figures that render as percentages", bool(pcts), sorted(pcts))

i = page.index("const SESSION = ")
rest = page[:i] + page[i + len(raw):]
# A real parse, script and style dropped (_kit.prose_of). What this replaced
# removed <style> and then bracket-stripped, so a page's mangled JavaScript
# stayed in "prose" -- a percentage sitting in script would have been reported
# as a restated literal, and any prose between a stray < and the next > was
# never searched at all. ADR-099.
prose = _kit.prose_of(rest)
# CSS widths are not claims; they are excluded by looking only outside <style>
# and by requiring the number not to be preceded by a colon or a quote.
literals = []
for p in sorted(pcts):
    for m in re.finditer(r"(?<![\w.:\"'-])%d\s*%%" % p, prose):
        literals.append((p, " ".join(prose[max(0, m.start() - 70):m.start() + 30].split())))
ck("no session figure is restated as a literal in the page's prose",
   not literals, literals[:4])

ck("the interpolation the prose actually uses is still there",
   "meanContent" in page and "meanStructural" in page
   and "${fmt(f.meanContent" in page, "")

# ---- link D: every OTHER document that quotes the headline pair ----------
# Link C bans a literal restatement inside ecology-lab.html. It says nothing
# about the next file that writes the same sentence, and two of them do: the
# field guide in markdown and its published HTML twin, which hand-write both
# figures in prose. That is ADR-072's shape -- the fix that names one caller
# does not cover the next one somebody writes -- and here the next one is a page
# a reader opens.
#
# Prose is allowed to quote a figure. What was missing is anything that fails
# when the quote drifts from the session, so this BINDS rather than bans:
# wherever the pair appears, the digits must be the digits the page renders.
#
# Dated records are exempt and named, not inferred: an ADR or changelog reports
# what was true on its date and must not be rewritten when the engine moves.
PAIR = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%\s*of keys.{0,90}?(\d{1,3}(?:\.\d+)?)\s*%\s*of\s*"
    r"(?:the\s*)?(?:physical\s*)?nodes", re.S | re.I)
DATED_RECORDS = ("ADR-", "CHANGELOG-", "AUDIT-", "SESSION-HANDOFF-")


def displayed(x, digits=1):
    """The digits the page will show for x*100 -- one shared implementation.

    This used to spell the rounding rule out here. It now borrows it from
    _kit.as_page_shows, because a second reader arrived (tools/audit_ties.py)
    and two copies of a rounding rule is the frozen-constant problem with a
    function instead of a number: they agree until one is edited. The rule
    itself, and the measured cases where Python's round() disagrees with it, are
    documented there.
    """
    return _kit.as_page_shows(x, digits, 100)


def is_rounding_tie(literal_text, digits):
    """Does this figure land EXACTLY on a .5 boundary at this display precision?

    Read from the JSON's own decimal literal, not from the double: 0.575000 is
    exactly 57.500 in decimal, and at 0 digits that is a tie. The page showed 57
    and every other document said 57, and they agreed only because the nearest
    double to 0.575 is 57.49999999999999 -- a coin flip that IEEE happened to
    win. Had the value been representable, JS would have shown 58 and the prose
    would still have said 57, with nothing in the kit noticing.

    A number displayed at a precision where it is a tie is not a reported
    figure, it is a coin flip between two implementations.
    """
    d = decimal.Decimal(literal_text) * 100
    return d == d.quantize(decimal.Decimal(1) if not digits
                           else decimal.Decimal(1).scaleb(-digits),
                           rounding=decimal.ROUND_FLOOR) + decimal.Decimal(5).scaleb(-digits - 1)


_LIT = re.compile(r'"meanStructural"\s*:\s*([0-9.]+)')
_lit = _LIT.search(shipped_txt)
ck("the session's own decimal literal for the structural figure is readable",
   _lit is not None, shipped_txt[:80])
if _lit:
    ck("the structural figure is NOT displayed at a precision where it is a tie",
       not is_rounding_tie(_lit.group(1), 1),
       "%s at 1 dp" % _lit.group(1))
    ck("...and it WOULD have been at the 0 dp this page used to render -- the "
       "agreement across the kit was a float-representation accident",
       is_rounding_tie(_lit.group(1), 0), _lit.group(1))

want = (displayed(shipped["fossils"]["meanContent"]),
        displayed(shipped["fossils"]["meanStructural"]))
quoting, drifted = [], []
for f in sorted(glob.glob(os.path.join(DOCS, "*"))):
    b = os.path.basename(f)
    if not os.path.isfile(f) or b.startswith(DATED_RECORDS) or b == "ecology-lab.html":
        continue
    try:
        raw_f = io.open(f, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        continue
    flat = _kit.prose_of(raw_f).replace("*", "")
    for m in PAIR.finditer(flat):
        quoting.append(b)
        if (m.group(1), m.group(2)) != want:
            drifted.append((b, m.group(1), m.group(2)))
ck("some document outside the lab page quotes the headline pair -- otherwise "
   "this check is asserting nothing", bool(quoting), quoting)
ck("every quote of the pair matches what the page renders (%s%% / %s%%)" % want,
   not drifted, drifted)

# The canary: seed the drift the check exists to catch, and a control beside it.
_GOOD = "in the demo, %s%% of keys survive a generation but only %s%% of physical nodes" % want
_BAD = "in the demo, %s%% of keys survive a generation but only 57%% of physical nodes" % want[0]
ck("CONTROL: a correct sentence is not reported as drift",
   [g.groups() for g in PAIR.finditer(_GOOD)] == [want], _GOOD)
ck("a sentence carrying the OLD figure is caught",
   [g.groups() for g in PAIR.finditer(_BAD)] != [want], _BAD)
ck("and the matcher survives markdown bold around the figures",
   [g.groups() for g in PAIR.finditer(
       ("in the demo, **%s%%** of keys survive but only **%s%%** of physical nodes"
        % want).replace("*", ""))] == [want], "")

# ---- the artifacts this does NOT bind ------------------------------------
# Named rather than implied covered. These are recorded sessions loaded by the
# visualizers; none has a deterministic run() this can call, so nothing here
# can say they are the engine's output.
UNBOUND = ["arena-session.json", "arena-search-session.json",
           "ecology-trace-session.json", "ecology-experiment-session.json",
           # A real observation, run through the engine from docs/tahoe-westshore.eco
           # (ADR-107). Unbound for the same reason as the rest: it is the output of a
           # spec that names external Darwin Core files, so there is no argument-free
           # run() this suite could call to regenerate it and compare.
           "tahoe-westshore-session.json",
           "viability-map.json"]
present = [os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "*.json"))]
ck("the unbound session artifacts are exactly the ones named here",
   sorted(set(present) - {"ecology-lab-session.json", "visualizer-contract.json"})
   == sorted(UNBOUND),
   sorted(set(present) - {"ecology-lab-session.json", "visualizer-contract.json"}))

# ---- the extractor gets its own fixtures ---------------------------------
ck("the brace matcher stops at the object's own end, not the first '}'",
   inline_session('x const SESSION = {"a":{"b":1}}; more{}') == '{"a":{"b":1}}',
   inline_session('x const SESSION = {"a":{"b":1}}; more{}'))
# A check that raises has told you nothing; it has to FAIL. The first version
# of this fixture crashed the suite on the very defect it existed to catch.
def _try(fn, *a):
    try:
        return fn(*a)
    except Exception as e:                       # noqa: BLE001 - reporting, not handling
        return "%s: %s" % (type(e).__name__, e)

BRACED = 'const SESSION = {"a":"} not the end","b":2};'
ck("and it is not fooled by a brace inside a string value",
   _try(json.loads, _try(inline_session, BRACED)) == {"a": "} not the end", "b": 2},
   _try(inline_session, BRACED))
ESCAPED = 'const SESSION = {"a":"x \\" } y","b":3};'
ck("nor by an escaped quote inside that string",
   _try(json.loads, _try(inline_session, ESCAPED)) == {"a": 'x " } y', "b": 3},
   _try(inline_session, ESCAPED))

# ---- link D: the page's plain-English thresholds ARE the engine's ---------
# `ecology-lab.html` says, in a comment above its reading functions, "same
# thresholds as FieldReport.java". Nothing checked it, and a mutation sweep
# walked straight through: `j >= .85` became `j > .85` and `i <= 1.5` became
# `i < 1.5`, and every suite stayed green. At exactly 0.85 a community stops
# reading "very even"; at exactly 1.5 a distribution stops reading "random".
#
# Both sides are extracted -- the Java's named constants and the comparisons
# that use them, the page's inline numbers and the operators beside them -- and
# compared as ORDERED (operator, value) pairs. A number moving on one side, or
# an operator changing on either, breaks the match. That is the same shape as
# link B: a value generated in one place and inlined in another, with something
# binding the two.
JAVA_SRC = os.path.join(ROOT, "csrbt-experimental", "src", "main", "java", "io",
                        "github", "richeyworks", "csrbt", "experimental", "ecology",
                        "FieldReport.java")
# page function -> the Java constants its bands are cut at, in the order the
# page tests them. Written out rather than inferred: the correspondence is the
# claim being checked, and a rule that derived it would be checking itself.
READINGS = [
    ("evenness",   ["EVEN_VERY", "EVEN_MODERATE", "EVEN_UNEVEN"]),
    ("dispersion", ["DISP_REGULAR", "DISP_CLUMPED"]),
    ("overlap",    ["OVERLAP_HIGH", "OVERLAP_PARTIAL"]),
    ("turnoverR",  ["TURNOVER_LOW", "TURNOVER_MODERATE"]),
    ("fillRead",   ["FILL_TIGHT", "FILL_HEALTHY"]),
]
OPNUM = re.compile(r"(>=|<=|>|<)\s*(\.\d+|\d+\.?\d*)")

if not os.path.exists(JAVA_SRC):
    unverified.append("the page's thresholds against FieldReport.java -- source not present")
else:
    _j = io.open(JAVA_SRC, encoding="utf-8").read()
    _const = dict((m.group(1), float(m.group(2))) for m in
                  re.finditer(r"public static final double (\w+)\s*=\s*([\d.]+);", _j))
    _jcmp = dict((m.group(2), m.group(1)) for m in
                 re.finditer(r"if \(\s*\w+\s*(>=|<=|>|<)\s*([A-Z_]+)\s*\)", _j))
    _page = io.open(os.path.join(ROOT, "docs", "ecology-lab.html"), encoding="utf-8").read()
    ck("FieldReport.java declares its thresholds as named constants",
       len(_const) >= 8, sorted(_const))
    for _fn, _names in READINGS:
        # `const NAME = ... ;` whether or not there is an arrow: four of these
        # are arrow functions and fillRead is a plain ternary computed inline,
        # and requiring `=>` found four of five and called the fifth missing.
        _m = re.search(r"\bconst %s\s*=(.*?);\s*\n" % _fn, _page, re.S)
        if not _m:
            ck("the page still has a %s reading to bind" % _fn, False, "not found")
            continue
        _want = [(_jcmp.get(n), _const.get(n)) for n in _names]
        _got = [(o, float(v)) for o, v in OPNUM.findall(_m.group(1))]
        ck("%s uses the engine's own constants, with the engine's own operators" % _fn,
           _got == _want, {"page": _got, "FieldReport": _want, "constants": _names})
    ck("and the binding is not vacuous -- the constants really are distinct values",
       len({_const[n] for _, ns in READINGS for n in ns}) >= 6,
       sorted({_const.get(n) for _, ns in READINGS for n in ns}))

# ---- ADR-139: the attestation, and its decay rule --------------------------
#
# The live check is the one that matters and it cannot run everywhere. What
# stands in for it must be weaker in a way that is STATED and that expires on
# its own, or it is a cached green.
_st = EA.load()
_dig, _n = EA.engine_digest()
_entry = (_st.get("artifacts") or {}).get("docs/ecology-lab-session.json")
ck("an attestation is committed for the shipped session, and it names what produced it",
   bool(_entry) and _entry.get("expr") == "EcologyFieldDay.run().json()"
   and _entry.get("at", 0) > 0 and _entry.get("sourceFiles", 0) > 10 and _entry.get("java"),
   _entry)
ck("the engine digest covers both modules' main sources, by path AND bytes",
   _n > 50 and len(_dig) == 64 and all(f.endswith(".java") for f in EA.source_files()), (_n, _dig[:12]))
ck("...and it is the digest the committed attestation was taken against",
   bool(_entry) and _entry.get("engineDigest") == _dig,
   (_entry or {}).get("engineDigest", "")[:12] + " vs " + _dig[:12])

# the decay rule, on fixtures: a moved source, a wrong sha, nothing at all
_fake = {"artifacts": {"docs/ecology-lab-session.json": dict(_entry or {}, sha=EA.sha_text(shipped_txt))}}
ck("with the engine unmoved and the bytes matching, the attestation APPLIES",
   EA.check("docs/ecology-lab-session.json", shipped_txt, _fake, _dig)[0] == "attested",
   EA.check("docs/ecology-lab-session.json", shipped_txt, _fake, _dig))
ck("move one byte of the engine and it stops applying -- STALE, not attested",
   EA.check("docs/ecology-lab-session.json", shipped_txt, _fake, "0" * 64)[0] == "stale",
   EA.check("docs/ecology-lab-session.json", shipped_txt, _fake, "0" * 64))
ck("edit the shipped file and the attestation says so -- on a machine with no Java at all",
   EA.check("docs/ecology-lab-session.json", shipped_txt + " ", _fake, _dig)[0] == "differs",
   EA.check("docs/ecology-lab-session.json", shipped_txt + " ", _fake, _dig))
ck("with nothing attested the answer is ABSENT, never a pass",
   EA.check("docs/ecology-lab-session.json", shipped_txt, {"artifacts": {}}, _dig)[0] == "absent")
# and the digest is over the path as well as the bytes: a file renamed with its
# content unchanged is a different engine, and a digest of contents alone would
# call it the same one.
_fx = tempfile.mkdtemp()
os.makedirs(os.path.join(_fx, "m", "src", "main", "java", "p"))
_one = os.path.join(_fx, "m", "src", "main", "java", "p", "A.java")
io.open(_one, "w", encoding="utf-8").write("class A {}\n")
_saved_roots, _saved_root = EA.SOURCE_ROOTS, EA.ROOT
try:
    EA.ROOT, EA.SOURCE_ROOTS = _fx, (os.path.join("m", "src", "main", "java"),)
    _d1, _c1 = EA.engine_digest()
    os.rename(_one, os.path.join(os.path.dirname(_one), "B.java"))
    _d2, _c2 = EA.engine_digest()
    io.open(os.path.join(os.path.dirname(_one), "B.java"), "a", encoding="utf-8").write("// x\n")
    _d3, _c3 = EA.engine_digest()
    ck("a renamed source file is a different engine even with its bytes unchanged, and an edited "
       "one is different again", len({_d1, _d2, _d3}) == 3 and _c1 == _c2 == _c3 == 1,
       (_d1[:8], _d2[:8], _d3[:8], _c1, _c2, _c3))
finally:
    EA.SOURCE_ROOTS, EA.ROOT = _saved_roots, _saved_root

# what --attest WRITES, without needing a JDK: the engine's output is faked, the
# record it produces is not. An attestation with no digest in it would apply to
# every engine forever, which is the failure this whole mechanism exists to
# avoid, and nothing would notice until an engine actually moved.
_saved_out = EA.engine_output
try:
    EA.engine_output = lambda artifact="docs/ecology-lab-session.json": ("PRETEND", None)
    _st2 = {"artifacts": {}}
    _rec, _rwhy = EA.attest("docs/ecology-lab-session.json", _st2)
finally:
    EA.engine_output = _saved_out
ck("an attestation records the engine digest as it stood, 64 hex, alongside what was emitted",
   _rwhy is None and _rec and len(_rec.get("engineDigest", "")) == 64
   and _rec["engineDigest"] == _dig and _rec["sha"] == EA.sha_text("PRETEND")
   and _rec.get("sourceFiles") == _n, _rec)
ck("...and the record it wrote applies to this engine and to nothing else",
   EA.check("docs/ecology-lab-session.json", "PRETEND", _st2, _dig)[0] == "attested"
   and EA.check("docs/ecology-lab-session.json", "PRETEND", _st2, "f" * 64)[0] == "stale",
   (EA.check("docs/ecology-lab-session.json", "PRETEND", _st2, _dig),
    EA.check("docs/ecology-lab-session.json", "PRETEND", _st2, "f" * 64)))

total = ok + bad + len(unverified)
print("-" * 70)
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d checks" % (ok, total))
sys.exit(1 if bad else 0)
