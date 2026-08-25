# -*- coding: utf-8 -*-
"""Inline the ordination engine into the page that uses it.

    python3 tools/ord_emit.py           # rewrite
    python3 tools/ord_emit.py --check   # report drift, write nothing
"""
import importlib.util, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
_spec = importlib.util.spec_from_file_location("ord", os.path.join(ROOT, "tools", "ord.py"))
ord_ = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ord_)

CONSUMERS = ["ordination.html"]
JS_RE = re.compile(r"/\* ---- Ordination v[\d.]+ :.*?\n\}\)\(\);", re.S)


def main(argv):
    check = "--check" in argv
    changed, missing = [], []
    for name in CONSUMERS:
        path = os.path.join(DOCS, name)
        src = io.open(path, encoding="utf-8").read()
        if not JS_RE.search(src):
            missing.append((name, "no ORD block -- wire the page first")); continue
        # A lambda replacement, not a string: a replacement string treats every
        # backslash as a group template, and the engine is full of regex-free
        # backslashes that are not.
        out = JS_RE.sub(lambda m: ord_.JS.strip("\n"), src, count=1)
        if out != src:
            changed.append(name)
            if not check:
                io.open(path, "w", encoding="utf-8").write(out)
    print("Ordination %s" % ord_.VERSION)
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
