# -*- coding: utf-8 -*-
"""The last unbound session artifact, and the four links it sits in.

ADR-052 bound the flagship page to the engine and listed five session artifacts
it had not bound. ADR-058 took four of them. This is the fifth, and it is the
only one whose reader is a *published* page:

    docs/sample-experiment.eco          the spec, written before the run
      -> ecologyExperiment              the engine grades it
      -> docs/ecology-experiment-session.json    the graded output, shipped
      -> docs/ecology-lab.html          draws it when you drop it in
      -> docs/eco-protocol-reference.html   tells you to

Nothing checked any link. The spec could gain a hypothesis the session does not
carry, the session could carry a verdict its own numbers contradict, and the lab
could quietly ignore a whole section of a file the reference page told you to
drop on it -- with every suite in the kit still green.

THE VERDICTS ARE REGRADED, NOT TRUSTED

Each hypothesis ships its expression, what was observed, and the engine's
verdict. That is enough to grade it again here, in Python, from the shipped
bytes: `evenness(bloom) > 0.9` observed at 0.494749 is REFUTED whoever does the
arithmetic. One of the seven is a boundary case -- `jaccard(pondA, pondB) <= 0.5`
observed at exactly 0.5 -- which is the check with teeth: an engine that used
`<` would call it REFUTED and this file would say so.

No engine needed, and no expected constants pinned (ADR-041): the comparison is
recomputed from the two numbers the file already carries, so it keeps passing
when the engine legitimately produces different data.

Run:  python3 tools/verify/verify_eco_experiment.py
"""
import io, json, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS = os.path.join(ROOT, "docs")
SPEC = os.path.join(DOCS, "sample-experiment.eco")
SESSION = os.path.join(DOCS, "ecology-experiment-session.json")
LAB = os.path.join(DOCS, "ecology-lab.html")
REFERENCE = os.path.join(DOCS, "eco-protocol-reference.html")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

SPEC_SRC = io.open(SPEC, encoding="utf-8").read()
S = json.load(io.open(SESSION, encoding="utf-8"))
LAB_SRC = io.open(LAB, encoding="utf-8").read()

COMMENT = re.compile(r"\s+#.*$")
def directives(kind):
    """Every `kind:` line in the spec, comment stripped, with the comment kept.

    `note(bloom):` is the same directive as `note:` -- the parenthesis scopes it
    to a phase -- so both forms count, or the note tally is short by two."""
    out = []
    for raw in SPEC_SRC.splitlines():
        line = raw.strip()
        if not re.match(r"^%s(\([^)]*\))?:" % re.escape(kind), line):
            continue
        body = COMMENT.sub("", line).split(":", 1)[1].strip()
        note = raw[len(COMMENT.sub("", raw)):].strip()
        out.append((body, note))
    return out


# ---- link 1: the spec is the session's input -----------------------------
PAIRS = [("expect", "hypotheses"), ("model", "models"), ("data", "entered"),
         ("note", "notes"), ("tree", "trees"), ("cross", "crosses")]
for kind, key in PAIRS:
    spec_n, sess_n = len(directives(kind)), len(S.get(key, []))
    ck("every `%s:` in the spec reached the session as %s (%d)" % (kind, key, spec_n),
       spec_n and spec_n == sess_n, (spec_n, sess_n))

EXPECTS = [b for b, _ in directives("expect")]
HYP = S["hypotheses"]
ck("each hypothesis carries its spec line verbatim, in order",
   [h["expr"] for h in HYP] == EXPECTS,
   [(a, b["expr"]) for a, b in zip(EXPECTS, HYP) if a != b["expr"]])

def setting(name):
    m = re.search(r"^%s:\s*(\S+)" % name, SPEC_SRC, re.M)
    return m.group(1) if m else None
ck("the spec's window reached the drift station",
   int(setting("window")) == S["drift"]["windowOps"],
   (setting("window"), S["drift"]["windowOps"]))
ck("the spec's phase names are the meadow's phases, in order",
   [p["name"] for p in S["meadow"]["phases"]] == [b.split()[0] for b in EXPECTS and
        [x for x, _ in directives("phase")]],
   ([p["name"] for p in S["meadow"]["phases"]], [x.split()[0] for x, _ in directives("phase")]))


# ---- link 2: the verdicts, regraded --------------------------------------
OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
       ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
       "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
NUMERIC = re.compile(r"^(.*?)\s*(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?)$")
QUALITATIVE = re.compile(r"^(.*?)\s+is\s+(\S+)$")

def regrade(h):
    """CONFIRMED / REFUTED from the hypothesis's own two fields, or None.

    ONE implementation, used by the live check and by every fixture below, so a
    fixture cannot pass against a second copy of the rule (ADR-039)."""
    expr, obs = h.get("expr", ""), h.get("observed")
    m = NUMERIC.match(expr)
    if m and isinstance(obs, (int, float)) and not isinstance(obs, bool):
        return "CONFIRMED" if OPS[m.group(2)](obs, float(m.group(3))) else "REFUTED"
    m = QUALITATIVE.match(expr)
    if m and isinstance(obs, str):
        return "CONFIRMED" if obs == m.group(2) else "REFUTED"
    return None

graded = [(h, regrade(h)) for h in HYP]
ck("every hypothesis is one this file knows how to grade",
   all(v is not None for _, v in graded),
   [h["expr"] for h, v in graded if v is None])
wrong = [(h["expr"], h.get("observed"), h.get("verdict"), v) for h, v in graded
         if v is not None and v != h.get("verdict")]
ck("and the engine's verdict is the one the arithmetic gives", not wrong, wrong)

boundary = [h for h in HYP if NUMERIC.match(h.get("expr", ""))
            and isinstance(h.get("observed"), (int, float))
            and float(NUMERIC.match(h["expr"]).group(3)) == h["observed"]]
ck("a hypothesis sits exactly ON its threshold -- the case that separates < from <=",
   boundary, [h["expr"] for h in HYP])
ck("and the engine took the inclusive reading its operator promises",
   all(h["verdict"] == ("CONFIRMED" if "=" in NUMERIC.match(h["expr"]).group(2) else "REFUTED")
       for h in boundary),
   [(h["expr"], h["verdict"]) for h in boundary])

# The spec marks one line as deliberately wrong. That comment is a claim about
# what the run will show, and it is checkable.
DELIBERATE = [b for b, note in directives("expect") if "deliberately wrong" in note.lower()]
ck("the spec marks exactly one hypothesis as deliberately wrong", len(DELIBERATE) == 1, DELIBERATE)
REFUTED = [h["expr"] for h in HYP if h.get("verdict") == "REFUTED"]
ck("exactly one hypothesis was refuted", len(REFUTED) == 1, REFUTED)
ck("and it is the one the spec said would be", DELIBERATE == REFUTED, (DELIBERATE, REFUTED))

# ---- link 2b: the grader is not vacuous ----------------------------------
def H(expr, obs, verdict="CONFIRMED"): return {"expr": expr, "observed": obs, "verdict": verdict}
ck("a true comparison grades CONFIRMED", regrade(H("evenness(x) > 0.9", 0.99)) == "CONFIRMED")
ck("a false one grades REFUTED", regrade(H("evenness(x) > 0.9", 0.49)) == "REFUTED")
ck("<= is inclusive at the boundary", regrade(H("jaccard(a, b) <= 0.5", 0.5)) == "CONFIRMED")
ck("< is exclusive at the same boundary", regrade(H("jaccard(a, b) < 0.5", 0.5)) == "REFUTED")
ck(">= is inclusive at the boundary", regrade(H("hill1(x) >= 20", 20.0)) == "CONFIRMED")
# Every operator gets a fixture ON its threshold, including the ones this
# spec happens not to use. A mutation sweep turned `>` into `>=` and nothing
# noticed: no hypothesis in the shipped session sits on a `>` boundary, so the
# only way to tell the two apart is to ask directly. An operator no fixture
# exercises is untested code that looks tested.
ck("> is exclusive at the boundary", regrade(H("evenness(x) > 0.9", 0.9)) == "REFUTED")
ck("< is exclusive at its own boundary", regrade(H("hill1(x) < 20", 20.0)) == "REFUTED")
ck("== holds only on the value", regrade(H("richness(x) == 12", 12)) == "CONFIRMED"
   and regrade(H("richness(x) == 12", 13)) == "REFUTED")
ck("!= is its exact inverse", regrade(H("richness(x) != 12", 12)) == "REFUTED"
   and regrade(H("richness(x) != 12", 13)) == "CONFIRMED")
ck("a qualitative match grades CONFIRMED", regrade(H("survivorship is type3", "type3")) == "CONFIRMED")
ck("a qualitative miss grades REFUTED", regrade(H("survivorship is type3", "type1")) == "REFUTED")
ck("a booleaned observation is not read as a number",
   regrade(H("evenness(x) > 0.9", True)) is None, regrade(H("evenness(x) > 0.9", True)))
ck("an expression with no operator is not silently graded",
   regrade(H("evenness(x)", 0.9)) is None)


# ---- link 3: the lab draws all of it -------------------------------------
LAB_BODY = LAB_SRC[LAB_SRC.index("function renderStations(S)"):]
READS = []
for m in re.finditer(r"\bS\.([A-Za-z_]\w*)", LAB_BODY):
    if m.group(1) not in READS:
        READS.append(m.group(1))
ck("the lab's renderer reads session keys at all", len(READS) > 5, READS)
ignored = sorted(set(S) - set(READS))
ck("the lab renders every section this session ships -- nothing dropped in silence",
   not ignored, ignored)

# The page's own message when nothing charted. It named eight keys; the renderer
# reads fourteen, and the six it left out -- models, crosses, entered, notes,
# trees, hypotheses -- are exactly what makes a graded protocol worth dropping
# in. A reader whose file failed to chart was told those were not supported.
# Anchored on the sentence's shape, not one noun: renaming "stations" to
# "sections" -- which this slice did, because models and crosses are not
# stations -- must not silently stop the check from finding anything. If the
# sentence goes away entirely the check below FAILS rather than passing on an
# empty list.
msg = re.search(r"no known \w+ \(([^)]*)\) were present", LAB_SRC)
ck("the lab explains itself when nothing charted", msg is not None)
LISTED = [k.strip() for k in msg.group(1).split(",")] if msg else []
ck("and that message names every key the renderer accepts",
   sorted(LISTED) == sorted(READS), (sorted(set(READS) - set(LISTED)), sorted(set(LISTED) - set(READS))))

# ---- link 4: the reference page points at a file that exists -------------
REF = io.open(REFERENCE, encoding="utf-8").read()
ck("the reference page names the session file", "ecology-experiment-session.json" in REF)
ck("and the spec it tells you to run", "ecologyExperiment" in SPEC_SRC)

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
