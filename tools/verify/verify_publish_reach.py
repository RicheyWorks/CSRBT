# -*- coding: utf-8 -*-
"""Is a published copy of this kit still current where a stale one would leak?

WHY THIS IS ITS OWN FILE

It used to be section 5 of verify_label_escaping, and it does not belong there.
ADR-055 had already had to separate the two ideas once -- reachability is a
property of the SOURCE, staleness is a property of the PUBLISHED COPY -- and
keeping them in one file put a cost on the other half that nobody saw until
ADR-070.

This check compares each page against a digest, so it fails on ANY edit to that
page. A mutation sweep edits pages by construction, so the sweep excluded the
WHOLE suite on all five reachable pages as "measuring bytes, not behaviour" --
correctly, and at the cost of the escaping rules in sections 1 to 4, which are
byte-insensitive and were perfectly able to testify.

Split, each half does its own job: the escaping rules can kill mutants again,
and this file stays byte-sensitive because that is exactly what it is for.

WHAT IT ASSERTS

For every page where a stale published copy would render typed text or an
angle-bracket label as markup, the published copy must be STAMPED CURRENT. The
reachable set comes from tools/reach.py, which verify_label_escaping also
imports, so the two cannot disagree about which pages those are.

Run:  python3 tools/verify/verify_publish_reach.py
"""
import glob, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import reach as _reach

DOCS = os.path.join(ROOT, "docs")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


pages = sorted(glob.glob(os.path.join(DOCS, "*.html")))
ck("there are pages to check", len(pages) > 20, len(pages))

angled = _reach.angled_pages(pages)
runtime = _reach.runtime_pages(pages)

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

# Through publish_state.entry_sha, not `stamps[n]` directly. ADR-056 gave an
# entry a timestamp -- `{"sha": ..., "at": ...}` where a bare string used to be
# -- and eight of the nineteen entries are the new shape today. Comparing the
# dict to a digest is never equal, so this check would have called a freshly
# stamped page "behind": a false alarm on correct work, arriving whenever
# somebody happened to re-stamp one of these five pages. It read as passing
# only because the two pages it covered were both still the old shape.
_ps = importlib.util.spec_from_file_location(
    "_pstate", os.path.join(ROOT, "tools", "publish_state.py"))
_pstate = importlib.util.module_from_spec(_ps); _ps.loader.exec_module(_pstate)
stamps = json.load(io.open(os.path.join(ROOT, "tools", "published.json"), encoding="utf-8"))["pages"]
ck("both entry shapes are read through publish_state, not compared raw",
   _pstate.entry_sha("abc") == "abc"
   and _pstate.entry_sha({"sha": "abc", "at": 1}) == "abc",
   (_pstate.entry_sha("abc"), _pstate.entry_sha({"sha": "abc", "at": 1})))
not_current = []
for n in sorted(reach):
    digest = hashlib.sha256(publish_bytes(n)).hexdigest()
    if n not in stamps:                             not_current.append((n, "never stamped"))
    elif _pstate.entry_sha(stamps[n]) != digest:    not_current.append((n, "behind"))
ck("every page where the injection is reachable is published current",
   not not_current, not_current)

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
