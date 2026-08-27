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
import glob, io, json, os, re, subprocess, sys, tempfile

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


def classpath():
    parts = [os.path.join(ROOT, "csrbt-experimental", "build", "classes", "java", "main"),
             os.path.join(ROOT, "csrbt-core", "build", "classes", "java", "main")]
    if not all(os.path.isdir(p) for p in parts):
        return None
    # log4j is a compile dependency of TreeContext's static initialiser, so the
    # engine will not start without it even though nothing here logs.
    for pat in ("log4j-api-*.jar", "log4j-core-*.jar"):
        hit = glob.glob(os.path.join(os.path.expanduser("~"), ".gradle", "caches",
                                     "modules-2", "files-2.1", "**", pat), recursive=True)
        if not hit:
            return None
        parts.append(sorted(hit)[-1])
    return os.pathsep.join(parts)


def engine_json():
    """(json_text, why_not). Never raises: an engine that will not start is an
    UNVERIFIED result, not a crash and certainly not a pass."""
    cp = classpath()
    if cp is None:
        return None, "engine classes or log4j not found -- run ./gradlew classes"
    src = ('import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;\n'
           'public class _Regen { public static void main(String[] a) throws Exception {\n'
           '  System.out.print(EcologyFieldDay.run().json()); } }\n')
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "_Regen.java")
        io.open(f, "w", encoding="utf-8").write(src)
        try:
            c = subprocess.run(["javac", "-cp", cp, "-d", d, f],
                               capture_output=True, text=True, timeout=180)
            if c.returncode:
                return None, "javac failed: " + c.stderr.strip().splitlines()[-1][:120]
            r = subprocess.run(["java", "-cp", cp + os.pathsep + d, "_Regen"],
                               capture_output=True, text=True, timeout=300)
            if r.returncode:
                return None, "engine run failed: " + r.stderr.strip().splitlines()[-1][:120]
            return r.stdout, None
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, "%s: %s" % (type(e).__name__, e)


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
    unverified.append("engine -> docs/ecology-lab-session.json (%s)" % why)
    print("UNVERIFIED  the shipped session is the engine's output   (%s)" % why)
else:
    ck("the shipped session is byte-for-byte what the engine emits today",
       txt == shipped_txt,
       "parsed-equal but bytes differ" if json.loads(txt) == shipped else "content differs")
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
prose = re.sub(r"<[^>]+>", " ", re.sub(r"<style\b.*?</style>", " ", rest, flags=re.S | re.I))
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

# ---- the artifacts this does NOT bind ------------------------------------
# Named rather than implied covered. These are recorded sessions loaded by the
# visualizers; none has a deterministic run() this can call, so nothing here
# can say they are the engine's output.
UNBOUND = ["arena-session.json", "arena-search-session.json",
           "ecology-trace-session.json", "ecology-experiment-session.json",
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

total = ok + bad + len(unverified)
print("-" * 70)
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d checks" % (ok, total))
sys.exit(1 if bad else 0)
