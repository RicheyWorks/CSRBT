# -*- coding: utf-8 -*-
"""The CI workflow's path filter is held to what the build actually reads.

ADR-202. The workflow runs a two-JDK Gradle matrix on every push to every
branch. Every slice since ADR-190-something has touched no Java at all, so each
one spent two runners rebuilding a tree nothing in it had changed -- and the
owner ran out of Actions minutes, which means the check is now DARK on the
pushes that do matter.

A path filter fixes that and introduces a new way to be wrong: a filter that
does not cover a file the build reads makes the build skip a change that could
break it, and nothing says so. The filter is a claim about the build, so it is
held to the build.

THE MATCHER IS APPROXIMATE AND SAYS SO. GitHub's filter syntax is its own
thing; what is implemented here covers the forms this workflow uses -- a
literal path, a `*` that does not cross a separator, and a `**` that does --
and any pattern outside those forms is a FAILURE rather than a silent pass,
because a pattern this file cannot evaluate is a pattern this file cannot hold
anything to.
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _kit

ROOT = _kit.ROOT
WF = os.path.join(ROOT, ".github", "workflows", "ci.yml")

P, F = [], []


def ck(cond, msg):
    (P if cond else F).append(msg)


# ---------------------------------------------------------------- the matcher
SIMPLE = re.compile(r"^[A-Za-z0-9_.*/-]+$")


def to_regex(pat):
    """A GitHub path filter as a regex, or None if the pattern is out of scope.

    Order matters: `**` is consumed before `*`, or the second star of a `**`
    would be read as a separate single-segment wildcard and the pattern would
    silently stop matching across directories -- which is the one mistake that
    makes a filter look right and cover nothing.
    """
    if not SIMPLE.match(pat or ""):
        return None
    out, i = [], 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if pat[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pat[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
            continue
        out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(pats, path):
    for p in pats:
        rx = to_regex(p)
        if rx and rx.match(path):
            return True
    return False


# ------------------------------------------------------------- the workflow
ck(os.path.exists(WF), "the workflow this suite is about exists: .github/workflows/ci.yml")
src = io.open(WF, encoding="utf-8").read() if os.path.exists(WF) else ""


def filter_of(event):
    """The `paths:` list under one event in `on:`.

    Parsed by indentation rather than with a YAML library, because this kit
    ships no dependency for one and the shape being read is four lines deep and
    fixed. A shape this cannot parse reads as an empty filter, which fails the
    checks below rather than passing them.
    """
    m = re.search(r"\n  %s:\n((?:    .*\n|\n)*)" % re.escape(event), src)
    if not m:
        return None
    body = m.group(1)
    m2 = re.search(r"    paths:\n((?:      - .*\n)+)", body)
    if not m2:
        return []
    return [re.sub(r'^\s*-\s*"?|"?\s*$', "", l) for l in m2.group(1).rstrip("\n").split("\n")]


push = filter_of("push")
pr = filter_of("pull_request")

ck(push, "THE PUSH EVENT CARRIES A PATH FILTER. Without one the two-JDK matrix rebuilds the Java "
         "tree on every push, including the harness slices that contain no Java at all -- which is "
         "how a repository runs out of Actions minutes and the check goes dark on the pushes that "
         "DO touch the build: %r" % (push,))
ck(pr, "and so does pull_request, or a branch could skip the build on the way in and run it on the "
       "way to main: %r" % (pr,))
ck(push == pr,
   "and they are THE SAME LIST. Two filters that drift apart mean a change can be built on the "
   "branch and skipped on the merge, or the reverse, and which one you get depends on how the "
   "change arrived rather than on what it touched:\n  push %r\n  pr   %r" % (push, pr))

ck(to_regex("csrbt-core/src/**/[ab]/*.java") is None
   and to_regex("**/*.java") is not None,
   "A PATTERN OUT OF SCOPE IS REFUSED, not quietly treated as covering everything. The matcher is "
   "what every check below rests on; one that answered yes to a pattern it had not understood "
   "would hold the filter to nothing while reporting that it held")
bad = [p for p in (push or []) if to_regex(p) is None]
ck(not bad,
   "every pattern in the filter is one this suite can evaluate. A pattern it cannot read is a "
   "pattern it cannot hold the build to, and passing over it silently would make this whole file "
   "decoration: %s" % bad)

# ------------------------------------------------- what the build actually reads
#
# Everything Gradle compiles, packages or is configured by. Collected from the
# tree rather than listed here, so a module added tomorrow is covered by the
# check on the day it appears rather than on the day somebody remembers.
build_files, others = [], []
# followlinks, because the mutant runner builds its tree out of symlinks to
# this one and a walk that stopped at them would find no build at all -- which
# would make every check below pass on an empty list, the exact shape of a
# suite that cannot fail.
for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=True):
    dirnames[:] = [d for d in dirnames
                   if d not in (".git", "build", ".gradle", "node_modules", "__pycache__")]
    for fn in filenames:
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
        is_build = (
            rel.endswith((".java", ".kt", ".kts"))
            or "/src/" in rel
            or rel.startswith("gradle/")
            or rel in ("gradlew", "gradlew.bat", "gradle.properties")
        )
        (build_files if is_build else others).append(rel)

ck(len(build_files) > 50,
   "the tree has a Java build to be about at all: %d file(s)" % len(build_files))

missed = [f for f in build_files if not matches(push or [], f)]
ck(not missed,
   "EVERY FILE THE BUILD READS IS INSIDE THE FILTER. A filter that misses one makes the build skip "
   "a change that could break it, and nothing says so -- which is worse than no filter, because a "
   "green history would mean the build had not run rather than that it had passed: %s"
   % (missed[:5],))

ck(matches(push or [], ".github/workflows/ci.yml"),
   "AND THE WORKFLOW IS INSIDE ITS OWN FILTER. A change to the build's definition that does not run "
   "the build cannot be told from one that does, so the first push after breaking this file would "
   "look exactly like a push that skipped it on purpose")

# ------------------------------------------------- and what it deliberately is not
#
# The point of the filter is the pages and the harness. If those matched it,
# the filter would be doing nothing.
QUIET = ["docs/AI_HARNESS.md", "docs/stand-sheet.html", "tools/harness_tasks.py",
         "tools/verify/verify_report.py", "tools/fek.py", "tools/delivery/adr201.json",
         "README.md"]
loud = [q for q in QUIET if matches(push or [], q)]
ck(not loud,
   "and a harness slice does NOT run it. These are the files the last dozen slices actually "
   "changed; if the filter matched them it would be a filter in name only: %s" % loud)

# One belt-and-braces check on the matcher itself, because a matcher that
# answered True to everything would make every check above vacuous.
ck(to_regex("**/*.java") is not None
   and to_regex("**/*.java").match("csrbt-core/src/main/java/A.java")
   and to_regex("**/*.java").match("A.java")
   and not to_regex("**/*.java").match("docs/a.html"),
   "the matcher's `**/` crosses directories and matches none of them, and `*` does not cross a "
   "separator -- if it answered yes to everything, every check above would be vacuous")
ck(not to_regex("*.java").match("csrbt-core/src/main/java/A.java"),
   "and a single star does NOT cross a separator, which is the difference between a filter that "
   "covers a module and one that covers only the repository root")

# ------------------------------------------- the copy the bridge can write
#
# The delivery bridge REFUSES to write .github/workflows: writing a CI
# definition onto somebody's machine from a remote tool is a supply-chain hole,
# and the refusal is right. So the workflow travels as tools/ci/ci.yml, which
# is an ordinary file, and is copied into place by the one command that pushes
# the slice. Two copies of anything drift, so the drift is a failure here
# rather than a surprise six slices later.
MIRROR = os.path.join(ROOT, "tools", "ci", "ci.yml")
ck(os.path.exists(MIRROR),
   "the workflow has a deliverable copy at tools/ci/ci.yml. The delivery bridge refuses to write "
   ".github/workflows -- rightly, since that is a supply-chain hole -- so the slice cannot land the "
   "workflow itself and must land something that can be copied into place")
mirror = io.open(MIRROR, encoding="utf-8").read() if os.path.exists(MIRROR) else ""
ck(mirror == src,
   "AND IT IS BYTE-IDENTICAL TO THE WORKFLOW. Two copies of one file drift, and a copy that drifted "
   "would install an older filter over a newer one on the next slice that touched CI -- silently, "
   "because the thing it overwrote is the thing nobody reads: %d vs %d bytes"
   % (len(mirror), len(src)))

for x in F:
    print("FAIL:", x)
print("PASS", len(P))
print("---")
print("%d/%d" % (len(P), len(P) + len(F)))
raise SystemExit(1 if F else 0)
