# -*- coding: utf-8 -*-
"""Prepare the science kit's pages for publishing as Artifacts.

Each page in docs/ is a standalone file that links to its neighbours by filename.
Published as Artifacts they each live on their own origin, so those filenames have
to become artifact URLs or every link in the kit is dead. This does that rewrite,
reading the page-to-artifact map from tools/artifact_map.json.

    python3 tools/publish.py                 # rewrite every page into build/publish/
    python3 tools/publish.py releve.html     # just one
    python3 tools/publish.py --check         # report unmapped pages and dead links, write nothing

It does NOT publish -- publishing needs the Artifact tool and an authenticated
session. This produces the exact bytes to hand it, which is the part that was
being redone from memory every time.

The map itself is the thing worth keeping: it is how the published kit stays
navigable, and for a long time it existed only in a scratch directory.
"""
import glob, json, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
OUT = os.path.join(ROOT, "build", "publish")
MAP = os.path.join(ROOT, "tools", "artifact_map.json")

# The Artifact runtime wraps the file in its own document skeleton at publish
# time, so the page must not bring one of its own.
SHELL = (r'<!doctype[^>]*>\s*', r'</?html[^>]*>\s*', r'</?head[^>]*>\s*', r'</?body[^>]*>\s*')


def load():
    with open(MAP, encoding="utf-8") as f:
        m = json.load(f)
    return m["_base"], m["pages"]


def strip(html):
    for pat in SHELL:
        html = re.sub(pat, "", html, flags=re.I)
    return html.strip()


def wire(html, base, pages):
    for name, uid in pages.items():
        html = html.replace('href="%s"' % name, 'href="%s%s"' % (base, uid))
        html = html.replace('href="%s#' % name, 'href="%s%s#' % (base, uid))
    return html


def main(argv):
    check = "--check" in argv
    names = [a for a in argv if a.endswith(".html")]
    base, pages = load()
    files = ([os.path.join(DOCS, n) for n in names] if names
             else sorted(glob.glob(os.path.join(DOCS, "*.html"))))

    unmapped = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(DOCS, "*.html")))
                if os.path.basename(p) not in pages]
    stale = [n for n in pages if not os.path.exists(os.path.join(DOCS, n))]

    if not check:
        os.makedirs(OUT, exist_ok=True)
    rc = 0
    for path in files:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            out = wire(strip(f.read()), base, pages)
        left = sorted(set(re.findall(r'href="([^"#][^"]*\.html)', out)))
        if left:
            rc = 1
        if not check:
            # newline="" so \n is written as \n on every platform. Without it
            # Python translates to \r\n on Windows, and publish_state.sha() reads
            # these files in binary -- so the SAME page stamped from Windows and
            # from Linux gets two different hashes, and a stamp taken on one
            # reads as BEHIND on the other. The ledger silently meant a different
            # thing depending on who last ran it. Measured: verify_publish_drift
            # is 50/50 on Linux and 49/50 on Windows, failing exactly the check
            # that compares a stamped sha to the bytes publish.py would emit.
            with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="") as f:
                f.write(out)
        print("%-30s %7d bytes   %s" % (name, len(out), "UNWIRED: " + ", ".join(left) if left else "ok"))

    print("-" * 66)
    print("pages in docs/ with no artifact: %s" % (", ".join(unmapped) if unmapped else "none"))
    print("map entries with no page:        %s" % (", ".join(stale) if stale else "none"))
    if not check:
        print("written to %s" % OUT)
    if unmapped or stale:
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
