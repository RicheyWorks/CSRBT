# -*- coding: utf-8 -*-
"""The sweep measures the suites. Nothing measured the sweep.

WHY THIS EXISTS

`mutate.py` is the instrument that says how much of this kit is really tested,
and it has now been fooled into reporting a kill three separate times:

  ADR-046  a suite printed FAIL and exited 0, so every failure read as a pass
           and the Field Entry Kit scored 7% when the truth was 95%.
  ADR-069  a suite was already RED on clean code, so it returned non-zero for
           every mutant. selection-log went from 33% to 100% in three seconds.
  ADR-069  a suite compared PUBLISH DIGESTS, so any edit failed it -- and a
           sweep edits the page by construction. 100% again, for a second
           reason, on the same page, an hour later.

Each of those was found by accident, by somebody noticing a number that looked
too good. Nothing in the kit could have caught any of them, because the
fifty-three suites test the pages and nothing tested the thing that tests them
(ADR-040: the finder was the defect).

HOW IT WORKS

A scratch tree with one small page and four deliberately pathological suites --
one honest, one always-red, one that fails on any byte change, one that prints
FAIL and exits 0 -- then `mutate.py` is run against it and its OUTPUT is read.

The point of building the suites rather than mocking the runner is that the
runner's guards are subprocess-level: they are about exit codes and printed
reasons, and a mock of those would be a test of the mock.

Run:  python3 tools/verify/verify_mutate.py
"""
import io, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))


# ---- the page under test -------------------------------------------------
# Small on purpose: every mutant costs four subprocess runs, and the point is
# the runner's bookkeeping, not the page's arithmetic.
PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Fake</title></head>
<body><div id="out"></div>
<script>
/* a comment carrying Math.max( and >= that must never be mutated */
function widest(a, b){ return Math.max(a, b); }
function atLeast(n){ return n >= 3; }
document.getElementById("out").textContent = widest(2, 5) + ":" + atLeast(3);
</script>
</body></html>
"""

HONEST = '''# names fake.html
import io, os, sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
src = io.open(os.path.join(ROOT, "docs", "fake.html"), encoding="utf-8").read()
bad = ("Math.min(a, b)" in src) or ("n > 3" in src)
print("1/1" if not bad else "0/1")
sys.exit(1 if bad else 0)
'''

ALWAYS_RED = '''# names fake.html and is simply broken
import sys
print("0/1  this suite is red on clean code")
sys.exit(1)
'''

# The shape of verify_label_escaping section 5: it compares the page against a
# recorded digest, so it fails on any edit at all -- including one that cannot
# change behaviour.
BYTE_SENSITIVE = '''# names fake.html
import io, os, sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
src = io.open(os.path.join(ROOT, "docs", "fake.html"), encoding="utf-8").read()
ok = (len(src) == %d)
print("1/1" if ok else "0/1  bytes differ from the stamp")
sys.exit(0 if ok else 1)
'''

# The subtler shape, and the one that actually happened. Silent and exit 0 on
# clean code, so it passes every baseline; prints FAIL and STILL exits 0 once
# something is wrong. That is verify_fek as ADR-046 found it.
SNEAKY = '''# names fake.html
import io, os, sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
src = io.open(os.path.join(ROOT, "docs", "fake.html"), encoding="utf-8").read()
if ("Math.min(a, b)" in src) or ("n > 3" in src):
    print("FAIL: the page is broken and I am exiting zero about it")
print("1/1")
sys.exit(0)
'''

LIAR = '''# names fake.html, prints FAIL, exits 0 -- the ADR-046 defect
import sys
print("FAIL: something is wrong and I am going to exit zero about it")
sys.exit(0)
'''


def build(tmp, suites):
    os.makedirs(os.path.join(tmp, "docs"))
    os.makedirs(os.path.join(tmp, "tools", "verify"))
    io.open(os.path.join(tmp, "docs", "fake.html"), "w", encoding="utf-8").write(PAGE)
    shutil.copy(os.path.join(ROOT, "tools", "mutate.py"), os.path.join(tmp, "tools"))
    for name, body in suites.items():
        io.open(os.path.join(tmp, "tools", "verify", name), "w", encoding="utf-8").write(body)


def sweep(tmp, extra=()):
    p = subprocess.run([sys.executable, os.path.join(tmp, "tools", "mutate.py"),
                        "--page", "fake.html", "--limit", "4"] + list(extra),
                       capture_output=True, text=True, cwd=tmp, timeout=600)
    return p.stdout + p.stderr


def score(out):
    m = re.search(r"mutation score: (\d+)%", out)
    return int(m.group(1)) if m else None


# ---- 1. the honest case, so nothing below is vacuous ---------------------
tmp = tempfile.mkdtemp(prefix="verify-mutate-")
try:
    build(tmp, {"verify_fake_good.py": HONEST})
    out = sweep(tmp)
    ck("a suite that really detects the fault scores 100%", score(out) == 100, out[-400:])
    ck("and the kill is attributed to it by name", "fake_good" in out, out[-400:])
    ck("the page's mutants are found at all", re.search(r"\d+ mutant\(s\) run", out), out[-300:])
    # A comment containing the same tokens must never be mutated: a mutant in a
    # comment changes nothing, survives, and buries the real survivors.
    ck("no mutant is generated inside a JS comment",
       "line 4 " not in out, [l for l in out.split("\n") if " line 4 " in l][:2])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 2. a suite that is red on clean code cannot testify -----------------
tmp = tempfile.mkdtemp(prefix="verify-mutate-")
try:
    build(tmp, {"verify_fake_good.py": HONEST, "verify_fake_red.py": ALWAYS_RED})
    out = sweep(tmp)
    ck("a suite red on the unmutated copy is excluded",
       "EXCLUDED, red on the UNMUTATED scratch copy" in out, out[-500:])
    # The wording matters and is asserted: this suite passes 98/98 in the real
    # tree and was red only in the scratch copy, and the old message -- "already
    # failing on clean code" -- sent the reader to look at the suite instead of
    # at the copy. It took a page sweep printing that line about verify_eco to
    # notice, so the line now says where to look.
    ck("and the message points at the scratch copy, not at the suite's own health",
       "If it passes in the real tree" in out, out[-500:])
    ck("and it is named in the exclusion", "fake_red" in out.split("EXCLUDED")[1][:200] if "EXCLUDED" in out else False,
       out[-500:])
    ck("no kill is ever attributed to it", not re.search(r"killed\s+fake_red", out),
       [l for l in out.split("\n") if "fake_red" in l][:3])
    ck("the score still comes from the honest suite", score(out) == 100, out[-400:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 3. a suite that measures bytes cannot testify either ----------------
tmp = tempfile.mkdtemp(prefix="verify-mutate-")
try:
    build(tmp, {"verify_fake_bytes.py": BYTE_SENSITIVE % len(PAGE)})
    out = sweep(tmp)
    ck("a byte-sensitive suite passes its own baseline",
       "red on the UNMUTATED scratch copy" not in out, out[-400:])
    ck("but is excluded by the null edit", "measuring bytes, not behaviour" in out, out[-500:])
    ck("and with nothing left, the page is reported as unmeasured, not as 100%",
       score(out) is None and "no green suite" in out, out[-400:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 4. a suite that prints FAIL and exits 0 ----------------------------
# ADR-046's defect, from the runner's side. The suite there was fixed; nothing
# stops the next one, and the runner reads an exit code it cannot check.
tmp = tempfile.mkdtemp(prefix="verify-mutate-")
try:
    build(tmp, {"verify_fake_liar.py": LIAR})
    out = sweep(tmp)
    ck("a suite that prints FAIL and exits 0 is excluded",
       "prints a failure and exits 0" in out, out[-500:])
    ck("and the page is not scored on it",
       score(out) is None, out[-400:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 4b. and the one that passes its baseline and lies later ------------
# Excluding this one would throw away a real detection: it DID notice. The
# runner takes the signal, counts the kill, and names the suite at the end.
tmp = tempfile.mkdtemp(prefix="verify-mutate-")
try:
    build(tmp, {"verify_fake_sneaky.py": SNEAKY})
    out = sweep(tmp)
    ck("a suite silent on clean code is not excluded at baseline",
       "EXCLUDED" not in out, out[-400:])
    ck("its printed failure is counted as a kill even though it exited 0",
       score(out) == 100, out[-400:])
    ck("and the runner says the suite's exit code lied",
       "SUITES THAT EXIT 0 ON A FAILURE" in out and "verify_fake_sneaky.py" in out,
       out[-500:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 5. an unviable mutant is not a kill -------------------------------
# A mutation that leaves JavaScript that will not parse is "caught" by every
# suite for free, because the page does not load and every check fails. Those
# flatter the score without measuring anything, and are counted separately.
tmp = tempfile.mkdtemp(prefix="verify-mutate-")
try:
    build(tmp, {"verify_fake_good.py": HONEST})
    out = sweep(tmp, ["--list"])
    ck("--list prints mutants and runs nothing",
       "mutant(s), suites:" in out and "killed" not in out, out[-300:])
    ops = set(re.findall(r"^\s+(\S+)\s+\S+\s+line", out, re.M))
    ck("the operators that apply to this page are the ones generated",
       ops <= {"max->min2", "gte->gt", "num-shift", "off-by-one", "neg-guard",
               "and->or", "lte->lt", "max->min", "drop-esc", "drop-half"},
       sorted(ops))
    ck("and there is at least one, so the fixture is not empty", bool(ops), sorted(ops))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 6. the scratch tree has to be a tree the suites can run in ---------
# Not hypothetical, and not caught by anything above: verify_eco checks that
# every link in the kit resolves, and tree-proofs.html links to ../README.md.
# scratch_root() copied docs/ and tools/ and nothing else, so that link was
# broken in every scratch copy, so verify_eco was red in every sweep, so the
# guard excluded it -- from every page it names, silently, while blaming the
# suite. Ninety-eight checks that had never once been allowed to testify.
#
# The guard was right to exclude a red suite. The instrument it was reading was
# broken, and the only way to see that was to ask whether the scratch copy is
# actually the tree.
sys.path.insert(0, os.path.join(ROOT, "tools"))
import mutate as _mu
_scratch = _mu.scratch_root()
try:
    # "Every top-level FILE" was the first version of this check, and it passed
    # while demo/ was missing -- so verify_visualizer_sessions, which reads
    # demo/visualizer.html, was red on the scratch copy one page after the
    # README fix went in. The instance, not the class.
    #
    # The rule now matches the tool's: everything except a NAMED exclusion. A
    # directory added to this repo is copied by default and this check passes
    # by default; leaving something out has to be a deliberate, visible act.
    real = set(os.listdir(ROOT)) - set(_mu.SCRATCH_SKIP)
    got = set(os.listdir(_scratch))
    ck("the scratch copy carries every top-level entry that is not explicitly skipped",
       real <= got, sorted(real - got))
    ck("and the fixture is not vacuous -- there ARE entries to carry", bool(real), sorted(real))
    ck("every skipped entry has a reason written beside it",
       all(isinstance(v, str) and len(v) > 20 for v in _mu.SCRATCH_SKIP.values()),
       sorted(k for k, v in _mu.SCRATCH_SKIP.items() if not (isinstance(v, str) and len(v) > 20)))
    for _rel, _why in _mu.SCRATCH_KEEP.items():
        ck("a file carried out of a skipped tree is really there: %s"
           % os.path.basename(_rel), os.path.exists(os.path.join(_scratch, _rel)),
           _rel)
        ck("...and it exists in the real tree too, so the entry is not stale",
           os.path.exists(os.path.join(ROOT, _rel)), _rel)
        ck("...with a reason written beside it", isinstance(_why, str) and len(_why) > 20, _why)
    ck("nothing docs/ or tools/ needs is on the skip list",
       not ({"docs", "tools", "demo"} & set(_mu.SCRATCH_SKIP)), sorted(_mu.SCRATCH_SKIP))
    ck("docs/ and tools/ are both in the scratch copy",
       os.path.isdir(os.path.join(_scratch, "docs"))
       and os.path.isdir(os.path.join(_scratch, "tools")), sorted(os.listdir(_scratch)))
    # The two files that started it, both resolved from inside the copy:
    # tree-proofs.html's ../README.md, and the demo page a suite reads directly.
    ck("a page a suite reads outside docs/ is in the scratch copy",
       os.path.exists(os.path.join(_scratch, "demo", "visualizer.html")),
       sorted(os.listdir(_scratch)))
    # The link that started it, resolved from inside the copy.
    _tp = os.path.join(_scratch, "docs", "tree-proofs.html")
    if os.path.exists(_tp):
        _src = io.open(_tp, encoding="utf-8").read()
        _links = sorted(set(re.findall(r'href="(\.\./[^"#?]+)"', _src)))
        _bad = [l for l in _links
                if not os.path.exists(os.path.normpath(os.path.join(_scratch, "docs", l)))]
        ck("a page's links out of docs/ still resolve inside the scratch copy",
           not _bad, _bad)
finally:
    shutil.rmtree(_scratch, ignore_errors=True)

print("PASS %d" % len(P))
for x in F: print("FAIL:", x)
print("-" * 70)
print("%d/%d" % (len(P), len(P) + len(F)))
sys.exit(1 if F else 0)
