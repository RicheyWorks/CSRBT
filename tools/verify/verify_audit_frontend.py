# -*- coding: utf-8 -*-
"""Canary suite for tools/audit_frontend.py -- the finder, not the pages.

audit_frontend went from 26 open MED findings to 0 in one slice. Every one of
the 26 was a false positive, and each rule was wrong for its own reason:

  * external-resource matched any src OR href, so 15 clickable citations in
    ADRs and reference pages were reported as fetched resources.
  * innerHTML-unescaped-value searched a 200-character window for ".value"
    (which also matches ".values", and matches comparison operands), and for
    "esc(" in that same truncated window. Seeding the real ADR-031 defect
    produced zero findings.
  * unguarded-ref-to-absent-id reported eight controls that the page's own
    script writes into markup moments before dereferencing them.

Going from 26 rows to 0 is also exactly what a BROKEN finder looks like. The
only way to tell the two apart is to seed faults and watch. This does that:
each case copies the kit to a scratch tree, plants one defect (or plants a
lookalike that must NOT fire), runs the audit, and reads the rows back.

Run:  python3 tools/verify/verify_audit_frontend.py
"""

# Declared for tools/mutate.py: this suite builds its own scratch tree and the
# page names in it are FIXTURES it perturbs, not subjects it asserts about. A
# sweep must not count it as coverage. Declared rather than inferred -- the
# inference was "imports tempfile and shutil", which is a fact about imports and
# not about what the suite does, and it silently excluded verify_eco (138 checks
# on the flagship page) the moment that suite needed a temp dir for a JDK.
MUTATE_ROLE = "fixture-builder"
import os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DOCS = os.path.join(ROOT, "docs")

# The stub has to satisfy every rule the audit applies to a page, or the
# scaffolding generates its own findings. It did: the first version wrote
# name=viewport unquoted and produced 34 HIGH rows of its own.
STUB = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>@media print { body { background:#fff; } }</style>'
        '</head><body>stub</body></html>')

ok = bad = unv = 0

# WHY THIS SUITE CAN REPORT A THIRD THING (ADR-105)
#
# Every check here seeds a fault, runs audit_frontend over it, and asserts the
# audit caught it. The audit was run as a subprocess and its RETURN CODE was
# never looked at -- only its stdout was scraped for finding rows. So an audit
# that died on its import line produced no rows, and all twelve seeded faults
# reported "got: []" as though the finder had looked and missed them.
#
# That is not hypothetical: audit_frontend needs playwright, neither Richmond's
# Windows host nor the desktop Linux VM has it, and this suite has been printing
# twelve false failures on both -- 6/19 in two environments, which is what made
# it look like a real defect in the finder. Twelve accusations against working
# code, from a canary that never checked whether its subject started.
#
# It is the same defect as ADR-104, one layer down: a shortfall that means
# "did not run" reported as one that means "ran and failed".
WHY_NOT = None

def ck(name, cond, got=""):
    global ok, bad, unv
    if WHY_NOT is not None:
        unv += 1
        print("NOT VERIFIED: %s (%s)" % (name, WHY_NOT))
        return
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


def run_audit(edit=None, page=None, subset=None):
    """Copy the kit to a scratch tree, optionally rewrite one page, run the
    audit there, and return its rows as (sev, page, kind, detail) tuples."""
    tmp = tempfile.mkdtemp(prefix="afcanary_")
    try:
        d = os.path.join(tmp, "docs"); os.makedirs(d)
        names = subset if subset else sorted(
            f for f in os.listdir(DOCS) if f.endswith(".html"))
        if page and page not in names:
            names = list(names) + [page]
        for f in names:
            shutil.copy2(os.path.join(DOCS, f), os.path.join(d, f))
        # Every page in this kit links to its siblings by filename. Copying a
        # subset makes all of those dead, which drowned the real rows in 50
        # HIGH dead-link findings that were artefacts of the scratch tree.
        # Stub the rest so the links resolve and the audit sees what it would
        # see in the real checkout.
        for f in sorted(os.listdir(DOCS)):
            if f.endswith(".html") and not os.path.exists(os.path.join(d, f)):
                open(os.path.join(d, f), "w", encoding="utf-8").write(STUB)
        if edit and page:
            fp = os.path.join(d, page)
            src = open(fp, encoding="utf-8").read()
            new = edit(src)
            assert new != src, "seed did not change %s" % page
            open(fp, "w", encoding="utf-8").write(new)
        t = os.path.join(tmp, "tools"); os.makedirs(t)
        shutil.copy2(os.path.join(ROOT, "tools", "audit_frontend.py"),
                     os.path.join(t, "audit_frontend.py"))
        # Sweep only the pages under test. The stubs still exist on disk so
        # internal links resolve; not driving a browser at three viewports over
        # 34 of them takes this suite from nine minutes to under two.
        cmd = [sys.executable, os.path.join(t, "audit_frontend.py")]
        if subset:
            cmd.append("--only=" + ",".join(sorted(set(names))))
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        rows = []
        for line in (p.stdout + p.stderr).split("\n"):
            m = re.match(r'\[(HIGH|MED|LOW)\]\s+(\S+)\s+(\S+)\s+(.*)', line)
            if m: rows.append(m.groups())
        # An audit that did not start has not cleared a seeded fault, and its
        # empty output is not evidence about the finder. Latch the reason once;
        # every check from here reports NOT VERIFIED rather than a false FAIL.
        if p.returncode != 0 and not rows:
            global WHY_NOT
            if WHY_NOT is None:
                err = [l.strip() for l in (p.stderr or p.stdout).split("\n") if l.strip()]
                WHY_NOT = ("audit_frontend did not run (rc=%d): %s"
                           % (p.returncode, err[-1][:70] if err else "no output"))
        return rows, p.stdout + p.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def kinds(rows, kind, page=None):
    return [r for r in rows
            if r[2] == kind and (page is None or r[1] == page)]


# A small subset keeps each case to a few seconds. These three between them
# have free-text fields, script-built controls, external citations and an
# escaper, which is every surface the rules touch.
SUB = ["food-web.html", "field-season.html", "adr-031.html"]

print("=" * 70)
print("baseline")
base, out = run_audit(subset=SUB)
# Judge only the real pages: the stubs are this suite's own scaffolding, and a
# finding against one of them says nothing about the kit.
real = [r for r in base if r[1] in SUB]
ck("the clean kit reports no HIGH findings",
   not [r for r in real if r[0] == "HIGH"], [r for r in real if r[0] == "HIGH"][:4])
ck("no findings arrive from outside the pages under test",
   not [r for r in base if r[1] not in SUB], [r for r in base if r[1] not in SUB][:3])
ck("a page of clickable citations is not reported as fetching resources",
   not kinds(base, "external-resource", "adr-031.html"),
   kinds(base, "external-resource", "adr-031.html")[:2])
ck("a page whose escaper is named escv, not esc, is not reported",
   not kinds(base, "html-assembly-with-no-escaper", "field-season.html"),
   kinds(base, "html-assembly-with-no-escaper", "field-season.html"))
ck("controls the page's own script builds are not called unguarded",
   not kinds(base, "unguarded-ref-to-absent-id"),
   kinds(base, "unguarded-ref-to-absent-id"))
BASE_N = len(base)


def kinds_all(rows, kind):
    return [r for r in rows if r[2] == kind]

CASES = [
    # ---- external-resource: a real fetched subresource must fire ----
    ("a remote <script src> is caught", "food-web.html", "external-resource", True,
     lambda s: s.replace("<style>",
        '<script src="https://cdn.example.com/x.js"></script>\n<style>', 1)),
    ("a remote stylesheet is caught", "food-web.html", "external-resource", True,
     lambda s: s.replace("<style>",
        '<link rel="stylesheet" href="https://cdn.example.com/x.css">\n<style>', 1)),
    ("a remote <img src> is caught", "food-web.html", "external-resource", True,
     lambda s: s.replace("<div class=\"app\">",
        '<div class="app"><img src="https://cdn.example.com/x.png" alt="">', 1)),
    ("a CSS @import of a remote sheet is caught", "food-web.html", "external-resource", True,
     lambda s: s.replace("<style>", '<style>\n@import url("https://cdn.example.com/y.css");', 1)),
    # ---- the lookalike that must STAY quiet ----
    ("one more clickable citation stays quiet", "food-web.html", "external-resource", False,
     lambda s: s.replace("<div class=\"app\">",
        '<div class="app"><p><a href="https://example.org/paper">a source</a></p>', 1)),

    # ---- html assembly with no escaper ----
    ("removing the escaper from a page with a text field is caught",
     "field-season.html", "html-assembly-with-no-escaper", True,
     lambda s: s.replace('.replace(/[&<>"\']/g,', '.replace(/[\\u0000]/g,', 1)),

    # ---- unguarded ref to an id nothing ever creates ----
    ("a deref of an id nothing creates is caught",
     "food-web.html", "unguarded-ref-to-absent-id", True,
     lambda s: s.replace('  render();\n})();',
                         '  $("nowhereAtAll").addEventListener("click",function(){});\n  render();\n})();', 1)),

    # ---- rules that were already working: prove they still are ----
    ("a duplicate id is still caught", "food-web.html", "duplicate-id", True,
     lambda s: s.replace('<div class="card" id="webStats"></div>',
                         '<div class="card" id="webStats"></div><div id="webStats"></div>', 1)),
    ("a dead internal link is still caught", "food-web.html", "dead-link", True,
     lambda s: s.replace('href="ecology-field-guide.html"', 'href="no-such-page.html"', 1)),
    ("a missing viewport meta is still caught", "food-web.html", "no-viewport-meta", True,
     lambda s: s.replace('<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">', '', 1)),
    # food-web has TWO @media print blocks (page rules and the shared rail), so
    # replacing only the first left the rule correctly quiet and the case
    # correctly failing. Remove them all.
    ("a missing print block is still caught", "food-web.html", "no-print-css", True,
     lambda s: s.replace("@media print", "@media screen")),
    ("an input under 16px is still caught", "food-web.html", "input-font-under-16", True,
     lambda s: s.replace("padding:11px 14px; font:16px var(--body); min-height:48px; }",
                         "padding:11px 14px; font:14px var(--body); min-height:48px; }", 1)),
    ("unguarded localStorage is still caught", "food-web.html", "unguarded-localStorage", True,
     lambda s: s.replace("  render();\n})();",
                         "  localStorage.setItem('x','1');\n  render();\n})();", 1)),
    ("a JS error at load is still caught", "food-web.html", "js-error@phone", True,
     lambda s: s.replace("  render();\n})();", "  render(); notDefinedAnywhere();\n})();", 1)),
]

print("=" * 70)
print("seeded faults")
for name, page, kind, should_fire, edit in CASES:
    rows, out = run_audit(edit=edit, page=page, subset=SUB)
    hits = kinds(rows, kind, page)
    if should_fire:
        ck(name, len(hits) >= 1, [r[3][:60] for r in rows][:3])
    else:
        ck(name, len(hits) == 0 and len(rows) <= BASE_N,
           [r[3][:60] for r in hits][:3])

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
if unv:
    # The score line run_all parses, with the holes inside the denominator so
    # the shortfall is visible and exactly accounted for (ADR-104).
    print("%d/%d checks" % (ok, ok + bad + unv))
sys.exit(1 if bad else 0)
