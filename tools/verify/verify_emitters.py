# -*- coding: utf-8 -*-
"""Do the regenerators actually regenerate?

The kit has no build step, so shared code is inlined into pages and a
regenerator keeps the copies in step. That works right up until a regenerator
quietly stops writing something -- and then nothing notices, because every page
still agrees with every other page. They are all equally stale.

That is not hypothetical. `fek_emit.py` defined a CSS pattern and a bounds
helper and then never called either: the stylesheet half was dead code from the
day it was written, so every bump to `fek.CSS` for months failed to reach a
single page. It surfaced only because a version bump left the CSS banner
reading an older number than the JS banner beside it. Worse, `fek.py` had
meanwhile drifted from the pages -- a hand-applied contrast fix never came back
to the source -- so repairing the emitter immediately pushed three
WCAG-failing colours into all fifteen consumers.

So this suite does not ask a regenerator whether it is happy. It breaks a page
and checks the regenerator notices:

  1. --check on a clean tree must be silent and exit 0.
  2. Perturb a consumer, and --check must report drift and exit non-zero.
  3. A plain run must put it back, byte for byte.

A regenerator that passes 1 but not 2 is writing nothing, which is exactly the
failure this exists for.
"""
import glob, io, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ROOT, TOOLS_DIR

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))

DOCS = os.path.join(ROOT, "docs")

# (emitter, the module it inlines, the GENERATED BANNER that marks its block).
# The banner, not the module's name: "Ordination" and "Keep" and "Field Entry
# Kit" all appear as ordinary prose in pages that are not consumers, and a
# probe that matches prose picks up the ADR describing the decision as though
# it were a page implementing it. That mistake has now been made three times in
# this kit, twice on data-claim greps and once here; matching a code shape
# rather than a word is the fix each time.
# The fourth field is the CSS banner, where the module inlines a stylesheet as
# well as script. It has to be probed SEPARATELY: the first version of this
# suite perturbed only the script banner, so deleting the line that writes the
# CSS still passed -- which is the original bug walking straight through the
# test written to catch it. A regenerator with two halves needs two canaries.
EMITTERS = [
    ("fek_emit.py",  "fek.py",  r"/\* ---- Field Entry Kit v[\d.]+ :",
     r"/\* =+ Field Entry Kit v[\d.]+ =+"),
    ("dwc_emit.py",  "dwc.py",  r"/\* ---- Darwin Core v[\d.]+ :",
     r"/\* =+ Darwin Core export v[\d.]+ =+"),
    ("ord_emit.py",  "ord.py",  r"/\* ---- Ordination v[\d.]+ :", None),
    ("keep_emit.py", "keep.py", r"/\* ---- Keep v[\d.]+ :",
     r"/\* =+ Keep \(local autosave\) v[\d.]+ =+"),
    ("nav_emit.py",  "nav.py",  r'<div class="rail">', None),
    ("gh_emit.py",   "gh.py",   r"/\* -+ Greenhouse engine v[\d.]+ -+ \*/",
     r"/\* =+ Greenhouse engine v[\d.]+ =+ \*/"),
]


_MODS = {}
def _load(emitter):
    """Import an emitter as a module, to reuse its own span finder.

    Cached: importing gh_emit renders the engine CSS, which is not free, and
    this suite asks four times.
    """
    if emitter not in _MODS:
        import importlib.util
        sys.path.insert(0, TOOLS_DIR.rstrip(os.sep))
        spec = importlib.util.spec_from_file_location(
            emitter[:-3], os.path.join(TOOLS_DIR, emitter))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        _MODS[emitter] = m
    return _MODS[emitter]


def run(emitter, *args):
    p = subprocess.run([sys.executable, os.path.join(TOOLS_DIR, emitter)] + list(args),
                       cwd=TOOLS_DIR, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def consumers(probe):
    rx = re.compile(probe)
    return [p for p in sorted(glob.glob(os.path.join(DOCS, "*.html")))
            if rx.search(io.open(p, encoding="utf-8").read())]


def version_of(mod):
    src = io.open(os.path.join(TOOLS_DIR, mod), encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([\d.]+)"', src, re.M)
    return m.group(1) if m else None


snapshot = tempfile.mkdtemp(prefix="csrbt-emit-")
for f in glob.glob(os.path.join(DOCS, "*.html")):
    shutil.copy(f, snapshot)

try:
    for emitter, mod, probe, css_probe in EMITTERS:
        cons = consumers(probe)
        ck("%s has consumers to regenerate" % emitter, len(cons) >= 1, len(cons))

        rc, out = run(emitter, "--check")
        ck("%s --check is clean on a clean tree" % emitter, rc == 0, out.strip()[-160:])

        ver = version_of(mod)
        # The rail carries no version stamp -- it is markup, not a module the
        # page reports at runtime -- so there is nothing to check it against.
        if ver and "v[" in probe:
            stale = [os.path.basename(p) for p in cons
                     if ("v" + ver) not in io.open(p, encoding="utf-8").read()]
            ck("%s: every consumer carries v%s" % (mod, ver), not stale, stale[:4])

        # ---- the part that matters: break a page, and see if it notices ----
        target = cons[0]
        name = os.path.basename(target)
        original = io.open(target, encoding="utf-8").read()

        # Perturb inside the generated block, not next to it: the banner marks
        # the region the emitter owns, so an insertion just after it must be
        # reverted by a rewrite. Each half of a two-part emitter gets its own.
        for half, pat in (("script", probe), ("stylesheet", css_probe)):
            if pat is None:
                continue
            m = re.search(pat, original)
            ck("%s: found the generated %s in %s" % (emitter, half, name), m is not None, pat)
            if not m:
                continue
            i = m.end()
            broken = original[:i] + "/* CANARY */" + original[i:]
            io.open(target, "w", encoding="utf-8").write(broken)
            try:
                rc, out = run(emitter, "--check")
                ck("%s --check NOTICES a perturbed %s in %s" % (emitter, half, name), rc != 0,
                   "check passed on a page it should have rejected")
                rc2, out2 = run(emitter)
                ck("%s rewrites the %s without error" % (emitter, half), rc2 == 0, out2.strip()[-160:])
                restored = io.open(target, encoding="utf-8").read()
                ck("%s restores the %s in %s byte for byte" % (emitter, half, name),
                   restored == original, "%d bytes differ" % abs(len(restored) - len(original)))
            finally:
                io.open(target, "w", encoding="utf-8").write(original)

        # ---- a SECOND copy of the block, which is not a perturbation ----
        #
        # The canary above edits inside the region the emitter owns, and every
        # emitter catches that. None of them caught a whole extra copy of the
        # region sitting further down the file, because the rewrite finds the
        # FIRST banner, replaces it, and stops looking.
        #
        # Found by reading a published page: survey-design.html carried the Keep
        # stylesheet four times, and `keep_emit.py --check` reported the tree
        # clean. Four identical copies render identically -- until keep.CSS
        # changes, at which point copy one is updated, copies two to four are
        # not, and the LAST rule wins in CSS. The page would then render the
        # stale stylesheet with every regenerator reporting success.
        if css_probe is not None:
            # The block's extent comes from the EMITTER's own css_span, not from
            # a guess. The first cut of this canary copied "banner to
            # </style>", which on fek and dwc pages swallows the stylesheets
            # that follow -- so the emitter removed its own duplicate correctly
            # and the byte comparison still failed, on three emitters at once,
            # for a reason that had nothing to do with them.
            emod = _load(emitter)
            span = getattr(emod, "css_span", None)
            span = span(original) if span else None
            if span:
                    block = original[span[0]:span[1]] + "\n"
                    doubled = original[:span[1] + 1] + block + original[span[1] + 1:]
                    io.open(target, "w", encoding="utf-8").write(doubled)
                    try:
                        rc, out = run(emitter, "--check")
                        ck("%s --check NOTICES a DUPLICATED stylesheet in %s"
                           % (emitter, name), rc != 0,
                           "check passed on a page carrying the block twice")
                        rc2, out2 = run(emitter)
                        ck("%s collapses the duplicate without error" % emitter,
                           rc2 == 0, out2.strip()[-160:])
                        back = io.open(target, encoding="utf-8").read()
                        ck("%s leaves exactly one copy of the stylesheet in %s"
                           % (emitter, name), back == original,
                           "%d bytes differ from the original" % (len(back) - len(original)))
                    finally:
                        io.open(target, "w", encoding="utf-8").write(original)

        rc, out = run(emitter, "--check")
        ck("%s --check clean again after the canary" % emitter, rc == 0, out.strip()[-160:])

    # ---- a regenerator must not be able to be dead ----
    # fek_emit's CSS half was dead because main() never called the helper it
    # defined. A defined-but-uncalled pattern is the signature.
    for emitter, mod, probe, css_probe in EMITTERS:
        src = io.open(os.path.join(TOOLS_DIR, emitter), encoding="utf-8").read()
        body = src[src.index("def main("):] if "def main(" in src else src
        defined = set(re.findall(r"^([A-Z_]+_RE)\s*=\s*re\.compile", src, re.M))
        unused = sorted(r for r in defined if r not in body)
        ck("%s: no compiled pattern is defined and never used" % emitter, not unused, unused)
        helpers = set(re.findall(r"^def ([a-z_]+)\(", src, re.M)) - {"main"}
        # `\bname\b`, not `\bname\(`. gh_emit's css_span is handed to
        # emit_common.dedupe as a VALUE and called from there, so counting call
        # syntax reported a live helper as dead -- and a check that fires on
        # working code is a check people learn to wave through, which is what
        # this one exists to prevent.
        dead = sorted(h for h in helpers if len(re.findall(r"\b%s\b" % h, src)) < 2)
        ck("%s: no helper is defined and never called or passed" % emitter, not dead, dead)

    # ---- and the whole tree must be at rest afterwards ----
    for emitter, mod, probe, css_probe in EMITTERS:
        rc, out = run(emitter, "--check")
        ck("%s leaves the tree at rest" % emitter, rc == 0, out.strip()[-120:])

    changed = [os.path.basename(f) for f in sorted(glob.glob(os.path.join(DOCS, "*.html")))
               if io.open(f, encoding="utf-8").read()
               != io.open(os.path.join(snapshot, os.path.basename(f)), encoding="utf-8").read()]
    ck("this suite changed nothing it did not put back", not changed, changed[:4])

finally:
    shutil.rmtree(snapshot, ignore_errors=True)

print("\n".join("PASS  " + x for x in P))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
