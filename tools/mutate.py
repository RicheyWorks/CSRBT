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
    _op("gte->gt", r">=", ">",
        "an inclusive boundary becomes exclusive -- the classic off-by-one"),
    _op("lte->lt", r"<=", "<",
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


def suites_for(page):
    """Suites whose source names this page. A suite that never mentions a page
    cannot be expected to notice it changed.

    Ordered so the page's OWN suite runs first. Two reasons, and the second is
    the important one: the common case is a killed mutant, so trying the most
    likely killer first makes the whole sweep affordable -- and a page named by
    a suite only as scaffolding (verify_audit_frontend plants faults IN
    food-web to test the audit) is not covered by it in any useful sense, so it
    should never be the thing that reports a kill."""
    hits = []
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
            continue
        hits.append(s)
    return hits


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
MODULES = {
    "fek":  ("tools/fek.py",  "tools/verify/verify_fek.py"),
    "keep": ("tools/keep.py", "tools/verify/verify_keep.py"),
    "gh":   ("tools/gh.py",   "tools/verify/verify_gh.py"),
    "dwc":  ("tools/dwc.py",  "tools/verify/verify_dwc.py"),
    "ord":  ("tools/ord.py",  "tools/verify/verify_ord.py"),
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


def run_suite(path, cwd, timeout=420):
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
    rel_src, rel_suite = MODULES[a.module]
    src_path = os.path.join(ROOT, rel_src)
    if not os.path.exists(src_path):
        print("no such module source: %s" % rel_src); return 1

    src, muts = mutants_for(src_path, a.limit, whole_file=True)
    if not muts:
        print("%s: no mutable code found" % rel_src); return 0

    print("mutation sweep -- module %s against %s"
          % (a.module, os.path.basename(rel_suite)))
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
    try:
        tsrc = os.path.join(tmp, rel_src)
        tsuite = os.path.join(tmp, rel_suite)
        for n, mu in enumerate(muts, 1):
            io.open(tsrc, "w", encoding="utf-8").write(mu["text"])
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
        suites = suites_for(page)
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
        print("SURVIVORS -- every relevant suite passed with these faults in place.")
        print("Each is a question, not a verdict: unreachable code and equivalent")
        print("mutants survive too, and there is no general way to tell them apart.")
        for page, mu in survivors:
            print("  %-24s %-12s %-5s line %-6d %s -> %s"
                  % (page, mu["op"], mu["block"], mu["line"], mu["was"], mu["now"]))
            print("  %-24s %s" % ("", mu["why"]))
            print("  %-24s %s" % ("", mu["ctx"][:70]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
