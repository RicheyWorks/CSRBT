# -*- coding: utf-8 -*-
"""Seed deliberate faults across the kit and report which ones nothing catches.

WHY THIS EXISTS

Twice this month a suite ran green while measuring almost nothing. verify_fw
reported "39 passed, 0 failed" and let EIGHT seeded faults through. audit_frontend
carried 26 findings of which 26 were false, and could not see the one defect it
was named for. Both were found the same way: by breaking the thing on purpose and
watching whether anything noticed.

That check has been done by hand, one slice at a time, on whichever page was in
front of me. Twenty-five suites have never had it done at all. A green run tells
you the suites passed; it does not tell you they would have failed. This measures
the second thing.

HOW IT WORKS

  1. Pick a target file and generate MUTANTS -- single small edits that ought to
     change behaviour: max becomes min, >= becomes >, an esc() call disappears, a
     trapezoid's /2 goes away, a numeric literal shifts by 10%.
  2. For each mutant, run only the suites that name that page. A full run per
     mutant would make this unaffordable and nobody would run it.
  3. Report the SURVIVORS -- mutants that every relevant suite passed. Those are
     the blind spots.

WHAT A SURVIVOR IS AND IS NOT

  A survivor is not automatically a bug. Some mutations are EQUIVALENT: they
  change the source without changing any behaviour a suite could observe --
  a constant that is overwritten before use, a branch that cannot be reached,
  a comparison on values that are never equal. Equivalent mutants are the
  standing tax of this technique and there is no general way to detect them.

  So this is a FINDER, not a gate. Every survivor is a question: is this
  unreachable, or is it a hole? It exits zero either way and prints a count for
  triage, on the same principle as audit_claims. A tool whose every row is noise
  teaches you to skim, and skimming is what let eight faults through verify_fw.

  Mutations are applied to a COPY. The tree is never modified. If this process is
  killed mid-run, nothing is left behind to clean up.

    python3 tools/mutate.py --page food-web.html
    python3 tools/mutate.py --page greenhouse.html --limit 20
    python3 tools/mutate.py --all --limit 60          # a sweep, bounded
    python3 tools/mutate.py --page releve.html --list # show mutants, run nothing
"""
import argparse, glob, io, os, re, shutil, subprocess, sys, tempfile, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
VERIFY = os.path.join(ROOT, "tools", "verify")


# ---------------------------------------------------------------- operators

def _op(name, pattern, repl, why, flags=0):
    return {"name": name, "re": re.compile(pattern, flags), "repl": repl, "why": why}


# Chosen for a low equivalent-mutant rate. Each one, applied to code that means
# anything, changes an answer -- which is the property that makes a survivor
# interesting rather than noise.
OPS = [
    _op("max->min", r"Math\.max\.apply", "Math.min.apply",
        "a reduction that takes the largest now takes the smallest"),
    _op("max->min2", r"Math\.max\(", "Math.min(",
        "same, in the two-argument form"),
    # The lookbehinds matter. A bare `>=` also matches inside `>>=` and `>>>=`,
    # and a bare `<=` inside `<<=`. Mutating a shift-assign into a comparison
    # produces a nonsense mutant, and nonsense mutants survive -- one turned up
    # in the ordination sweep sitting inside a PRNG's `s >>>= 0` and was
    # reported as a coverage gap. A survivor list padded with garbage is a
    # worklist nobody finishes.
    _op("gte->gt", r"(?<![>=!<])>=", ">",
        "an inclusive boundary becomes exclusive -- the classic off-by-one"),
    _op("lte->lt", r"(?<![<=!>])<=", "<",
        "the other inclusive boundary"),
    _op("and->or", r"&&", "||",
        "a conjunction becomes a disjunction, so a guard stops guarding"),
    # The negative lookbehind is not decoration. Without it this matched the
    # DEFINITION -- `function esc(s){` became `function s{` -- which is not a
    # mutant, it is a syntax error. Every suite "kills" a page that will not
    # parse, so unviable mutants inflate the score for free; and this particular
    # one is what an unrestored in-place run left in the real tree.
    _op("drop-esc", r"(?<!function )esc\(([A-Za-z_$][\w$.\[\]]*)\)", r"\1",
        "an escaping call disappears -- the ADR-031 defect, seeded"),
    _op("drop-half", r"\)\s*/\s*2\s*\*", ")*",
        "a trapezoid's averaging term goes away, leaving a rectangle sum"),
    _op("off-by-one", r"\.length\s*-\s*1", ".length",
        "a loop bound or an index shifts by one"),
    _op("neg-guard", r"if\(!\s*", "if(",
        "a negated guard is inverted"),
    _op("num-shift", r"(?<![\w.$])(\d+\.\d+)(?![\w.])", None,
        "a decimal constant moves by 10% -- a coefficient, a threshold, a factor"),
]

# Regions never mutated, with a reason for each.
SKIP_REGIONS = [
    (re.compile(r"<style>.*?</style>", re.S), "stylesheet -- a colour is not arithmetic"),
    (re.compile(r"<!--.*?-->", re.S), "HTML comment"),
]


def script_spans(src):
    """Byte ranges of <script> bodies. Nothing outside them is code."""
    out = []
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script>", src, re.S):
        out.append((m.start(1), m.end(1)))
    return out


def in_spans(i, spans):
    for a, b in spans:
        if a <= i < b: return True
    return False


def comment_spans(src):
    """JS comment ranges. Mutating a comment changes nothing and every such
    mutant survives, which would bury the real survivors in noise."""
    out = []
    for m in re.finditer(r"/\*.*?\*/", src, re.S):
        out.append((m.start(), m.end()))
    for m in re.finditer(r"(^|[^:])//[^\n]*", src):
        out.append((m.start(), m.end()))
    return out


def block_of(src, i):
    """Which inlined module a position falls in, so a survivor is attributed to
    the code that owns it rather than to whichever page happened to carry it."""
    head = src[:i]
    for tag, label in (("Field Entry Kit v", "FEK"),
                       ("Keep v", "KEEP"),
                       ("Greenhouse engine v", "GH"),
                       ("Darwin Core v", "DWC"),
                       ("Ordination v", "ORD")):
        a = head.rfind("/* ---- " + tag)
        if a == -1: a = head.rfind("/* ---------- " + tag)
        if a == -1: continue
        b = src.find("})();", a)
        if b != -1 and a < i < b: return label
    return "page"


# ---- a mutation inside a module function the page never calls ---------------
#
# Every page inlines the Field Entry Kit whole. A page that uses steppers and
# fields still carries picker(), slider() and chips(), and a mutation inside a
# constructor the page never calls cannot change anything the page does. Those
# came back as survivors on micro-bench and on cell-bench, and would have come
# back on all thirty-nine -- the same two rows forever, which is how a worklist
# teaches you to skim (ADR-047).
#
# This is a FACT about the page, not a heuristic: the module publishes its
# constructors in a `return { name: fn, ... }`, and if the page never writes
# `FEK.name(` then that constructor is dead code in this copy.
#
# Deliberately narrow. It applies ONLY to published names. An internal helper --
# reg(), el(), buzz(), clamp() -- is called from inside the module, so "the page
# never calls FEK.reg(" is true and irrelevant, and treating it as unreachable
# would hide a real survivor.
# ---- survivors examined and left, with the reason ---------------------------
#
# ADR-047: "the defence is saying out loud which survivors you decided not to
# kill and why." These three recur on every page that inlines the Field Entry
# Kit, which is all of them, and re-triaging the same three rows on thirty-nine
# pages is how a worklist teaches you to skim.
#
# Each was settled by MEASUREMENT, not by reading, and the measurement is named.
# None is a licence: a mutant only matches here if its operator and its context
# both match, so the same operator somewhere else is still a survivor.
#
# An automated version was attempted and withdrawn. Deciding "this module
# function is never called on this page" needs the position matched to the
# function that CONTAINS it, which needs JavaScript braces matched properly,
# which needs regex literals told apart from division -- and the first cut
# attributed every FEK mutation to esc(), because the escaper's own
# /[&<>"']/g swallowed the matcher. A rule that cannot be got right is worse
# than a list that is honest about being a list.
KNOWN_EQUIVALENT = [
    # --- esc() over a value the page itself wrote -------------------------
    # An escape whose input is a constant this page authored cannot be observed
    # by dropping it: there is nothing in the input to escape. The escape is
    # still correct -- it is what keeps the line safe if the table ever becomes
    # user-editable -- so these are equivalent TODAY, not pointless.
    #
    # The criterion is a measurement, not a look: the source of the value must
    # have no path from typed input. Each entry names the one that settled it.
    ("drop-esc", "esc(lastErr)",
     "the KEEP autosave banner; lastErr is never the exception's message but one "
     "of three literals keep.py chooses, so no runtime path can put markup in it "
     "-- and verify_keep now asserts statically that no assignment reaches "
     "e.message or e.stack"),
    ("drop-esc", "esc(c.n)",
     "breeding-bench crop heading; c comes from cropBy() over the CROPS literal "
     "at line 930, and grep finds 0 pushes to it"),
    ("drop-esc", "esc(it[4])",
     "soil-recipes ingredient note; rows() is called only with r.base/r.items "
     "from the RECIPES literal, and grep finds 0 pushes to it anywhere"),
    ("drop-esc", "esc(it[1])+'<small>'",
     "ethogram's design chips; chips() is called only with the SAMPLE and RECORD "
     "literals, and grep finds 0 pushes to either"),
    ("gte->gt", "indexOf(qq)>=0",
     "inside FEK.picker's filter; grep shows FEK.picker used 0 times on the "
     "bench pages, so the constructor is dead code in those copies"),
    ("and->or", "if(o && o.field)",
     "FEK.reg(o,h); all 6 call sites pass the constructor's own o, which every "
     "constructor has already defaulted to {} -- so o && is always true"),
    ("lte->lt", "v<=0",
     "the plated-volume guard; the stepper clamps to its min, measured: typing "
     "0 or -5 both yield 0.001, so v<=0 is unreachable through the UI"),
    # NOT equivalent -- a genuinely open question, parked here so it stops
    # crowding the fresh list while it waits for the claims worklist.
    ("num-shift", "from 0.2 to 5 mm",
     "OPEN, not equivalent: an uncited size range for Utricularia bladders in "
     "cp-characters' genus table. Shifting it is a wrong fact and nothing "
     "catches it. The fix is a source (audit_claims), not a pinned constant "
     "in a suite -- ADR-041 -- so it waits there rather than being killed here"),
    ("lte->lt", "a[i]<=a[i-1]",
     "tree-visualizer's own checkBST; the tree refuses duplicates (bstInsert "
     "returns null for a key already present, and verify_tv asserts that "
     "inserting 50 twice leaves the count unchanged), so no two adjacent "
     "in-order keys are ever equal and <= cannot differ from <"),
    ("lte->lt", "every <= 0",
     "deployment-log's duty-cycle divisor guard; aOn and aEvery are FEK steppers "
     "with min:1 and no nullable flag, measured to clamp, so `every` can never "
     "reach 0 through the UI and the guard is defensive"),
    ("lte->lt", "c<=0",
     "soil-recipes fmtCup's zero guard; measured: 51 quantities in the RECIPES "
     "literal with a minimum of 0.25, and the batch dial's smallest multiplier "
     "is 0.25, so the smallest value fmtCup can ever see is 0.0625"),
    ("lte->lt", "lam<=0",
     "field-season's Poisson draw; with lam=0 the guard is redundant -- L=exp(0)=1 "
     "and the do/while exits on the first draw because the PRNG returns t/2^32 < 1, "
     "so k-1 = 0 either way"),
    ("drop-esc", "esc(mm.label)",
     "soil-bench's reading row; mm comes from MOIST, a five-entry page literal at "
     "line 991 with no push, splice or reassignment anywhere in the file"),
    ("drop-esc", "esc(s)",
     "cp-bench's water-reading row; s is a SOURCES label and SOURCES is a page "
     "literal at line 1011 with no push, splice or reassignment anywhere in the "
     "file -- so there is nothing in the input to escape"),
    # --- a guard whose two branches converge ------------------------------
    ("and->or", "navigator.clipboard&&navigator",
     "eco-protocol-library's copy button. With `||` a truthy navigator.clipboard "
     "short-circuits and writeText is called even if absent -- which THROWS, and "
     "the whole expression sits inside a try that calls fallback(). Both spellings "
     "reach fallback() in every browser where they differ, so the mutation cannot "
     "be observed from outside: measured by reading the enclosing try, not by "
     "reading the condition"),
    ("lte->lt", "i<=8;i++) S.plants",
     "pheno-tracker's starting roster size. No independent witness exists for "
     "it: the page writes its own runN field back from the roster length, so "
     "'the grid matches the control' compares a number with itself and passes "
     "with the mutant in place -- measured. Pinning 8 would pin an arbitrary "
     "default (ADR-041), so it is left"),
    ("lte->lt", "t<=4",
     "tree-proofs chart gridlines: five lines at 0/25/50/75/100% become four. "
     "Chart furniture, no claim depends on it -- examined and left"),
    ("lte->lt", "sq<=0",
     "the squares-counted guard; same clamp, measured: typing 0 or -3 both "
     "yield hidden cSq = 1"),
    # experiment-guide.html, first sweep (ADR-095): five examined, all measured.
    ("gte->gt", "(r >= 10",
     "experiment-guide fmtRatio's rounding boundary: the operators differ only "
     "at r == 10 exactly, where Math.round(10) and Math.round(100)/10 both "
     "render '10\u00d7' -- measured at the boundary"),
    ("and->or", "(k) { return row[k]",
     "experiment-guide rowComplete: the defined/non-empty clauses are subsumed "
     "by isFinite(parseFloat(...)) -- undefined and '' both parse to NaN, so "
     "the disjunction cannot change the verdict; kept for readability"),
    ("and->or", 'row[k] !== "" && i',
     "the second conjunction of the same subsumed guard, same reason"),
    ("and->or", "(p) { return row[p]",
     "experiment-guide table cells: the mutant pushes undefined, which "
     "Array.join renders as the empty string -- one space of markdown cell "
     "padding, and markdown renders both identically; measured"),
    ("and->or", "ells.push(row.floor",
     "the floor cell of the same row builder, same join behaviour"),
]


def examined(mu):
    """The recorded reason this survivor was left, or None."""
    for op, frag, why in KNOWN_EQUIVALENT:
        if mu["op"] == op and frag in mu["ctx"]:
            return why
    return None


def mutants_for(path, limit=None, whole_file=False):
    src = io.open(path, encoding="utf-8").read()
    if whole_file:
        # A module source is code end to end -- but its CSS and JS live inside
        # Python string literals, and the surrounding Python is not what the
        # module's suite exercises. Mutate only the JS body.
        spans = [(m.start(1), m.end(1))
                 for m in re.finditer(r'JS\s*=\s*"""(.*?)"""', src, re.S)]
        if not spans:
            spans = [(0, len(src))]
    else:
        spans = script_spans(src)
    if not spans:
        return src, []
    cspans = comment_spans(src)
    seen, out = set(), []
    for op in OPS:
        for m in op["re"].finditer(src):
            i = m.start()
            if not in_spans(i, spans): continue
            if in_spans(i, cspans): continue
            if op["name"] == "num-shift":
                v = float(m.group(1))
                if v == 0 or v == 1: continue
                new = repr(round(v * 1.1, 6))
            else:
                new = m.expand(op["repl"])
            key = (op["name"], i)
            if key in seen: continue
            seen.add(key)
            line = src.count("\n", 0, i) + 1
            ctx = re.sub(r"\s+", " ", src[max(0, i - 34):i + len(m.group(0)) + 26]).strip()
            out.append({"op": op["name"], "why": op["why"], "at": i, "line": line,
                        "was": m.group(0), "now": new, "ctx": ctx,
                        "block": block_of(src, i),
                        "text": src[:i] + new + src[i + len(m.group(0)):]})
    # Spread the sample across operators rather than taking the first N, which
    # would be every `>=` on the page and nothing else.
    if limit and len(out) > limit:
        by_op = {}
        for mu in out: by_op.setdefault(mu["op"], []).append(mu)
        picked, i = [], 0
        while len(picked) < limit:
            added = False
            for k in sorted(by_op):
                if i < len(by_op[k]) and len(picked) < limit:
                    picked.append(by_op[k][i]); added = True
            if not added: break
            i += 1
        out = picked
    return src, out


# A cross-cutting audit names no page -- it globs them all -- so suites_for()
# can never return one, and every mutant of a kind only an audit can catch was
# reported as surviving. audit_escaping kills a seeded `drop-esc` on
# micro-bench outright, and the sweep called it a survivor because it never ran
# it. ADR-047: a survivor list padded with garbage is a worklist nobody
# finishes.
#
# Mapped by KIND, and only where the audit demonstrably kills that kind. There
# is no entry for the other audits: contrast, offline, print and focus are not
# reachable from any mutation this file generates, and adding them on a hunch
# would buy a slower sweep for no kills.
AUDITS_FOR_OP = {"drop-esc": ["audit_escaping.py"]}


def run_audit(name, page, cwd):
    """A page-scoped audit run. Non-zero means it caught the fault."""
    return run_suite_argv([sys.executable, os.path.join(cwd, "tools", name),
                           "--page", page], cwd)


# ---- a mutation inside a module's INLINED copy ------------------------------
#
# Every page carries a verbatim copy of the Field Entry Kit, and some carry Keep,
# the greenhouse engine, Darwin Core or Ordination too. `verify_fek` builds its
# own harness page from `tools/fek.py` and never opens docs/ at all -- correctly,
# because that is what makes it a test of the module rather than of one consumer.
# The consequence is that a mutation to the FEK block INSIDE selection-log.html
# is invisible to every suite the sweep runs for that page, and comes back as a
# survivor. It came back on every page swept so far, which is how a worklist
# teaches you to skim (ADR-047).
#
# It is not a blind spot. `fek_emit.py --check` compares each page's inlined
# block against the module byte for byte and exits non-zero on any difference --
# measured here, not assumed: seeding `Math.max(min,x)` -> `Math.min(min,x)` into
# selection-log's clamp() makes --check report one consumer would be rewritten.
#
# So the coverage is real, in two links: the emitter proves the page's copy IS
# the module, and the module's suite proves the module behaves. Worth being
# precise about what this kill means, which is why the output attributes it to
# `fek_emit` by name rather than to a suite. A mutant killed this way is not
# evidence that anything TESTS that line's behaviour on that page -- it is
# evidence the line is not that page's to change.
MODULE_EMITTER = {"FEK": "fek_emit.py", "KEEP": "keep_emit.py", "GH": "gh_emit.py",
                  "DWC": "dwc_emit.py", "ORD": "ord_emit.py"}


def green_on_clean(run, key, tpath, clean_src, mutant_src, cache):
    """Would this checker pass on the UNMUTATED page?

    The named suites are baselined once, up front, while the scratch tree is
    still clean. The audits and the cross-cutting suites are not: they run only
    when a mutant is otherwise about to survive, which is rare, so baselining
    all of them for every page would be paid for on every mutant and collected
    on almost none. Instead the page is put back for the length of one run, the
    answer is cached per checker, and the mutant is restored.
    """
    if key not in cache:
        io.open(tpath, "w", encoding="utf-8").write(clean_src)
        try:
            cache[key] = (run() == 0)
        finally:
            io.open(tpath, "w", encoding="utf-8").write(mutant_src)
    return cache[key]


def run_emitter(name, cwd):
    """`<module>_emit.py --check`. Non-zero means the inlined copy has drifted."""
    return run_suite_argv([sys.executable, os.path.join(cwd, "tools", name),
                           "--check"], cwd)


def run_suite_argv(argv, cwd, timeout=None):
    timeout = timeout or SUITE_TIMEOUT[0]
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd).returncode
    except subprocess.TimeoutExpired:
        return 99


def cross_cutting():
    """Suites that GLOB the docs instead of naming a page.

    ADR-061 found that cross-cutting AUDITS were excluded from every sweep by
    construction, because suites_for() keeps the suites whose source names the
    page and an audit names none. The same is true of a verify_* suite written
    the same way, and there is one: verify_offline_slice globs docs/*.html and
    checks the shared webfont loader on all of them -- including that the
    deferred link really is promoted back to media="all", which is the half of
    the contract audit_offline does not check.

    So a `neg-guard` mutant on that loader (`if(!l)return` -> `if(l)return`,
    which leaves every page in fallback fonts forever) came back as a survivor
    on cp-characters while a suite in this very repo would have killed it.

    Derived, not listed: a suite qualifies if it globs the docs directory and
    names no page. Fixture-builders are excluded by the same DECLARATION
    suites_for reads, which is how verify_emitters stays out -- one answer to
    the question, in one place, rather than two predicates that can drift.
    """
    pages = {os.path.basename(x) for x in glob.glob(os.path.join(DOCS, "*.html"))}
    out = []
    for s in sorted(glob.glob(os.path.join(VERIFY, "verify_*.py"))):
        txt = io.open(s, encoding="utf-8").read()
        if not re.search(r"glob\.glob\([^)]*DOCS", txt):
            continue
        if any(p in txt for p in pages):
            continue
        # The SAME declaration suites_for reads. This used to be a second,
        # sharper text predicate -- `"shutil" in txt` -- chosen because it
        # separated the suites that copy a whole scratch TREE from the two that
        # write one fixture FILE and otherwise assert about the real kit. Two
        # predicates answering one question is one too many, and they duly
        # disagreed: a comment added to verify_offline_slice that MENTIONED
        # shutil, while explaining the sniff, dropped it out of the cross-cutting
        # set and the webfont killer went back to reporting a survivor. A rule
        # that a sentence about the rule can break is not a rule.
        if FIXTURE_MARK in txt:
            continue
        out.append(s)
    return out


CROSS = None


def suites_for(page):
    """Suites whose source names this page. A suite that never mentions a page
    cannot be expected to notice it changed.

    Returns (kept, skipped). The skipped list is REPORTED rather than dropped
    quietly: this heuristic is a judgement about coverage, and ADR-061 is what a
    silent exclusion costs -- every audit was excluded from every sweep by
    construction and nobody could see it from the output. Measured for
    verify_claims_triage, which names three real pages and also builds a canary:
    it passes the mutants mutate.py generates, because it asserts on rendered
    TEXT and these mutants change interactive behaviour. Right call, and now a
    visible one.

    Ordered so the page's OWN suite runs first. Two reasons, and the second is
    the important one: the common case is a killed mutant, so trying the most
    likely killer first makes the whole sweep affordable -- and a page named by
    a suite only as scaffolding (verify_audit_frontend plants faults IN
    food-web to test the audit) is not covered by it in any useful sense, so it
    should never be the thing that reports a kill."""
    hits, skipped = [], []
    for s in sorted(glob.glob(os.path.join(VERIFY, "verify_*.py"))):
        txt = io.open(s, encoding="utf-8").read()
        if page not in txt:
            continue
        # A suite that builds its own scratch tree names pages as FIXTURES, not
        # as subjects -- verify_audit_frontend plants faults in food-web to test
        # the AUDIT, and verify_emitters perturbs blocks to test the emitters.
        # Counting those as coverage would let a page look tested by a suite
        # that asserts nothing about it, and would make every sweep pay for a
        # ninety-second run that cannot kill a page-logic mutant anyway.
        #
        # DECLARED, not inferred. This used to read "imports tempfile and either
        # shutil or mkdtemp", which is a fact about a suite's imports and not
        # about what it does -- and the day verify_eco needed a temp dir to
        # compile a JDK oracle, 138 checks on the flagship page silently stopped
        # voting on that page's mutants and the sweep reported the escapes they
        # cover as survivors. Same shape as ADR-061: a silent exclusion is worse
        # than a wrong one, because nothing in the output disagrees with it.
        if FIXTURE_MARK in txt:
            skipped.append(os.path.basename(s)[:-3])
            continue
        hits.append(s)
    return hits, skipped


FIXTURE_MARK = 'MUTATE_ROLE = "fixture-builder"'
SUBJECT_MARK = 'MUTATE_ROLE = "subject"'


def marker_drift():
    """Suites that use a temp dir without saying what for.

    The old inference -- "imports tempfile and either shutil or mkdtemp" -- is
    no longer the rule, but it is still a decent smoke alarm, so it is kept as
    the trigger for a QUESTION rather than a decision: a suite that reaches for
    a temp dir is either building fixture pages (not coverage) or doing
    something else entirely (verify_eco compiles a JDK oracle in one), and only
    the person writing it knows which. So the sniff no longer guesses; it
    demands one of the two markers, and reports the suites that carry neither.

    The stale list is the mirror: a suite still declaring itself a
    fixture-builder after its tree went away is sitting out sweeps it could
    win, silently, which is the ADR-061 failure again.  Returns
    (undeclared, stale)."""
    undeclared, stale = [], []
    for s in sorted(glob.glob(os.path.join(VERIFY, "verify_*.py"))):
        txt = io.open(s, encoding="utf-8").read()
        looks = "tempfile" in txt and ("shutil" in txt or "mkdtemp" in txt)
        says = FIXTURE_MARK in txt
        if looks and not says and SUBJECT_MARK not in txt:
            undeclared.append(os.path.basename(s)[:-3])
        if says and not looks: stale.append(os.path.basename(s)[:-3])
    return undeclared, stale


# Mutating a shared module's INLINED COPY inside a page and then running the
# module's own suite cannot work -- and the first version of this tool did
# exactly that. verify_fek builds its harness fresh from tools/fek.py so it can
# never test a stale copy, which is right, and which makes it structurally blind
# to anything done to a page's inlined copy. Adding it to the suite list cost
# runtime and could never kill anything.
#
# The tool told on itself: the SAME FEK mutation survived on ethogram and was
# killed on farm-scout. That difference is real -- verify_fs drives a picker
# filter and verify_etho does not -- but chasing it is what exposed the useless
# suite call underneath.
#
# So a shared-block mutation on a page measures THAT PAGE'S suite, honestly, and
# a module is measured by mutating its own source with --module.
# The third entry is the EMITTER, and leaving it out silently measures nothing.
#
# verify_fek builds its harness from tools/fek.py at run time, so mutating that
# file reaches the suite directly. verify_gh does not: it opens docs/greenhouse.
# html, which is a BUILT artefact with the engine already inlined. Mutating
# tools/gh.py and running verify_gh scored four survivors that a hand test
# killed instantly -- the suite was reading the unmutated copy the whole time.
#
# That is the second time this tool has assumed a suite could see a mutation it
# structurally could not. The first was running verify_fek against a page's
# inlined FEK. Both share a shape: a module's source and the code a suite
# actually executes are two different things unless something regenerates one
# from the other. Where an emitter does that, it has to run.
MODULES = {
    "fek":  ("tools/fek.py",  "tools/verify/verify_fek.py",  None),
    "keep": ("tools/keep.py", "tools/verify/verify_keep.py", "tools/keep_emit.py"),
    "gh":   ("tools/gh.py",   "tools/verify/verify_gh.py",   "tools/gh_emit.py"),
    "dwc":  ("tools/dwc.py",  "tools/verify/verify_dwc.py",  "tools/dwc_emit.py"),
    "ord":  ("tools/ord.py",  "tools/verify/verify_ord.py",  "tools/ord_emit.py"),
}


def viable(text):
    """Does this mutant still parse? node --check on each script block.

    Without this, a mutation that produces a syntax error counts as killed by
    whatever suite ran first -- the page fails to load, every check fails, and
    the score goes up for a mutant that measured nothing at all."""
    blocks = re.findall(r"<script>(.*?)</script>", text, re.S)
    if not blocks:
        blocks = [text]
    for b in blocks:
        fd, p = tempfile.mkstemp(suffix=".js")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(b)
            r = subprocess.run(["node", "--check", p], capture_output=True, text=True,
                               timeout=30)
            if r.returncode != 0:
                return False
        except (OSError, subprocess.TimeoutExpired):
            return True          # cannot tell -- assume viable rather than skip
        finally:
            try: os.unlink(p)
            except OSError: pass
    return True


# A mutant that makes a suite HANG is killed by the timeout -- correctly, since
# a suite that normally finishes in 25 s and now does not finish at all has
# failed by any reading. But at 420 s each, two such mutants cost fifteen
# minutes and the sweep looks stalled rather than working. The budget is
# measured from the suite's own clean runtime instead of guessed.
SUITE_TIMEOUT = [150]


# A suite that prints a failure and exits 0. ADR-046: verify_fek did exactly
# this, so the sweep read every one of its failures as a pass and the Field
# Entry Kit scored 7% when the truth was 95%. The suite was fixed; nothing
# stopped the next one, because an exit code is all this runner ever looked at.
# Anchored and word-bounded, the same shape run_all.py uses: "FAIL" and "FAIL:"
# are results, "FAILURES" in a table header is not.
FAIL_LINE = re.compile(r"^[ \t]*FAIL\b", re.M)

# Suites caught exiting 0 on a failure, reported once at the end rather than on
# every mutant.
LIARS = set()


def run_suite(path, cwd, timeout=None):
    """Non-zero if the suite noticed. A printed failure counts as noticing."""
    timeout = timeout or SUITE_TIMEOUT[0]
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)
        if p.returncode == 0 and FAIL_LINE.search((p.stdout or "") + (p.stderr or "")):
            # It DID notice. Take the signal and name the defect, rather than
            # discarding a real detection because the suite's exit code lied.
            LIARS.add(os.path.basename(path))
            return 1
        return p.returncode
    except subprocess.TimeoutExpired:
        return 99


# Top-level entries the scratch copy leaves out, each with a reason. Anything
# not named here is copied, so the failure direction is a slower copy rather
# than a suite that cannot run.
SCRATCH_SKIP = {
    "build": "generated output; no page or suite reads it, and publish.py rebuilds it",
    "csrbt-core": "the Java engine, 24 MB, reached only through committed session JSON",
    "csrbt-experimental": "the experimental Java tree, 6 MB, same reasoning",
    "csrbt-benchmarks": "the JMH benchmark sources; nothing in docs/ or tools/ reads them",
    "gradle": "the wrapper's jar and properties; nothing in docs/ or tools/ reads it",
    ".git": "history, and by far the largest thing here",
    "_to_delete": "parked older copies of tools; copying them would put stale "
                  "suites in the scratch tree next to the real ones",
}


# ...and paths INSIDE a skipped tree that come across anyway, because a suite
# reads them. Each is one file, named, with the suite that needs it.
#
# The alternative is un-skipping a 6 MB tree to carry a 4 KB file. The cost of
# this list is that it has to be maintained; the cost of not having it is a
# suite that reports NOT VERIFIED inside every sweep and a mutation that lives
# because of it -- which is what happened to the threshold binding the day it
# was written.
SCRATCH_KEEP = {
    os.path.join("csrbt-experimental", "src", "main", "java", "io", "github",
                 "richeyworks", "csrbt", "experimental", "ecology", "FieldReport.java"):
        "verify_engine_sessions binds ecology-lab's plain-English thresholds to it",
}


def scratch_root():
    """A throwaway copy of docs/ and tools/ to mutate.

    The first version of this tool edited docs/ in place and restored in a
    finally, and its own docstring said mutations went to a copy. They did not.
    A finally survives SIGTERM and does not survive SIGKILL, a full disk, or a
    container that goes away -- and the failure mode is a mutant left in the
    real tree, which is the single worst thing a tool like this could do.
    Suites resolve their root from their own file location, so copying both
    directories lets them run entirely inside the scratch tree -- ALMOST.

    The top-level files come too, and finding out why is the whole point of
    ADR-070's guard. `verify_eco` checks every link in the kit resolves, and
    `tree-proofs.html` links to `../README.md`. That file is not in docs/ or
    tools/, so in the scratch copy the link was broken, so verify_eco was red,
    so the guard excluded it -- from every sweep of every page it names, which
    is most of the kit, silently, and reported as "already failing on clean
    code" when it passes 98/98 in the real tree.

    Ninety-eight checks that had never been allowed to testify.

    That fix copied the top-level FILES and stopped, which was the instance and
    not the class: verify_visualizer_sessions reads demo/visualizer.html, and
    demo/ is a directory, so the next sweep reported IT red on the scratch copy
    for the same reason one page later.

    So the default is inverted. Everything at the top level comes across unless
    it is named in SCRATCH_SKIP, which means a directory added to this repo
    tomorrow is copied without anybody remembering to say so -- the same lesson
    KEEP's formSnapshot learned about hand-maintained lists of fields. The
    exclusions are the two large trees and the things that cannot matter:
    together they are 33 of the repo's 44 MB, and no page or suite reads into
    any of them.
    """
    tmp = tempfile.mkdtemp(prefix="csrbt_mutate_")
    for nm in sorted(os.listdir(ROOT)):
        if nm in SCRATCH_SKIP:
            continue
        src, dst = os.path.join(ROOT, nm), os.path.join(tmp, nm)
        if os.path.isdir(src):
            shutil.copytree(src, dst,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)
    for rel in SCRATCH_KEEP:
        src = os.path.join(ROOT, rel)
        if os.path.exists(src):
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    return tmp


def module_sweep(a):
    """Mutate a shared module's own source and run its own suite.

    This is where a module's coverage actually lives. Everything the kit inlines
    is emitted from one file and its suite builds a harness from that file, so
    the module source is the thing to break."""
    if a.module not in MODULES:
        print("unknown module %r -- known: %s" % (a.module, ", ".join(sorted(MODULES))))
        return 1
    rel_src, rel_suite, rel_emit = MODULES[a.module]
    src_path = os.path.join(ROOT, rel_src)
    if not os.path.exists(src_path):
        print("no such module source: %s" % rel_src); return 1

    src, muts = mutants_for(src_path, a.limit, whole_file=True)
    if not muts:
        print("%s: no mutable code found" % rel_src); return 0

    print("mutation sweep -- module %s against %s%s"
          % (a.module, os.path.basename(rel_suite),
             (" (via %s)" % os.path.basename(rel_emit)) if rel_emit else " (built at run time)"))
    print("-" * 78)
    if a.list:
        for mu in muts:
            print("   %-12s line %-6d %s -> %s   [%s]"
                  % (mu["op"], mu["line"], mu["was"], mu["now"], mu["ctx"][:56]))
        return 0

    killed = lived = 0
    survivors = []
    tmp = scratch_root()
    t0 = time.time()
    # Time one clean run and allow four times it. Generous enough that a slow
    # machine does not produce false kills, tight enough that a hang is cheap.
    _t = time.time()
    run_suite(os.path.join(tmp, rel_suite), tmp, timeout=600)
    SUITE_TIMEOUT[0] = max(45, int((time.time() - _t) * 4))
    print("   (clean run %.0f s -- a mutant gets %d s before it counts as hung)"
          % (time.time() - _t, SUITE_TIMEOUT[0]))
    try:
        tsrc = os.path.join(tmp, rel_src)
        tsuite = os.path.join(tmp, rel_suite)
        temit = os.path.join(tmp, rel_emit) if rel_emit else None
        for n, mu in enumerate(muts, 1):
            io.open(tsrc, "w", encoding="utf-8").write(mu["text"])
            if temit:
                # Regenerate the consumers inside the scratch tree, or the suite
                # opens a page that still carries the ORIGINAL module.
                r = subprocess.run([sys.executable, temit], capture_output=True,
                                   text=True, cwd=tmp, timeout=180)
                if r.returncode != 0 and "would change" not in (r.stdout or ""):
                    print("   %3d/%-3d %-12s line %-6d %-8s emitter refused: %s"
                          % (n, len(muts), mu["op"], mu["line"], "unviable",
                             (r.stdout or r.stderr or "").strip().split("\n")[-1][:40]))
                    continue
            caught = run_suite(tsuite, tmp) != 0
            if caught: killed += 1
            else:
                lived += 1
                survivors.append((rel_src, mu))
            print("   %3d/%-3d %-12s line %-6d %-8s %s"
                  % (n, len(muts), mu["op"], mu["line"],
                     "killed" if caught else "SURVIVED", mu["ctx"][:44]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 78)
    total = killed + lived
    print("%d mutant(s) in %.0f s: %d killed, %d survived"
          % (total, time.time()-t0, killed, lived))
    if total: print("mutation score: %.0f%%" % (100.0*killed/total))
    for rel, mu in survivors:
        print("  %-16s %-12s line %-6d %s -> %s"
              % (rel, mu["op"], mu["line"], mu["was"], mu["now"]))
        print("  %-16s %s" % ("", mu["ctx"][:70]))
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="a page in docs/")
    ap.add_argument("--module", help="a shared module: " + ", ".join(sorted(MODULES)))
    ap.add_argument("--all", action="store_true", help="every page that has a suite")
    ap.add_argument("--limit", type=int, default=25, help="mutants per page (default 25)")
    ap.add_argument("--list", action="store_true", help="print mutants and run nothing")
    ap.add_argument("--status", action="store_true",
                    help="how far the sweep has got -- counts computed, not stored")
    ap.add_argument("--record", metavar="ADR",
                    help="append this run to tools/sweep_ledger.json under that ADR")
    a = ap.parse_args(argv)

    if a.status:
        import sweep_ledger
        print("\n".join(sweep_ledger.status_lines()))
        return 0

    if a.module:
        return module_sweep(a)

    pages = []
    if a.all:
        pages = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(DOCS, "*.html")))]
    elif a.page:
        pages = [a.page]
    else:
        ap.error("give --page NAME or --all")

    print("mutation sweep -- seeding faults and watching whether anything notices")
    print("root: %s" % ROOT)
    print("-" * 78)

    grand_killed = grand_survived = grand_nosuite = 0
    survivors = []
    t0 = time.time()

    for page in pages:
        path = os.path.join(DOCS, page)
        if not os.path.exists(path):
            print("%-28s no such page" % page); continue
        src, muts = mutants_for(path, a.limit)
        if not muts:
            print("%-28s no mutable code found" % page); continue
        global CROSS
        if CROSS is None:
            CROSS = cross_cutting()
        suites, skipped = suites_for(page)
        if skipped:
            print("%-28s excluded (declares itself a fixture-builder, so it names this "
                  "page as a fixture): %s" % ("", ", ".join(skipped)))
        _und, _stale = marker_drift()
        if _und:
            print("%-28s NOTE: uses a temp dir and declares neither role, so the sweep "
                  "is guessing it is coverage: %s" % ("", ", ".join(_und)))
        if _stale:
            print("%-28s NOTE: declares itself a fixture-builder but no longer looks like "
                  "one, so it is sitting out sweeps: %s" % ("", ", ".join(_stale)))
        # "No suite names this page" is not the same as "nothing covers this
        # page": the cross-cutting suites reach every page in docs/ precisely
        # BECAUSE they name none of them, and this guard used to return before
        # they were ever consulted. So a page whose only cover is cross-cutting
        # was reported as having none, and its mutants were binned as unrunnable
        # rather than run -- the ADR-061 defect one more time, in the branch
        # written to report it.
        if not suites and not CROSS:
            print("%-28s %3d mutant(s)  NOTHING COVERS THIS PAGE -- no suite names it and "
                  "there are no cross-cutting suites, so every mutant survives by default"
                  % (page, len(muts)))
            grand_nosuite += len(muts)
            continue
        if not suites:
            print("%-28s %3d mutant(s), no suite NAMES this page -- run against the "
                  "cross-cutting suites only: %s"
                  % (page, len(muts),
                     ", ".join(os.path.basename(x)[:-3] for x in CROSS)))

        if a.list:
            print("%s  -- %d mutant(s), suites: %s"
                  % (page, len(muts), ", ".join(os.path.basename(s)[:-3] for s in suites)))
            for mu in muts:
                print("   %-12s %-5s line %-6d %s -> %s   [%s]"
                      % (mu["op"], mu["block"], mu["line"], mu["was"], mu["now"], mu["ctx"][:52]))
            print()
            continue

        print("%s  -- %d mutant(s) against %s"
              % (page, len(muts), ", ".join(os.path.basename(s)[:-3] for s in suites)))
        killed = lived = unviable = 0
        tmp = scratch_root()
        try:
            tpath = os.path.join(tmp, "docs", page)
            tsuites = [os.path.join(tmp, "tools", "verify", os.path.basename(s))
                       for s in suites]

            # ---- a suite has to be able to testify before it is believed ----
            #
            # Three ways this runner has been fooled into reporting a kill:
            #
            #   ADR-046  a suite printed FAIL and exited 0, so every failure read
            #            as a pass and FEK scored 7% against a true 95%.
            #   ADR-069  a suite was already RED on clean code, so it returned
            #            non-zero for every mutant. 33% -> 100% in three seconds.
            #   ADR-069  a suite compared PUBLISH DIGESTS, so any edit failed it
            #            -- and a sweep edits the page by construction. 100%
            #            again, an hour later, for a different reason.
            #
            # One probe settles all three: run each suite against the page with
            # a COMMENT APPENDED. That changes the bytes and cannot change the
            # behaviour, so a suite that passes it is green AND is not measuring
            # the file. A suite that fails gets one more run, on the clean page,
            # only to say WHICH of the two it is -- so the common case costs one
            # run per suite rather than two. run_suite() reports a printed
            # failure as a failure whatever the exit code, which is what puts
            # the ADR-046 shape into the same net.
            NULL = src + "\n<!-- sweep: byte-only edit, no behaviour changes -->\n"
            io.open(tpath, "w", encoding="utf-8").write(NULL)
            red, liars, bytesy = [], [], []
            for s in list(tsuites):
                before = set(LIARS)
                if run_suite(s, tmp) == 0:
                    continue                     # green, and blind to the edit
                nm = os.path.basename(s)[:-3].replace("verify_", "")
                tsuites.remove(s)
                if LIARS - before:
                    liars.append(nm); continue
                io.open(tpath, "w", encoding="utf-8").write(src)
                clean_rc = run_suite(s, tmp)
                io.open(tpath, "w", encoding="utf-8").write(NULL)
                (red if clean_rc != 0 else bytesy).append(nm)
            io.open(tpath, "w", encoding="utf-8").write(src)
            if red:
                print("%-28s EXCLUDED, red on the UNMUTATED scratch copy -- a red suite "
                      "kills every mutant. If it passes in the real tree, the scratch "
                      "copy is missing something it reads: %s" % ("", ", ".join(red)))
            if liars:
                print("%-28s EXCLUDED, prints a failure and exits 0 on clean code -- "
                      "the ADR-046 defect: %s" % ("", ", ".join(liars)))
            if bytesy:
                print("%-28s EXCLUDED, fails on a comment appended to the page -- it is "
                      "measuring bytes, not behaviour: %s" % ("", ", ".join(bytesy)))

            # Same distinction as the guard above: no GREEN NAMING suite is not
            # the same as nothing to measure against, because the cross-cutting
            # suites are still there and are the whole reason a page nothing
            # names is covered at all.
            if not tsuites and not CROSS:
                print("%-28s no green suite names this page and there are no "
                      "cross-cutting suites -- nothing to measure against" % "")
                grand_nosuite += len(muts)
                continue
            if not tsuites:
                print("%-28s no green suite NAMES this page -- measured against the "
                      "cross-cutting suites alone" % "")

            _clean = {}
            for n, mu in enumerate(muts, 1):
                io.open(tpath, "w", encoding="utf-8").write(mu["text"])
                if not viable(mu["text"]):
                    # A page that will not parse is killed by every suite for
                    # free, which flatters the score without measuring anything.
                    # Counted separately and excluded from the ratio.
                    unviable += 1
                    print("   %3d/%-3d %-12s %-5s line %-6d %-8s %-10s %s"
                          % (n, len(muts), mu["op"], mu["block"], mu["line"],
                             "unviable", "", mu["ctx"][:38]))
                    continue
                caught, by = False, ""
                for s in tsuites:
                    if run_suite(s, tmp) != 0:
                        caught = True
                        by = os.path.basename(s)[:-3].replace("verify_", "")
                        break
                # The drift check first, when the mutation landed in an
                # inlined module: it is one cheap subprocess and it settles the
                # commonest survivor in the kit.
                if not caught and mu["block"] in MODULE_EMITTER:
                    em = MODULE_EMITTER[mu["block"]]
                    if os.path.exists(os.path.join(tmp, "tools", em)):
                        if run_emitter(em, tmp) != 0:
                            caught = True
                            by = em[:-3]
                if not caught:
                    for aud in AUDITS_FOR_OP.get(mu["op"], []):
                        if run_audit(aud, page, tmp) != 0 and green_on_clean(
                                lambda: run_audit(aud, page, tmp),
                                aud, tpath, src, mu["text"], _clean):
                            caught = True
                            by = aud[:-3]
                            break
                # Last, and only for something still alive: the cross-cutting
                # suites. They are the slowest thing here and the rarest to
                # fire, so they are paid for only when the alternative is a
                # survivor -- which costs a human far more than seventeen
                # seconds of CPU.
                if not caught:
                    for s in CROSS:
                        tp = os.path.join(tmp, "tools", "verify", os.path.basename(s))
                        if run_suite(tp, tmp) != 0 and green_on_clean(
                                lambda tp=tp: run_suite(tp, tmp),
                                tp, tpath, src, mu["text"], _clean):
                            caught = True
                            by = os.path.basename(s)[:-3].replace("verify_", "")
                            break
                if caught:
                    killed += 1
                    mark = "killed"
                else:
                    lived += 1
                    mark = "SURVIVED"
                    survivors.append((page, mu))
                print("   %3d/%-3d %-12s %-5s line %-6d %-8s %-10s %s"
                      % (n, len(muts), mu["op"], mu["block"], mu["line"], mark, by,
                         mu["ctx"][:38]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print("   %d killed, %d survived%s"
              % (killed, lived, (", %d unviable" % unviable) if unviable else ""))
        if a.record:
            import sweep_ledger
            n_fresh = len([1 for p_, m_ in survivors
                           if p_ == page and not examined(m_)])
            sweep_ledger.append(page, a.record, killed=killed, survived=lived,
                                fresh=n_fresh)
            print("   recorded in tools/sweep_ledger.json under %s" % a.record)
        print()
        grand_killed += killed; grand_survived += lived

    if a.list: return 0

    print("-" * 78)
    total = grand_killed + grand_survived
    print("%d mutant(s) run in %.0f s: %d killed, %d survived"
          % (total, time.time() - t0, grand_killed, grand_survived))
    if total:
        print("mutation score: %.0f%%" % (100.0 * grand_killed / total))
    if LIARS:
        print("")
        print("SUITES THAT EXIT 0 ON A FAILURE -- their detections were counted, but")
        print("an exit code that lies is what made the Field Entry Kit read 7%% in")
        print("ADR-046. Fix the suite: %s" % ", ".join(sorted(LIARS)))
    if grand_nosuite:
        print("%d mutant(s) on pages NO suite names -- not run, and not a score"
              % grand_nosuite)
    if survivors:
        print("")
        fresh = [(p_, m_) for p_, m_ in survivors if not examined(m_)]
        old = [(p_, m_) for p_, m_ in survivors if examined(m_)]
        print("SURVIVORS -- every relevant suite passed with these faults in place.")
        print("Each is a question, not a verdict: unreachable code and equivalent")
        print("mutants survive too, and there is no general way to tell them apart.")
        for page, mu in fresh:
            print("  %-24s %-12s %-5s line %-6d %s -> %s"
                  % (page, mu["op"], mu["block"], mu["line"], mu["was"], mu["now"]))
            print("  %-24s %s" % ("", mu["why"]))
            print("  %-24s %s" % ("", mu["ctx"][:70]))
        if not fresh:
            print("  (none that have not already been examined)")
        if old:
            print("")
            print("ALREADY EXAMINED -- survivors triaged in an earlier slice and left,")
            print("with the measurement that settled each one. Not a licence: the")
            print("operator AND the context both have to match.")
            for page, mu in old:
                print("  %-24s %-12s line %-6d %s" % (page, mu["op"], mu["line"], mu["ctx"][:40]))
                print("  %-24s %s" % ("", examined(mu)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
