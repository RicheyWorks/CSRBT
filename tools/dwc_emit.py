# -*- coding: utf-8 -*-
"""Inline the Darwin Core exporter into the pages that record occurrences.

Same constraint as FEK: no build step, so the shared code is inlined rather than
linked, and inlined copies drift unless something regenerates them. This is that
something.

    python3 tools/dwc_emit.py           # rewrite every consumer
    python3 tools/dwc_emit.py --check   # report drift, write nothing
"""
import glob, importlib.util, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
_spec = importlib.util.spec_from_file_location("dwc", os.path.join(ROOT, "tools", "dwc.py"))
dwc = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(dwc)

CONSUMERS = ["releve.html", "stand-sheet.html", "collection-sheet.html"]

CSS_RE = re.compile(r"[ \t]*/\* =+ Darwin Core export v[\d.]+ =+ \*/.*?(?=\n[ \t]*/\* |\n[ \t]*</style>)", re.S)
JS_RE = re.compile(r"/\* ---- Darwin Core v[\d.]+ :.*?\n\}\)\(\);", re.S)


def main(argv):
    check = "--check" in argv
    changed, missing = [], []
    for name in CONSUMERS:
        path = os.path.join(DOCS, name)
        src = io.open(path, encoding="utf-8").read()
        out = src
        if CSS_RE.search(out):
            out = CSS_RE.sub(lambda m: dwc.CSS.strip("\n"), out, count=1)
        else:
            i = out.rfind("</style>")
            if i == -1: missing.append((name, "no </style>")); continue
            out = out[:i] + dwc.CSS.strip("\n") + "\n" + out[i:]
        if JS_RE.search(out):
            out = JS_RE.sub(lambda m: dwc.JS.strip("\n"), out, count=1)
        else:
            missing.append((name, "no DWC block -- wire the page first")); continue
        if out != src:
            changed.append(name)
            if not check:
                io.open(path, "w", encoding="utf-8").write(out)
    print("Darwin Core %s" % dwc.VERSION)
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
