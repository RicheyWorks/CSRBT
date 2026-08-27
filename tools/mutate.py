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
    ("lte->lt", "c<=0",
     "soil-recipes fmtCup's zero guard; measured: 51 quantities in the RECIPES "
     "literal with a minimum of 0.25, and the batch dial's smallest multiplier "
     "is 0.25, so the smallest value fmtCup can ever see is 0.0625"),
    ("lte->lt", "lam<=0",
     "field-season's Poisson draw; with lam=0 the guard is redundant -- L=exp(0)=1 "
     "and the do/while exits on the first draw because the PRNG returns t/2^32 < 1, "
     "so k-1 = 0 either way"),
    ("lte->lt", "t<=4",
     "tree-proofs chart gridlines: five lines at 0/25/50/75/100% become four. "
     "Chart furniture, no claim depends on it -- examined and left"),
    ("lte->lt", "sq<=0",
     "the squares-counted guard; same clamp, measured: typing 0 or -3 both "
     "yield hidden cSq = 1"),
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


def run_suite_argv(argv, cwd, timeout=None):
    timeout = timeout or SUITE_TIMEOUT[0]
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd).returncode
    except subprocess.TimeoutExpired:
        return 99


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
        if "tempfile" in txt and ("shutil" in txt or "mkdtemp" in txt):
            skipped.append(os.path.basename(s)[:-3])
            continue
        hits.append(s)
    return hits, skipped


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


def run_suite(path, cwd, timeout=None):
    timeout = timeout or SUITE_TIMEOUT[0]
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)
        return p.returncode
    except subprocess.TimeoutExpired:
        return 99


def scratch_root():
    """A throwaway copy of docs/ and tools/ to mutate.

    The first version of this tool edited docs/ in place and restored in a
    finally, and its own docstring said mutations went to a copy. They did not.
    A finally survives SIGTERM and does not survive SIGKILL, a full disk, or a
    container that goes away -- and the failure mode is a mutant left in the
    real tree, which is the single worst thing a tool like this could do.
    Suites resolve their root from their own file location, so copying both
    directories is enough for them to run entirely inside the scratch tree.
    """
    tmp = tempfile.mkdtemp(prefix="csrbt_mutate_")
    shutil.copytree(DOCS, os.path.join(tmp, "docs"))
    shutil.copytree(os.path.join(ROOT, "tools"), os.path.join(tmp, "tools"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
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
    a = ap.parse_args(argv)

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
        suites, skipped = suites_for(page)
        if skipped:
            print("%-28s excluded (builds a scratch tree, so it names this page as a "
                  "fixture): %s" % ("", ", ".join(skipped)))
        if not suites:
            print("%-28s %3d mutant(s)  NO SUITE NAMES THIS PAGE -- every mutant survives "
                  "by default" % (page, len(muts)))
            grand_nosuite += len(muts)
            continue

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
                if not caught:
                    for aud in AUDITS_FOR_OP.get(mu["op"], []):
                        if run_audit(aud, page, tmp) != 0:
                            caught = True
                            by = aud[:-3]
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
        print()
        grand_killed += killed; grand_survived += lived

    if a.list: return 0

    print("-" * 78)
    total = grand_killed + grand_survived
    print("%d mutant(s) run in %.0f s: %d killed, %d survived"
          % (total, time.time() - t0, grand_killed, grand_survived))
    if total:
        print("mutation score: %.0f%%" % (100.0 * grand_killed / total))
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
