# -*- coding: utf-8 -*-
"""Re-emit the Field Entry Kit into every page that uses it.

The kit has no build step, so FEK's CSS and JS are inlined into each consumer
rather than linked. That is a deliberate constraint -- one self-contained file
per page -- but it means a change to tools/fek.py reaches nobody until the
copies are refreshed, and hand-patching fourteen copies is how they drift. The
banner in every consumer said v1.1.1 while the runtime `version` string inside
still returned "1.1.0", because an earlier bump edited the comment and not the
code.

    python3 tools/fek_emit.py           # rewrite every consumer
    python3 tools/fek_emit.py --check   # report drift, write nothing

Blocks are found by their own banners and replaced whole, so a consumer is
regenerated rather than patched.
"""
import glob, importlib.util, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")

spec = importlib.util.spec_from_file_location("fek", os.path.join(ROOT, "tools", "fek.py"))
fek = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fek)

CSS_RE = re.compile(r"[ \t]*/\* =+ Field Entry Kit v[\d.]+ =+.*?\n(?=\s*/\* |\s*\.fek|\s*</style>)", re.S)
JS_RE = re.compile(r"/\* ---- Field Entry Kit v[\d.]+ :.*?\n\}\)\(\);", re.S)


def block_bounds(src):
    """The CSS block runs from its banner to the last rule that belongs to it."""
    m = re.search(r"[ \t]*/\* =+ Field Entry Kit v[\d.]+ =+", src)
    if not m:
        return None
    start = m.start()
    # the kit's CSS is every rule up to the next non-FEK top-level comment
    tail = src[m.end():]
    end_rel = re.search(r"\n(?![ \t]*(/\*|\.fek|\s*$|[ \t]*[a-z-]+\s*\{[^}]*fek))[ \t]*/\* (?!=)", tail)
    return start, (m.end() + end_rel.start() + 1) if end_rel else None


def main(argv):
    check = "--check" in argv
    changed, drift = [], []
    for path in sorted(glob.glob(os.path.join(DOCS, "*.html"))):
        src = io.open(path, encoding="utf-8").read()
        if "Field Entry Kit v" not in src:
            continue
        nm = os.path.basename(path)
        out = src
        jm = JS_RE.search(out)
        if not jm:
            drift.append((nm, "no JS block found")); continue
        out = out[:jm.start()] + fek.JS.strip("\n") + out[jm.end():]

        stale = re.findall(r'version:"([\d.]+)"', src)
        banner = sorted(set(re.findall(r"Field Entry Kit v([\d.]+)", src)))
        if out != src:
            changed.append((nm, ",".join(banner) or "?", ",".join(stale) or "?"))
            if not check:
                io.open(path, "w", encoding="utf-8").write(out)

    print("FEK %s" % fek.VERSION)
    print("-" * 62)
    for nm, banner, runtime in changed:
        print("%-30s banner %-8s runtime %-8s -> %s" % (nm, banner, runtime, fek.VERSION))
    for nm, why in drift:
        print("%-30s SKIPPED  %s" % (nm, why))
    print("-" * 62)
    print("%d consumer(s) %s" % (len(changed), "would be rewritten" if check else "rewritten"))
    return 1 if (check and changed) or drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
