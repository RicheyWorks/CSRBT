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
# Declared for tools/mutate.py: this suite writes fixture pages into a temp dir,
# so the page names in it are fixtures and comments, not subjects. Two of the
# three real page names it contains appear only inside prose explaining a past
# finding, and ADR-077 is exactly that: a sentence ABOUT a page is a mention, and
# mutate.py reads mentions as coverage. Excluding them is not a loss -- checked
# rather than assumed, the one page this suite genuinely probes is covered by six
# other suites, so nothing goes uncovered by this declaration.
MUTATE_ROLE = "fixture-builder"

import glob, io, os, re, sys, tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import reach as _reach

DOCS = os.path.join(ROOT, "docs")

ok = bad = 0
unverified = []
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

# ---- a stamp says HOW it was earned (ADR-078) ---------------------------
# "Unknown" was the honest state for nineteen pages, and the only way out of it
# was to republish nineteen artifacts -- a real cost paid for a bookkeeping gap.
# It is avoidable, because ADR-055's own principle says staleness is a property
# of the PUBLISHED COPY, and the published copy can be read. So a stamp can be
# earned by measuring the live page rather than by publishing it.
#
# Two stamps, two different pieces of evidence, and the whole value of the
# distinction is that they never read as one:
#     via "publish"  the bytes I handed the publisher
#     via "read"     the bytes the URL was serving at that moment
# The report has to keep them apart, and entries written before any of this
# existed must not be silently upgraded into either.
ck("a stamp's provenance is read through publish_state, like its hash and time",
   _pstate.entry_via({"sha": "a", "at": 1, "via": "read"}) == "read"
   and _pstate.entry_via({"sha": "a", "at": 1, "via": "publish"}) == "publish",
   (_pstate.entry_via({"sha": "a", "at": 1, "via": "read"}),))
ck("an entry with no provenance reads as None, never as 'publish'",
   _pstate.entry_via({"sha": "a", "at": 1}) is None
   and _pstate.entry_via("abc") is None,
   (_pstate.entry_via({"sha": "a", "at": 1}), _pstate.entry_via("abc")))

# containment, not equality -- and not skeleton-stripping. The publisher wraps
# the build bytes in a page shell; parsing that shell back off would be a filter
# written against today's wrapper, which is the shape that produced
# publish_drift's twenty-four false findings.
_probe = os.path.join(ROOT, "build", "publish", "cp-bench.html")
if os.path.exists(_probe):
    _body = io.open(_probe, encoding="utf-8").read()
    ck("a wrapped copy of the publish bytes verifies",
       _pstate.contains_build("<!doctype html><head>SHELL</head><body>"
                              + _body + "</body></html>", _probe))
    ck("...and one byte of drift inside the content does not",
       not _pstate.contains_build("<!doctype html><body>"
                                  + _body.replace("<style>", "<style >", 1)
                                  + "</body>", _probe),
       "cp-bench has no <style> to perturb" if "<style>" not in _body else "")
    ck("a truncated copy does not verify",
       not _pstate.contains_build(_body[:-40], _probe))
    # the test has to be able to fail: if the perturbation above changed nothing
    # the check above would pass vacuously (ADR-039).
    ck("the drift probe actually perturbs the bytes", "<style>" in _body,
       _body[:80])
else:
    print("NOT VERIFIED: no build output to test containment against")

# The pages this suite covers must be current, and now the report can say on
# what evidence. Nothing here demands "read" -- publish-time stamps are the
# normal case -- only that whatever the file says is what the tool reports.
_shapes = {n: _pstate.entry_via(stamps[n]) for n in sorted(reach) if n in stamps}
ck("every stamp for a reachable page carries a provenance this tool understands",
   all(v in (None, "read", "publish") for v in _shapes.values()), _shapes)

# ---- the offline contract, measured where the reader is (ADR-078) ------
# verify_offline_slice checks ADR-031's webfont rule on the REPO. Nothing
# checked it on the PUBLISHED copies, and the published copies are the ones a
# reader opens -- ADR-055's principle, applied to a rule instead of to bytes.
# Measured today: adr-031.html's own published copy blocks first paint on a
# font request. The page that states the constraint shipped in violation of it.
_F = "https://fonts.googleapis.com/css2?family=X"
_DEFER = ('<link rel="stylesheet" href="' + _F + '" media="print" data-webfont>'
          '<noscript><link rel="stylesheet" href="' + _F + '"></noscript>'
          '<script>(function(){var l=document.querySelector(\'link[data-webfont]\');'
          'l.media="all";})();</script>')
_BLOCK = '<link rel="stylesheet" href="' + _F + '">'
_bad, _prom = _pstate.blocking_webfont("<head>" + _DEFER + "</head>")
ck("the deferred webfont form is not reported as blocking", not _bad, _bad)
ck("...and its promoter is seen", _prom)
_bad2, _ = _pstate.blocking_webfont("<head>" + _BLOCK + "</head>")
ck("a plain stylesheet link to the font host IS reported as blocking",
   len(_bad2) == 1, _bad2)
# the <noscript> fallback is a deliberately blocking copy; counting it would
# report every correct page, which is the false-positive shape ADR-055 named.
_bad3, _ = _pstate.blocking_webfont(
    '<head><link rel="stylesheet" href="' + _F + '" media="print" data-webfont>'
    '<noscript>' + _BLOCK + '</noscript></head>')
ck("the noscript fallback is not counted as the defect", not _bad3, _bad3)
# a page with no webfont at all is not a finding either way
_bad4, _prom4 = _pstate.blocking_webfont("<head><title>x</title></head>")
ck("a page with no webfont reports neither a block nor a promoter",
   not _bad4 and not _prom4, (_bad4, _prom4))

# ---- a measurement decays when the repo moves (ADR-078) ----------------
# A negative measurement is knowledge -- "I read that URL at T and it was not
# serving this build" beats "unknown" -- but only about the build it was taken
# against. The moment the repo moves, carrying the verdict forward would be a
# stale claim about a live page, which is precisely the failure ADR-055 is
# named for. So the rule is stated as one function and checked here, both ways.
_ST = {"pages": {"a.html": {"sha": "AAA", "at": 10, "via": "publish"}},
       "observed": {"b.html": {"sha": "BBB", "at": 20, "via": "read",
                               "state": "behind"}}}
ck("a stamp matching the build reads current",
   _pstate.classify("a.html", "AAA", _ST)[0] == "current",
   _pstate.classify("a.html", "AAA", _ST))
ck("a stamp against a moved build reads behind",
   _pstate.classify("a.html", "ZZZ", _ST)[0] == "behind",
   _pstate.classify("a.html", "ZZZ", _ST))
ck("an observation against THIS build reads measured-behind",
   _pstate.classify("b.html", "BBB", _ST)[0] == "measured-behind",
   _pstate.classify("b.html", "BBB", _ST))
ck("...and against a moved build DECAYS to unknown, not to a stale verdict",
   _pstate.classify("b.html", "ZZZ", _ST)[0] == "unknown",
   _pstate.classify("b.html", "ZZZ", _ST))
ck("a page with neither a stamp nor an observation is unknown",
   _pstate.classify("c.html", "AAA", _ST)[0] == "unknown",
   _pstate.classify("c.html", "AAA", _ST))
# a stamp always wins over an observation -- publishing is the later event
_ST2 = {"pages": {"b.html": {"sha": "BBB", "at": 30, "via": "read"}},
        "observed": {"b.html": {"sha": "BBB", "at": 20, "state": "behind"}}}
ck("a stamp outranks a leftover observation for the same page",
   _pstate.classify("b.html", "BBB", _ST2)[0] == "current",
   _pstate.classify("b.html", "BBB", _ST2))

# ---- may a dated read replace the stamp it found? -------------------------
# Three cases, and the one that mattered was invisible while the rule lived in
# inline conditionals: an UNDATED stamp gave the copy nothing to be newer than,
# so the ordering test could never be satisfied and every page still on a
# pre-ADR-056 stamp was permanently unmeasurable. Fourteen pages were in that
# state -- exactly the set ADR-083 predicted would verify CURRENT, which the
# tool had made untestable. Stated as a function, all three cases are visible
# and all three are checked, including the one that must still REFUSE.
_UNDATED = "abc123"                                    # pre-ADR-056 bare sha
_DATED   = {"sha": "abc123", "at": 100, "via": "publish"}

ck("with no previous stamp, a read may stamp",
   _pstate.stamp_allowed(None, 50)[0] is True, _pstate.stamp_allowed(None, 50))
ck("a dated read supersedes an UNDATED stamp",
   _pstate.stamp_allowed(_UNDATED, 50)[0] is True, _pstate.stamp_allowed(_UNDATED, 50))
ck("...and it says so, rather than replacing it silently",
   "undated" in _pstate.stamp_allowed(_UNDATED, 50)[1], _pstate.stamp_allowed(_UNDATED, 50))
ck("a copy OLDER than a dated stamp is still refused (ADR-056, unchanged)",
   _pstate.stamp_allowed(_DATED, 99)[0] is False, _pstate.stamp_allowed(_DATED, 99))
ck("a copy newer than a dated stamp may stamp",
   _pstate.stamp_allowed(_DATED, 101)[0] is True, _pstate.stamp_allowed(_DATED, 101))
ck("a copy taken at exactly the stamp's time may stamp",
   _pstate.stamp_allowed(_DATED, 100)[0] is True, _pstate.stamp_allowed(_DATED, 100))
# Two clocks for one event: --stamp writes time.time() locally, the artifact's
# version epoch is assigned seconds EARLIER, so a read of exactly the version a
# stamp describes always looks slightly stale against it. Without the same-build
# case every publish-time stamp was permanently unimprovable -- ADR-084's wall,
# rebuilt by the honest dates of ADR-085.
ck("a read of the SAME build supersedes a publish-time stamp it looks older than",
   _pstate.stamp_allowed(_DATED, 99, True)[0] is True,
   _pstate.stamp_allowed(_DATED, 99, True))
ck("...and says it is the same publish, not that it won on time",
   "same" in _pstate.stamp_allowed(_DATED, 99, True)[1],
   _pstate.stamp_allowed(_DATED, 99, True))
ck("the same-build case is the ONLY thing that changed that verdict",
   _pstate.stamp_allowed(_DATED, 99, False)[0] is False,
   _pstate.stamp_allowed(_DATED, 99, False))
# ...and it must not leak into the observation rule, which has no such case: a
# stale copy of the same build still cannot say the page is behind now.
ck("observation_allowed has no same-build escape -- it takes no such argument",
   _pstate.observation_allowed(_DATED, 99)[0] is False,
   _pstate.observation_allowed(_DATED, 99))

# The canary the refusal needs: a rule that returned True for everything would
# pass five of the six above. Only this one distinguishes it.
ck("the rule can say no at all -- exactly one of these six is a refusal",
   [_pstate.stamp_allowed(*a)[0] for a in
    [(None, 50), (_UNDATED, 50), (_DATED, 99), (_DATED, 101), (_DATED, 100)]
   ].count(False) == 1)


# ---- is this copy a copy of THIS page? ------------------------------------
# --verify took a page name and a path and nothing made them agree. Handing it
# one page's copy under another page's name produced "BEHIND, measured" about a
# page that was current, and wrote it to state["observed"] with via="read".
import tempfile

_TMP = tempfile.mkdtemp(prefix="pubreach-")


def _w(name, text):
    fp = os.path.join(_TMP, name)
    io.open(fp, "w", encoding="utf-8").write(text)
    return fp


_BUILD = _w("fixture-bench.html", "<title>Fixture Bench</title>\n<p>body</p>\n")
_MAP = {"fixture-bench.html": "58e9b6d9-5a9b-496a-8b71-4644db78f750",
        "other-bench.html": "287e03ab-3c15-468f-a15c-6bb2d95a09c9"}
_WRAP = '<base href="/_f/1787695412-79bc/"><title>Fixture Bench</title>\n<p>body</p>\n'
_WRONG = '<base href="/_f/1787695406-faf3/"><title>Other Bench</title>\n<p>body</p>\n'
_named_right = _w("artifact-58e9b6d9-1787695412-79bc.html", _WRAP)
_named_wrong = _w("artifact-287e03ab-1787695406-faf3.html", _WRAP)
_hand = _w("saved-copy.html", _WRAP)
_hand_wrong = _w("saved-other.html", _WRONG)
_untitled = _w("saved-untitled.html", "<p>body</p>\n")


def _of(name, path, text):
    return _pstate.copy_is_of(name, path, text, _BUILD, _MAP)


ck("CONTROL: the right page's copy, named as that page, is attributed",
   _of("fixture-bench.html", _named_right, _WRAP)[0] is True,
   _of("fixture-bench.html", _named_right, _WRAP))
ck("a copy whose FILENAME names another artifact is refused",
   _of("fixture-bench.html", _named_wrong, _WRAP)[0] is False,
   _of("fixture-bench.html", _named_wrong, _WRAP))
ck("...and the refusal names both artifacts, so the mix-up is visible",
   "287e03ab" in _of("fixture-bench.html", _named_wrong, _WRAP)[1],
   _of("fixture-bench.html", _named_wrong, _WRAP))
ck("a hand-named copy is attributed by its TITLE alone",
   _of("fixture-bench.html", _hand, _WRAP)[0] is True,
   _of("fixture-bench.html", _hand, _WRAP))
ck("a hand-named copy of a DIFFERENT page is refused on its title",
   _of("fixture-bench.html", _hand_wrong, _WRONG)[0] is False,
   _of("fixture-bench.html", _hand_wrong, _WRONG))
# ADR-061: the case where nothing can speak must be loud, not a silent pass.
ck("a copy with no artifact id and no title ties to nothing, and is refused",
   _of("fixture-bench.html", _untitled, "<p>body</p>\n")[0] is False,
   _of("fixture-bench.html", _untitled, "<p>body</p>\n"))
ck("...and says that is why, rather than naming a mismatch it did not find",
   "nothing" in _of("fixture-bench.html", _untitled, "<p>body</p>\n")[1])
# The title must be the TITLE ELEMENT, not the string appearing anywhere: a hub
# page quoting another page's title in a card would otherwise be attributed to it.
_quoting = _w("saved-hub.html",
              '<title>Hub</title>\n<a>Fixture Bench</a>\n')
ck("a page that merely MENTIONS this page's title is not a copy of it",
   _of("fixture-bench.html", _quoting, '<title>Hub</title>\n<a>Fixture Bench</a>\n')[0] is False,
   _of("fixture-bench.html", _quoting, '<title>Hub</title>\n<a>Fixture Bench</a>\n'))
# The canary the seven need: a function that refused everything would pass six of
# them, and one that accepted everything would pass the other one. Stated as the
# property rather than as a count -- a pinned number here would be the frozen
# constant ADR-041 is about, and it was wrong on the first try.
_VERDICTS = set(_of(*a)[0] for a in
                [("fixture-bench.html", _named_right, _WRAP),
                 ("fixture-bench.html", _named_wrong, _WRAP),
                 ("fixture-bench.html", _hand, _WRAP),
                 ("fixture-bench.html", _hand_wrong, _WRONG),
                 ("fixture-bench.html", _untitled, "<p>body</p>\n"),
                 ("fixture-bench.html", _quoting,
                  '<title>Hub</title>\n<a>Fixture Bench</a>\n')])
ck("the rule is not a constant -- it both accepts and refuses across these six",
   _VERDICTS == {True, False}, sorted(map(str, _VERDICTS)))

# ---- may this copy be recorded as an OBSERVATION? -------------------------
# A different question from "may it stamp", and sharing one answer between them
# recorded "behind, measured, via read" for the two pages with no dated stamp,
# from copies of versions three days old. Both may be current; the copies could
# not say. The two rules are checked side by side here precisely because the bug
# was that they were the same rule.
ck("with nothing on record, an observation contradicts nothing and is allowed",
   _pstate.observation_allowed(None, 50)[0] is True,
   _pstate.observation_allowed(None, 50))
ck("against an UNDATED stamp, a copy cannot be ordered -- and so may NOT observe",
   _pstate.observation_allowed(_UNDATED, 50)[0] is False,
   _pstate.observation_allowed(_UNDATED, 50))
ck("...which is the exact case where it MAY stamp -- the two rules differ here",
   _pstate.stamp_allowed(_UNDATED, 50)[0] is True
   and _pstate.observation_allowed(_UNDATED, 50)[0] is False)
ck("a copy older than a dated stamp may not observe either",
   _pstate.observation_allowed(_DATED, 99)[0] is False,
   _pstate.observation_allowed(_DATED, 99))
ck("a copy newer than a dated stamp may observe",
   _pstate.observation_allowed(_DATED, 101)[0] is True,
   _pstate.observation_allowed(_DATED, 101))
ck("the observation rule is not a constant -- it both allows and refuses",
   set(_pstate.observation_allowed(*a)[0] for a in
       [(None, 50), (_UNDATED, 50), (_DATED, 99), (_DATED, 101)]) == {True, False})

# ---- what dates a copy ----------------------------------------------------
# mtime is a property of the local file. Measured across 103 saved copies, every
# mtime was later than the version the copy carries -- by up to 3.1 days, never
# once equal -- so every date this file wrote for a via="read" entry was
# overstated, always in the direction ADR-056 exists to refuse.
_at, _how = _pstate.copy_taken_at(_named_right, _WRAP)
ck("a copy is dated by the version marker in its own bytes",
   _at == 1787695412, (_at, _how))
ck("...and says so, so a date's provenance is never left to be assumed",
   "version marker" in _how, _how)
_at2, _how2 = _pstate.copy_taken_at(_hand, _WRAP)
ck("a hand-named copy is still dated from its bytes, not its mtime",
   _at2 == 1787695412, (_at2, _how2))
_at3, _how3 = _pstate.copy_taken_at(
    _w("artifact-58e9b6d9-1787695412-79bc.html", "<p>no base</p>"), "<p>no base</p>")
ck("with no marker in the bytes, the filename's epoch is used",
   _at3 == 1787695412, (_at3, _how3))
_at4, _how4 = _pstate.copy_taken_at(_untitled, "<p>body</p>")
ck("with neither, mtime is the last resort and is LABELLED as not the version",
   _at4 is not None and "NOT the version" in _how4, (_at4, _how4))
# Disagreement between the two written-from-the-page sources takes the older,
# which is the reading that can only understate.
_dis = _w("artifact-58e9b6d9-1787695999-79bc.html", _WRAP)
ck("name and bytes disagreeing takes the OLDER of the two",
   _pstate.copy_taken_at(_dis, _WRAP)[0] == 1787695412,
   _pstate.copy_taken_at(_dis, _WRAP))
ck("...and does not pass that off as an ordinary reading",
   "disagreeing" in _pstate.copy_taken_at(_dis, _WRAP)[1])
# The canary: a function that always returned the same epoch would pass five.
ck("the date actually comes from the copy -- a different version reads different",
   _pstate.copy_taken_at(_named_wrong, _WRONG)[0] == 1787695406,
   _pstate.copy_taken_at(_named_wrong, _WRONG))

# ---- ADR-138: measurement is the default, and a hole is a hole -------------
#
# `via "publish"` says the repo's bytes were handed to a publisher. `via "read"`
# says the URL was serving them. Only the second answers the question every
# audit in this kit silently depends on -- does a green audit of docs/ describe
# what a reader gets? -- and until ADR-138 twenty-two of forty-one pages carried
# only the first, because measuring meant a human remembering to fetch a copy.
#
# So: an unmeasured artifact is NOT VERIFIED here. Never a pass. The suite
# cannot fetch (an artifact is read through the host's Artifact tool, not over
# HTTP from a container), and a suite that pretended to would be manufacturing
# the evidence it exists to demand -- so it reports the hole and names the
# command that closes it.
sys.path.insert(0, os.path.join(ROOT, "tools"))
import publish_reach as _pr
import publish_state as _ps2

_ps2.build_current([])        # compare against what WOULD be published now, not a stale build dir
_art = _pr.artifacts()
ck("every artifact this kit publishes is mapped, the Harness Board included",
   len(_art) >= 42 and "_harness-board.html" in _art, sorted(_art)[:2])
_reach = _pr.reach()
_unmeasured = [n for n, (k, _e) in sorted(_reach.items()) if k != "measured"]
_missing = [n for n, (_i, bp) in sorted(_art.items()) if not os.path.exists(bp)]
ck("every mapped artifact has bytes in build/publish -- an artifact nothing builds cannot be "
   "compared to anything", not _missing, _missing[:4])
ck("the reach is known for every mapped artifact",
   all(k in ("measured", "stamped", "behind", "unknown", "not-built")
       for k, _e in _reach.values()), sorted(set(k for k, _e in _reach.values())))
# A KNOWN-STALE URL IS A FAILURE; A NEVER-LOOKED-AT ONE IS A HOLE. They are not
# the same claim and must not share an outcome. `behind` means the repo has
# moved past what that URL was last known to serve -- a reader is being handed
# an old page, and this suite says so. `stamped` and `unknown` mean nobody has
# looked; that is a gap in the evidence, reported as NOT VERIFIED so it counts
# against nothing and hides from nobody.
_behind = [n for n in _unmeasured if _reach[n][0] in ("behind", "not-built")]
for _n in _unmeasured:
    if _n not in _behind:
        unverified.append("%s is %s, not MEASURED -- for this artifact a green audit of docs/ "
                          "says nothing about what a reader is served. Close it with: "
                          "python3 tools/publish_reach.py --plan" % (_n, _reach[_n][0].upper()))
ck("no mapped artifact is known to be serving bytes this repo has moved past",
   not _behind, _behind[:4])
ck("--plan names exactly the artifacts that are not measured",
   [n for n, _a, _b in _pr.plan()] == _unmeasured, [n for n, _a, _b in _pr.plan()][:4])

# a copy is offered to the page whose artifact id it names, and to no other
# a page whose build output EXISTS: under a mutation that makes publish.py
# refuse a page, picking the first name alphabetically picks a file that is not
# there, and the suite dies of a FileNotFoundError instead of reporting what it
# found. A suite that falls over has not noticed anything.
_built_ok = sorted((n, i) for n, (i, bp) in _art.items() if os.path.exists(bp))
_a_page, _a_id = _built_ok[0] if _built_ok else ("none.html", "0" * 32)
ck("a saved copy is attributed by the artifact id in its name",
   _pr.attribute("artifact-%s-1788000000-abcd.html" % _a_id[:8], _art) == _a_page,
   _pr.attribute("artifact-%s-1788000000-abcd.html" % _a_id[:8], _art))
ck("...and a copy naming no artifact this kit publishes is attributed to nothing",
   _pr.attribute("artifact-deadbeef-1788000000-abcd.html", _art) is None
   and _pr.attribute("some-file.html", _art) is None)

# the two stamps are not one stamp: reach() must not read `via publish` as measured
_fake = {"pages": {_a_page: {"sha": (_ps2.sha(os.path.join(_ps2.BUILD, _a_page))
                                    if os.path.exists(os.path.join(_ps2.BUILD, _a_page)) else "x"),
                             "at": 1788000000, "via": "publish"}}, "observed": {}}
ck("a page stamped at PUBLISH time reads as stamped, never as measured",
   _pr.reach(_fake)[_a_page][0] == "stamped", _pr.reach(_fake)[_a_page])
_fake["pages"][_a_page]["via"] = "read"
ck("...and the same entry earned by READING the live copy reads as measured",
   _pr.reach(_fake)[_a_page][0] == "measured", _pr.reach(_fake)[_a_page])
_fake["pages"][_a_page]["sha"] = "0" * 64
ck("a stamp that does not match the bytes that would be published now is BEHIND -- a URL known "
   "to be serving something else, not merely one nobody has looked at",
   _pr.reach(_fake)[_a_page][0] == "behind", _pr.reach(_fake)[_a_page])

# a prefix that fits two artifacts fits neither: an ambiguous id names nothing
_two = {"a.html": ("abcdef1111", "x"), "b.html": ("abcdef2222", "y")}
ck("a copy whose id prefix fits two artifacts is attributed to neither",
   _pr.attribute("artifact-abcdef-1788000000-aaaa.html", _two) is None,
   _pr.attribute("artifact-abcdef-1788000000-aaaa.html", _two))
ck("...while one that fits exactly one is attributed to it",
   _pr.attribute("artifact-abcdef11-1788000000-aaaa.html", _two) == "a.html")

# sweeping a directory with two copies of a page takes the newer VERSION
_old = "artifact-%s-1788000000-aaaa.html" % _a_id[:8]
_new = "artifact-%s-1788999999-bbbb.html" % _a_id[:8]
_d = tempfile.mkdtemp()
for _f in (_old, _new):
    io.open(os.path.join(_d, _f), "w", encoding="utf-8").write("<p>%s</p>" % _f)
# and the older VERSION is touched last, so a sweep that dated copies by mtime
# would take exactly the wrong one -- which is the mistake ADR-078 measured
# across 103 saved copies and this rule exists to refuse.
os.utime(os.path.join(_d, _old), (2000000000, 2000000000))
_done, _orph = _pr.pick(sorted(os.path.join(_d, f) for f in (_old, _new)), _art)
ck("sweeping two copies of one page takes the newer VERSION, not the newer file",
   os.path.basename(_done[_a_page][0]) == _new, _done.get(_a_page))
_orphan = os.path.join(_d, "artifact-deadbeef-1788000000-cccc.html")
io.open(_orphan, "w", encoding="utf-8").write("<p>x</p>")
_done2, _orph2 = _pr.pick([_orphan], _art)
# ADR-140: a copy the reader just fetched, whose bytes carry no version marker
_bare = os.path.join(_d, "artifact-%s-0001.html" % _a_id[:8])
io.open(_bare, "w", encoding="utf-8").write("<p>no marker anywhere</p>")
_at0, _how0 = _ps2.copy_taken_at(_bare, "<p>no marker anywhere</p>")
ck("with no marker in the bytes and no epoch in the name, mtime is still the last resort and says so",
   "NOT the version" in _how0, _how0)
_at1, _how1 = _ps2.copy_taken_at(_bare, "<p>no marker anywhere</p>", told=1788400000)
ck("a reader that says when it fetched dates the copy -- ranked below the marker and above mtime, "
   "and stated as being about the FETCH", _at1 == 1788400000 and "about the fetch" in _how1
   and "version" in _how1, (_at1, _how1))
_marked = os.path.join(_d, "artifact-%s-0002.html" % _a_id[:8])
_wrap = '<base href="/_f/1788111111-abc/">body'
io.open(_marked, "w", encoding="utf-8").write(_wrap)
ck("...and it never overrides the marker: the bytes still win when they have one",
   _ps2.copy_taken_at(_marked, _wrap, told=1788999999)[0] == 1788111111,
   _ps2.copy_taken_at(_marked, _wrap, told=1788999999))

ck("...and a copy of nothing this kit publishes is an orphan, not attributed to a page",
   _done2 == {} and _orph2 == [_orphan], (_done2, _orph2))

# ---- ADR-138: the strip that ate a page ------------------------------------
#
# publish.py removes the document skeleton because the Artifact runtime wraps
# the file in its own. Written as `</?head[^>]*>`, that pattern also matched
# `<header class="hero">` AND `</header>` -- eight pages of this kit opened with
# one -- and, because a character class matches newlines, it matched from
# `i<headers.length` in greenhouse's mapHeaders() all the way to the next ">"
# anywhere in the file, deleting 321 characters of JavaScript. The published
# greenhouse carried `for(var i=0;i= 0){`: a syntax error, so every interactive
# feature on that page was dead. No audit in this kit could see it -- they all
# measure docs/, and docs/ was fine.
import publish as _pub


def _strip(html):
    """strip(), reporting a refusal rather than dying of it: a suite that
    crashes on a mutation has not noticed it, it has fallen over."""
    try:
        return _pub.strip(html)
    except Exception as e:
        return "RAISED: %s" % e


_HERO = '<header class="hero"><h1>x</h1></header><p>after</p>'
ck("a <header> element survives the shell strip, opening tag and closing tag",
   _strip("<!doctype html><html><head><title>t</title></head><body>" + _HERO + "</body></html>")
   == "<title>t</title>" + _HERO,
   _strip("<!doctype html><html><head><title>t</title></head><body>" + _HERO + "</body></html>"))
_JS = "<script>for(var i=0;i<headers.length;i++){ q(i); }</script><p>after</p>"
ck("a JS comparison that reads like a tag survives it too",
   _strip("<html><body>" + _JS + "</body></html>") == _JS,
   _strip("<html><body>" + _JS + "</body></html>"))
ck("the skeleton itself is still removed -- doctype, html, head, body, in any case",
   _strip("<!DOCTYPE html>\n<HTML lang=en>\n<HEAD>\n<title>t</title>\n</HEAD>\n"
              "<BODY class=x>\n<p>p</p>\n</BODY>\n</HTML>\n") == "<title>t</title>\n<p>p</p>",
   _strip("<!DOCTYPE html>\n<HTML lang=en>\n<HEAD>\n<title>t</title>\n</HEAD>\n"
              "<BODY class=x>\n<p>p</p>\n</BODY>\n</HTML>\n"))
try:
    _pub.SHELL, _saved = (r'</?head[^>]*>\s*',), _pub.SHELL
    _pub.strip("<p>for(var i=0;i<headers.length;i++){ q(i); }</p><p>after</p>")
    ck("a pattern that spans past a shell tag is REFUSED, not published", False, "no refusal")
except ValueError as e:
    ck("a pattern that spans past a shell tag is REFUSED, not published",
       "not part of the document skeleton" in str(e), str(e)[:70])
finally:
    _pub.SHELL = _saved
ck("...and the guard counts, rather than trusting the patterns: N tags, N '<'",
   _strip("<html><body><p>a<b>c</b></p></body></html>") == "<p>a<b>c</b></p>")

# every page of the kit that opens with a <header> keeps it in the build output
_heroes = [p for p in pages if re.search(r"<header\b", io.open(p, encoding="utf-8").read())]
_built = os.path.join(ROOT, "build", "publish")
_lost = [os.path.basename(p) for p in _heroes
         if os.path.exists(os.path.join(_built, os.path.basename(p)))
         and "<header" not in io.open(os.path.join(_built, os.path.basename(p)), encoding="utf-8").read()]
ck("every page that opens with a <header> still has one in the bytes handed to the publisher",
   not _lost and len(_heroes) >= 6, (len(_heroes), _lost))

print("-" * 70)
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
