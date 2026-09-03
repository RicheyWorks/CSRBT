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
#
# \b AFTER EACH TAG NAME, AND IT IS NOT PEDANTRY (ADR-138). Written without it,
# `</?head[^>]*>` matches `<header class="hero">` -- `head` then `[^>]*` eating
# `er class="hero"` -- and matches `</header>` the same way. Eight pages of this
# kit open with a <header class="hero"> banner, and every published copy of them
# had BOTH tags deleted: the hero content survived unwrapped, so .hero never
# applied and the banner rendered as loose text. No audit could see it, by
# construction -- every audit in this kit measures docs/, and docs/ was fine. It
# took ADR-138 measuring what the URL was actually serving to find it, four
# months after publish.py was written.
SHELL = (r'<!doctype[^<>]*>\s*', r'</?html\b[^<>]*>\s*', r'</?head\b[^<>]*>\s*',
         r'</?body\b[^<>]*>\s*')


def load():
    with open(MAP, encoding="utf-8") as f:
        m = json.load(f)
    return m["_base"], m["pages"]


def others():
    """Artifacts that are not docs pages (ADR-138). Build name -> source path.

    The Harness Board is published like any page of the kit and, until ADR-138,
    was tracked like none of them. It carries no links into the kit, so it needs
    no rewrite -- only the same build output every other artifact has, under a
    name the publish ledger can key on, so `publish_state` and `publish_reach`
    can hold it to the same rule as the rest."""
    with open(MAP, encoding="utf-8") as f:
        m = json.load(f)
    return dict((name, os.path.join(ROOT, spec["source"]))
                for name, spec in (m.get("others") or {}).items())


def strip(html):
    """Remove the document skeleton, and prove that is all that was removed.

    A tag cannot contain "<", so `[^<>]*` is the right class and `[^>]*` was
    the wrong one: without it `</?head[^>]*>` matched from `i<headers.length`
    in a JS loop all the way to the next ">" ANYWHERE in the file -- a
    character class matches newlines -- and deleted 321 characters out of
    greenhouse's mapHeaders(). The published page carried `for(var i=0;i= 0){`,
    a syntax error, so every interactive feature on it was dead. For months.

    The guard below is the general form of that lesson: stripping N shell tags
    removes exactly N "<" characters. Anything else means a pattern spanned
    something that is not a shell tag, and the right response is to refuse to
    build rather than to publish a page with a hole in it."""
    before = html.count("<")
    tags = 0
    for pat in SHELL:
        html, n = re.subn(pat, "", html, flags=re.I)
        tags += n
    gone = before - html.count("<")
    if gone != tags:
        raise ValueError("shell-stripping removed %d '<' for %d shell tag(s): a pattern "
                         "spanned something that is not part of the document skeleton" % (gone, tags))
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

    for name, src in sorted(others().items()):
        if not os.path.exists(src):
            print("%-30s %7s bytes   MISSING: %s" % (name, "-", src)); rc = 1; continue
        with open(src, encoding="utf-8") as f:
            out = strip(f.read())
        if not check:
            with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="") as f:
                f.write(out)
        print("%-30s %7d bytes   ok (from %s)" % (name, len(out), os.path.relpath(src, ROOT)))

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
