# -*- coding: utf-8 -*-
"""Inline the Darwin Core exporter into the pages that record occurrences.

Same constraint as FEK: no build step, so the shared code is inlined rather than
linked, and inlined copies drift unless something regenerates them. This is that
something.

    python3 tools/dwc_emit.py           # rewrite every consumer
    python3 tools/dwc_emit.py --check   # report drift, write nothing
"""
import glob, importlib.util, io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emit_common

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
_spec = importlib.util.spec_from_file_location("dwc", os.path.join(ROOT, "tools", "dwc.py"))
dwc = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(dwc)

CONSUMERS = ["releve.html", "stand-sheet.html", "collection-sheet.html"]

JS_RE = re.compile(r"/\* ---- Darwin Core v[\d.]+ :.*?\n\}\)\(\);", re.S)


CSS_OPEN = re.compile(r"[ \t]*/\* =+ Darwin Core export v[\d.]+ =+")


def css_span(src, from_=0):
    """Where the inlined stylesheet starts and ends in a page.

    Not a lookahead for "the next comment". The block acquired an explanatory
    comment of its own, the lookahead stopped there, and every run replaced the
    head while leaving the tail -- so the tail was duplicated once per run, five
    times over before verify_emitters.py caught it. Exactly the failure
    fek_emit had, arrived at from the other direction.

    The boundary comes from the source of truth: banner to the end of dwc.CSS's
    own last rule. A page that lacks that rule is reported, not guessed at.
    """
    start = src.find("/* ============ Darwin Core export v", from_)
    if start == -1:
        return None
    line_start = src.rfind("\n", 0, start) + 1
    tail = [l for l in dwc.CSS.strip("\n").split("\n") if l.strip()][-1].strip()
    end = src.find(tail, start)
    if end == -1:
        return None
    return line_start, end + len(tail)


def main(argv):
    check = "--check" in argv
    changed, missing, extra = [], [], []
    for name in CONSUMERS:
        path = os.path.join(DOCS, name)
        src = io.open(path, encoding="utf-8").read()
        out, dupes = emit_common.dedupe(src, CSS_OPEN, css_span)
        if dupes:
            extra.append((name, dupes))
        span = css_span(out)
        if span:
            out = out[:span[0]] + dwc.CSS.strip("\n") + out[span[1]:]
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
    for n, k in extra:
        print("%-28s %d DUPLICATE stylesheet block(s) %s"
              % (n, k, "found" if check else "removed"))
    for n, why in missing:
        print("%-28s SKIPPED  %s" % (n, why))
    print("-" * 56)
    print("%d consumer(s) %s" % (len(changed), "would change" if check else "rewritten"))
    return 1 if (check and changed) or missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
