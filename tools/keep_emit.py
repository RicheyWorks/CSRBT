# -*- coding: utf-8 -*-
"""Inline the local-autosave layer into the pages that hold data worth losing.

Same constraint as FEK: no build step, so the shared code is inlined rather than
linked, and inlined copies drift unless something regenerates them. This is that
something.

    python3 tools/keep_emit.py           # rewrite every consumer
    python3 tools/keep_emit.py --check   # report drift, write nothing
"""
import glob, importlib.util, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
_spec = importlib.util.spec_from_file_location("keep", os.path.join(ROOT, "tools", "keep.py"))
keep = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(keep)

CONSUMERS = ["ordination.html", "releve.html", "stand-sheet.html", "collection-sheet.html",
             "pheno-tracker.html", "deployment-log.html",
             "survey-design.html"]

JS_RE = re.compile(r"/\* ---- Keep v[\d.]+ :.*?\n\}\)\(\);", re.S)


def css_span(src):
    """Banner to the end of keep.CSS's own last rule.

    Inherited the lookahead-for-the-next-comment boundary from dwc_emit, and
    inherited its bug with it: any comment inside the block ends the match, so
    the tail is left behind and duplicated on the next run. Bound the region by
    the source of truth instead.
    """
    start = src.find("/* ============ Keep (local autosave) v")
    if start == -1:
        return None
    line_start = src.rfind("\n", 0, start) + 1
    tail = [l for l in keep.CSS.strip("\n").split("\n") if l.strip()][-1].strip()
    end = src.find(tail, start)
    if end == -1:
        return None
    return line_start, end + len(tail)


def main(argv):
    check = "--check" in argv
    changed, missing = [], []
    for name in CONSUMERS:
        path = os.path.join(DOCS, name)
        src = io.open(path, encoding="utf-8").read()
        out = src
        span = css_span(out)
        if span:
            out = out[:span[0]] + keep.CSS.strip("\n") + out[span[1]:]
        else:
            i = out.rfind("</style>")
            if i == -1: missing.append((name, "no </style>")); continue
            out = out[:i] + keep.CSS.strip("\n") + "\n" + out[i:]
        if JS_RE.search(out):
            out = JS_RE.sub(lambda m: keep.JS.strip("\n"), out, count=1)
        else:
            missing.append((name, "no KEEP block -- wire the page first")); continue
        if out != src:
            changed.append(name)
            if not check:
                io.open(path, "w", encoding="utf-8").write(out)
    print("Keep %s" % keep.VERSION)
    print("-" * 56)
    for n in changed:
        print("%-28s %s" % (n, "would be rewritten" if check else "rewritten"))
    for n, why in missing:
        print("%-28s SKIPPED  %s" % (n, why))
    print("-" * 56)
    print("%d consumer(s) %s" % (len(changed), "would change" if check else "rewritten"))
    return 1 if (check and changed) or missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
