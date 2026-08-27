# -*- coding: utf-8 -*-
"""Inline the greenhouse engine into its consumers.

Same constraint as FEK and KEEP: no build step, so the shared code lives inlined
in each page and drifts unless something regenerates it.

Two canaries per emitter, not one. The first version of verify_emitters
perturbed only the script banner, so deleting the CSS-write line still passed --
and the same inherited bug then turned up in keep_emit. Both halves of this
emitter are exercised by tools/verify/verify_emitters.py.

    python3 tools/gh_emit.py           # rewrite every consumer
    python3 tools/gh_emit.py --check   # report drift, write nothing
"""
import importlib.util, io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emit_common

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
_spec = importlib.util.spec_from_file_location("gh", os.path.join(ROOT, "tools", "gh.py"))
gh = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(gh)

CONSUMERS = ["greenhouse.html"]

CSS_TEXT = gh.render_css()
JS_TEXT = gh.render_js()

# Both blocks are bounded by their OWN opening and closing banners rather than
# by "the next comment". dwc_emit used a lookahead for the next comment, the
# block later acquired one, and every run duplicated the tail until .dwc-out
# appeared five times in one page. A closing banner cannot drift that way.
CSS_RE = re.compile(r"[ \t]*/\* =+ Greenhouse engine v[\d.]+ =+ \*/.*?"
                    r"/\* =+ /Greenhouse engine v[\d.]+ =+ \*/", re.S)
JS_RE = re.compile(r"/\* -+ Greenhouse engine v[\d.]+ -+ \*/.*?"
                   r"/\* -+ /Greenhouse engine v[\d.]+ -+ \*/", re.S)


CSS_OPEN = re.compile(r"[ \t]*/\* =+ Greenhouse engine v[\d.]+ =+ \*/")


def css_span(src, from_=0):
    """The engine's CSS block, opening banner to closing banner."""
    m = CSS_RE.search(src, from_)
    return (m.start(), m.end()) if m else None


def main(argv):
    check = "--check" in argv
    changed, missing, extra = [], [], []
    for name in CONSUMERS:
        path = os.path.join(DOCS, name)
        if not os.path.exists(path):
            missing.append((name, "page does not exist")); continue
        src = io.open(path, encoding="utf-8").read()
        out, dupes = emit_common.dedupe(src, CSS_OPEN, css_span)
        if dupes:
            extra.append((name, dupes))
        if CSS_RE.search(out):
            out = CSS_RE.sub(lambda m: CSS_TEXT.strip("\n"), out, count=1)
        else:
            missing.append((name, "no engine CSS block -- wire the page first")); continue
        if JS_RE.search(out):
            out = JS_RE.sub(lambda m: JS_TEXT.strip("\n"), out, count=1)
        else:
            missing.append((name, "no engine JS block -- wire the page first")); continue
        if out != src:
            changed.append(name)
            if not check:
                io.open(path, "w", encoding="utf-8").write(out)
    print("Greenhouse engine %s" % gh.VERSION)
    print("-" * 60)
    for n in changed:
        print("%-28s %s" % (n, "would be rewritten" if check else "rewritten"))
    for n, k in extra:
        print("%-28s %d DUPLICATE stylesheet block(s) %s"
              % (n, k, "found" if check else "removed"))
    for n, why in missing:
        print("%-28s SKIPPED  %s" % (n, why))
    print("-" * 60)
    print("%d consumer(s) %s" % (len(changed), "would change" if check else "rewritten"))
    return 1 if (check and changed) or missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
